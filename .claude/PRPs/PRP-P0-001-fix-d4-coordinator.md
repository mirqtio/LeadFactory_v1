# PRP: Fix D4 Coordinator

## Task ID: P0-001

> 💡 **Claude Implementation Note**: Consider how task subagents can be used to execute portions of this task in parallel to improve efficiency and reduce overall completion time.

## Wave: A

## Business Logic (Why This Matters)
Accurate enrichment merge prevents stale or duplicate provider data in assessments.

## Overview
Repair enrichment coordinator merge/cache logic

## Dependencies
- P0-000

**Note**: Depends on P0-000 completing successfully in the same CI run.

## Outcome-Focused Acceptance Criteria
`test_d4_coordinator.py` passes **and** coordinator returns freshest, deduped fields; cache key collisions across businesses impossible (property-based test).

### Task-Specific Acceptance Criteria
- [ ] Remove xfail marker from test file
- [ ] Fix merge_enrichment_data method
- [ ] Fix cache key generation
- [ ] All 12 coordinator tests passing
- [ ] Add property-based test for cache key collisions using hypothesis
- [ ] Add dedicated unit tests for merge_enrichment_data method
- [ ] Add performance test ensuring merge operations remain O(n)
- [ ] Test coverage for d4_enrichment module ≥ 80%

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)
- [ ] Add inline documentation for complex merge logic
- [ ] Update module docstring to reflect fixed behavior

## Integration Points
- `d4_enrichment/coordinator.py`
- `d4_enrichment/models.py`
- `tests/unit/d4_enrichment/test_d4_coordinator.py` (for new tests)

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py -v` (all 12 existing tests)
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py::test_merge_enrichment_data -v` (new dedicated test)
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py::test_cache_key_uniqueness -v` (new property-based test)
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py::test_merge_performance -v` (new performance test)
- `pytest tests/unit/d4_enrichment/ --cov=d4_enrichment --cov-report=term-missing` (coverage ≥ 80%)

## Example: D4 Coordinator Merge Fix

**Before (broken):**
```python
def merge_enrichment_data(self, existing_data, new_data):
    # Naive merge that causes duplicates
    return {**existing_data, **new_data}
```

**After (fixed):**
```python
def merge_enrichment_data(self, existing_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge enrichment data by (field, provider) with freshest collected_at.
    
    Args:
        existing_data: Previously collected enrichment data
        new_data: New enrichment data to merge
        
    Returns:
        Merged data with no duplicates, keeping freshest values
    """
    merged = {}
    
    # Combine all data items for deduplication
    all_items = []
    for field, value in existing_data.items():
        if isinstance(value, dict) and 'provider' in value and 'collected_at' in value:
            all_items.append((field, value))
    for field, value in new_data.items():
        if isinstance(value, dict) and 'provider' in value and 'collected_at' in value:
            all_items.append((field, value))
    
    # Merge by (field, provider) keeping freshest
    for field, value in all_items:
        key = (field, value['provider'])
        if key not in merged or value['collected_at'] > merged[key]['collected_at']:
            merged[key] = value
    
    # Convert back to flat structure
    result = {}
    for (field, provider), value in merged.items():
        result[field] = value
        
    return result
```

## Example: Cache Key Generation Fix

**Before (collision-prone):**
```python
def generate_cache_key(self, business_id: str) -> str:
    return f"enrichment_{business_id}"
```

**After (collision-proof):**
```python
def generate_cache_key(self, business_id: str, provider: str, timestamp: Optional[datetime] = None) -> str:
    """
    Generate unique cache key including business, provider, and time window.
    
    Args:
        business_id: Unique business identifier
        provider: Data provider name (e.g., 'google_places', 'pagespeed')
        timestamp: Optional timestamp for time-windowed caching
        
    Returns:
        Unique cache key that prevents collisions
    """
    # Ensure business_id is properly sanitized
    safe_business_id = hashlib.sha256(business_id.encode()).hexdigest()[:16]
    
    # Include provider to prevent cross-provider collisions
    safe_provider = provider.lower().replace(' ', '_')
    
    # Add time window for cache invalidation (hourly buckets)
    if timestamp is None:
        timestamp = datetime.utcnow()
    time_bucket = timestamp.strftime('%Y%m%d%H')
    
    return f"enrichment:v1:{safe_business_id}:{safe_provider}:{time_bucket}"
```

## Example: Property-Based Test for Cache Keys

