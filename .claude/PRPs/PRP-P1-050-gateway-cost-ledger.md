# PRP: Gateway Cost Ledger

## Task ID: P1-050
## Wave: B

## Business Logic (Why This Matters)
Without per-call cost tracking you cannot manage profit or guardrails.

## Overview
Track all external API costs

## Dependencies
- P1-040

**Note**: Depends on P1-040 completing successfully in the same CI run.

## Outcome-Focused Acceptance Criteria
Every external API request inserts a ledger row with `cost_usd`; daily aggregation view returns non-NULL totals.

### Task-Specific Acceptance Criteria
- [ ] Every API call logged
- [ ] Costs calculated per provider
- [ ] Daily aggregation views
- [ ] No performance impact
- [ ] Cleanup job for old records

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

## Integration Points
- Create migration for `gateway_cost_ledger` table
- Update `BaseAPIClient._make_request()`
- Add cost calculation methods

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
- `tests/unit/d0_gateway/test_cost_ledger.py`
- `tests/integration/test_cost_tracking.py`


## Example: Cost Ledger Implementation

```python
class GatewayCostLedger(Base):
    __tablename__ = "gateway_cost_ledger"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    provider = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    cost_usd = Column(Numeric(10, 4), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    business_id = Column(UUID, ForeignKey("businesses.id"))
    response_time_ms = Column(Integer)
    
    __table_args__ = (
        Index("idx_cost_ledger_daily", "provider", "timestamp"),
    )
```


## Example File/Pattern
Gateway cost ledger

## Reference Documentation
`tests/unit/d0_gateway/test_cost_ledger.py`

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-050): Gateway Cost Ledger`

## Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d0_gateway/test_cost_ledger.py` `tests/integration/test_cost_tracking.py` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

## Rollback Strategy
**Rollback**: Drop gateway_cost_ledger table

## Feature Flag Requirements
Feature flag required: See integration points for flag name.

## Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

## Critical Context

### From CLAUDE.md (Project Instructions)
```markdown
🧱 Code Structure & Modularity
Never create a file longer than 500 lines of code. If a file approaches this limit, refactor by splitting it into modules or helper files.
Organize code into clearly separated modules, grouped by feature or responsibility. For agents this looks like:
agent.py - Main agent definition and execution logic
tools.py - Tool functions used by the agent
prompts.py - System prompts
Use clear, consistent imports (prefer relative imports within packages).
Use clear, consistent imports (prefer relative imports within packages).
Use python_dotenv and load_env() for environment variables.
🧪 Testing & Reliability
Always create Pytest unit tests for new features (functions, classes, routes, etc).
After updating any logic, check whether existing unit tests need to be updated. If so, do it.
Tests should live in a /tests folder mirroring the main app structure.
Include at least:
1 test for expected use
1 edge case
1 failure case
✅ Task Completion
Mark completed tasks in TASK.md immediately after finishing them.
Add new sub-tasks or TODOs discovered during development to TASK.md under a “Discovered During Work” section.
📎 Style & Conventions
Use Python as the primary language.
Follow PEP8, use type hints, and format with black.
Use pydantic for data validation.
Use FastAPI for APIs and SQLAlchemy or SQLModel for ORM if applicable.
Write docstrings for every function using the Google style:
def example():
    """
    Brief summary.

    Args:
        param1 (type): Description.

    Returns:
        type: Description.
    """
📚 Documentation & Explainability
Update README.md when new features are added, dependencies change, or setup steps are modified.
Comment non-obvious code and ensure everything is understandable to a mid-level developer.
When writing complex logic, add an inline # Reason: comment explaining the why, not just the what.
🧠 AI Behavior Rules
Never assume missing context. Ask questions if uncertain.
Never hallucinate libraries or functions – only use known, verified Python packages.
Always confirm file paths and module names exist before referencing them in code or tests.
Never delete or overwrite existing code unless explicitly instructed to or if part of a task 
```

