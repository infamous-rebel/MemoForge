"""Data Agent — retrieves client data from internal/external sources via RAG + connectors.

First agent in the pipeline. Fetches all relevant documents for the client
(via RAG, filtered by ACL) and enriches with live data from CRM, core banking,
and market-data connectors. Prepares the combined context for downstream agents.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.rag.retriever import RetrievedChunk, retrieve, retrieve_all_for_client

logger = logging.getLogger(__name__)


@dataclass
class DataAgentResult:
    """Result from the data retrieval agent."""
    client_id: str
    retrieved_chunks: List[RetrievedChunk] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    context_summary: str = ""
    document_types_found: List[str] = field(default_factory=list)
    connector_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def retrieved_context_text(self) -> str:
        """Concatenate all retrieved chunks and connector data into a context string."""
        parts = []

        # Connector data first (structured, high-signal)
        if self.connector_data:
            parts.append("[Source 0 | connector | integration_data]")
            parts.append(_format_connector_data(self.connector_data))

        # RAG chunks
        for i, chunk in enumerate(self.retrieved_chunks, 1):
            parts.append(
                f"[Source {i} | {chunk.chunk_id} | {chunk.document_type or 'unknown'}]\n"
                f"{chunk.content}"
            )

        if not parts:
            return "No data retrieved for this client."

        return "\n\n---\n\n".join(parts)


def _format_connector_data(data: Dict[str, Any]) -> str:
    """Format connector data into a human-readable context block."""
    lines = []

    # Client profile
    profile = data.get("client_profile")
    if profile:
        lines.append(f"Client: {profile.get('legal_name', 'N/A')}")
        lines.append(f"  Type: {profile.get('client_type', 'N/A')}")
        lines.append(f"  Sector: {profile.get('sector', 'N/A')} / {profile.get('sub_sector', 'N/A')}")
        lines.append(f"  Risk Rating: {profile.get('risk_rating', 'N/A')}")
        lines.append(f"  RM: {profile.get('rm_name', 'N/A')}")
        if profile.get("group_name"):
            lines.append(f"  Group: {profile['group_name']}")

    # Financial statements
    financials = data.get("financial_statements", [])
    if financials:
        lines.append("\nFinancial Statements:")
        for fs in financials:
            lines.append(f"  Period {fs.get('period_end', 'N/A')}:")
            lines.append(f"    Revenue: {fs.get('revenue', 0):,.0f} {fs.get('currency', 'KWD')}")
            lines.append(f"    Net Income: {fs.get('net_income', 0):,.0f}")
            lines.append(f"    Total Assets: {fs.get('total_assets', 0):,.0f}")
            lines.append(f"    Total Liabilities: {fs.get('total_liabilities', 0):,.0f}")
            lines.append(f"    Total Equity: {fs.get('total_equity', 0):,.0f}")

    # Existing facilities
    facilities = data.get("existing_facilities", [])
    if facilities:
        lines.append(f"\nExisting Facilities ({len(facilities)}):")
        for fac in facilities:
            lines.append(
                f"  {fac.get('facility_id', 'N/A')}: {fac.get('facility_type', 'N/A')} "
                f"| Outstanding: {fac.get('outstanding_balance', 0):,.0f} "
                f"| Profit Rate: {fac.get('profit_rate', 0):.2%} "
                f"| Stage: {fac.get('stage', 'N/A')}"
            )

    # Sector benchmarks
    benchmarks = data.get("sector_benchmarks", {})
    if benchmarks:
        lines.append("\nSector Benchmarks:")
        for key, bp in benchmarks.items():
            lines.append(f"  {key}: {bp.get('value', 0):.2f}")

    return "\n".join(lines)


def run_data_agent(
    db: Session,
    client_id: str,
    facility_type: str,
    deal_value: float,
    rm_acl_groups: Optional[List[str]] = None,
    queries: Optional[List[str]] = None,
) -> DataAgentResult:
    """Execute the data retrieval agent.

    Retrieves data from two sources:
    1. RAG pipeline (documents in the vector store, ACL-filtered)
    2. Integration connectors (CRM, core banking, market data)

    Args:
        db: Database session.
        client_id: Client identifier.
        facility_type: Islamic facility type.
        deal_value: Deal value in KD.
        rm_acl_groups: ACL groups for the requesting RM.
        queries: Optional custom queries (defaults to auto-generated).

    Returns:
        DataAgentResult with retrieved chunks, connector data, and metadata.
    """
    logger.info("DataAgent: retrieving data for client=%s facility=%s", client_id, facility_type)

    result = DataAgentResult(client_id=client_id)

    # ---- Part 1: Integration connectors ----
    connector_data: Dict[str, Any] = {}
    sector = ""
    try:
        from app.integrations.factory import (
            get_core_banking_connector,
            get_crm_connector,
            get_market_data_connector,
        )

        crm = get_crm_connector()
        profile = crm.get_client_profile(client_id)
        connector_data["client_profile"] = {
            "client_id": profile.client_id,
            "legal_name": profile.legal_name,
            "trade_name": profile.trade_name,
            "client_type": profile.client_type,
            "sector": profile.sector,
            "sub_sector": profile.sub_sector,
            "risk_rating": profile.risk_rating,
            "rm_name": profile.rm_name,
            "rm_email": profile.rm_email,
            "group_name": profile.group_name,
            "relationship_start_date": str(profile.relationship_start_date)
            if profile.relationship_start_date
            else None,
        }
        sector = profile.sector

        core = get_core_banking_connector()
        financials = core.get_financial_statements(client_id, periods=3)
        connector_data["financial_statements"] = [
            {
                "period_end": str(fs.period_end),
                "period_type": fs.period_type,
                "currency": fs.currency,
                "total_assets": fs.total_assets,
                "total_liabilities": fs.total_liabilities,
                "total_equity": fs.total_equity,
                "net_operating_income": fs.net_operating_income,
                "net_income": fs.net_income,
                "current_assets": fs.current_assets,
                "current_liabilities": fs.current_liabilities,
                "total_debt_service": fs.total_debt_service,
                "revenue": fs.revenue,
            }
            for fs in financials
        ]

        facilities = core.get_existing_facilities(client_id)
        connector_data["existing_facilities"] = [
            {
                "facility_id": f.facility_id,
                "facility_type": f.facility_type,
                "original_amount": f.original_amount,
                "outstanding_balance": f.outstanding_balance,
                "profit_rate": f.profit_rate,
                "maturity_date": str(f.maturity_date) if f.maturity_date else None,
                "collateral_type": f.collateral_type,
                "collateral_value": f.collateral_value,
                "days_past_due": f.days_past_due,
                "stage": f.stage,
            }
            for f in facilities
        ]

        collateral = core.get_collateral_records(client_id)
        connector_data["collateral_records"] = collateral

        market = get_market_data_connector()
        if sector:
            benchmarks = market.get_sector_benchmarks(sector)
            connector_data["sector_benchmarks"] = {
                k: {"symbol": v.symbol, "value": v.value, "as_of": str(v.as_of)}
                for k, v in benchmarks.items()
            }

        policy_rate = market.get_policy_rate()
        connector_data["policy_rate"] = {
            "symbol": policy_rate.symbol,
            "value": policy_rate.value,
            "as_of": str(policy_rate.as_of),
        }

        logger.info("DataAgent: connector data loaded for client=%s (sector=%s)", client_id, sector)

    except Exception as e:
        logger.warning("DataAgent: connector retrieval failed: %s", e)
        result.errors.append(f"Connector retrieval failed: {str(e)[:100]}")

    result.connector_data = connector_data

    # ---- Part 2: RAG retrieval ----
    if queries is None:
        queries = [
            f"client {client_id} financial statements income balance sheet",
            f"client {client_id} {facility_type} facility agreement terms",
            f"client {client_id} collateral security valuation",
            f"client {client_id} credit history performance",
            f"client {client_id} industry sector analysis",
        ]

    all_chunks: Dict[str, RetrievedChunk] = {}
    doc_types: set = set()

    for query in queries:
        try:
            chunks = retrieve(
                db=db,
                query=query,
                client_id=client_id,
                rm_acl_groups=rm_acl_groups,
                top_k=5,
            )
            for chunk in chunks:
                if chunk.chunk_id not in all_chunks:
                    all_chunks[chunk.chunk_id] = chunk
                if chunk.document_type:
                    doc_types.add(chunk.document_type)
        except Exception as e:
            logger.warning("DataAgent: query failed '%s': %s", query[:50], e)
            result.errors.append(f"Query failed: {str(e)[:100]}")

    # Also retrieve all client documents for comprehensive coverage
    try:
        all_client_chunks = retrieve_all_for_client(db, client_id, rm_acl_groups, limit=30)
        for chunk in all_client_chunks:
            if chunk.chunk_id not in all_chunks:
                all_chunks[chunk.chunk_id] = chunk
            if chunk.document_type:
                doc_types.add(chunk.document_type)
    except Exception as e:
        logger.warning("DataAgent: client retrieval failed: %s", e)
        result.errors.append(f"Client retrieval failed: {str(e)[:100]}")

    result.retrieved_chunks = list(all_chunks.values())
    result.chunk_ids = [c.chunk_id for c in result.retrieved_chunks]
    result.document_types_found = sorted(doc_types)

    result.context_summary = (
        f"Retrieved {len(result.retrieved_chunks)} chunks from "
        f"{len(doc_types)} document types for client {client_id}. "
        f"Connector data: {'yes' if connector_data else 'no'}."
    )

    logger.info("DataAgent: %s", result.context_summary)
    return result
