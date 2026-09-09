"""LangGraph pipeline orchestrator with sequential fallback.

Pipeline flow:
DataAgent → DataValidationAgent → RatioAgent → ECL Engine →
RiskIntelligenceAgent → NarrativeAgent → ComplianceAgent →
ApprovalOrchestrator → (conditional) → CompilerAgent

The pipeline passes `db` via `RunnableConfig` (not through PipelineState).
If LangGraph is not available, a sequential fallback is used.

Design decision: The sequential fallback ensures the system works in
all environments, including those where LangGraph cannot be installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.agents.compliance_agent import check_section
from app.agents.compiler_agent import run_compiler_agent
from app.agents.data_agent import run_data_agent
from app.agents.data_validation_agent import validate_context
from app.agents.narrative_agent import run_narrative_agent
from app.agents.ratio_agent import run_ratio_agent
from app.agents.risk_intelligence_agent import analyze_risk
from app.core import audit
from app.core.approval_rules import SectionFlags, should_auto_approve
from app.db.models import Memo, MemoSection, WorkflowEvent

logger = logging.getLogger(__name__)

# Try to import LangGraph
_HAS_LANGGRAPH = False
try:
    from langgraph.graph import END, StateGraph
    _HAS_LANGGRAPH = True
    logger.info("LangGraph available — graph orchestrator enabled")
except ImportError:
    logger.info("LangGraph not available — using sequential fallback")


@dataclass
class PipelineState:
    """State passed through the pipeline (LangGraph or sequential).

    The `db` session is passed via RunnableConfig (LangGraph) or directly
    (sequential fallback), NOT stored in this state object.
    """
    memo_id: str = ""
    client_id: str = ""
    client_name: str = ""
    facility_type: str = "murabaha"
    deal_value: float = 0.0
    bank_type: str = "islamic"
    rm_acl_groups: List[str] = field(default_factory=list)
    created_by: str = "system"

    # Intermediate results
    retrieved_context: str = ""
    chunk_ids: List[str] = field(default_factory=list)
    retrieved_chunks: List[Any] = field(default_factory=list)
    data_quality: Dict[str, Any] = field(default_factory=dict)
    ratio_result: Any = None
    ecl_result: Optional[Dict[str, Any]] = None
    risk_analysis: Any = None
    narrative_sections: List[Any] = field(default_factory=list)
    compliance_results: List[Dict[str, Any]] = field(default_factory=list)

    # Status
    errors: List[str] = field(default_factory=list)
    current_step: str = ""


def _step_data(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 1: Data Retrieval via DataAgent + RAG."""
    state.current_step = "data_retrieval"
    result = run_data_agent(
        db=db,
        client_id=state.client_id,
        facility_type=state.facility_type,
        deal_value=state.deal_value,
        rm_acl_groups=state.rm_acl_groups,
    )
    state.retrieved_context = result.retrieved_context_text
    state.chunk_ids = result.chunk_ids
    state.retrieved_chunks = result.retrieved_chunks
    return state