### From CURRENT_STATE.md (Current State vs PRD)
```markdown
# Current State vs Original PRD — LeadFactory MVP

*(Updated 11 Jul 2025)*

---

## Executive Summary

The original Phase-0 PRDs (June 2025) assumed **Yelp-centric sourcing**, a **single-host Mac-Mini deployment**, and **minimal cost controls**. During July we pivoted to:

* **Remove Yelp entirely** in favour of purchased firmographic data + Google Business Profile (GBP).
* **Container-first infrastructure** (Docker, GitHub Actions, Ubuntu VPS).
* **Two-wave delivery plan**

  * **Wave A (P0)** – stabilise existing code, green the KEEP tests, dockerise CI, deploy app + Postgres container to the VPS.
  * **Wave B (P1/P2)** – add SEMrush, Lighthouse, Visual-rubric, LLM audits and full cost-ledger / guardrails.

---

## Data Sources & Providers

| Status             | Provider                           | Usage                                                 | Notes                                                                                       |
| ------------------ | ---------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Removed**        | Yelp API                           | (was primary in PRD)                                  | Deleted July 2025; schema columns `yelp_id` & `yelp_json` dropped (migration 01dbf243d224). |
| **Active**         | Google Business Profile            | Hours, rating, review\_count, photos                  | Free quota ≈ 500 calls/day.                                                                 |
|                    | PageSpeed Insights                 | FCP, LCP, CLS, TBT, TTI, Speed Index, Perf Score      | Runtime scores collected in Wave A.                                                         |
| **Planned (P0.5)** | Purchased CSV feed (DataAxle-like) | e-mail, phone, domain, NAICS, size codes              | Negotiation underway; expected \$0.10 / record.                                             |
|                    | SEMrush API                        | Site Health, DA, Backlinks, Keywords, Traffic, Issues | New gateway client in Wave B.                                                               |
|                    | Lighthouse (headless)              | Perf/Acc/Best-Pract/SEO/PWA                           | Run via Playwright in Wave B.                                                               |
|                    | ScreenshotOne + OpenAI Vision      | Screenshot & 9-dim Visual Rubric                      | Wave B.                                                                                     |
|                    | GPT-4o (LLM Heuristic Audit)       | UVP clarity, CTA, Readability, etc.                   | Managed in Humanloop.                                                                       |

---

## Assessment & Scoring Changes

| Aspect              | Original PRD             | **Wave A**                               | **Wave B target**                                                   |
| ------------------- | ------------------------ | ---------------------------------------- | ------------------------------------------------------------------- |
| Metrics implemented | PageSpeed + tech headers | + GBP enrichment & review signals        | + SEMrush SEO, Lighthouse scores, Visual Rubric 1-9, LLM heuristics |
| Scoring tiers       | A / B / C                | **A–D** (A ≥ 90, D < 60)                 | May add A+ (≥ 95)                                                   |
| Algorithm           | Simple weighted sum      | Same weights, plus GBP signals (+10 pts) | Vertical-specific weights; impact calculator                        |

---

## Business Model Evolution

| Topic                 | Original                    | **Current**                                                                                                             |
| --------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Lead pool             | Top 10 % via Yelp (≈ 500/d) | **Analyse 100 %** of purchased dataset; score & outreach all leads                                                      |
| Pricing               | \$199 / report              | **\$399 launch** price — will lower after experiments                                                                   |
| Conversion assumption | 0.25 – 0.6 %                | Conservative **0.2 %** of total leads (cold SMB benchmark 2 % → personalised 0.2 % assumption)                          |
| Outreach channels     | ESP cold mail only          | Phase rollout: ① manual low-volume inbox → ② warm-inbox automation → ③ ESP.<br>Parallel LinkedIn + optional snail-mail. |
| Revenue goal          | \$25 k MRR in 6 weeks       | Target slips to **Q1 FY26**                                                                                             |

---

## Technical Architecture

| Layer         | Original PRD         | Current / Planned                                                           |
| ------------- | -------------------- | --------------------------------------------------------------------------- |
| Infra         | Bare-metal Mac-Mini  | **Ubuntu VPS** + Docker.  App + Stub server + Postgres containers (Wave A). |
| Database      | Yelp columns present | Yelp columns removed; new **gateway\_cost\_ledger** table scheduled Wave B. |
| Deployment    | Manual copy          | GitHub Actions ➜ GHCR push ➜ SSH deploy workflow.                           |
| Cost tracking | "Future item"        | Implemented gateway hooks; ledger & guardrails Wave B.                      |

---

## DO NOT IMPLEMENT (Deprecated from PRD)

- **Yelp Integration**: All Yelp-related code/tests/migrations
- **Mac Mini Deployment**: Use VPS + Docker only
- **Top 10% Filtering**: Analyze 100% of purchased data
- **$199 Pricing**: Use $399 launch price
- **Simple Email Templates**: Use LLM-powered personalization
- **Basic scoring only**: Implement full multi-metric assessment

---

## Code Migration Status

| Component | Current State | Required Changes |
|-----------|--------------|------------------|
| d0_gateway | Yelp client exists | Remove Yelp, add DataAxle/SEMrush |
| d3_assessment | PageSpeed works | Add Lighthouse/Visual |
| d5_scoring | Basic algorithm | Add vertical weights |
| d6_reports | PDF generation works | Add unit economics section |
| d8_personalization | Basic templates | LLM-powered generation |
| d9_delivery | SendGrid integrated | Add compliance headers |

---

## Wave A (P0) — Stabilise & Deploy

| Ref        | Feature                     | Key Tests / Checks                                    |
| ---------- | --------------------------- | ----------------------------------------------------- |
| **P0-000** | Prerequisites check         | `pytest --collect-only` OK inside Docker              |
| **P0-001** | Fix D4 Coordinator          | `tests/unit/d4_enrichment/test_d4_coordinator.py`     |
| **P0-002** | Prefect full-pipeline flow  | new `tests/smoke/test_full_pipeline_flow.py`          |
| **P0-003** | Dockerised CI               | KEEP suite passes inside image                        |
| **P0-004** | Database migrations current | `tests/unit/test_migrations.py`                       |
| **P0-005** | Env & stub wiring           | `tests/integration/test_stub_server.py`               |
| **P0-006** | KEEP test-suite green       | `pytest -m "not slow and not phase_future"` = 0 fails |
| **P0-007** | Health endpoint             | `tests/smoke/test_health.py`                          |
| **P0-008** | Test-infra cleanup          | slow-marker & phase\_future auto-tag verified         |
| **P0-009** | Yelp remnants purged        | `tests/test_yelp_purge.py` (grep 0 hits)              |
| **P0-010** | Missing-dependency fix      | fresh `pip install` & `pip check` green               |
| **P0-011** | VPS deploy workflow         | GH Actions → VPS, `/health` 200                       |
| **P0-012** | Postgres container on VPS   | docker-compose up app + db; Alembic upgrade head      |

*Wave A success = PDF & email for one business created, KEEP suite green, app live on VPS.*

---

## Wave B (P1–P2) — Phase 0.5 Expansion

| Ref        | Feature                         | Metrics / Outputs                                                     |
| ---------- | ------------------------------- | --------------------------------------------------------------------- |
| **P1-010** | SEMrush client & 6 metrics      | Site Health, DA, Backlink Toxicity, Organic Traffic, Keywords, Issues |
| **P1-020** | Lighthouse headless audit       | Perf, Accessibility, Best-Practices, SEO, PWA                         |
| **P1-030** | Visual Rubric analyzer          | 9 visual scores via ScreenshotOne + Vision                            |
| **P1-040** | LLM Heuristic audit (Humanloop) | UVP, Contact info, CTA, Social proof, Readability, Viewport, Popup    |
| **P1-050** | Gateway cost ledger             | Per-call cost rows                                                    |
| **P1-060** | Cost guardrails                 | Daily \$100 cap, per-lead \$2.50, provider caps                       |
| **P1-070** | DataAxle provider               | Email/firmographic enrichment                                         |
| **P1-080** | Bucket enrichment flow          | Scheduled nightly, cost-aware                                         |
| **P2-010** | Unit-economics views & API      | CPL, CAC, ROI, LTV                                                    |
| **P2-020** | Unit-econ PDF section           | Charts & projections                                                  |
| **P2-030** | Email personalisation V2        | 5 subject, 3 body variants via LLM                                    |
| **P2-040** | Orchestration budget-stop       | Monthly circuit-breaker                                               |
| **P2-050** | Supabase migration              | Swap VPS Postgres → managed Supabase                                  |

---

## Test Coverage Requirements

- **Wave A**: >80% coverage on core modules (current reality)
- **Wave B**: >95% coverage on all new code (target)
- **Critical paths**: 100% coverage required (payment, email delivery)
- **Integration tests**: Must pass in Docker, not just locally

---

## Feature Flags Required

```python
# Wave A flags (core functionality)
USE_STUBS = True  # False in production
ENABLE_EMAILS = True  # Core feature

