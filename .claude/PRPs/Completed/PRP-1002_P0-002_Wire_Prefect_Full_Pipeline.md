# PRP: Wire Prefect Full Pipeline

## Task ID: P0-002

> 💡 **Claude Implementation Note**: Consider how task subagents can be used to execute portions of this task in parallel to improve efficiency and reduce overall completion time.

## Wave: A

## Business Logic (Why This Matters)
One orchestrated flow proves the entire MVP works end-to-end.

## Overview
Create end-to-end orchestration flow that chains all coordinators together to process a business from targeting through delivery. This demonstrates the complete LeadFactory pipeline working as an integrated system.

## Dependencies
- P0-001

**Note**: Depends on P0-001 completing successfully in the same CI run.

## Outcome-Focused Acceptance Criteria
`smoke/test_full_pipeline_flow.py` generates PDF + email + DB rows for a sample URL within 90 s runtime.

### Task-Specific Acceptance Criteria
- [ ] Flow chains: Target → Source → Assess → Score → Report → Deliver
- [ ] Error handling with retries at each stage
- [ ] Metrics logged at each stage with proper logging
- [ ] Integration test creates PDF and email record (mocked in tests)
- [ ] Pipeline continues on non-critical failures (e.g., email)
- [ ] Pipeline fails on critical failures (e.g., report generation)
- [ ] All coordinator methods called correctly match actual implementations
- [ ] Execution time tracked and reported

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (operations remain efficient)
- [ ] Only modify files within specified integration points (no scope creep)
- [ ] All tests in test_full_pipeline_flow.py must pass
- [ ] Pipeline must handle both async and sync coordinator methods
- [ ] Proper error messages and logging at each stage

## Integration Points
- Update existing `flows/full_pipeline_flow.py`
- Import all coordinator classes correctly
- Wire sequential flow with proper error handling
- Use actual coordinator method names, not invented ones

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
- Existing: `tests/smoke/test_full_pipeline_flow.py`
- Must process a business from targeting through delivery
- All 7 test methods must pass:
  - test_full_pipeline_success
  - test_pipeline_json_output
  - test_pipeline_with_assessment_failure
  - test_pipeline_with_email_failure
  - test_pipeline_critical_failure
  - test_pipeline_performance
  - test_pipeline_flow_decorated

## Implementation Details

### Coordinator Method Mapping
The existing flow uses incorrect method names. Here's the correct mapping:

1. **SourcingCoordinator**
   - WRONG: `source_single_business()` 
   - CORRECT: Use `process_batch()` or create simple wrapper

2. **AssessmentCoordinator**
   - WRONG: `assess_business()`
   - CORRECT: Use `execute_comprehensive_assessment()`

3. **ScoringEngine**
   - WRONG: `score_lead()` (async)
   - CORRECT: `calculate_score()` (sync method)

4. **ReportGenerator**
   - Verify actual method signature
   - Ensure proper async/await usage

5. **DeliveryManager**
   - Verify `send_assessment_email()` exists
   - Check parameter requirements

### Error Handling Strategy
```python
# Non-critical failures (continue pipeline)
- Assessment failures → use default scores
- Email failures → mark as failed but continue

# Critical failures (stop pipeline)
- Report generation failures → fail entire pipeline
- Scoring failures → fail entire pipeline
```

### Example: Correct Coordinator Usage

```python
# Sourcing - create wrapper since no single-business method exists
async def source_business_data(business_data: Dict[str, Any]) -> Dict[str, Any]:
    coordinator = SourcingCoordinator()
    # Either create a minimal wrapper or use existing batch with single item
    # Check if coordinator has initialization requirements
    
# Assessment - use correct method name
coordinator = AssessmentCoordinator()
result = await coordinator.execute_comprehensive_assessment(
    business_id=business_data['id'],
    url=business_data['url'],
    assessment_types=["pagespeed", "tech_stack", "seo_basics"]
)

# Scoring - handle sync method properly
calculator = ScoringEngine()
# Note: calculate_score is SYNC not ASYNC
score_result = calculator.calculate_score(assessment_data)
```

## Reference Documentation
- `d2_sourcing/coordinator.py` - Check actual methods available
- `d3_assessment/coordinator.py` - Use execute_comprehensive_assessment
- `d5_scoring/scoring_engine.py` - Use calculate_score (sync)
- `tests/smoke/test_full_pipeline_flow.py` - All tests must pass

## Implementation Guide

### Step 1: Analyze Existing Coordinators
- Map each coordinator's actual public methods
- Identify if methods are async or sync
- Check initialization requirements
- Note required parameters

### Step 2: Update Flow Implementation
1. Fix method calls to use actual coordinator methods
2. Handle async/sync differences properly
3. Ensure error handling matches test expectations
4. Add proper logging at each stage

### Step 3: Wrapper Functions
For coordinators lacking expected methods, create minimal wrappers:
```python
async def source_single_business(url: str) -> Dict[str, Any]:
    # Wrapper to adapt SourcingCoordinator for single business
    # Use existing batch methods or create minimal implementation
```

### Step 4: Testing Strategy
- Run test file to identify specific failures
- Fix one test at a time
- Ensure mocks match actual implementation
- Verify all 7 tests pass

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-002): Wire Prefect Full Pipeline`

## Validation Commands
```bash
# Run task-specific tests
pytest tests/smoke/test_full_pipeline_flow.py -v

# Verify no import errors
python -c "from flows.full_pipeline_flow import full_pipeline_flow"

# Run with coverage
pytest tests/smoke/test_full_pipeline_flow.py --cov=flows --cov-report=term-missing

# Run standard validation
bash scripts/validate_wave_a.sh
```

## Rollback Strategy
**Rollback**: 
- Revert changes to flows/full_pipeline_flow.py
- Restore original implementation
- Document why changes failed

## Feature Flag Requirements
No new feature flag required - this fix updates existing integration code.

## Success Criteria
- All 7 tests in test_full_pipeline_flow.py passing
- Correct coordinator methods used throughout
- No hardcoded/mocked coordinator logic in production code
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

## Performance Requirements
- Complete pipeline execution < 90 seconds
- Individual stage timeouts:
  - Targeting: 5 seconds
  - Sourcing: 10 seconds  
  - Assessment: 30 seconds
  - Scoring: 5 seconds
  - Report Generation: 20 seconds
  - Email Delivery: 10 seconds

## Security Considerations
- No credentials in logs
- Sanitize URLs before processing
- Validate input URLs
- Handle PII appropriately in logs

## Monitoring & Observability
- Log entry/exit for each stage
- Log execution time per stage
- Log any retries or failures
- Include correlation ID for tracing

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
Add new sub-tasks or TODOs discovered during development to TASK.md under a "Discovered During Work" section.
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
- **Supabase**: Continue using self-hosted Postgres on VPS

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