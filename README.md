# MemoForge — AI Client Documentation Generator for Warba Bank

Production-grade, Shariah-compliant AI client documentation generator built for **Warba Bank** (100% Islamic, Kuwait).

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     React + TypeScript                   │
│           (Vite, Tailwind, Recharts, React Router)       │
│  Login │ Dashboard │ Generate │ Review │ ECL │ Reports   │
│     │ Audit Log │ Admin │ Landing Page (public)          │
└────────────────────────┬─────────────────────────────────┘
                         │  REST API (JWT + RBAC)
┌────────────────────────▼─────────────────────────────────┐
│                    FastAPI Backend                         │
│  /auth/token │ /generate-memo │ /approve │ /reject       │
│  /finalize │ /ecl/compute │ /audit-log │ /reports        │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│              LangGraph Pipeline + Sequential Fallback     │
│                                                          │
│  DataAgent → DataValidation → Ratio → ECL → Risk →      │
│  Narrative → Compliance → Approval → Compiler            │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    Core Modules                           │
│  • approval_rules — deterministic auto-approve decisions │
│  • shariah_filter — Islamic terminology validation       │
│  • citation_validator — factual claim grounding           │
│  • ecl_engine — CBK/IFRS 9 three-stage ECL              │
│  • security — JWT + 5-role RBAC                         │
│  • audit — hash-chain tamper-evident log                 │
│  • integrations — CRM/CoreBanking/MarketData connectors  │
│  • llm_client — 6 providers (no silent mock fallback)   │
└──────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Backend (FastAPI)

```bash
# From the project root (MemoForge/)
cp .env.example .env
pip install -r requirements.txt

# Set local demo environment (SQLite + Mock LLM)
export MOCK_MODE=true
export DATABASE_URL=sqlite:///./memoforge.db

# Seed the database with demo clients, memos, and users
python3 -m app.scripts.seed_demo_data

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (React + Vite)

```bash
# In a new terminal, from the project root
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000/) to access MemoForge.

---

## Demo Credentials (for evaluation)

Use these login credentials to explore all roles. All passwords are for demo purposes only.

| Role | Username | Password |
|------|----------|----------|
| Relationship Manager (RM) | `rm_ahmad` | `warba2025` |
| Risk Manager | `risk_sara` | `warba2025` |
| Credit Committee | `cc_khalid` | `warba2025` |
| Shariah Board | `sb_omar` | `warba2025` |
| Admin | `admin_system` | `warba2025` |

> **Note:** If your `.env` file is missing or you prefer not to copy it, set the environment variables shown above before running the seed script. This is especially important for `DATABASE_URL` – by default it points to PostgreSQL; for local demo, use the SQLite URL.

---

## Configuration

All settings via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `MOCK_MODE` | `true` | Use mock LLM + connectors. When `false`, requires real API keys. |
| `INTEGRATION_MODE` | `mock` | `mock` = synthetic data; `real` = live bank APIs. |
| `LLM_PROVIDER` | `anthropic` | One of: anthropic, openai, azure, ollama, mock. |
| `LLM_API_KEY` | _(empty)_ | API key for the chosen provider. |
| `DATABASE_URL` | `postgresql://...` | SQLAlchemy connection string. |
| `JWT_SECRET_KEY` | _(change me)_ | Secret for JWT signing. |

## Modules

### Core
- **`app/core/config.py`** — Pydantic settings with env-var override
- **`app/core/business_config.py`** — config.json loader/validator
- **`app/core/approval_rules.py`** — Deterministic auto-approve logic (pure functions)
- **`app/core/security.py`** — JWT creation/verification + RBAC
- **`app/core/audit.py`** — SHA-256 hash-chained audit trail

### Agents
- **`llm_client.py`** — 6 providers (Anthropic, OpenAI, Azure, Bedrock, Ollama, Mock). Raises `LLMProviderError` when `MOCK_MODE=false` and credentials missing.
- **`data_agent.py`** — RAG + integration connectors for client data retrieval
- **`data_validation_agent.py`** — Data completeness/confidence scoring
- **`ratio_agent.py`** — Financial ratio computation (DSCR, leverage, current, etc.)
- **`risk_intelligence_agent.py`** — Risk identification and severity assessment
- **`narrative_agent.py`** — Section narrative generation with citation grounding
- **`compliance_agent.py`** — Shariah + citation compliance checking
- **`approval_orchestrator.py`** — Multi-stage workflow state machine
- **`compiler_agent.py`** — HTML/PDF memo compilation
- **`notification_agent.py`** — Email/SMS/WhatsApp notifications
- **`reporting_agent.py`** — Operational report generation
- **`escalation_agent.py`** — SLA-based escalation ladder

