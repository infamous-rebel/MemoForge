"""Seed script — populates the database with sample data for demonstration.

Inserts:
- Default user accounts (five RBAC roles, password: warba2025)
- Sample client documents indexed through the RAG pipeline
- Sample credit memos across the approval workflow with sections,
  workflow events, audit entries, and notifications
- Runs the escalation check so SLA breaches are recorded naturally

Usage:
    python -m app.scripts.seed_demo_data            # seed if empty
    python -m app.scripts.seed_demo_data --force    # wipe memos and re-seed
"""

from __future__ import annotations

import logging
import sys
from datetime import timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def seed():
    """Populate the database with demo data."""
    import os
    os.environ.setdefault("MOCK_MODE", "true")
    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("EMBEDDING_PROVIDER", "tfidf")

    from datetime import datetime, timezone

    from app.core import audit, users
    from app.db.models import (
        Chunk,
        Document,
        Memo,
        MemoSection,
        Notification,
        WorkflowEvent,
    )
    from app.db.session import get_db_session, get_engine, init_db

    logger.info("Initializing database...")
    engine = get_engine()
    init_db(engine)

    db = get_db_session()
    now = datetime.now(timezone.utc)

    def hours_ago(h: float) -> datetime:
        return now - timedelta(hours=h)

    try:
        # =================================================================
        # Users
        # =================================================================
        users.ensure_default_users(db)
        db.commit()
        logger.info("User accounts ready (5 default roles)")

        # =================================================================
        # Sample Documents (RAG corpus)
        # =================================================================
        existing = db.query(Document).first()
        if not existing:
            clients_docs = [
                {
                    "client_id": "CLIENT-001",
                    "client_name": "Al-Rashid Trading Company",
                    "documents": [
                        {
                            "title": "Annual Financial Statements 2024",
                            "doc_type": "financial_statement",
                            "content": (
                                "Al-Rashid Trading Company — Annual Financial Statements FY2024. "
                                "Net operating income: KD 2,500,000. Total debt service: KD 1,720,000. "
                                "Total liabilities: KD 8,500,000. Total equity: KD 4,200,000. "
                                "Current assets: KD 6,300,000. Current liabilities: KD 3,500,000. "
                                "Revenue growth: 8.5% year-over-year. Operating margin: 22%. "
                                "The company maintains a DSCR of 1.45x, well above the bank's minimum of 1.2x."
                            ),
                        },
                        {
                            "title": "Murabaha Facility Agreement",
                            "doc_type": "facility_agreement",
                            "content": (
                                "Murabaha Facility Agreement between Warba Bank and Al-Rashid Trading Company. "
                                "Facility amount: KD 3,000,000. Structure: cost-plus sale (Murabaha). "
                                "Profit rate: 5.5% per annum. Deferred payment period: 36 months. "
                                "Collateral: Commercial property valued at KD 4,500,000. "
                                "The facility is structured in full compliance with Shariah principles, "
                                "utilizing cost-plus profit rate and deferred payment terms."
                            ),
                        },
                        {
                            "title": "Industry Analysis — Trading Sector",
                            "doc_type": "market_analysis",
                            "content": (
                                "Kuwait trading sector analysis Q2 2024. The sector showed resilient "
                                "growth of 4.2% driven by government infrastructure spending and "
                                "increased consumer demand. Key risks include concentration in "
                                "government contracts and exposure to oil price volatility. "
                                "Al-Rashid Trading Company is positioned in the upper quartile "
                                "with diversified revenue streams across construction materials "
                                "and general trading activities."
                            ),
                        },
                    ],
                },
                {
                    "client_id": "CLIENT-002",
                    "client_name": "Gulf Real Estate Development",
                    "documents": [
                        {
                            "title": "Quarterly Financial Review Q2 2024",
                            "doc_type": "financial_statement",
                            "content": (
                                "Gulf Real Estate Development — Q2 2024 Review. "
                                "Net operating income: KD 4,800,000. Total debt service: KD 3,200,000. "
                                "Total liabilities: KD 15,000,000. Total equity: KD 6,000,000. "
                                "Current assets: KD 8,000,000. Current liabilities: KD 5,500,000. "
                                "Leverage ratio of 2.5x. Current ratio of 1.45x. "
                                "Portfolio includes 12 residential projects and 3 commercial developments."
                            ),
                        },
                        {
                            "title": "Ijara Facility Agreement",
                            "doc_type": "facility_agreement",
                            "content": (
                                "Ijara (Islamic Lease) Facility between Warba Bank and Gulf Real Estate Development. "
                                "Facility amount: KD 5,000,000. Structure: Ijara (forward lease). "
                                "Rental rate: 6.0% per annum. Lease term: 60 months. "
                                "Leased asset: Commercial building in Sharq district. "
                                "Collateral: The leased property plus additional real estate valued at KD 8,000,000. "
                                "The usufruct and rental payments are structured per Shariah-compliant Ijara principles."
                            ),
                        },
                    ],
                },
            ]

            for client in clients_docs:
                for doc_data in client["documents"]:
                    doc = Document(
                        title=doc_data["title"],
                        document_type=doc_data["doc_type"],
                        client_id=client["client_id"],
                        source_system="seed_script",
                        acl_groups=["corporate_banking", "credit_analysis"],
                        content_hash=str(hash(doc_data["content"])),
                    )
                    db.add(doc)
                    db.flush()

                    content = doc_data["content"]
                    for i in range(0, len(content), 500):
                        db.add(Chunk(
                            document_id=doc.id,
                            chunk_index=i // 500,
                            content=content[i:i + 500],
                            client_id=client["client_id"],
                            acl_groups=["corporate_banking", "credit_analysis"],
                            token_count=len(content[i:i + 500].split()),
                        ))
            db.commit()
            logger.info("Seeded RAG documents for %d clients", len(clients_docs))

        # =================================================================
        # Sample Memos
        # =================================================================
        force = "--force" in sys.argv
        if force:
            for m in db.query(Memo).all():
                db.delete(m)
            db.commit()
            logger.info("--force: cleared existing memos")

        if db.query(Memo).count() > 0:
            logger.info("Memos already seeded — skipping memo seeding.")
        else:
            _seed_memos(db, now, hours_ago)
            db.commit()
            logger.info("Seeded %d sample memos", db.query(Memo).count())

        # =================================================================
        # Escalations (natural — computed by the real escalation agent)
        # =================================================================
        from app.agents.escalation_agent import check_and_escalate

        triggered = check_and_escalate(db)
        db.commit()
        if triggered:
            logger.info("Escalation agent triggered %d escalations", len(triggered))

        logger.info(
            "Seed complete. Login with rm_ahmad / warba2025 (or risk_sara, cc_khalid, sb_omar, admin_system)."
        )

    except Exception as e:
        logger.error("Seed failed: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


def _seed_memos(db, now, hours_ago) -> None:
    """Create realistic sample memos across the approval workflow."""
    from app.core import audit
    from app.db.models import Memo, MemoSection, Notification, WorkflowEvent

    def ratios_block(dscr, leverage, current, breaches=None):
        return {
            "dscr": dscr,
            "leverage_ratio": leverage,
            "current_ratio": current,
            "net_operating_income": 2_500_000,
            "total_debt_service": 1_720_000,
            "total_liabilities": 8_500_000,
            "total_equity": 4_200_000,
            "breaches": breaches or [],
        }

    borrower_overview_content = (
        "KTL Digital Infrastructure KSC is a regional provider of hyper-scale data-center "
        "and sovereign-cloud solutions, established in 2014 and operating under the Al-Sabah "
        "Holding Group. The company has delivered a 22% revenue CAGR over the past three years, "
        "anchored by long-term capacity contracts with Kuwaiti government entities. Strategy is "
        "aligned with Kuwait's Vision 2035 digital transformation agenda. [ref:chunk_001]"
    )
    financial_analysis_content = (
        "Cash-flow generation from the Infrastructure Services segment (60% of revenue) remains "
        "robust. Debt service coverage of 1.44x sits above the 1.2x policy floor, leverage of "
        "2.02x is within the 3.0x maximum, and the current ratio of 1.82x indicates sound "
        "short-term liquidity. Debt-to-equity of 38% modestly exceeds the 33.3% Shariah guidance "
        "threshold. [ref:chunk_003]"
    )
    risk_content = (
        "Key risks include customer concentration (top-3 clients represent 54% of contracted "
        "revenue), technology obsolescence requiring continuous capex, and supply-chain exposure "
        "for server hardware. Mitigants include 7-year take-or-pay contracts, maintenance margin "
        "reserves, and comprehensive equipment insurance. [ref:chunk_005]"
    )

    memo_specs = [
        {
            "id": "MEM-2026-081",
            "client_id": "CORP-001",
            "client_name": "KTL Digital Infrastructure KSC",
            "facility_type": "murabaha",
            "deal_value": 1_250_000.0,
            "created_by": "rm_ahmad",
            "created_hours_ago": 26,
            "stage": "risk_review",
            "stage_entered_hours_ago": 22,
            "finalized": False,
            "ratios": ratios_block(1.44, 2.02, 1.82),
            "risk_rating": "medium",
            "sections": [
                {
                    "key": "borrower_overview",
                    "title": "Borrower Overview",
                    "content": borrower_overview_content,
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "rm_ahmad",
                    "flags": {},
                },
                {
                    "key": "financial_analysis",
                    "title": "Financial Analysis",
                    "content": financial_analysis_content,
                    "status": "pending",
                    "requires_review": True,
                    "review_reason": "required_review_above_threshold:1250000>1000000",
                    "flags": {"shariah": [], "citation": []},
                },
                {
                    "key": "risk_and_mitigants",
                    "title": "Risk & Mitigants",
                    "content": risk_content,
                    "status": "pending",
                    "requires_review": True,
                    "review_reason": "required_review_auto_approve_disabled",
                    "flags": {"shariah": [], "citation": []},
                },
            ],
        },
        {
            "id": "MEM-2026-078",
            "client_id": "CORP-002",
            "client_name": "Gulf Al-Oula Ltd",
            "facility_type": "ijara",
            "deal_value": 3_400_000.0,
            "created_by": "rm_ahmad",
            "created_hours_ago": 49,
            "stage": "shariah_board",
            "stage_entered_hours_ago": 23,
            "finalized": False,
            "ratios": ratios_block(1.31, 2.50, 1.45),
            "risk_rating": "medium",
            "sections": [
                {
                    "key": "borrower_overview",
                    "title": "Borrower Overview",
                    "content": (
                        "Gulf Al-Oula Ltd is a real-estate development and leasing company operating "
                        "in Kuwait and the wider GCC, with a portfolio of 12 residential projects and "
                        "3 commercial developments. The company has a 15-year relationship with the bank "
                        "and an unblemished repayment record. [ref:chunk_007]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "rm_ahmad",
                    "flags": {},
                },
                {
                    "key": "financial_analysis",
                    "title": "Financial Analysis",
                    "content": (
                        "Rental income grew 11% year-over-year on the back of Sharq-district commercial "
                        "leases. DSCR of 1.31x exceeds the policy floor, though leverage of 2.50x is "
                        "elevated for the real-estate sector and warrants monitoring. [ref:chunk_009]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "risk_sara",
                    "flags": {"shariah": [], "citation": []},
                },
                {
                    "key": "shariah_flags",
                    "title": "Shariah Compliance Assessment",
                    "content": (
                        "Clause 4.2 of the draft Ijara agreement references a conventional penalty "
                        "rate structure that must be replaced with a Shariah-compliant late-payment "
                        "charity contribution clause per AAOIFI standards. [ref:chunk_011]"
                    ),
                    "status": "pending",
                    "requires_review": True,
                    "review_reason": "required_review_flags_present",
                    "flags": {
                        "shariah": [
                            {
                                "flag_type": "prohibited",
                                "term": "penalty rate",
                                "section": "shariah_flags",
                                "detail": "Prohibited term detected in facility agreement clause 4.2",
                            }
                        ],
                        "citation": [],
                    },
                },
            ],
        },
        {
            "id": "MEM-2026-075",
            "client_id": "SME-001",
            "client_name": "Beacon National Trading WLL",
            "facility_type": "tawarruq",
            "deal_value": 900_000.0,
            "created_by": "rm_ahmad",
            "created_hours_ago": 96,
            "stage": "credit_committee",
            "stage_entered_hours_ago": 40,
            "finalized": False,
            "ratios": ratios_block(1.62, 1.40, 2.10),
            "risk_rating": "low",
            "sections": [
                {
                    "key": "borrower_overview",
                    "title": "Borrower Overview",
                    "content": (
                        "Beacon National Trading WLL is a general-trading SME supplying construction "
                        "materials to Kuwaiti contractors, with revenues of KD 6.8M and a 9-year "
                        "operating history. [ref:chunk_013]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "rm_ahmad",
                    "flags": {},
                },
                {
                    "key": "financial_analysis",
                    "title": "Financial Analysis",
                    "content": (
                        "All ratios are comfortably within policy: DSCR 1.62x, leverage 1.40x, current "
                        "ratio 2.10x. Working-capital financing need is seasonal and well covered by "
                        "the proposed tawarruq limit. [ref:chunk_015]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "risk_sara",
                    "flags": {"shariah": [], "citation": []},
                },
            ],
        },
        {
            "id": "MEM-2026-069",
            "client_id": "CORP-003",
            "client_name": "Amghara Industries Co.",
            "facility_type": "musharakah",
            "deal_value": 5_600_000.0,
            "created_by": "rm_ahmad",
            "created_hours_ago": 120,
            "stage": "draft",
            "stage_entered_hours_ago": 120,
            "finalized": False,
            "ratios": ratios_block(1.28, 2.30, 1.55),
            "risk_rating": "medium",
            "sections": [
                {
                    "key": "borrower_overview",
                    "title": "Borrower Overview",
                    "content": (
                        "Amghara Industries Co. is a Kuwaiti manufacturing group producing precast "
                        "construction materials with two plants in Amghara Industrial Area. "
                        "A declining-musharakah structure is proposed for the production-line "
                        "expansion. [ref:chunk_017]"
                    ),
                    "status": "pending",
                    "requires_review": True,
                    "review_reason": "required_review_above_threshold:5600000>1000000",
                    "flags": {"shariah": [], "citation": []},
                },
            ],
        },
        {
            "id": "MEM-2026-062",
            "client_id": "CORP-002",
            "client_name": "Sharq Holdings KSCC",
            "facility_type": "sukuk",
            "deal_value": 12_000_000.0,
            "created_by": "rm_ahmad",
            "created_hours_ago": 74,
            "stage": "risk_review",
            "stage_entered_hours_ago": 44,
            "finalized": False,
            "ratios": ratios_block(1.15, 2.80, 1.35),
            "risk_rating": "high",
            "sections": [
                {
                    "key": "borrower_overview",
                    "title": "Borrower Overview",
                    "content": (
                        "Sharq Holdings KSCC is a diversified investment company with holdings across "
                        "logistics, retail, and financial services in the GCC. The proposed sukuk "
                        "issuance funds the acquisition of a regional logistics platform. [ref:chunk_019]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "rm_ahmad",
                    "flags": {},
                },
                {
                    "key": "financial_analysis",
                    "title": "Financial Analysis",
                    "content": (
                        "DSCR of 1.15x is marginally below the 1.2x policy floor, driven by "
                        "elevated debt service during the acquisition window. Leverage of 2.80x "
                        "approaches the sector maximum. Pro-forma synergies restore coverage above "
                        "1.3x by FY2027. [ref:chunk_021]"
                    ),
                    "status": "pending",
                    "requires_review": True,
                    "review_reason": "required_review_flags_present",
                    "flags": {
                        "shariah": [],
                        "citation": [],
                        "ratio_breaches": [
                            {"ratio": "DSCR", "value": 1.15, "threshold": 1.2, "breach_type": "below_minimum"}
                        ],
                    },
                },
            ],
        },
        {
            "id": "MEM-2026-055",
            "client_id": "CLIENT-001",
            "client_name": "Al-Rashid Trading Company",
            "facility_type": "murabaha",
            "deal_value": 3_000_000.0,
            "created_by": "rm_ahmad",
            "created_hours_ago": 168,
            "stage": "final_approval",
            "stage_entered_hours_ago": 72,
            "finalized": True,
            "finalized_hours_ago": 70,
            "ratios": ratios_block(1.45, 2.02, 1.80),
            "risk_rating": "low",
            "sections": [
                {
                    "key": "borrower_overview",
                    "title": "Borrower Overview",
                    "content": (
                        "Al-Rashid Trading Company is an upper-quartile player in the Kuwaiti trading "
                        "sector with diversified revenue across construction materials and general "
                        "trading. [ref:chunk_001]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "rm_ahmad",
                    "flags": {},
                },
                {
                    "key": "financial_analysis",
                    "title": "Financial Analysis",
                    "content": (
                        "DSCR of 1.45x, leverage of 2.02x, and current ratio of 1.80x are all within "
                        "policy thresholds, supported by 8.5% revenue growth. [ref:chunk_003]"
                    ),
                    "status": "approved",
                    "requires_review": False,
                    "approved_by": "risk_sara",
                    "flags": {"shariah": [], "citation": []},
                },
            ],
        },
    ]

    notification_specs = {
        "MEM-2026-081": [
            {
                "event": "memo_generated",
                "recipient": "rm_ahmad",
                "subject": "New Memo Generated",
                "body": "A new credit memo has been generated for client CORP-001 (Murabaha, KD 1,250,000). Please review.",
                "hours_ago": 26,
            },
            {
                "event": "section_requires_review",
                "recipient": "risk_sara",
                "subject": "Section Requires Review",
                "body": "Section 'Financial Analysis' in memo MEM-2026-081 requires your review. Reason: deal value above auto-approval threshold.",
                "hours_ago": 25,
            },
            {
                "event": "approval_stage_changed",
                "recipient": "rm_ahmad",
                "subject": "Approval Stage Changed",
                "body": "Section 'Borrower Overview' in MEM-2026-081 was approved by rm_ahmad.",
                "hours_ago": 20,
            },
        ],
        "MEM-2026-078": [
            {
                "event": "memo_generated",
                "recipient": "rm_ahmad",
                "subject": "New Memo Generated",
                "body": "A new credit memo has been generated for client CORP-002 (Ijara, KD 3,400,000). Please review.",
                "hours_ago": 49,
            },
            {
                "event": "section_requires_review",
                "recipient": "sb_omar",
                "subject": "Shariah Review Required",
                "body": "Section 'Shariah Compliance Assessment' in MEM-2026-078 contains prohibited terminology and requires Board review.",
                "hours_ago": 23,
            },
        ],
        "MEM-2026-062": [
            {
                "event": "memo_generated",
                "recipient": "rm_ahmad",
                "subject": "New Memo Generated",
                "body": "A new credit memo has been generated for client CORP-002 (Sukuk, KD 12,000,000). Please review.",
                "hours_ago": 74,
            },
            {
                "event": "section_requires_review",
                "recipient": "risk_sara",
                "subject": "Section Requires Review",
                "body": "Section 'Financial Analysis' in MEM-2026-062 requires your review. Reason: DSCR ratio breach.",
                "hours_ago": 73,
            },
        ],
        "MEM-2026-055": [
            {
                "event": "finalization_ready",
                "recipient": "rm_ahmad",
                "subject": "Memo Ready for Finalization",
                "body": "Memo MEM-2026-055 is ready for finalization. All sections have been approved.",
                "hours_ago": 70,
            },
        ],
    }

    for spec in memo_specs:
        memo = Memo(
            id=spec["id"],
            client_id=spec["client_id"],
            client_name=spec["client_name"],
            facility_type=spec["facility_type"],
            bank_type="islamic",
            deal_value=spec["deal_value"],
            status="finalized" if spec["finalized"] else spec["stage"],
            workflow_stage=spec["stage"],
            created_by=spec["created_by"],
            created_at=hours_ago(spec["created_hours_ago"]),
            finalized_at=hours_ago(spec["finalized_hours_ago"]) if spec.get("finalized_hours_ago") else None,
            metadata_json={
                "ratios": spec["ratios"],
                "risk_rating": spec["risk_rating"],
                "data_quality": {"confidence": 0.92, "is_valid": True, "reason": None},
                "chunk_ids": ["chunk_001", "chunk_003", "chunk_005"],
            },
        )
        db.add(memo)
        db.flush()

        for s in spec["sections"]:
            db.add(MemoSection(
                memo_id=memo.id,
                section_key=s["key"],
                title=s["title"],
                content=s["content"],
                citations_json=[{"chunk_id": "chunk_001"}, {"chunk_id": "chunk_003"}],
                requires_review=s["requires_review"],
                review_reason=s.get("review_reason", ""),
                review_status=s["status"],
                approved_by=s.get("approved_by"),
                approved_at=hours_ago(spec["created_hours_ago"] - 2) if s.get("approved_by") else None,
                auto_approved_rule="auto_approved_no_flags" if s["status"] == "auto_approved" else None,
                flags_json=s.get("flags") or {},
            ))

        # Workflow events (stage progression history)
        stages = ["draft", "risk_review", "credit_committee", "shariah_board", "final_approval"]
        target_idx = stages.index(spec["stage"]) if spec["stage"] in stages else 0
        entered = spec["stage_entered_hours_ago"]
        for idx in range(target_idx + 1):
            stage = stages[idx]
            db.add(WorkflowEvent(
                memo_id=memo.id,
                from_stage=stages[idx - 1] if idx > 0 else "none",
                to_stage=stage,
                user_id=spec["created_by"],
                action="initialize" if idx == 0 else "advance",
                comment="Workflow initialized after memo generation" if idx == 0
                        else f"Advanced to {stage}",
                timestamp=hours_ago(entered + (target_idx - idx) * 8),
            ))
        if spec["finalized"]:
            db.add(WorkflowEvent(
                memo_id=memo.id,
                from_stage=spec["stage"],
                to_stage="finalized",
                user_id="cc_khalid",
                action="advance",
                comment="Memo finalized — all sections approved",
                timestamp=hours_ago(spec["finalized_hours_ago"]),
            ))

        # Audit entries (hash-chained via the real audit module)
        audit.record_event(
            db=db,
            action="generate_memo",
            user_id=spec["created_by"],
            memo_id=memo.id,
            payload={
                "client_id": spec["client_id"],
                "facility_type": spec["facility_type"],
                "deal_value": spec["deal_value"],
                "sections_generated": len(spec["sections"]),
                "seed": True,
            },
        )
        for s in spec["sections"]:
            if s["status"] == "approved":
                audit.record_approval(
                    db=db,
                    memo_id=memo.id,
                    section_key=s["key"],
                    user_id=s.get("approved_by"),
                    action="manual_approve",
                )
        if spec["finalized"]:
            audit.record_event(
                db=db,
                action="finalize",
                user_id="cc_khalid",
                memo_id=memo.id,
                comment="All sections approved, memo finalized",
            )

        # Notifications
        for n in notification_specs.get(memo.id, []):
            db.add(Notification(
                memo_id=memo.id,
                event_type=n["event"],
                recipient=n["recipient"],
                channel="in_app",
                status="sent",
                subject=n["subject"],
                body=n["body"],
                payload_json={"memo_id": memo.id},
                timestamp=hours_ago(n["hours_ago"]),
                sent_at=hours_ago(n["hours_ago"]),
            ))


if __name__ == "__main__":
    seed()