# Wave B flags (progressive rollout)
ENABLE_SEMRUSH = False  # Wave B
ENABLE_LIGHTHOUSE = False  # Wave B
ENABLE_VISUAL_ANALYSIS = False  # Wave B
ENABLE_LLM_AUDIT = False  # Wave B
ENABLE_COST_TRACKING = False  # Until P1-050
USE_DATAAXLE = False  # Until negotiated

# Guardrail flags
ENABLE_COST_GUARDRAILS = False  # P1-060
DAILY_BUDGET_CAP = 100.00  # USD
PER_LEAD_CAP = 2.50  # USD
```

---

## External Dependencies Status

| Dependency | Status | Action Required |
|------------|--------|----------------|
| DataAxle API | Negotiating | Use mock until contract |
| SEMrush API | Have key | Implement in Wave B |
| Humanloop | Active | Already integrated |
| ScreenshotOne | Have account | Wire up in Wave B |
| OpenAI | Active | Manage costs carefully |
| SendGrid | Active | Add compliance headers |
| Stripe | Test mode | Move to live for launch |
| Supabase | Evaluating | Decision before P2-050 |

---

## LLM & Prompt-Management

*All production prompts managed in **Humanloop**; deterministic stubs used in tests.*

| Prompt            | Humanloop project  | Used in                            |
| ----------------- | ------------------ | ---------------------------------- |
| Report synthesis  | `report_synthesis` | `d6_reports/synthesizer.py`        |
| Outreach email    | `outreach_email`   | `d9_delivery/email_builder_v2.py`  |
| Visual rubric     | `visual_rubric`    | `d3_assessment/visual_analyzer.py` |
| Mock-up generator | `mockups`          | `d6_reports/mockup_generator.py`   |

---

## Cost Model Snapshot (Wave A only)

| Component           | Cost/lead  |
| ------------------- | ---------- |
| GBP API             | \$0.00     |
| PageSpeed           | \$0.005    |
| ScreenshotOne (PDF) | \$0.002    |
| **Total Wave A**    | **\$0.01** |

Budget guardrails (Wave B) keep spend < **\$100/day** and **\$2.50/lead**.

---

## Quick PRD Validation Guide

When reading PRD.md, ask:
1. Does it mention Yelp? → **Invalid**
2. Does it assume Mac Mini? → **Invalid**
3. Does it filter to 10%? → **Invalid** (analyze 100%)
4. Does it use $199 pricing? → **Invalid** (use $399)
5. Does it use basic templates? → **Invalid** (use LLM)
6. Is it about domain architecture? → **Likely Valid**
7. Is it about database schema? → **Check migrations first**
8. Is it about external APIs? → **Check current providers**
9. Is it about testing strategy? → **Mostly Valid**
10. Is it about orchestration patterns? → **Valid**

---

## Open Questions

1. **Supabase vs RDS** — final call before P2-050.
2. **Which LLM tier** for audit & email to stay within cost cap.
3. **Pricing elasticity** — test \$399 vs \$299 vs usage-based?
4. **DataAxle contract** — timeline and final pricing?
5. **Compliance risk** — CAN-SPAM/GDPR for purchased lists?

---

## Appendix — Working Commands (Wave A)

```bash
# Run full pipeline locally (stubs)
USE_STUBS=true python -m leadfactory.run_demo --url https://example.com