### Integrations
- **`base.py`** — Abstract `CRMConnector`, `CoreBankingConnector`, `MarketDataConnector`
- **`mock_crm.py`** — Realistic Kuwaiti corporate client profiles
- **`mock_core_banking.py`** — Financial statements, facilities, collateral
- **`mock_market_data.py`** — CBK rates, sector benchmarks, FX rates
- **`factory.py`** — Returns correct connector based on `INTEGRATION_MODE`

### ECL Engine (CBK/IFRS 9)
- Three-stage model: Stage 1 (12-month), Stage 2 (lifetime), Stage 3 (credit-impaired)
- Real Warba Bank parameters: 1% PD floor, 30+ DPD Stage 2 trigger, three-scenario weighting
- Portfolio-level computation with per-facility audit trail

### Shariah-Native ECL Adjustments

The ECL engine aligns with Warba Bank's **dual-prerogative approach**: it calculates ECL under IFRS 9 in accordance with CBK guidelines, then takes the **higher of** IFRS 9 ECL or CBK provisioning rules. On top of this, the engine applies Shariah-specific adjustments:

- **EAD — Profit margin stripping**: For Murabaha, Ijara, and Tawarruq contracts, the unearned profit portion is subtracted from gross exposure before applying CCF. Musharakah and Sukuk use gross exposure directly (no profit stripping). This reflects the Islamic finance principle that unearned profit is not part of the credit risk exposure.
- **LGD — Asset-based recovery**: For Ijara and Musharakah facilities with a tangible `asset_recovery_rate`, LGD is computed as `1 - recovery_rate` (blended with CBK collateral haircuts), rather than using conventional LGD floors. This reflects the asset-backed nature of these contracts where the bank retains ownership of the underlying asset.
- **Stage 2 SICR — Shariah non-compliance**: A `shariah_non_compliant` flag on a facility triggers an immediate Stage 2 classification (significant increase in credit risk), taking precedence over DPD and rating-downgrade triggers. This captures the additional risk from Shariah non-compliance events.
- **Gharamah (penalty) exclusion**: Penalty amounts are excluded from EAD calculations, consistent with the principle that Gharamah is not recognised as income and is channelled to charity.
- **Configuration**: Profit margin rates and asset recovery rates by facility type are defined in `config.json` under the `ecl_shariah` section.

### Shariah Compliance
- 5 facility types: Murabaha, Ijara, Musharakah, Sukuk, Tawarruq
- Required terms check (e.g., "cost-plus", "profit rate")
- Prohibited terms check (e.g., "interest rate", "conventional loan")
- APR exemption for profit rate disclosure context

### RBAC Roles
| Role | Permissions |
|---|---|
| RM | Generate memos, approve sections, view all |
| Risk | Approve risk sections, view ECL |
| CreditCommittee | Final approve, finalize memos |
| ShariahBoard | Approve Shariah-flagged sections |
| Admin | Full access + user management |

## Frontend

React + TypeScript + Tailwind CSS + Recharts + Vite, redesigned around the **Frost Bank Blue** design system:

- **Palette** — deep navy `#0F2A4A`, gold `#C9A227`, light gray `#F1F5F9`, white
- **Typography** — Playfair Display (headings) + Open Sans (body)
- **Layout** — Transactional Focus split-view: main content + right sidebar (workflow, charts)
- **Components** — Toast notifications, shimmer skeletons, badge/badge/table design primitives
- **Responsive** — desktop and tablet breakpoints throughout

### Screens (10)

1. **Landing Page** (`/landing`, public) — see below
2. **Login** — JWT authentication
3. **Dashboard** — see Dashboard Features below
4. **Generate Memo** — 3-step wizard (Configuration → Review & Confirm → Live Pipeline)
5. **Memo Review** — Section cards with citations/flags, role-gated Approve/Reject, Review Status sidebar with SLA countdown, Audit Trail
6. **ECL Dashboard** — Staging distribution bar chart, portfolio composition donut, MemoForge-vs-Warba actuals, facility-level breakdown with rule applied
7. **Reporting Center** — Pipeline status donut, SLA breach risk, avg approval time, performance logs (SLA violations / approval delays) with CSV export
8. **Audit Log** — Searchable, CSV-exportable hash-chained log
9. **Admin & RBAC** — Role configuration, security policy toggles, system audit log, add-user provisioning
10. **Notification Center** — In-app notifications with unread count, mark-as-read, and filter (bell icon in Layout)

## Landing Page