def _step_validation(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 2: Data Validation."""
    state.current_step = "data_validation"
    validation = validate_context(
        retrieved_chunks=state.retrieved_chunks,
        facility_type=state.facility_type,
    )
    state.data_quality = {
        "confidence": validation.confidence_score,
        "is_valid": validation.is_valid,
        "reason": validation.rejection_reason if not validation.is_valid else None,
        "blocking": False,
    }
    if not validation.is_valid:
        state.data_quality["blocking"] = True
        logger.warning(
            "Pipeline: data validation failed (confidence=%.2f) — auto-approval overridden",
            validation.confidence_score,
        )
    return state


def _step_ratios(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 3: Financial Ratio Computation."""
    state.current_step = "ratio_computation"
    state.ratio_result = run_ratio_agent(
        retrieved_context=state.retrieved_context,
        client_id=state.client_id,
    )
    return state


def _step_ecl(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 4: ECL Computation (CBK/IFRS 9)."""
    state.current_step = "ecl_computation"
    try:
        from app.risk.ecl_engine import compute_ecl
        from app.risk.synthetic_portfolio import generate_synthetic_portfolio
        portfolio = generate_synthetic_portfolio()
        ecl_result_obj = compute_ecl(portfolio)
        state.ecl_result = ecl_result_obj.to_dict()
    except Exception as e:
        logger.warning("Pipeline: ECL computation skipped: %s", e)
        state.ecl_result = None
    return state


def _step_risk(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 5: Risk Intelligence Analysis."""
    state.current_step = "risk_intelligence"
    state.risk_analysis = analyze_risk(
        ratio_result=state.ratio_result,
        ecl_result=state.ecl_result,
        retrieved_context=state.retrieved_context,
        facility_type=state.facility_type,
    )
    return state


def _step_narrative(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 6: Narrative Generation."""
    state.current_step = "narrative_generation"
    valid_chunk_ids = set(state.chunk_ids)
    narrative_result = run_narrative_agent(
        client_id=state.client_id,
        facility_type=state.facility_type,
        deal_value=state.deal_value,
        retrieved_context=state.retrieved_context,
        ratio_result=state.ratio_result,
        valid_chunk_ids=valid_chunk_ids,
    )
    state.narrative_sections = narrative_result.sections
    return state


def _step_compliance(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 7: Compliance Checking (Shariah + Citations)."""
    state.current_step = "compliance_checking"
    valid_chunk_ids = set(state.chunk_ids)
    state.compliance_results = []
    for section_draft in state.narrative_sections:
        cr = check_section(
            section_key=section_draft.section_key,
            content=section_draft.content,
            facility_type=state.facility_type,
            valid_chunk_ids=valid_chunk_ids,
        )
        state.compliance_results.append(cr)
    return state


def _step_approval(state: PipelineState, *, db: Session) -> PipelineState:
    """Step 8: Approval evaluation + persist sections to DB."""
    state.current_step = "approval_evaluation"

    memo = db.query(Memo).filter(Memo.id == state.memo_id).first()
    if not memo:
        state.errors.append(f"Memo {state.memo_id} not found in DB")
        return state

    # Enter the first review stage of the configured approval workflow.
    from app.core.business_config import get_approval_workflow

    first_review_stage = get_approval_workflow().get("stages", ["draft", "risk_review"])[1]
    memo.status = first_review_stage
    memo.workflow_stage = first_review_stage

    for section_draft in state.narrative_sections:
        # Build flags for approval decision
        flags = SectionFlags(
            shariah_flags=section_draft.shariah_flags,
            citation_problems=section_draft.citation_problems,
            ratio_breaches=(
                [b.to_dict() for b in state.ratio_result.breaches]
                if state.ratio_result and section_draft.section_key == "financial_analysis"
                else []
            ),
            risk_flags=(
                [r.to_dict() for r in state.risk_analysis.key_risks]
                if state.risk_analysis and section_draft.section_key == "risk_and_mitigants"
                else []
            ),
        )

        auto_approved, rule = should_auto_approve(
            section_key=section_draft.section_key,
            flags=flags,
            facility_type=state.facility_type,
            deal_value=state.deal_value,
        )

        # If data validation failed, override auto-approval to require review
        data_blocking = state.data_quality.get("blocking", False)
        if auto_approved and data_blocking:
            auto_approved = False
            rule = "required_review_data_validation_blocking"

        section = MemoSection(
            memo_id=memo.id,
            section_key=section_draft.section_key,
            title=section_draft.title,
            content=section_draft.content,
            citations_json=section_draft.citations,
            requires_review=not auto_approved,
            review_reason=rule if not auto_approved else "",
            review_status="auto_approved" if auto_approved else "pending",
            auto_approved_rule=rule if auto_approved else None,
            flags_json=section_draft.flags,
        )
        db.add(section)

        if auto_approved:
            audit.record_approval(
                db=db,
                memo_id=memo.id,
                section_key=section_draft.section_key,
                user_id=None,
                action="auto_approve",
                rule_applied=rule,
            )

    # Audit the generation
    audit.record_event(
        db=db,
        action="generate_memo",
        user_id=state.created_by,
        memo_id=memo.id,
        payload={
            "client_id": state.client_id,
            "facility_type": state.facility_type,
            "deal_value": state.deal_value,
            "sections_generated": len(state.narrative_sections),
            "data_quality": state.data_quality.get("confidence"),
        },
    )

    # Record the stage-entry event so SLA timers start at generation.
    db.add(WorkflowEvent(
        memo_id=memo.id,
        from_stage="draft",
        to_stage=first_review_stage,
        user_id=state.created_by,
        action="advance",
        comment="Pipeline complete — entered review",
    ))

    # Persist pipeline artifacts for downstream consumption (review UI,
    # reporting, ECL dashboard). Kept in metadata_json to avoid schema churn.
    memo.metadata_json = {
        "data_quality": state.data_quality,
        "ratios": state.ratio_result.to_dict() if state.ratio_result else None,
        "risk_rating": (
            state.risk_analysis.overall_risk_rating if state.risk_analysis else None
        ),
        "key_risks": (
            [r.to_dict() for r in state.risk_analysis.key_risks]
            if state.risk_analysis else []
        ),
        "ecl": state.ecl_result,
        "chunk_ids": state.chunk_ids,
    }
    return state


# =============================================================================
# LangGraph state machine builder
# =============================================================================

def _build_langgraph_pipeline():
    """Build a real LangGraph StateGraph when langgraph is installed.

    Pipeline: Data → Validation → Ratio → ECL → Risk → Narrative → Compliance → Approval

    The `db` session is passed via `RunnableConfig.configurable["db"]`.
    """
    if not _HAS_LANGGRAPH:
        return None

    from langgraph.graph import END, StateGraph

    graph = StateGraph(PipelineState)

    # Add nodes — each node receives (state) and we bind db via closures
    # The actual db is injected at invocation time via _run_langgraph_pipeline()
    _db_holder: Dict[str, Optional[Session]] = {"db": None}

    def make_node(step_fn):
        def node(state: PipelineState) -> PipelineState:
            db = _db_holder["db"]
            if db is None:
                raise RuntimeError("Database session not provided to LangGraph pipeline")
            return step_fn(state, db=db)
        return node

    graph.add_node("data", make_node(_step_data))
    graph.add_node("validation", make_node(_step_validation))
    graph.add_node("ratios", make_node(_step_ratios))
    graph.add_node("ecl", make_node(_step_ecl))
    graph.add_node("risk", make_node(_step_risk))
    graph.add_node("narrative", make_node(_step_narrative))
    graph.add_node("compliance", make_node(_step_compliance))
    graph.add_node("approval", make_node(_step_approval))

    # Edges: linear pipeline
    graph.set_entry_point("data")
    graph.add_edge("data", "validation")
    graph.add_edge("validation", "ratios")
    graph.add_edge("ratios", "ecl")
    graph.add_edge("ecl", "risk")
    graph.add_edge("risk", "narrative")
    graph.add_edge("narrative", "compliance")
    graph.add_edge("compliance", "approval")
    graph.add_edge("approval", END)

    compiled = graph.compile()
    return compiled, _db_holder


def _run_langgraph_pipeline(
    db: Session,
    client_id: str,
    client_name: str,
    facility_type: str,
    deal_value: float,
    bank_type: str = "islamic",
    rm_acl_groups: Optional[List[str]] = None,
    created_by: str = "system",
) -> Memo:
    """Execute the pipeline using LangGraph (if available)."""
    result = _build_langgraph_pipeline()
    if result is None:
        return None

    compiled_graph, db_holder = result
    db_holder["db"] = db

    # Create memo record
    memo = Memo(
        client_id=client_id,
        client_name=client_name,
        facility_type=facility_type,
        bank_type=bank_type,
        deal_value=deal_value,
        status="generating",
        workflow_stage="draft",
        created_by=created_by,
    )
    db.add(memo)
    db.flush()

    initial_state = PipelineState(
        memo_id=memo.id,
        client_id=client_id,
        client_name=client_name,
        facility_type=facility_type,
        deal_value=deal_value,
        bank_type=bank_type,
        rm_acl_groups=rm_acl_groups or [],
        created_by=created_by,
    )

    try:
        final_state = compiled_graph.invoke(initial_state)
        db.commit()
        logger.info(
            "LangGraph pipeline: memo %s generated with %d sections",
            memo.id, len(final_state.get("narrative_sections", [])),
        )
    except Exception as e:
        logger.error("LangGraph pipeline error: %s", e, exc_info=True)
        memo.status = "error"
        memo.metadata_json = {"error": str(e)[:500]}
        db.commit()

    return memo


# =============================================================================
# Sequential fallback
# =============================================================================

def _run_sequential_pipeline(
    db: Session,
    client_id: str,
    client_name: str,
    facility_type: str,
    deal_value: float,
    bank_type: str = "islamic",
    rm_acl_groups: Optional[List[str]] = None,
    created_by: str = "system",
) -> Memo:
    """Execute the pipeline sequentially (fallback when LangGraph not available)."""
    memo = Memo(
        client_id=client_id,
        client_name=client_name,
        facility_type=facility_type,
        bank_type=bank_type,
        deal_value=deal_value,
        status="generating",
        workflow_stage="draft",
        created_by=created_by,
    )
    db.add(memo)
    db.flush()

    acl = rm_acl_groups or []

    try:
        state = PipelineState(
            memo_id=memo.id,
            client_id=client_id,
            client_name=client_name,
            facility_type=facility_type,
            deal_value=deal_value,
            bank_type=bank_type,
            rm_acl_groups=acl,
            created_by=created_by,
        )

        # Run each step sequentially
        state = _step_data(state, db=db)
        state = _step_validation(state, db=db)
        state = _step_ratios(state, db=db)
        state = _step_ecl(state, db=db)
        state = _step_risk(state, db=db)
        state = _step_narrative(state, db=db)
        state = _step_compliance(state, db=db)
        state = _step_approval(state, db=db)

        db.commit()
        logger.info(
            "Sequential pipeline: memo %s generated with %d sections",
            memo.id, len(state.narrative_sections),
        )

    except Exception as e:
        logger.error("Sequential pipeline error: %s", e, exc_info=True)
        memo.status = "error"
        memo.metadata_json = {"error": str(e)[:500]}
        db.commit()

    return memo


# =============================================================================
# Public API
# =============================================================================

def run_pipeline_up_to_review(
    db: Session,
    client_id: str,
    client_name: str,
    facility_type: str,
    deal_value: float,
    bank_type: str = "islamic",
    rm_acl_groups: Optional[List[str]] = None,
    created_by: str = "system",
) -> Memo:
    """Run the full pipeline up to the review stage.

    This is the primary entry point for generating a memo. It uses
    the LangGraph pipeline if available, otherwise falls back to
    the sequential pipeline.

    Args:
        db: Database session.
        client_id: Client identifier.
        client_name: Client display name.
        facility_type: Islamic facility type.
        deal_value: Deal value in KD.
        bank_type: Bank type (always "islamic" for Warba).
        rm_acl_groups: ACL groups for the requesting RM.
        created_by: User ID creating the memo.

    Returns:
        The created Memo with all sections populated.
    """
    logger.info("Pipeline: generating memo for client=%s facility=%s", client_id, facility_type)

    if _HAS_LANGGRAPH:
        logger.info("Using LangGraph pipeline orchestrator")
        memo = _run_langgraph_pipeline(
            db=db,
            client_id=client_id,
            client_name=client_name,
            facility_type=facility_type,
            deal_value=deal_value,
            bank_type=bank_type,
            rm_acl_groups=rm_acl_groups,
            created_by=created_by,
        )
        if memo is not None:
            return memo
        logger.warning("LangGraph pipeline failed, falling back to sequential")

    return _run_sequential_pipeline(
        db=db,
        client_id=client_id,
        client_name=client_name,
        facility_type=facility_type,
        deal_value=deal_value,
        bank_type=bank_type,
        rm_acl_groups=rm_acl_groups,
        created_by=created_by,
    )


def is_langgraph_available() -> bool:
    """Check if LangGraph is installed."""
    return _HAS_LANGGRAPH