```python
from hypothesis import given, strategies as st
import string

@given(
    business_id=st.text(alphabet=string.printable, min_size=1, max_size=1000),
    provider=st.sampled_from(['google_places', 'pagespeed', 'semrush', 'lighthouse']),
    timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
)
def test_cache_key_uniqueness(business_id, provider, timestamp):
    """Property-based test ensuring cache keys are unique for different inputs."""
    coordinator = D4EnrichmentCoordinator()
    
    # Generate keys for same inputs
    key1 = coordinator.generate_cache_key(business_id, provider, timestamp)
    key2 = coordinator.generate_cache_key(business_id, provider, timestamp)
    
    # Same inputs should produce same key (deterministic)
    assert key1 == key2
    
    # Different business IDs should produce different keys
    if business_id != "different_business":
        key3 = coordinator.generate_cache_key("different_business", provider, timestamp)
        assert key1 != key3
    
    # Different providers should produce different keys
    other_provider = 'lighthouse' if provider != 'lighthouse' else 'google_places'
    key4 = coordinator.generate_cache_key(business_id, other_provider, timestamp)
    assert key1 != key4
    
    # Keys should have expected format
    assert key1.startswith("enrichment:v1:")
    assert len(key1.split(':')) == 5
```

## Example: Performance Test

```python
import time
from typing import Dict, Any

def test_merge_performance():
    """Ensure merge operations remain O(n) complexity."""
    coordinator = D4EnrichmentCoordinator()
    
    # Create test data sets of increasing size
    sizes = [100, 1000, 10000]
    times = []
    
    for size in sizes:
        # Generate test data
        existing_data = {
            f"field_{i}": {
                "value": f"value_{i}",
                "provider": "google_places",
                "collected_at": datetime.utcnow() - timedelta(hours=1)
            }
            for i in range(size)
        }
        
        new_data = {
            f"field_{i}": {
                "value": f"new_value_{i}",
                "provider": "google_places",
                "collected_at": datetime.utcnow()
            }
            for i in range(size // 2, size + size // 2)
        }
        
        # Measure merge time
        start_time = time.time()
        result = coordinator.merge_enrichment_data(existing_data, new_data)
        end_time = time.time()
        
        times.append(end_time - start_time)
        
        # Verify correctness
        assert len(result) == size + size // 2  # Union of both sets
    
    # Check that time complexity is roughly linear
    # Time should increase linearly with size (allowing 2x variance)
    ratio1 = times[1] / times[0]  # 1000 vs 100
    ratio2 = times[2] / times[1]  # 10000 vs 1000
    
    # Both ratios should be roughly 10x (the size increase)
    assert 5 <= ratio1 <= 20, f"Performance degradation detected: {ratio1}x for 10x size increase"
    assert 5 <= ratio2 <= 20, f"Performance degradation detected: {ratio2}x for 10x size increase"
```

## Reference Documentation
- `tests/unit/d4_enrichment/test_d4_coordinator.py` - Existing test file
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/) - Property-based testing
- [Python Performance Testing](https://docs.python.org/3/library/timeit.html) - Performance measurement

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development
- Install hypothesis for property-based testing: `pip install hypothesis`

### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)
5. Add comprehensive unit tests for merge_enrichment_data
6. Implement property-based test for cache key uniqueness
7. Add performance test to ensure O(n) complexity

### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased (must be ≥ 80%)
- Run property-based tests with multiple seeds: `pytest tests/unit/d4_enrichment/test_d4_coordinator.py::test_cache_key_uniqueness --hypothesis-seed=0`

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-001): Fix D4 Coordinator merge logic and cache key generation`

## Validation Commands
```bash
# Run task-specific tests
pytest tests/unit/d4_enrichment/test_d4_coordinator.py -v

# Run coverage check
pytest tests/unit/d4_enrichment/ --cov=d4_enrichment --cov-report=term-missing --cov-fail-under=80

# Run property-based tests with extended examples
pytest tests/unit/d4_enrichment/test_d4_coordinator.py::test_cache_key_uniqueness --hypothesis-seed=0 --hypothesis-verbosity=verbose

# Run performance test
pytest tests/unit/d4_enrichment/test_d4_coordinator.py::test_merge_performance -v

# Run standard validation
bash scripts/validate_wave_a.sh
```

## Pre-commit Hooks Required
```yaml
# .pre-commit-config.yaml additions
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        files: ^d4_enrichment/
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        files: ^d4_enrichment/
        args: ['--max-line-length=120']
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        files: ^d4_enrichment/
        additional_dependencies: [types-all]
```

## Rollback Strategy
**Rollback**: `git revert` to restore previous coordinator logic

## Feature Flag Requirements
No new feature flag required - this fix is unconditional.

## Security Considerations
- Cache keys use SHA256 hashing to prevent injection attacks
- No sensitive data stored in cache keys
- Time-based cache invalidation prevents stale data exposure

## Performance Requirements
- Merge operations must complete in O(n) time complexity
- Cache key generation must be < 1ms per key
- No memory leaks in merge operations
- Support merging up to 10,000 fields without degradation

## Success Criteria
- All specified tests passing (including new ones)
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained for d4_enrichment module
- CI green after push
- No performance regression
- Property-based tests pass with 1000+ examples

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