The public marketing page at `/landing` communicates MemoForge to bank stakeholders:

- **Hero** — "AI-Powered Client Documentation Engine for Islamic Banks" with stat strip (<1 hr generation, 5-stage workflow, 100% Shariah compliance)
- **Problem** — the 4–8 hour manual memo burden vs. <1 hr with MemoForge
- **How It Works** — Retrieve → Synthesize → Approve (3-step explainer)
- **Features** — 6 capability cards (RAG grounding, CBK/IFRS 9 ECL, Shariah compliance engine, approval workflows, audit trail, integrations)
- **Comparison Table** — MemoForge vs. Traditional manual process vs. Western AI tools (6 criteria)
- **Compliance & Security** — ISO 27001, Kuwait data residency, zero write-back, RBAC
- **CTA** — pilot-program request form with toast confirmation
- **Footer** — product navigation and regulatory badges

## Dashboard Features

The internal Credit Dashboard (post-login home) follows the Transactional Focus split-view:

- **KPI cards** — Active Memos, Pending Approvals, Portfolio ECL Total, Compliance Flags
- **Memo Pipeline table** — searchable pipeline with facility type, workflow stage badges, SLA status (On Track / At Risk / Overdue), deal value, and row-level actions (View, Escalate)
- **Approval Workflow panel** — 5-stage progress tracker for the selected memo with live SLA countdown and assigned-role context
- **ECL Breakdown donut** — MemoForge ECL vs. Warba audited actuals with variance note
- **Compliance Alerts** — Shariah flags, citation issues, and policy exceptions with direct review links
- **Quick Actions** — Approve Section, Escalate, Export Memo Report

```bash
cd frontend && npm run build    # Production build → dist/
```

## Testing

```bash
python3 -m pytest tests/ -v     # 76 tests, all passing
```

> **Note:** `.pytest_cache/` is excluded from version control via `.gitignore`.

## Evaluation Framework

MemoForge includes a built-in evaluation and benchmarking framework (`app/evaluation/`) that measures pipeline quality against a ground-truth corpus.

### Metrics (8)

| Metric | Description |
|---|---|
| `source_extraction_accuracy` | How faithfully data agents extract source fields |
| `ratio_accuracy` | Computed financial ratios vs. ground truth |
| `ecl_accuracy` | ECL figures vs. annotated expected values |
| `shariah_classification` | Facility type and Shariah term correctness |
| `citation_correctness` | Citation grounding accuracy |
| `human_override_frequency` | Rate of human corrections to auto-generated content |
| `final_memo_quality` | Overall memo quality score |
| `processing_time` | End-to-end generation latency |

### Corpus

A seeded evaluation corpus lives in `data/evaluation/corpus/` with 10 benchmark cases. Each case contains:
- `client_profile.json` — synthetic client data
- `facility_details.json` — facility parameters
- `reference_annotations.json` — ground-truth expected values

### Running Evaluations

```bash
# Seed the corpus
python3 -m app.scripts.seed_evaluation_corpus --cases 10

# Run evaluation via API
POST /v1/evaluation/run
```

The evaluation runner (`app/evaluation/runner.py`) operates in shadow mode — it runs the live pipeline against corpus entries and aggregates deltas against reference annotations without affecting production memos.

## Docker

```bash
docker compose up --build       # Full stack on port 8000 (API) + 3000 (UI)
```

## Quality Gates

- No `TODO`, `pass`, or `NotImplementedError` in main code paths
- All 76 tests pass
- Frontend builds without errors (`tsc + vite build`)
- CBK ECL parameters unchanged (validated)
- No silent mock fallback when `MOCK_MODE=false`
- PDF generation via WeasyPrint (requires system deps: `libpango`, `libcairo`, `libgdk-pixbuf`, `libffi` — included in Dockerfile). Falls back to HTML when WeasyPrint unavailable.
- System deployable with real API keys and connectors

## Known Limitations

- **ECL in memo pipeline**: The ECL figures in the memo pipeline use synthetic data for demonstration purposes. The ECL engine itself (`app/risk/ecl_engine.py`) is validated separately with CBK/IFRS 9 parameters.
- **Integration connectors**: Real CRM/Core Banking/Market Data connectors are currently mock adapters returning realistic synthetic data. Real bank API integrations are planned for production deployment.
- **Vector store**: The current implementation uses JSON-based TF-IDF embedding storage rather than pgvector. A pgvector-backed store is recommended for production scale.
- **Generation time claim**: The "<1 hour generation" claim in marketing materials is architectural — no formal benchmark suite is included. Actual generation time depends on LLM provider latency and infrastructure.



