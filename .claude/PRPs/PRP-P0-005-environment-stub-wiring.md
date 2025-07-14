# PRP: Environment & Stub Wiring

## Task ID: P0-005
## Wave: A

## Business Logic (Why This Matters)
Tests must never hit paid APIs; prod must never run with stubs.

## Overview
Proper test/prod environment separation

## Dependencies
- P0-004

**Note**: Depends on P0-004 completing successfully in the same CI run.

## Outcome-Focused Acceptance Criteria
Running tests with `USE_STUBS=true` yields 0 external calls (network mocked); prod env rejects `USE_STUBS=true` at startup.

### Task-Specific Acceptance Criteria
- [ ] Stub server auto-starts in tests
- [ ] Environment variables documented
- [ ] Secrets never logged
- [ ] Feature flags for each provider:
  - [ ] `ENABLE_GBP` for Google Business Profile (default: True in prod, False in tests with stubs)
  - [ ] `ENABLE_PAGESPEED` for PageSpeed Insights (default: True in prod, False in tests with stubs)
  - [ ] `ENABLE_SENDGRID` for SendGrid email delivery (default: True in prod, False in tests with stubs)
  - [ ] `ENABLE_OPENAI` for OpenAI API calls (default: True in prod, False in tests with stubs)
  - [ ] Provider flags respect `USE_STUBS` setting (when `USE_STUBS=true`, all provider flags auto-disable)
- [ ] Provider configuration validates on startup (missing required keys fail fast)
- [ ] Test coverage includes all provider flag combinations

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

## Integration Points
- `core/config.py` - Add provider feature flags and validation
- `stubs/server.py` - Mock all provider endpoints
- All test fixtures in `conftest.py`
- Provider clients in `d0_gateway/` - Respect feature flags

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
- All tests pass with `USE_STUBS=true`
- No real API calls in test suite
- `tests/integration/test_stub_server.py` passes
- `tests/unit/core/test_config.py` validates all provider flags
- `tests/unit/d0_gateway/test_provider_flags.py` verifies providers respect flags
- Production startup fails if `USE_STUBS=true` and `ENVIRONMENT=production`


## Example: Provider Feature Flags in Config

```python
# In core/config.py
class Settings(BaseSettings):
    """Application settings with provider feature flags."""
    
    # Core settings
    use_stubs: bool = Field(default=False, description="Use stub server for all external APIs")
    environment: str = Field(default="development", description="Environment name")
    
    # Provider feature flags - auto-disabled when USE_STUBS=true
    enable_gbp: bool = Field(default=True, description="Enable Google Business Profile API")
    enable_pagespeed: bool = Field(default=True, description="Enable PageSpeed Insights API")
    enable_sendgrid: bool = Field(default=True, description="Enable SendGrid email delivery")
    enable_openai: bool = Field(default=True, description="Enable OpenAI API calls")
    
    # Provider API keys (required when provider enabled and not using stubs)
    google_places_api_key: Optional[str] = Field(default=None)
    sendgrid_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    
    @validator("enable_gbp", "enable_pagespeed", "enable_sendgrid", "enable_openai", pre=True)
    def disable_providers_when_using_stubs(cls, v, values):
        """Auto-disable all providers when USE_STUBS=true."""
        if values.get("use_stubs"):
            return False
        return v
    
    @validator("environment")
    def validate_production_settings(cls, v, values):
        """Ensure production never runs with stubs."""
        if v == "production" and values.get("use_stubs"):
            raise ValueError("Production environment cannot run with USE_STUBS=true")
        return v
    
    @root_validator
    def validate_provider_keys(cls, values):
        """Ensure required API keys are present when providers are enabled."""
        if not values.get("use_stubs"):
            if values.get("enable_gbp") and not values.get("google_places_api_key"):
                raise ValueError("Google Places API key required when GBP enabled")
            if values.get("enable_sendgrid") and not values.get("sendgrid_api_key"):
                raise ValueError("SendGrid API key required when SendGrid enabled")
            if values.get("enable_openai") and not values.get("openai_api_key"):
                raise ValueError("OpenAI API key required when OpenAI enabled")
        return values

    class Config:
        env_file = ".env"
        case_sensitive = False

# In conftest.py
@pytest.fixture(autouse=True)
def enforce_stubs(monkeypatch):
    """Ensure tests never hit real APIs."""
    monkeypatch.setenv("USE_STUBS", "true")
    # This automatically disables all provider flags via the validator
```