# Build & test container
docker build -f Dockerfile.test -t lf-test .
docker run --rm lf-test pytest -q

# Alembic upgrade
alembic upgrade head

# Prefect flow manual run
prefect run -p flows/full_pipeline_flow.py -n full_pipeline --param url=https://example.com

# Check CI status
gh run list --limit 5
gh run view --log

# Deploy to VPS (after CI passes)
gh workflow run deploy.yml
```

**Environment variables (Wave A)**
```bash
DATABASE_URL=postgresql://user:pass@localhost/leadfactory
SENDGRID_API_KEY=SG.xxxxx
OPENAI_API_KEY=sk-xxxxx
USE_STUBS=true  # Always true in tests
ENABLE_SEMRUSH=false
ENABLE_LIGHTHOUSE=false
ENVIRONMENT=development  # or production
SECRET_KEY=your-secret-key-here
```

---

This document serves as the single source of truth for what LeadFactory actually is today, superseding any conflicting information in the original PRD.
```

**IMPORTANT**: The CURRENT_STATE.md document above contains critical information about:
- Features that have been REMOVED (like Yelp integration)
- Current implementation decisions that differ from the original PRD
- The DO NOT IMPLEMENT section that must be respected
- Current provider status and what's actually being used

Always follow CURRENT_STATE.md when there's any conflict with older documentation.
