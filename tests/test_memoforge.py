"""Comprehensive test suite for MemoForge.

Tests all modules: config, approval rules, Shariah filter, citation validator,
ratio agent, data validation, compliance, risk intelligence, ECL engine,
approval orchestrator, notification, reporting, escalation, integrations,
and API endpoints.
"""

import json
import os
import pytest
from pathlib import Path

# Ensure MOCK_MODE for all tests
os.environ["MOCK_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "tfidf"
os.environ["DATABASE_URL"] = "sqlite:///test_memoforge.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["INTEGRATION_MODE"] = "mock"


# =============================================================================
# Test: Business Config
# =============================================================================

class TestBusinessConfig:
    def test_load_config(self):
        from app.core.business_config import load_config
        config = load_config()
        assert config is not None
        assert "rbac" in config
        assert "shariah_terminology" in config
        assert "hitl_rules" in config

    def test_get_shariah_terminology(self):
        from app.core.business_config import get_shariah_terminology
        terms = get_shariah_terminology("murabaha")
        assert "required_terms" in terms
        assert "prohibited_terms" in terms
        assert "cost-plus" in terms["required_terms"]

    def test_get_risk_thresholds(self):
        from app.core.business_config import get_risk_thresholds
        thresholds = get_risk_thresholds()
        assert "min_dscr" in thresholds
        assert thresholds["min_dscr"] == 1.2

    def test_get_approval_workflow(self):
        from app.core.business_config import get_approval_workflow
        wf = get_approval_workflow()
        assert "stages" in wf
        assert "draft" in wf["stages"]

    def test_unknown_facility_type(self):
        from app.core.business_config import get_shariah_terminology
        with pytest.raises(ValueError):
            get_shariah_terminology("unknown_type")


# =============================================================================
# Test: Approval Rules (matches Section 7 spec exactly)
# =============================================================================

class TestApprovalRules:
    def test_auto_approve_no_flags(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags()
        approved, rule = should_auto_approve(
            "borrower_overview", flags, "murabaha", 1_000_000
        )
        assert approved is True
        assert rule == "auto_approved_no_flags"

    def test_no_auto_approve_sukuk(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags()
        approved, rule = should_auto_approve(
            "borrower_overview", flags, "sukuk", 1_000_000
        )
        assert approved is False
        assert "facility_type" in rule

    def test_no_auto_approve_high_value(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags()
        approved, rule = should_auto_approve(
            "borrower_overview", flags, "murabaha", 10_000_000
        )
        assert approved is False
        assert "threshold" in rule

    def test_no_auto_approve_with_flags(self):
        """Any flags present → requires review."""
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags(shariah_flags=[{"term": "interest rate"}])
        approved, rule = should_auto_approve(
            "borrower_overview", flags, "murabaha", 1_000_000
        )
        assert approved is False
        assert rule == "required_review_flags_present"

    def test_no_auto_approve_ratio_breaches(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags(ratio_breaches=[{"ratio": "DSCR", "actual": 0.9}])
        approved, rule = should_auto_approve(
            "financial_analysis", flags, "murabaha", 1_000_000
        )
        assert approved is False
        assert rule == "required_review_flags_present"

    def test_no_auto_approve_risk_flags(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags(risk_flags=[{"risk": "concentration"}])
        approved, rule = should_auto_approve(
            "risk_and_mitigants", flags, "murabaha", 1_000_000
        )
        assert approved is False
        assert rule == "required_review_flags_present"

    def test_no_auto_approve_citation_problems(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags(citation_problems=[{"problem": "missing_ref"}])
        approved, rule = should_auto_approve(
            "borrower_overview", flags, "murabaha", 1_000_000
        )
        assert approved is False
        assert rule == "required_review_flags_present"

    def test_no_auto_approve_policy_exceptions(self):
        from app.core.approval_rules import should_auto_approve, SectionFlags
        flags = SectionFlags(policy_exceptions=[{"exception": "limit_breach"}])
        approved, rule = should_auto_approve(
            "policy_exceptions", flags, "murabaha", 1_000_000
        )
        assert approved is False
        assert rule == "never_auto_approve_section:policy_exceptions"

    def test_evaluate_risk_level(self):
        from app.core.approval_rules import evaluate_risk_level, SectionFlags
        flags = SectionFlags()
        assert evaluate_risk_level(flags) == "low"

        flags = SectionFlags(shariah_flags=[{"term": "interest"}])
        assert evaluate_risk_level(flags) == "critical"

    def test_get_required_review_role(self):
        from app.core.approval_rules import get_required_review_role, SectionFlags
        flags = SectionFlags(shariah_flags=[{"term": "interest"}])
        roles = get_required_review_role("borrower_overview", flags)
        assert "ShariahBoard" in roles

    def test_has_any_flags_property(self):
        from app.core.approval_rules import SectionFlags
        flags = SectionFlags()
        assert flags.has_any_flags is False
        flags = SectionFlags(risk_flags=[{"r": "x"}])
        assert flags.has_any_flags is True


# =============================================================================
# Test: Shariah Filter
# =============================================================================

class TestShariahFilter:
    def test_compliant_murabaha_content(self):
        from app.guardrails.shariah_filter import check_shariah_compliance, is_compliant
        content = (
            "The Murabaha facility is structured as a cost-plus sale with deferred payment. "
            "The profit rate is set at 5.5% per annum on the sale price."
        )
        flags = check_shariah_compliance(content, "murabaha")
        assert is_compliant(flags)

    def test_prohibited_interest_rate(self):
        from app.guardrails.shariah_filter import check_shariah_compliance, is_compliant
        content = "The interest rate on the loan is 7.5% per annum."
        flags = check_shariah_compliance(content, "murabaha")
        assert not is_compliant(flags)
        assert any(f.flag_type == "prohibited" for f in flags)

    def test_apr_exemption(self):
        from app.guardrails.shariah_filter import check_shariah_compliance
        content = (
            "The annual percentage rate (profit rate) on the Murabaha facility "
            "is 5.5% per annum, representing the agreed profit on the cost-plus sale."
        )
        flags = check_shariah_compliance(content, "murabaha")
        prohibited = [f for f in flags if f.flag_type == "prohibited" and f.term == "interest rate"]
        assert len(prohibited) == 0

    def test_missing_required_terms(self):
        from app.guardrails.shariah_filter import check_shariah_compliance
        content = "This is a generic financial facility."
        flags = check_shariah_compliance(content, "murabaha")
        missing = [f for f in flags if f.flag_type == "missing_required"]
        assert len(missing) > 0


# =============================================================================
# Test: Citation Validator
# =============================================================================

class TestCitationValidator:
    def test_valid_citations(self):
        from app.guardrails.validators import validate_citations
        content = "The client has KD 5,000,000 in assets [ref:chunk_001]."
        valid, problems = validate_citations(content, {"chunk_001"})
        assert not any(p.problem_type == "missing_citation" and p.severity == "error" for p in problems)

    def test_missing_citation(self):
        from app.guardrails.validators import validate_citations
        content = "The client has KD 5,000,000 in total assets according to the latest statement."
        valid, problems = validate_citations(content, {"chunk_001"})
        assert any(p.problem_type == "missing_citation" for p in problems)

    def test_invalid_chunk_id(self):
        from app.guardrails.validators import validate_citations, extract_citations
        content = "Value is KD 1,000,000 [ref:nonexistent_chunk]."
        citations = extract_citations(content)
        assert "nonexistent_chunk" in citations


# =============================================================================
# Test: Data Validation Agent
# =============================================================================

class TestDataValidation:
    def test_empty_context(self):
        from app.agents.data_validation_agent import validate_context
        result = validate_context([], "murabaha")
        assert not result.is_valid
        assert result.confidence_score == 0.0

    def test_confidence_scoring(self):
        from app.agents.data_validation_agent import validate_context
        from app.rag.retriever import RetrievedChunk

        chunks = [
            RetrievedChunk(
                chunk_id="c1", document_id="d1",
                content="Net operating income of KD 2,500,000. Total debt service of KD 1,700,000. "
                        "Total liabilities KD 8,500,000. Total equity KD 4,200,000. "
                        "Current assets KD 6,300,000. Current liabilities KD 3,500,000.",
                score=0.9, document_type="financial_statement",
            ),
        ]
        result = validate_context(chunks, "murabaha")
        assert result.confidence_score > 0
        assert len(result.missing_fields) < 6


# =============================================================================
# Test: Ratio Agent
# =============================================================================

class TestRatioAgent:
    def test_mock_extraction(self):
        from app.agents.ratio_agent import run_ratio_agent
        context = "Client financial data showing net operating income of KD 2,500,000 [ref:chunk_001]."
        result = run_ratio_agent(context, "CLIENT-001")
        assert result.dscr is not None
        assert result.dscr > 0


# =============================================================================
# Test: ECL Engine
# =============================================================================

class TestECLEngine:
    def test_single_facility_stage1(self):
        from app.risk.ecl_engine import compute_ecl, Facility
        facility = Facility(
            facility_id="F001",
            client_id="C001",
            facility_type="murabaha",
            gross_exposure=1_000_000,
            utilized_amount=800_000,
            unutilized_amount=200_000,
            pd_1yr=0.02,
            lgd=0.45,
            days_past_due=0,
            internal_rating="BBB",
            is_investment_grade=True,
            rating_at_origination="BBB",
            collateral_type="real_estate",
            collateral_value=500_000,
        )
        result = compute_ecl([facility])
        assert result.stage1_ecl > 0
        assert result.stage2_ecl == 0
        assert result.stage3_ecl == 0

    def test_defaulted_facility_stage3(self):
        from app.risk.ecl_engine import compute_ecl, Facility
        facility = Facility(
            facility_id="F002",
            client_id="C002",
            facility_type="ijara",
            gross_exposure=2_000_000,
            pd_1yr=0.50,
            lgd=0.60,
            days_past_due=120,
            internal_rating="CCC",
            is_investment_grade=False,
            rating_at_origination="BBB",
            is_defaulted=True,
        )
        result = compute_ecl([facility])
        assert result.stage3_ecl > 0

    def test_stage2_30dpd(self):
        from app.risk.ecl_engine import compute_ecl, Facility
        facility = Facility(
            facility_id="F003",
            client_id="C003",
            facility_type="murabaha",
            gross_exposure=500_000,
            pd_1yr=0.03,
            lgd=0.50,
            days_past_due=45,
            internal_rating="BB+",
            is_investment_grade=False,
            rating_at_origination="BBB",
        )
        result = compute_ecl([facility])
        assert result.stage2_ecl > 0

    def test_pd_floor(self):
        from app.risk.ecl_engine import compute_ecl, Facility
        facility = Facility(
            facility_id="F004",
            client_id="C004",
            facility_type="murabaha",
            gross_exposure=1_000_000,
            pd_1yr=0.001,
            lgd=0.50,
            days_past_due=0,
            internal_rating="AAA",
            is_investment_grade=True,
            rating_at_origination="AAA",
        )
        result = compute_ecl([facility])
        assert result.stage_breakdown[0]["facilities"][0]["pd"] >= 0.01


# =============================================================================
# Test: Synthetic Portfolio
# =============================================================================

class TestSyntheticPortfolio:
    def test_portfolio_generation(self):
        from app.risk.synthetic_portfolio import generate_synthetic_portfolio
        portfolio = generate_synthetic_portfolio(num_facilities=50)
        assert len(portfolio) >= 45
        total = sum(f.gross_exposure for f in portfolio)
        assert total > 0

    def test_deterministic(self):
        from app.risk.synthetic_portfolio import generate_synthetic_portfolio
        p1 = generate_synthetic_portfolio(num_facilities=20)
        p2 = generate_synthetic_portfolio(num_facilities=20)
        assert p1[0].facility_id == p2[0].facility_id
        assert p1[0].gross_exposure == p2[0].gross_exposure


# =============================================================================
# Test: Security / JWT
# =============================================================================

class TestSecurity:
    def test_create_and_verify_token(self):
        from app.core.security import create_access_token, verify_token
        token = create_access_token(
            user_id="user1",
            username="analyst1",
            full_name="Test Analyst",
            role="RM",
            acl_groups=["corporate_banking"],
        )
        identity = verify_token(token)
        assert identity.user_id == "user1"
        assert identity.role == "RM"
        assert "corporate_banking" in identity.acl_groups


# =============================================================================
# Test: LLM Client
# =============================================================================

class TestLLMClient:
    def test_mock_provider(self):
        from app.agents.llm_client import MockProvider
        provider = MockProvider()
        response = provider.complete("Generate a borrower overview")
        assert response.content
        assert len(response.content) > 0

    def test_mock_structured(self):
        from app.agents.llm_client import MockProvider
        provider = MockProvider()
        schema = {
            "type": "object",
            "properties": {
                "net_operating_income": {"type": "number"},
                "source_chunk_ids": {"type": "object"},
            },
        }
        response = provider.complete_structured("Extract financials", schema)
        assert "net_operating_income" in response.data

    def test_mock_structured_array_fields(self):
        """MockProvider must handle array-type fields with chunk_id refs."""
        from app.agents.llm_client import MockProvider
        provider = MockProvider()
        schema = {
            "type": "object",
            "properties": {
                "key_risks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "severity": {"type": "string"},
                            "chunk_id": {"type": "string"},
                        },
                    },
                },
                "mitigants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "chunk_id": {"type": "string"},
                        },
                    },
                },
            },
        }
        response = provider.complete_structured("Analyze risks", schema)
        assert isinstance(response.data["key_risks"], list)
        assert len(response.data["key_risks"]) > 0
        assert "chunk_id" in response.data["key_risks"][0]
        assert isinstance(response.data["mitigants"], list)
        assert len(response.data["mitigants"]) > 0

    def test_get_llm_client_mock_mode(self):
        from app.agents.llm_client import get_llm_client, MockProvider
        client = get_llm_client()
        assert isinstance(client, MockProvider)

    def test_no_silent_mock_fallback(self):
        """When MOCK_MODE=false and no API key, LLMProviderError must be raised."""
        from app.agents.llm_client import get_llm_client, LLMProviderError
        from app.core.config import Settings

        # Temporarily create settings with mock_mode=False
        old_mock = os.environ.get("MOCK_MODE", "true")
        os.environ["MOCK_MODE"] = "false"
        os.environ["LLM_PROVIDER"] = "anthropic"
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()

        try:
            with pytest.raises(LLMProviderError):
                get_llm_client()
        finally:
            os.environ["MOCK_MODE"] = old_mock
            get_settings.cache_clear()

    def test_unknown_provider_raises(self):
        """Unknown provider name should raise LLMProviderError."""
        from app.agents.llm_client import get_llm_client, LLMProviderError

        old_mock = os.environ.get("MOCK_MODE", "true")
        os.environ["MOCK_MODE"] = "false"
        os.environ["LLM_PROVIDER"] = "nonexistent"
        from app.core.config import get_settings
        get_settings.cache_clear()

        try:
            with pytest.raises(LLMProviderError):
                get_llm_client()
        finally:
            os.environ["MOCK_MODE"] = old_mock
            os.environ["LLM_PROVIDER"] = "mock"
            get_settings.cache_clear()


# =============================================================================
# Test: Risk Intelligence Agent
# =============================================================================

class TestRiskIntelligence:
    def test_risk_analysis(self):
        from app.agents.risk_intelligence_agent import analyze_risk
        from app.agents.ratio_agent import RatioAgentResult, RatioBreach

        ratio_result = RatioAgentResult(
            dscr=1.1,
            leverage_ratio=3.5,
            current_ratio=0.8,
            breaches=[
                RatioBreach("DSCR", 1.1, 1.2, "below_minimum", "DSCR below threshold"),
                RatioBreach("Leverage", 3.5, 3.0, "above_maximum", "Leverage above max"),
            ],
        )

        analysis = analyze_risk(ratio_result, retrieved_context="Client operates in real estate sector")
        assert len(analysis.key_risks) > 0
        assert analysis.overall_risk_rating in ("low", "medium", "high", "critical")


# =============================================================================
# Test: Compliance Agent
# =============================================================================

class TestComplianceAgent:
    def test_compliant_section(self):
        from app.agents.compliance_agent import check_section
        content = (
            "The Murabaha facility uses cost-plus profit rate with deferred payment terms "
            "as documented in [ref:chunk_001]."
        )
        result = check_section("borrower_overview", content, "murabaha", {"chunk_001"})
        assert result.section_key == "borrower_overview"

    def test_non_compliant_section(self):
        from app.agents.compliance_agent import check_section
        content = "The interest rate on the conventional loan is 7.5%."
        result = check_section("borrower_overview", content, "murabaha", set())
        assert result.severity in ("high", "critical")


# =============================================================================
# Test: Integration Layer
# =============================================================================

class TestIntegrations:
    def test_mock_crm_connector(self):
        from app.integrations.mock_crm import MockCRMConnector
        crm = MockCRMConnector()
        profile = crm.get_client_profile("CORP-001")
        assert profile.client_id == "CORP-001"
        assert profile.legal_name
        assert profile.sector == "Real Estate"

    def test_mock_crm_unknown_client(self):
        from app.integrations.mock_crm import MockCRMConnector
        crm = MockCRMConnector()
        profile = crm.get_client_profile("UNKNOWN-999")
        assert profile.client_id == "UNKNOWN-999"

    def test_mock_core_banking(self):
        from app.integrations.mock_core_banking import MockCoreBankingConnector
        core = MockCoreBankingConnector()
        financials = core.get_financial_statements("CORP-001")
        assert len(financials) >= 1
        assert financials[0].total_assets > 0

        facilities = core.get_existing_facilities("CORP-001")
        assert len(facilities) >= 1

        collateral = core.get_collateral_records("CORP-001")
        assert len(collateral) >= 1

    def test_mock_market_data(self):
        from app.integrations.mock_market_data import MockMarketDataConnector
        market = MockMarketDataConnector()
        benchmarks = market.get_sector_benchmarks("Real Estate")
        assert "avg_dscr" in benchmarks
        assert benchmarks["avg_dscr"].value > 0

        fx = market.get_fx_rates()
        assert "USD" in fx

        policy_rate = market.get_policy_rate()
        assert policy_rate.value > 0

    def test_factory_mock_mode(self):
        from app.integrations.factory import (
            get_crm_connector,
            get_core_banking_connector,
            get_market_data_connector,
            reset_connectors,
        )
        reset_connectors()
        crm = get_crm_connector()
        core = get_core_banking_connector()
        market = get_market_data_connector()
        assert crm is not None
        assert core is not None
        assert market is not None
        reset_connectors()


# =============================================================================
# Test: API Endpoints
# =============================================================================

class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        from app.core.security import create_access_token
        token = create_access_token(
            user_id="test_user",
            username="analyst",
            full_name="Test Analyst",
            role="RM",
            acl_groups=["corporate_banking"],
        )
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def admin_headers(self):
        from app.core.security import create_access_token
        token = create_access_token(
            user_id="admin_user",
            username="admin",
            full_name="Admin User",
            role="Admin",
            acl_groups=["corporate_banking", "credit_analysis"],
        )
        return {"Authorization": f"Bearer {token}"}

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "MemoForge" in response.json()["name"]

    def test_auth_token(self, client):
        """Test legacy auth endpoint (now requires real user store)."""
        from app.core import users
        from app.db.session import get_db_session, init_db, get_engine
        engine = get_engine()
        init_db(engine)
        db = get_db_session()
        try:
            users.ensure_default_users(db)
            db.commit()
            response = client.post("/v1/auth/token", json={
                "username": "rm_ahmad", "password": "warba2025"
            })
            assert response.status_code == 200
            assert "access_token" in response.json()
        finally:
            db.close()

    def test_unauthorized_access(self, client):
        response = client.get("/v1/memo/test-id")
        assert response.status_code == 401

    def test_auth_token_with_valid_credentials(self, client):
        """Test login with default bootstrap user."""
        from app.core import users
        from app.db.session import get_db_session, init_db, get_engine
        engine = get_engine()
        init_db(engine)
        db = get_db_session()
        try:
            users.ensure_default_users(db)
            db.commit()
            response = client.post("/v1/auth/token", json={
                "username": "rm_ahmad", "password": "warba2025"
            })
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["user_id"] is not None
            assert data["role"] == "RM"
            assert data["full_name"] is not None
        finally:
            db.close()

    def test_auth_token_with_invalid_credentials(self, client):
        """Test login with wrong password."""
        response = client.post("/v1/auth/token", json={
            "username": "rm_ahmad", "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_list_memos(self, client, auth_headers):
        """Test listing memos with SLA computation."""
        response = client.get("/v1/memos", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "memos" in data
        assert isinstance(data["memos"], list)

    def test_notifications_list(self, client, auth_headers):
        """Test listing notifications for current user."""
        response = client.get("/v1/notifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert "unread_count" in data

    def test_escalations_list(self, client, admin_headers):
        """Test listing active escalations (Admin/Risk/CC only)."""
        response = client.get("/v1/escalations", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "escalations" in data

    def test_escalations_check_admin(self, client, admin_headers):
        """Test running escalation check (admin only)."""
        response = client.post("/v1/escalations/check", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "triggered" in data

    def test_global_audit_log(self, client, auth_headers):
        """Test global hash-chained audit log."""
        response = client.get("/v1/audit-log", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_users_list_admin(self, client, admin_headers):
        """Test listing users (admin only)."""
        response = client.get("/v1/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_clients_list(self, client, auth_headers):
        """Test client directory from CRM connector."""
        response = client.get("/v1/clients", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data

    def test_reports_generation(self, client, auth_headers):
        """Test on-demand report generation."""
        response = client.get("/v1/reports/pipeline_status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "report_type" in data
        assert data["report_type"] == "pipeline_status"
        assert "generated_at" in data
        assert "summary" in data