## Example: Provider Client Respecting Feature Flags

```python
# In d0_gateway/gbp_client.py
from core.config import get_settings

class GBPClient:
    """Google Business Profile API client."""
    
    def __init__(self):
        self.settings = get_settings()
        if not self.settings.enable_gbp:
            raise RuntimeError("GBP client initialized but ENABLE_GBP=false")
        if self.settings.use_stubs:
            self.base_url = "http://localhost:8100"  # Stub server
        else:
            self.base_url = "https://maps.googleapis.com"
            self.api_key = self.settings.google_places_api_key
    
    async def get_place_details(self, place_id: str) -> dict:
        """Fetch place details from GBP API or stub."""
        if self.settings.use_stubs:
            # Hit stub server
            url = f"{self.base_url}/maps/api/place/details/json"
            params = {"place_id": place_id}
        else:
            # Hit real API
            url = f"{self.base_url}/maps/api/place/details/json"
            params = {"place_id": place_id, "key": self.api_key}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
```


## Example File/Pattern
**Stub-server wiring**

## Reference Documentation
`tests/integration/test_stub_server.py` passes with `USE_STUBS=true`.

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

### Step 3: Implementation Order
1. **Update `core/config.py`**:
   - Add provider feature flags with proper types and defaults
   - Add validators for stub/production conflict
   - Add root validator for API key requirements
   - Ensure secrets are never logged (use `SecretStr` for API keys)

2. **Update provider clients in `d0_gateway/`**:
   - Check feature flag in `__init__` methods
   - Switch between stub/real endpoints based on `use_stubs`
   - Fail fast if provider disabled but client instantiated

3. **Update `conftest.py`**:
   - Add autouse fixture to enforce `USE_STUBS=true` in all tests
   - Ensure stub server starts automatically when needed

4. **Create/update tests**:
   - `tests/unit/core/test_config.py` - Test all validation rules
   - `tests/unit/d0_gateway/test_provider_flags.py` - Test provider flag respect
   - `tests/integration/test_stub_server.py` - Test stub server integration

### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green with `USE_STUBS=true`
- Check coverage hasn't decreased below 80%
- Manually test production validation rejection

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-005): Environment & Stub Wiring with provider feature flags`

## Validation Commands
```bash
# Run task-specific tests
USE_STUBS=true pytest tests/integration/test_stub_server.py -xvs
USE_STUBS=true pytest tests/unit/core/test_config.py -xvs
USE_STUBS=true pytest tests/unit/d0_gateway/test_provider_flags.py -xvs

# Verify no real API calls in test suite
USE_STUBS=true pytest -xvs 2>&1 | grep -E "(googleapis|sendgrid|openai)" | wc -l
# Should output: 0

# Test production validation
USE_STUBS=true ENVIRONMENT=production python -c "from core.config import get_settings; get_settings()"
# Should fail with: "Production environment cannot run with USE_STUBS=true"

# Run standard validation
bash scripts/validate_wave_a.sh
```

## Rollback Strategy
**Rollback**: Revert config.py changes

## Feature Flag Requirements

### Core Environment Flags
- `USE_STUBS`: Controls whether to use stub server (must be `false` in production)
- `ENVIRONMENT`: Environment name (development/staging/production)

### Provider Feature Flags (Wave A)
- `ENABLE_GBP`: Enable Google Business Profile API
- `ENABLE_PAGESPEED`: Enable PageSpeed Insights API  
- `ENABLE_SENDGRID`: Enable SendGrid email delivery
- `ENABLE_OPENAI`: Enable OpenAI API calls

### Future Provider Flags (Wave B - DO NOT IMPLEMENT YET)
- `ENABLE_SEMRUSH`: SEMrush API (Wave B)
- `ENABLE_LIGHTHOUSE`: Lighthouse audits (Wave B)
- `ENABLE_VISUAL_ANALYSIS`: Visual rubric analysis (Wave B)
- `ENABLE_LLM_AUDIT`: LLM heuristic audit (Wave B)
- `ENABLE_COST_TRACKING`: Cost ledger tracking (Wave B)
- `USE_DATAAXLE`: DataAxle provider (Wave B)

### Implementation Rules
1. When `USE_STUBS=true`, all provider flags automatically become `false`
2. Production environment (`ENVIRONMENT=production`) must reject `USE_STUBS=true` at startup
3. Each provider client must check its feature flag before initialization
4. Missing required API keys (when provider enabled and not using stubs) must fail fast at startup

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
