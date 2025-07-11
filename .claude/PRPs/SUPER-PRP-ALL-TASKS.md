# SUPER PRP: Combined Review Document - All Tasks

This document combines all 25 PRPs for comprehensive review before execution begins.

---

## Table of Contents

### Wave A - Stabilize (Priority P0)
- [P0-000: Prerequisites Check](#p0-000-prerequisites-check)
- [P0-001: Fix D4 Coordinator](#p0-001-fix-d4-coordinator)
- [P0-002: Wire Prefect Full Pipeline](#p0-002-wire-prefect-full-pipeline)
- [P0-003: Dockerize CI](#p0-003-dockerize-ci)
- [P0-004: Database Migrations Current](#p0-004-database-migrations-current)
- [P0-005: Environment & Stub Wiring](#p0-005-environment--stub-wiring)
- [P0-006: Green KEEP Test Suite](#p0-006-green-keep-test-suite)
- [P0-007: Health Endpoint](#p0-007-health-endpoint)
- [P0-008: Test Infrastructure Cleanup](#p0-008-test-infrastructure-cleanup)
- [P0-009: Remove Yelp Remnants](#p0-009-remove-yelp-remnants)
- [P0-010: Fix Missing Dependencies](#p0-010-fix-missing-dependencies)
- [P0-011: Deploy to VPS](#p0-011-deploy-to-vps)
- [P0-012: Postgres on VPS Container](#p0-012-postgres-on-vps-container)

### Wave B - Expand (Priority P1-P2)
- [P1-010: SEMrush Client & Metrics](#p1-010-semrush-client--metrics)
- [P1-020: Lighthouse Headless Audit](#p1-020-lighthouse-headless-audit)
- [P1-030: Visual Rubric Analyzer](#p1-030-visual-rubric-analyzer)
- [P1-040: LLM Heuristic Audit](#p1-040-llm-heuristic-audit)
- [P1-050: Gateway Cost Ledger](#p1-050-gateway-cost-ledger)
- [P1-060: Cost Guardrails](#p1-060-cost-guardrails)
- [P1-070: DataAxle Client](#p1-070-dataaxle-client)
- [P1-080: Bucket Enrichment Flow](#p1-080-bucket-enrichment-flow)
- [P2-010: Unit Economics Views](#p2-010-unit-economics-views)
- [P2-020: Unit Economics PDF Section](#p2-020-unit-economics-pdf-section)
- [P2-030: Email Personalization V2](#p2-030-email-personalization-v2)
- [P2-040: Orchestration Budget Stop](#p2-040-orchestration-budget-stop)

---

## Wave Summary

### Wave A Goals
- Fix all broken tests and get KEEP suite green
- Dockerize the application and CI pipeline
- Deploy to VPS with PostgreSQL
- Remove all deprecated code (Yelp)
- Establish solid foundation for Wave B

### Wave B Goals
- Add advanced assessment providers (SEMrush, Lighthouse, Visual Analysis)
- Implement cost tracking and guardrails
- Add unit economics reporting
- Enhanced personalization with LLM
- Production-ready cost controls

---


---

## P0-000-prerequisites-check


### Task ID: P0-000
### Wave: A

### Business Logic (Why This Matters)
Ensure any new contributor or CI runner has the minimum tool-chain before code executes.

### Overview
Ensure development environment is properly configured

### Dependencies
- None

### Outcome-Focused Acceptance Criteria
`pytest --collect-only` exits 0 inside Docker **and** a checklist in README lists required versions (Python 3.11, Docker ≥ 20, Compose ≥ 2).

#### Task-Specific Acceptance Criteria
- [ ] Document system dependencies in README
- [ ] Create setup.sh script for new developers
- [ ] Verify all requirements installable
- [ ] Database migrations run cleanly

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `.env` file creation
- Virtual environment setup
- Database initialization

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `pytest --collect-only` succeeds without errors



### Example File/Pattern
**Prerequisites & Setup**

### Reference Documentation
*No code tests* – PRP passes if `pytest --collect-only` exits 0 inside Docker.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-000): Prerequisites Check`

### Validation Commands
```bash
# Run specific tests for this task
pytest `pytest --collect-only` succeeds without errors -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Delete setup.sh if created

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-001-fix-d4-coordinator


### Task ID: P0-001
### Wave: A

### Business Logic (Why This Matters)
Accurate enrichment merge prevents stale or duplicate provider data in assessments.

### Overview
Repair enrichment coordinator merge/cache logic

### Dependencies
- P0-000

**Note**: Depends on P0-000 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`test_d4_coordinator.py` passes **and** coordinator returns freshest, deduped fields; cache key collisions across businesses impossible (property-based test).

#### Task-Specific Acceptance Criteria
- [ ] Remove xfail marker from test file
- [ ] Fix merge_enrichment_data method
- [ ] Fix cache key generation
- [ ] All 12 coordinator tests passing

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `d4_enrichment/coordinator.py`
- `d4_enrichment/models.py`

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py -v`


### Example: D4 Coordinator Merge Fix

**Before (broken):**
```python
def merge_enrichment_data(self, existing_data, new_data):
    # Naive merge that causes duplicates
    return {**existing_data, **new_data}
```

**After (fixed):**
```python
def merge_enrichment_data(self, existing_data, new_data):
    # Merge by (field, provider) with freshest collected_at
    merged = {}
    for field, value in chain(existing_data.items(), new_data.items()):
        key = (field, value['provider'])
        if key not in merged or value['collected_at'] > merged[key]['collected_at']:
            merged[key] = value
    return merged
```


### Example File/Pattern
**Fix D4 Coordinator**

### Reference Documentation
`tests/unit/d4_enrichment/test_d4_coordinator.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-001): Fix D4 Coordinator`

### Validation Commands
```bash
# Run specific tests for this task
pytest `pytest tests/unit/d4_enrichment/test_d4_coordinator.py -v` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: `git revert` to restore previous coordinator logic

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-002-wire-prefect-full-pipeline


### Task ID: P0-002
### Wave: A

### Business Logic (Why This Matters)
One orchestrated flow proves the entire MVP works end-to-end.

### Overview
Create end-to-end orchestration flow

### Dependencies
- P0-001

**Note**: Depends on P0-001 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`smoke/test_full_pipeline_flow.py` generates PDF + email + DB rows for a sample URL within 90 s runtime.

#### Task-Specific Acceptance Criteria
- [ ] Flow chains: Target → Source → Assess → Score → Report → Deliver
- [ ] Error handling with retries
- [ ] Metrics logged at each stage
- [ ] Integration test creates PDF and email record

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `flows/full_pipeline_flow.py`
- Import all coordinator classes
- Wire sequential flow with error handling

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- New: `tests/smoke/test_full_pipeline_flow.py`
- Must process a business from targeting through delivery


### Example: Prefect Pipeline Flow

```python
from prefect import flow, task

@flow(name="full_pipeline")
def full_pipeline_flow(url: str):
    business = target_business(url)
    assessment = assess_website(business)
    score = calculate_score(assessment)
    report = generate_report(score)
    send_email(report)
    return {"status": "complete", "report_id": report.id}
```


### Example File/Pattern
**Prefect full-pipeline flow**

### Reference Documentation
`tests/smoke/test_full_pipeline_flow.py` *(new)* — asserts JSON contains `"score"` and a PDF path.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-002): Wire Prefect Full Pipeline`

### Validation Commands
```bash
# Run specific tests for this task
pytest New: `tests/smoke/test_full_pipeline_flow.py` Must process a business from targeting through delivery -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Delete flows/full_pipeline_flow.py

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-003-dockerize-ci


### Task ID: P0-003
### Wave: A

### Business Logic (Why This Matters)
"Works on my machine" disparities disappear when tests always run in the same image.

### Overview
Create working Docker test environment

### Dependencies
- P0-002

**Note**: Depends on P0-002 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
GitHub Actions logs show image build, KEEP suite green, coverage ≥ 80%, image pushed to GHCR.

#### Task-Specific Acceptance Criteria
- [ ] Multi-stage Dockerfile with test target
- [ ] All Python dependencies installed
- [ ] Postgres service in docker-compose.test.yml
- [ ] Stub server accessible from container
- [ ] CI builds and runs tests in container

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `Dockerfile.test`
- Update `.dockerignore`
- Update `.github/workflows/test.yml`

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `docker build -f Dockerfile.test -t leadfactory-test .` succeeds
- `docker run leadfactory-test pytest -q` shows 0 failures
- Entire KEEP suite must pass inside the Docker image


### Example: Dockerfile.test for CI

```dockerfile
# Multi-stage build for test environment
FROM python:3.11.0-slim as test

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .

# Run tests as default command
CMD ["pytest", "-m", "not slow and not phase_future", "--tb=short"]
```


### Example File/Pattern
**Dockerised CI**

### Reference Documentation
Entire KEEP suite must pass **inside** the Docker image.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-003): Dockerize CI`

### Validation Commands
```bash
# Run specific tests for this task
pytest `docker build -f Dockerfile.test -t leadfactory-test .` succeeds `docker run leadfactory-test pytest -q` shows 0 failures Entire KEEP suite must pass inside the Docker image -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")

# Docker/deployment specific validation
docker build -f Dockerfile.test -t leadfactory-test .
```

### Rollback Strategy
**Rollback**: Remove Dockerfile.test and revert CI workflow

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-004-database-migrations-current


### Task ID: P0-004
### Wave: A

### Business Logic (Why This Matters)
Schema drift breaks runtime and Alembic autogenerate.

### Overview
Ensure schema matches models

### Dependencies
- P0-003

**Note**: Depends on P0-003 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`alembic upgrade head` + autogen diff both return no changes on CI; downgrade path tested for latest revision.

#### Task-Specific Acceptance Criteria
- [ ] All model changes captured in migrations
- [ ] No duplicate migrations
- [ ] Migrations run in correct order
- [ ] Rollback tested for each migration

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `alembic/versions/`
- All model files in `*/models.py`

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `alembic upgrade head` runs cleanly
- `alembic check` shows no pending changes
- New: `tests/unit/test_migrations.py` - runs alembic upgrade and asserts autogenerate diff is empty


### Example: Migration Validation Test

```python
def test_migrations_current():
    """Ensure no pending migrations"""
    # Run upgrade to head
    alembic_cfg = Config("alembic.ini")
    upgrade(alembic_cfg, "head")
    
    # Check for model changes
    context = MigrationContext.configure(connection)
    diff = compare_metadata(context, target_metadata)
    
    assert len(diff) == 0, f"Uncommitted changes: {diff}"
```


### Example File/Pattern
**Alembic migrations up-to-date**

### Reference Documentation
`tests/unit/test_migrations.py` *(new)* — runs `alembic upgrade head` and asserts autogenerate diff is empty.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-004): Database Migrations Current`

### Validation Commands
```bash
# Run specific tests for this task
pytest `alembic upgrade head` runs cleanly `alembic check` shows no pending changes New: `tests/unit/test_migrations.py` - runs alembic upgrade and asserts autogenerate diff is empty -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")

# Docker/deployment specific validation
docker build -f Dockerfile.test -t leadfactory-test .
```

### Rollback Strategy
**Rollback**: Use `alembic downgrade` to previous revision

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-005-environment-stub-wiring


### Task ID: P0-005
### Wave: A

### Business Logic (Why This Matters)
Tests must never hit paid APIs; prod must never run with stubs.

### Overview
Proper test/prod environment separation

### Dependencies
- P0-004

**Note**: Depends on P0-004 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Running tests with `USE_STUBS=true` yields 0 external calls (network mocked); prod env rejects `USE_STUBS=true` at startup.

#### Task-Specific Acceptance Criteria
- [ ] Stub server auto-starts in tests
- [ ] Environment variables documented
- [ ] Secrets never logged
- [ ] Feature flags for each provider

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `core/config.py`
- `stubs/server.py`
- All test fixtures

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- All tests pass with `USE_STUBS=true`
- No real API calls in test suite
- `tests/integration/test_stub_server.py` passes


### Example: Stub Detection in Tests

```python
# In conftest.py
@pytest.fixture(autouse=True)
def enforce_stubs(monkeypatch):
    """Ensure tests never hit real APIs"""
    if os.getenv("USE_STUBS") == "true":
        monkeypatch.setattr("requests.get", mock_requests_get)
        monkeypatch.setattr("requests.post", mock_requests_post)
```


### Example File/Pattern
**Stub-server wiring**

### Reference Documentation
`tests/integration/test_stub_server.py` passes with `USE_STUBS=true`.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-005): Environment & Stub Wiring`

### Validation Commands
```bash
# Run specific tests for this task
pytest All tests pass with `USE_STUBS=true` No real API calls in test suite `tests/integration/test_stub_server.py` passes -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Revert config.py changes

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-006-green-keep-test-suite


### Task ID: P0-006
### Wave: A

### Business Logic (Why This Matters)
A green baseline proves core logic is stable for further work.

### Overview
All core tests passing

### Dependencies
- P0-005

**Note**: Depends on P0-005 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`pytest -m "not phase_future and not slow"` exits 0 in < 5 min on CI.

#### Task-Specific Acceptance Criteria
- [ ] 0 test failures
- [ ] 0 error collections
- [ ] <5 minute total runtime
- [ ] Coverage >80% on core modules (Wave A target)

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- 60 test files marked as KEEP
- Remove/fix all xfail markers

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- New: `tests/test_marker_policy.py` - collects tests and asserts no un-marked failures



### Example File/Pattern
**KEEP / phase_future gating**

### Reference Documentation
`tests/test_marker_policy.py` *(new)* — collects tests and asserts no un-marked reds.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-006): Green KEEP Test Suite`

### Validation Commands
```bash
# Run specific tests for this task
pytest New: `tests/test_marker_policy.py` - collects tests and asserts no un-marked failures -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Re-add xfail markers to unblock CI

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-007-health-endpoint


### Task ID: P0-007
### Wave: A

### Business Logic (Why This Matters)
External uptime monitors need a single, fast status route.

### Overview
Production monitoring endpoint

### Dependencies
- P0-006

**Note**: Depends on P0-006 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`/health` returns JSON `{status:"ok"}` plus DB connectivity ≤ 100 ms; monitored in deploy workflow.

#### Task-Specific Acceptance Criteria
- [ ] Returns 200 with JSON status
- [ ] Checks database connectivity
- [ ] Checks Redis connectivity
- [ ] Returns version info
- [ ] <100ms response time

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `api/health.py`
- Main FastAPI app

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/test_health_endpoint.py`
- Deploy workflow health check
- Already covered in P0-004 smoke test


### Example: Health Endpoint Implementation

```python
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        # Check DB connectivity
        db.execute("SELECT 1")
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.VERSION,
            "database": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )
```


### Example File/Pattern
**/health endpoint**

### Reference Documentation
`tests/unit/test_health_endpoint.py` and smoke test in `tests/smoke/test_health.py` *(new)*.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-007): Health Endpoint`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/test_health_endpoint.py` Deploy workflow health check Already covered in P0-004 smoke test -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Remove /health route from API

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-008-test-infrastructure-cleanup


### Task ID: P0-008
### Wave: A

### Business Logic (Why This Matters)
Slow or mis-marked tests waste CI minutes and confuse signal.

### Overview
Fix test discovery and marking issues

### Dependencies
- P0-007

**Note**: Depends on P0-007 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Collect phase shows correct counts; `pytest -m slow` runs 0 tests in CI; import errors in ignored files eliminated.

#### Task-Specific Acceptance Criteria
- [ ] Phase 0.5 tests auto-marked as xfail
- [ ] Slow tests excluded from PR builds
- [ ] Import errors in ignored files fixed
- [ ] Test collection time <5 seconds

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `conftest.py`
- `pytest.ini`
- CI workflow files

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `pytest --collect-only` shows correct test counts
- CI runs in <10 minutes
- `pytest -m "slow" -q` runs zero slow tests in CI



### Example File/Pattern
**Test infrastructure cleanup**

### Reference Documentation
`pytest -m "slow" -q` runs **zero** slow tests in CI; import errors in ignored files are gone.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-008): Test Infrastructure Cleanup`

### Validation Commands
```bash
# Run specific tests for this task
pytest `pytest --collect-only` shows correct test counts CI runs in <10 minutes `pytest -m "slow" -q` runs zero slow tests in CI -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Revert conftest.py and pytest.ini changes

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-009-remove-yelp-remnants


### Task ID: P0-009
### Wave: A

### Business Logic (Why This Matters)
Stray Yelp code causes dead imports and schema noise.

### Overview
Complete Yelp provider removal

### Dependencies
- P0-008

**Note**: Depends on P0-008 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`git grep -i yelp` finds only comments/docs; migration drops last Yelp columns; stub server has no `/yelp/*` routes.

#### Task-Specific Acceptance Criteria
- [ ] No Yelp imports in codebase
- [ ] Migrations to drop Yelp columns
- [ ] Documentation updated
- [ ] Stub server Yelp routes removed

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Any remaining Yelp imports
- Database columns mentioning Yelp
- Stub server endpoints

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `grep -r "yelp" --include="*.py" .` returns only comments
- New: `tests/test_yelp_purge.py` - verifies no active Yelp code


### Example: Yelp Removal Check

```bash
# Before: Yelp references found
$ git grep -i yelp | wc -l
47

# After: Only docs/comments remain
$ git grep -i yelp
CHANGELOG.md:- Removed Yelp provider (July 2025)
docs/history.md:Original design included Yelp integration
```


### Example File/Pattern
**Remove Yelp remnants**

### Reference Documentation
`git grep -i yelp` returns 0 active-code hits inside `tests/test_yelp_purge.py` *(new)*.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-009): Remove Yelp Remnants`

### Validation Commands
```bash
# Run specific tests for this task
pytest `grep -r "yelp" --include="*.py" .` returns only comments New: `tests/test_yelp_purge.py` - verifies no active Yelp code -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Not applicable - Yelp already removed

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-010-fix-missing-dependencies


### Task ID: P0-010
### Wave: A

### Business Logic (Why This Matters)
Fresh clone + install must succeed for new devs and CI.

### Overview
Align local and CI environments

### Dependencies
- P0-009

**Note**: Depends on P0-009 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`pip install -r requirements.txt` succeeds in clean venv; `pip check` green; version pins documented.

#### Task-Specific Acceptance Criteria
- [ ] All imports resolve correctly
- [ ] Version pins for all packages
- [ ] No conflicting dependencies
- [ ] CI cache working properly

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- `requirements.txt`
- `requirements-dev.txt`
- CI cache configuration

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- Fresh virtualenv install works
- CI and local tests have same results
- CI green on a fresh Docker build
- `pip check` passes in CI



### Example File/Pattern
**Fix missing dependencies**

### Reference Documentation
CI green on a fresh Docker build; `requirements.txt` contains all imports (checked by `pip-check` step in CI).

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-010): Fix Missing Dependencies`

### Validation Commands
```bash
# Run specific tests for this task
pytest Fresh virtualenv install works CI and local tests have same results CI green on a fresh Docker build `pip check` passes in CI -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Restore previous requirements.txt

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-011-deploy-to-vps


### Task ID: P0-011
### Wave: A

### Business Logic (Why This Matters)
Automated prod deploy removes human error and provides rollback point.

### Overview
Automated deployment pipeline

### Dependencies
- P0-010

**Note**: Depends on P0-010 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
GH Actions deploy job completes; container responds 200 on `/health`; restart policy is `always`; SSH key auth works.

#### Task-Specific Acceptance Criteria
- [ ] GHCR image pushed on main branch
- [ ] SSH key authentication working
- [ ] Docker installed on VPS if missing
- [ ] Container runs with restart policy
- [ ] Nginx reverse proxy configured

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `.github/workflows/deploy.yml`
- Add production Dockerfile
- Configure GitHub secrets

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- Deployment workflow runs without errors
- `curl https://vps-ip/health` returns 200
- New: `tests/smoke/test_health.py` passes



### Example File/Pattern
**Automated VPS deploy**

### Reference Documentation
`deploy_vps.yml` workflow completes & `/health` endpoint test returns 200.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-011): Deploy to VPS`

### Validation Commands
```bash
# Run specific tests for this task
pytest Deployment workflow runs without errors `curl https://vps-ip/health` returns 200 New: `tests/smoke/test_health.py` passes -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")

# Docker/deployment specific validation
docker build -f Dockerfile.test -t leadfactory-test .
```

### Rollback Strategy
**Rollback**: Delete deploy.yml workflow

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P0-012-postgres-on-vps-container


### Task ID: P0-012
### Wave: A

### Business Logic (Why This Matters)
Local DB on VPS avoids external dependency while you evaluate Supabase.

### Overview
Database container with persistent storage

### Dependencies
- P0-011

**Note**: Depends on P0-011 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Postgres service starts with named volume; app connects; `alembic upgrade head` runs during deploy; data survives container restart.

#### Task-Specific Acceptance Criteria
- [ ] Deploy workflow pulls postgres:15 image
- [ ] Database runs with named volume for persistence
- [ ] App uses DATABASE_URL=postgresql://lf:strongpassword@db/leadfactory
- [ ] Migrations run after database is ready
- [ ] Database backup strategy documented

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Extend `.github/workflows/deploy.yml`
- Docker network for app-db communication
- Named volume for data persistence

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- Database container runs with named volume
- App container connects successfully
- `alembic upgrade head` completes in deployment



### Example File/Pattern
**Postgres on VPS Container**

### Reference Documentation
Database container runs with volume; `alembic upgrade head` completes in deployment.

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-012): Postgres on VPS Container`

### Validation Commands
```bash
# Run specific tests for this task
pytest Database container runs with named volume App container connects successfully `alembic upgrade head` completes in deployment -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")

# Docker/deployment specific validation
docker build -f Dockerfile.test -t leadfactory-test .
```

### Rollback Strategy
**Rollback**: Stop postgres container, keep volume for data recovery

### Feature Flag Requirements
No new feature flag required - this fix is unconditional.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-010-semrush-client-metrics


### Task ID: P1-010
### Wave: B

### Business Logic (Why This Matters)
SEO snapshot is a client-value driver and upsell hook.

### Overview
Add SEMrush provider with 6 key metrics

### Dependencies
- All P0-*

**Note**: Depends on All P0-* completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Stubbed unit tests pass; live smoke test fetches all six metrics; metrics appear in PDF section "SEO Snapshot".

#### Task-Specific Acceptance Criteria
- [ ] Client extends BaseAPIClient
- [ ] Cost tracking: $0.10 per API call
- [ ] Rate limit: 10 requests/second
- [ ] Stub responses for all endpoints
- [ ] Metrics appear in PDF report

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `d0_gateway/providers/semrush.py`
- Update `d0_gateway/factory.py`
- Add to assessment coordinator

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d0_gateway/test_semrush_client.py`
- `tests/smoke/test_smoke_semrush.py` (with API key)



### Example File/Pattern
SEMrush client & metrics

### Reference Documentation
`tests/unit/d0_gateway/test_semrush_client.py` (stub)

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-010): SEMrush Client & Metrics`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d0_gateway/test_semrush_client.py` `tests/smoke/test_smoke_semrush.py` (with API key) -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Feature flag ENABLE_SEMRUSH=false

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-020-lighthouse-headless-audit


### Task ID: P1-020
### Wave: B

### Business Logic (Why This Matters)
Core Web Vitals & accessibility scores are industry benchmarks demanded by prospects.

### Overview
Browser-based performance testing

### Dependencies
- P1-010

**Note**: Depends on P1-010 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Headless run completes ≤ 30 s; returns 5 scores; cached 7 days; results populate assessment row and PDF.

#### Task-Specific Acceptance Criteria
- [ ] Runs headless Chrome via Playwright
- [ ] 30-second timeout per audit
- [ ] Caches results for 7 days
- [ ] Falls back gracefully on timeout
- [ ] Detailed metrics in JSON format

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `d3_assessment/lighthouse.py`
- Add Playwright to requirements
- Update assessment coordinator

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d3_assessment/test_lighthouse.py`
- `tests/integration/test_lighthouse_integration.py`
- `tests/unit/d4_enrichment/test_lighthouse_runner.py`



### Example File/Pattern
Lighthouse headless audit

### Reference Documentation
`tests/unit/d4_enrichment/test_lighthouse_runner.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-020): Lighthouse Headless Audit`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d3_assessment/test_lighthouse.py` `tests/integration/test_lighthouse_integration.py` `tests/unit/d4_enrichment/test_lighthouse_runner.py` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Remove lighthouse.py and uninstall Playwright

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-030-visual-rubric-analyzer


### Task ID: P1-030
### Wave: B

### Business Logic (Why This Matters)
Visual trust cues correlate with conversion; automated scoring yields scalable insights.

### Overview
Score visual design quality (1-9 scale)

### Dependencies
- P1-020

**Note**: Depends on P1-020 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Screenshot captured; 9 rubric scores (0-100) persisted; PDF shows coloured bar chart per dimension.

#### Task-Specific Acceptance Criteria
- [ ] Screenshot capture via API
- [ ] OpenAI Vision API scoring
- [ ] Deterministic stub for tests
- [ ] Scores persist to database
- [ ] Visual report section in PDF

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `d3_assessment/visual_analyzer.py`
- Integrate ScreenshotOne API
- Store scores in assessment model

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d3_assessment/test_visual_analyzer.py`
- `tests/unit/d3_assessment/test_visual_rubric.py`
- Visual regression tests



### Example File/Pattern
Visual rubric analyser

### Reference Documentation
`tests/unit/d3_assessment/test_visual_rubric.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-030): Visual Rubric Analyzer`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d3_assessment/test_visual_analyzer.py` `tests/unit/d3_assessment/test_visual_rubric.py` Visual regression tests -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Feature flag ENABLE_VISUAL_ANALYSIS=false

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-040-llm-heuristic-audit


### Task ID: P1-040
### Wave: B

### Business Logic (Why This Matters)
Narrative feedback differentiates the report and feeds email personalisation.

### Overview
GPT-4 powered content analysis

### Dependencies
- P1-030

**Note**: Depends on P1-030 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
For a given URL stub, audit returns 7 structured fields; JSON matches schema; costs logged in ledger.

#### Task-Specific Acceptance Criteria
- [ ] Structured prompt template
- [ ] JSON response parsing
- [ ] Cost: ~$0.03 per audit
- [ ] Timeout handling
- [ ] Metrics in assessment record

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `d3_assessment/llm_audit.py`
- Extend LLM insights module
- Add audit results model

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d3_assessment/test_llm_audit.py`
- `tests/unit/d3_assessment/test_llm_heuristic.py`
- Deterministic stub responses



### Example File/Pattern
LLM heuristic audit

### Reference Documentation
`tests/unit/d3_assessment/test_llm_heuristic.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-040): LLM Heuristic Audit`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d3_assessment/test_llm_audit.py` `tests/unit/d3_assessment/test_llm_heuristic.py` Deterministic stub responses -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Feature flag ENABLE_LLM_AUDIT=false

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-050-gateway-cost-ledger


### Task ID: P1-050
### Wave: B

### Business Logic (Why This Matters)
Without per-call cost tracking you cannot manage profit or guardrails.

### Overview
Track all external API costs

### Dependencies
- P1-040

**Note**: Depends on P1-040 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Every external API request inserts a ledger row with `cost_usd`; daily aggregation view returns non-NULL totals.

#### Task-Specific Acceptance Criteria
- [ ] Every API call logged
- [ ] Costs calculated per provider
- [ ] Daily aggregation views
- [ ] No performance impact
- [ ] Cleanup job for old records

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create migration for `gateway_cost_ledger` table
- Update `BaseAPIClient._make_request()`
- Add cost calculation methods

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d0_gateway/test_cost_ledger.py`
- `tests/integration/test_cost_tracking.py`


### Example: Cost Ledger Implementation

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


### Example File/Pattern
Gateway cost ledger

### Reference Documentation
`tests/unit/d0_gateway/test_cost_ledger.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-050): Gateway Cost Ledger`

### Validation Commands
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

### Rollback Strategy
**Rollback**: Drop gateway_cost_ledger table

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-060-cost-guardrails


### Task ID: P1-060
### Wave: B

### Business Logic (Why This Matters)
Prevent invoice shock and keep unit economics predictable.

### Overview
Prevent runaway API costs

### Dependencies
- P1-050

**Note**: Depends on P1-050 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Flow halts when simulated spend > cap; Slack (or log) warning emitted; admin override flag tested.

#### Task-Specific Acceptance Criteria
- [ ] Soft limits log warnings
- [ ] Hard limits halt execution
- [ ] Admin override capability
- [ ] Slack notifications
- [ ] Costs reset at midnight UTC

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `d11_orchestration/guardrails.py`
- Update Prefect flows
- Add config for limits

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d11_orchestration/test_cost_guardrails.py`
- `tests/integration/test_guardrail_integration.py`



### Example File/Pattern
Cost guardrails

### Reference Documentation
`tests/unit/d11_orchestration/test_cost_guardrails.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-060): Cost Guardrails`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d11_orchestration/test_cost_guardrails.py` `tests/integration/test_guardrail_integration.py` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Set all guardrail limits to None

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-070-dataaxle-client


### Task ID: P1-070
### Wave: B

### Business Logic (Why This Matters)
Purchased enrichment fills firmographic gaps essential for lead resale.

### Overview
Business data enrichment provider

### Dependencies
- P1-060

**Note**: Depends on P1-060 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Stub test passes; live smoke returns ≥ 10 firmographic fields; enrichment merged into business record.

#### Task-Specific Acceptance Criteria
- [ ] OAuth2 authentication
- [ ] Rate limit: 3000/hour
- [ ] Cost: $0.10 per record
- [ ] 15+ data fields returned
- [ ] Match confidence scoring

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `d0_gateway/providers/dataaxle.py`
- Update factory registration
- Add to enrichment flow

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d0_gateway/test_dataaxle_client.py`
- `tests/smoke/test_smoke_dataaxle.py`



### Example File/Pattern
Data provider client (DataAxle/TBD)

### Reference Documentation
`tests/unit/d0_gateway/test_dataaxle_client.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-070): DataAxle Client`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d0_gateway/test_dataaxle_client.py` `tests/smoke/test_smoke_dataaxle.py` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Feature flag ENABLE_DATAAXLE=false

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P1-080-bucket-enrichment-flow


### Task ID: P1-080
### Wave: B

### Business Logic (Why This Matters)
Processing by vertical maximises ROI under budget caps.

### Overview
Process businesses by industry segment

### Dependencies
- P1-070

**Note**: Depends on P1-070 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
Prefect schedule runs; summary email lists processed counts per bucket; respects guardrails.

#### Task-Specific Acceptance Criteria
- [ ] Runs nightly at 2 AM UTC
- [ ] Respects cost guardrails
- [ ] Processes highest-value first
- [ ] Emails summary report
- [ ] Handles partial failures

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create `flows/bucket_enrichment_flow.py`
- Add scheduling to Prefect
- Update targeting models

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d11_orchestration/test_bucket_flow.py`
- `tests/integration/test_bucket_enrichment.py`
- `tests/integration/test_bucket_enrichment_flow.py`



### Example File/Pattern
Bucket enrichment flow

### Reference Documentation
`tests/integration/test_bucket_enrichment_flow.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P1-080): Bucket Enrichment Flow`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d11_orchestration/test_bucket_flow.py` `tests/integration/test_bucket_enrichment.py` `tests/integration/test_bucket_enrichment_flow.py` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Disable Prefect schedule

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P2-010-unit-economics-views


### Task ID: P2-010
### Wave: B

### Business Logic (Why This Matters)
Transparency on CPL/CAC drives pricing and spend decisions.

### Overview
Cost/revenue analytics API

### Dependencies
- All P1-*

**Note**: Depends on All P1-* completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
`/analytics/unit_econ?date=…` returns CPL, CAC, ROI; SQL view tested; response cached 24 h.

#### Task-Specific Acceptance Criteria
- [ ] Read-only endpoints
- [ ] 24-hour cache
- [ ] JSON and CSV export
- [ ] Date range filtering
- [ ] Cohort analysis support

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Create SQL views in migration
- Add `api/analytics.py` endpoints
- Create analytics models

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d10_analytics/test_unit_economics.py`
- `tests/unit/d10_analytics/test_unit_econ_views.py`
- `tests/integration/test_analytics_api.py`



### Example File/Pattern
Unit-economics views & API

### Reference Documentation
`tests/unit/d10_analytics/test_unit_econ_views.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P2-010): Unit Economics Views`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d10_analytics/test_unit_economics.py` `tests/unit/d10_analytics/test_unit_econ_views.py` `tests/integration/test_analytics_api.py` -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Drop unit economics views

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P2-020-unit-economics-pdf-section


### Task ID: P2-020
### Wave: B

### Business Logic (Why This Matters)
Buyers want a visually digestible cost story.

### Overview
Add cost insights to reports

### Dependencies
- P2-010

**Note**: Depends on P2-010 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
New 2-page section renders pie, bar, gauge charts; PDF snapshot test diff < 2%.

#### Task-Specific Acceptance Criteria
- [ ] New 2-page section
- [ ] Charts render correctly
- [ ] Conditional display logic
- [ ] Mobile-friendly layout
- [ ] Data freshness indicator

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Update PDF template
- Add cost data to context
- Create visualization charts

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d6_reports/test_economics_section.py`
- `tests/unit/d6_reports/test_pdf_unit_econ_section.py`
- PDF snapshot tests



### Example File/Pattern
Unit-economics PDF section

### Reference Documentation
`tests/unit/d6_reports/test_pdf_unit_econ_section.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P2-020): Unit Economics PDF Section`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d6_reports/test_economics_section.py` `tests/unit/d6_reports/test_pdf_unit_econ_section.py` PDF snapshot tests -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Remove economics section from PDF template

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P2-030-email-personalization-v2


### Task ID: P2-030
### Wave: B

### Business Logic (Why This Matters)
Higher personalisation lifts open & click rates.

### Overview
LLM-powered email content

### Dependencies
- P2-020

**Note**: Depends on P2-020 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
For sample lead, builder returns 5 subjects / 3 bodies with placeholders filled; deterministic stub for tests; live emails sent in SendGrid sandbox.

#### Task-Specific Acceptance Criteria
- [ ] 5 subject line variants
- [ ] 3 body copy variants
- [ ] Deterministic test mode
- [ ] Preview in admin UI
- [ ] Click tracking enabled

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Update `d8_personalization/generator.py`
- Create new email templates
- Add A/B test variants

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/unit/d8_personalization/test_llm_personalization.py`
- `tests/unit/d9_delivery/test_email_personalisation_v2.py`
- Email rendering tests



### Example File/Pattern
Email personalisation V2

### Reference Documentation
`tests/unit/d9_delivery/test_email_personalisation_v2.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P2-030): Email Personalization V2`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/unit/d8_personalization/test_llm_personalization.py` `tests/unit/d9_delivery/test_email_personalisation_v2.py` Email rendering tests -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Revert to V1 email templates

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## P2-040-orchestration-budget-stop


### Task ID: P2-040
### Wave: B

### Business Logic (Why This Matters)
Monthly burn must not exceed planned spend.

### Overview
Monthly spend circuit breaker

### Dependencies
- P2-030

**Note**: Depends on P2-030 completing successfully in the same CI run.

### Outcome-Focused Acceptance Criteria
When ledger total > monthly cap, all flows transition to `Failed` with custom message; auto-resume next month verified.

#### Task-Specific Acceptance Criteria
- [ ] Graceful flow shutdown
- [ ] State preserved for resume
- [ ] Email notifications
- [ ] Auto-resume next month
- [ ] Override requires 2FA

#### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

### Integration Points
- Add to all Prefect flows
- Create admin override UI
- Add monitoring alerts

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `tests/integration/test_budget_stop.py`
- Flow halt verification



### Example File/Pattern
Orchestration budget-stop

### Reference Documentation
`tests/integration/test_budget_stop.py`

### Implementation Guide

#### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

#### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

#### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

#### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

#### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P2-040): Orchestration Budget Stop`

### Validation Commands
```bash
# Run specific tests for this task
pytest `tests/integration/test_budget_stop.py` Flow halt verification -xvs

# Verify no existing tests broken
pytest -m "not phase_future and not slow" -q

# Check coverage meets Wave A requirement
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Lint-level compile check
python -m py_compile $(git ls-files "*.py")
```

### Rollback Strategy
**Rollback**: Remove budget stop decorator from flows

### Feature Flag Requirements
Feature flag required: See integration points for flag name.

### Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

---

## Shared Context (Applies to All Tasks)

### Critical Success Factors
1. **Wave Separation**: All P0 tasks must complete before any P1/P2 tasks begin
2. **Coverage Requirements**: Maintain >80% coverage throughout Wave A, target >95% in Wave B
3. **Docker Consistency**: All tests must pass in Docker containers, not just locally
4. **No Scope Creep**: Only modify files within specified integration points
5. **Documentation**: Update README and docs for any behavior changes

### Common Validation Commands
```bash
# Standard validation suite for all tasks
pytest -m "not phase_future and not slow" -q  # KEEP suite
coverage run -m pytest tests/unit              # Coverage check
coverage report --fail-under=80                # Wave A minimum
python -m py_compile $(git ls-files "*.py")   # Syntax check
```

### DO NOT IMPLEMENT (From CURRENT_STATE.md)
- **Yelp Integration**: All Yelp-related code/tests/migrations
- **Mac Mini Deployment**: Use VPS + Docker only
- **Top 10% Filtering**: Analyze 100% of purchased data
- **$199 Pricing**: Use $399 launch price
- **Simple Email Templates**: Use LLM-powered personalization
- **Basic scoring only**: Implement full multi-metric assessment

### Environment Setup (All Tasks)
- Python 3.11.0 (exact version for CI compatibility)
- Docker 20.10+ for containerization
- `USE_STUBS=true` for local development
- Virtual environment activation required
- All sensitive data in `.env` file

---

**Note**: The full CLAUDE.md and CURRENT_STATE.md content has been removed from individual PRPs above to reduce redundancy. These documents should be reviewed separately and apply to all tasks.
