# SUPER PRP: Combined Review Document - All Tasks (FIXED)

**IMPORTANT ORCHESTRATOR RULES**:
1. **Linear Execution Only**: Process PRPs strictly in the order listed below. No parallelism.
2. **Failure Protocol**: On test failure → run rollback strategy → halt execution → alert via logs
3. **Human Review Required**: Tasks marked with `## HUMAN REVIEW REQUIRED` need manual approval before proceeding
4. **Environment Safety**: Deploy workflow MUST fail if `USE_STUBS=true` in production

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
- [P0-012: Postgres on VPS Container](#p0-012-postgres-on-vps-container) ⚠️ HUMAN REVIEW

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
- [P2-040: Orchestration Budget Stop](#p2-040-orchestration-budget-stop) ⚠️ HUMAN REVIEW

---

## Wave Summary

### Wave A Goals
- Fix all broken tests and get KEEP suite green
- Dockerize the application and CI pipeline
- Deploy to VPS with PostgreSQL
- Remove all deprecated code (Yelp)
- Establish solid foundation for Wave B
- **Coverage Target**: 80%

### Wave B Goals
- Add advanced assessment providers (SEMrush, Lighthouse, Visual Analysis)
- Implement cost tracking and guardrails
- Add unit economics reporting
- Enhanced personalization with LLM
- Production-ready cost controls
- **Coverage Target**: 95%

---

## P0-000: Prerequisites Check

### Business Logic (Why This Matters)
Ensure any new contributor or CI runner has the minimum tool-chain before code executes.

### Outcome-Focused Acceptance Criteria
- [ ] `pytest --collect-only` exits 0 inside Docker
- [ ] README lists required versions (Python 3.11, Docker ≥ 20, Compose ≥ 2)
- [ ] setup.sh script enables one-command developer onboarding
- [ ] All requirements installable in fresh virtualenv
- [ ] Database migrations run cleanly from scratch

### Integration Points
- `.env` file creation
- Virtual environment setup
- Database initialization

**Critical Path**: May create new files under `tests/**`, `docs/**`; may edit only files in integration points.

### Tests to Pass
- `pytest --collect-only` succeeds without errors
- `python -m py_compile $(git ls-files "*.py")` has no syntax errors
- `docker --version` shows 20.10+
- `docker-compose --version` shows 2.0+

### Implementation Example
```bash
# setup.sh content
#!/bin/bash
set -e

echo "Setting up LeadFactory development environment..."

# Check Python version
python3 --version | grep -q "3.11" || echo "WARNING: Python 3.11 required"

# Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Setup database
alembic upgrade head

# Create .env from example
cp .env.example .env

echo "Setup complete! Run 'source venv/bin/activate' to start"
```

### Validation Commands
```bash
# Run pytest collection test
pytest --collect-only

# Verify setup script works
bash setup.sh

# Check all dependencies
pip check
```

### Rollback Strategy
Delete setup.sh if created

### Feature Flag
No feature flag required - foundational task

---

## P0-001: Fix D4 Coordinator

### Business Logic (Why This Matters)
Accurate enrichment merge prevents stale or duplicate provider data in assessments.

### Outcome-Focused Acceptance Criteria
- [ ] `test_d4_coordinator.py` passes with 0 failures
- [ ] Coordinator returns freshest data by collected_at timestamp
- [ ] Cache key collisions across businesses impossible
- [ ] Merge operations remain O(n) complexity
- [ ] No duplicate (field, provider) pairs in output

### Integration Points
- `d4_enrichment/coordinator.py`
- `d4_enrichment/models.py`

**Critical Path**: May create new files under `tests/**`, `docs/**`; may edit only files in integration points.

### Tests to Pass
- `tests/unit/d4_enrichment/test_d4_coordinator.py`

### Implementation Example
```python
# Fixed merge logic - illustrative only, do not copy verbatim
def merge_enrichment_data(self, existing_data, new_data):
    """Merge by (field, provider) with freshest collected_at"""
    merged = {}
    
    # Process all data points
    all_items = []
    for data in [existing_data, new_data]:
        for field, value in data.items():
            all_items.append((field, value))
    
    # Keep only freshest by (field, provider)
    for field, value in all_items:
        key = (field, value.get('provider'))
        if key not in merged or value['collected_at'] > merged[key]['collected_at']:
            merged[key] = value
    
    # Return as field->value dict
    return {field: value for (field, _), value in merged.items()}
```

### Validation Commands
```bash
# Run coordinator tests
pytest tests/unit/d4_enrichment/test_d4_coordinator.py -xvs

# Run standard Wave A validation
make validate-standard
```

### Rollback Strategy
`git revert` to restore previous coordinator logic

### Feature Flag
No feature flag required - bug fix

---

## P0-002: Wire Prefect Full Pipeline

### Business Logic (Why This Matters)
One orchestrated flow proves the entire MVP works end-to-end.

### Outcome-Focused Acceptance Criteria
- [ ] `smoke/test_full_pipeline_flow.py` generates PDF + email + DB rows within 90s
- [ ] Flow chains all coordinators: Target → Source → Assess → Score → Report → Deliver
- [ ] Error handling with automatic retries (max 3)
- [ ] Metrics logged at each stage with timing
- [ ] Flow state persisted for debugging

### Integration Points
- Create `flows/full_pipeline_flow.py`
- Import all coordinator classes
- Wire sequential flow with error handling

**Critical Path**: May create new files under `tests/**`, `docs/**`, `flows/**`; may edit only files in integration points.

### Tests to Pass
- `tests/smoke/test_full_pipeline_flow.py` (new)

### Implementation Example
```python
# Prefect flow structure - illustrative only
from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(retries=3, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def assess_website(business):
    """Run website assessment with caching"""
    return assessment_coordinator.run(business)

@flow(name="full_pipeline")
def full_pipeline_flow(url: str):
    """End-to-end pipeline with error handling"""
    try:
        business = target_business(url)
        assessment = assess_website(business)
        score = calculate_score(assessment)
        report = generate_report(score)
        send_email(report)
        return {"status": "complete", "report_id": report.id}
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise
```

### Validation Commands
```bash
# Test the new flow
pytest tests/smoke/test_full_pipeline_flow.py -xvs

# Run standard validation
make validate-standard
```

### Rollback Strategy
Delete flows/full_pipeline_flow.py

### Feature Flag
No feature flag required - core functionality

---

## P0-003: Dockerize CI

### Business Logic (Why This Matters)
"Works on my machine" disparities disappear when tests always run in the same image.

### Outcome-Focused Acceptance Criteria
- [ ] GitHub Actions logs show image build success
- [ ] KEEP suite passes inside Docker container
- [ ] Coverage ≥ 80% in containerized tests
- [ ] Image pushed to GHCR on main branch
- [ ] Build time < 5 minutes

### Integration Points
- Create `Dockerfile.test`
- Update `.dockerignore`
- Update `.github/workflows/test.yml`

**Critical Path**: May create new files under `tests/**`, `docs/**`, `docker/**`; may edit only files in integration points.

### Tests to Pass
- `docker build -f Dockerfile.test -t leadfactory-test .`
- `docker run leadfactory-test`
- KEEP suite passes inside container

### Implementation Example
```dockerfile
# Dockerfile.test - production-ready example
FROM python:3.11.0-slim as test

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Copy application code
COPY . .

# Run tests by default
CMD ["pytest", "-m", "not slow and not phase_future", "--tb=short"]
```

### Validation Commands
```bash
# Build test image
docker build -f Dockerfile.test -t leadfactory-test .

# Run tests in container
docker run --rm leadfactory-test

# Verify coverage in container
docker run --rm leadfactory-test coverage run -m pytest tests/unit
```

### Rollback Strategy
Remove Dockerfile.test and revert CI workflow

### Feature Flag
No feature flag required - infrastructure

---

## P0-004: Database Migrations Current

### Business Logic (Why This Matters)
Schema drift breaks runtime and Alembic autogenerate.

### Outcome-Focused Acceptance Criteria
- [ ] `alembic upgrade head` runs without errors
- [ ] `alembic check` shows no pending model changes
- [ ] Downgrade path tested for latest revision
- [ ] All models have corresponding table definitions
- [ ] Migration runs in < 30 seconds

### Integration Points
- `alembic/versions/`
- All model files in `*/models.py`

**Critical Path**: May create new files under `tests/**`, `alembic/versions/**`; may edit only files in integration points.

### Tests to Pass
- `alembic upgrade head`
- `alembic check`
- `tests/unit/test_migrations.py` (new)

### Implementation Example
```python
# test_migrations.py
import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata

def test_migrations_current(alembic_config, engine):
    """Ensure no pending migrations"""
    # Run migrations
    command.upgrade(alembic_config, "head")
    
    # Check for uncommitted changes
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        diff = compare_metadata(context, target_metadata)
        
    assert len(diff) == 0, f"Uncommitted changes: {diff}"

def test_migration_rollback(alembic_config):
    """Test downgrade path"""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "-1")
    command.upgrade(alembic_config, "head")
```

### Validation Commands
```bash
# Run migrations
alembic upgrade head

# Check for changes
alembic check

# Test rollback
alembic downgrade -1
alembic upgrade head

# Run migration tests
pytest tests/unit/test_migrations.py -xvs
```

### Rollback Strategy
- `alembic downgrade -1` to previous revision
- Restore from `pg_dump` if data loss

### Feature Flag
No feature flag required - infrastructure

---

## P0-005: Environment & Stub Wiring

### Business Logic (Why This Matters)
Tests must never hit paid APIs; prod must never run with stubs.

### Outcome-Focused Acceptance Criteria
- [ ] Tests with `USE_STUBS=true` make 0 external API calls
- [ ] Production startup fails if `USE_STUBS=true`
- [ ] All provider calls routed through gateway facade
- [ ] Stub server auto-starts in test fixtures
- [ ] Secrets never appear in logs

### Integration Points
- `core/config.py`
- `stubs/server.py`
- All test fixtures in `conftest.py`

**Critical Path**: May create new files under `tests/**`, `stubs/**`; may edit only files in integration points.

### Tests to Pass
- All tests pass with `USE_STUBS=true`
- `tests/integration/test_stub_server.py`

### Implementation Example
```python
# In core/config.py
class Settings(BaseSettings):
    USE_STUBS: bool = False
    ENVIRONMENT: str = "development"
    
    @validator("USE_STUBS")
    def validate_stubs(cls, v, values):
        if values.get("ENVIRONMENT") == "production" and v:
            raise ValueError("Cannot use stubs in production")
        return v

# In conftest.py
@pytest.fixture(autouse=True)
def enforce_stubs(monkeypatch):
    """Force stub usage in tests"""
    monkeypatch.setenv("USE_STUBS", "true")
    
    # Start stub server if needed
    if not is_stub_server_running():
        start_stub_server()
```

### Validation Commands
```bash
# Run with stubs enforced
USE_STUBS=true pytest tests/integration/test_stub_server.py -xvs

# Verify production check
ENVIRONMENT=production USE_STUBS=true python -c "from core.config import settings" 2>&1 | grep -q "Cannot use stubs"

# Standard validation
make validate-standard
```

### Rollback Strategy
Revert config.py changes

### Feature Flag
USE_STUBS flag itself

---

## P0-006: Green KEEP Test Suite

### Business Logic (Why This Matters)
A green baseline proves core logic is stable for further work.

### Outcome-Focused Acceptance Criteria
- [ ] `pytest -m "not phase_future and not slow"` exits 0
- [ ] 0 test failures or errors
- [ ] Total runtime < 5 minutes
- [ ] Coverage > 80% on core modules
- [ ] No xfail markers remain

### Integration Points
- 60 test files marked as KEEP
- Remove/fix all xfail markers

**Critical Path**: May create new files under `tests/**`; may edit test files only.

### Tests to Pass
- All tests matching KEEP criteria
- `tests/test_marker_policy.py` (new)

### Validation Commands
```bash
# Run KEEP suite
pytest -m "not phase_future and not slow" -q

# Check runtime
time pytest -m "not phase_future and not slow" -q

# Verify coverage
make coverage
```

### Rollback Strategy
Re-add xfail markers to unblock CI

### Feature Flag
No feature flag required

---

## P0-007: Health Endpoint

### Business Logic (Why This Matters)
External uptime monitors need a single, fast status route.

### Outcome-Focused Acceptance Criteria
- [ ] `/health` returns 200 with JSON `{"status": "ok"}`
- [ ] Database connectivity check included
- [ ] Response time < 100ms
- [ ] Version info in response
- [ ] Works in Docker container

### Integration Points
- `api/health.py`
- Main FastAPI app

**Critical Path**: May create new files under `tests/**`, `api/**`; may edit only files in integration points.

### Tests to Pass
- `tests/unit/test_health_endpoint.py`
- `tests/smoke/test_health.py` (new)

### Implementation Example
```python
# Health endpoint implementation
from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Check DB
        db.execute("SELECT 1")
        
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.VERSION,
            "database": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )
```

### Validation Commands
```bash
# Test endpoint
pytest tests/unit/test_health_endpoint.py -xvs

# Test response time
python -c "import requests, time; start=time.time(); r=requests.get('http://localhost:8000/health'); print(f'Response time: {(time.time()-start)*1000:.0f}ms')"

# Standard validation
make validate-standard
```

### Rollback Strategy
Remove /health route from API

### Feature Flag
No feature flag required

---

## P0-008: Test Infrastructure Cleanup

### Business Logic (Why This Matters)
Slow or mis-marked tests waste CI minutes and confuse signal.

### Outcome-Focused Acceptance Criteria
- [ ] Test collection shows correct counts
- [ ] `pytest -m slow` runs 0 tests in CI
- [ ] Import errors eliminated
- [ ] Collection time < 5 seconds
- [ ] Phase 0.5 tests auto-marked as xfail

### Integration Points
- `conftest.py`
- `pytest.ini`
- CI workflow files

**Critical Path**: May create new files under `tests/**`; may edit only test configuration.

### Tests to Pass
- `pytest --collect-only`
- CI completes in < 10 minutes

### Validation Commands
```bash
# Check collection
pytest --collect-only

# Verify no slow tests in CI
pytest -m "slow" --collect-only | grep "0 selected"

# Time collection
time pytest --collect-only

# Standard validation
make validate-standard
```

### Rollback Strategy
Revert conftest.py and pytest.ini changes

### Feature Flag
No feature flag required

---

## P0-009: Remove Yelp Remnants

### Business Logic (Why This Matters)
Stray Yelp code causes dead imports and schema noise.

### Outcome-Focused Acceptance Criteria
- [ ] `git grep -i yelp` finds only comments/docs
- [ ] No Yelp imports in any Python file
- [ ] Yelp columns dropped from database
- [ ] Stub server has no `/yelp/*` routes
- [ ] Documentation updated to reflect removal

### Integration Points
- Any remaining Yelp imports
- Database columns mentioning Yelp
- Stub server endpoints

**Critical Path**: May create new files under `tests/**`, `alembic/versions/**`; may edit only files with Yelp references.

### Tests to Pass
- `grep -r "yelp" --include="*.py" .` returns only comments
- `tests/test_yelp_purge.py` (new)

### Implementation Example
```python
# test_yelp_purge.py
import subprocess

def test_no_yelp_code():
    """Verify Yelp is fully removed"""
    result = subprocess.run(
        ["git", "grep", "-i", "yelp", "--", "*.py"],
        capture_output=True,
        text=True
    )
    
    # Check only comments/docs remain
    for line in result.stdout.splitlines():
        assert "#" in line or "doc" in line.lower(), f"Active Yelp code found: {line}"
```

### Validation Commands
```bash
# Search for Yelp
git grep -i yelp

# Check Python files specifically
grep -r "yelp" --include="*.py" . | grep -v "#"

# Run purge test
pytest tests/test_yelp_purge.py -xvs
```

### Rollback Strategy
Not applicable - Yelp already removed

### Feature Flag
No feature flag required

---

## P0-010: Fix Missing Dependencies

### Business Logic (Why This Matters)
Fresh clone + install must succeed for new devs and CI.

### Outcome-Focused Acceptance Criteria
- [ ] `pip install -r requirements.txt` succeeds in clean venv
- [ ] `pip check` reports no conflicts
- [ ] All imports resolve correctly
- [ ] Version pins for all packages
- [ ] CI cache works properly

### Integration Points
- `requirements.txt`
- `requirements-dev.txt`
- CI cache configuration

**Critical Path**: May only edit requirements files.

### Tests to Pass
- Fresh virtualenv install
- `pip check` passes

### Validation Commands
```bash
# Test fresh install
python -m venv test_venv
source test_venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip check

# Import test
python -c "import leadfactory"

# Cleanup
deactivate
rm -rf test_venv
```

### Rollback Strategy
Restore previous requirements.txt

### Feature Flag
No feature flag required

---

## P0-011: Deploy to VPS

### Business Logic (Why This Matters)
Automated prod deploy removes human error and provides rollback point.

### Outcome-Focused Acceptance Criteria
- [ ] GitHub Actions deploy job completes successfully
- [ ] Container responds 200 on `/health`
- [ ] Restart policy set to `always`
- [ ] SSH key authentication works
- [ ] GHCR image pushed and pulled

### Integration Points
- Create `.github/workflows/deploy.yml`
- Add production Dockerfile
- Configure GitHub secrets

**Critical Path**: May create new files under `.github/**`, `docker/**`; may edit only deployment files.

### Tests to Pass
- Deployment workflow runs
- `curl https://vps-ip/health` returns 200

### Validation Commands
```bash
# Test deployment locally
docker-compose -f docker-compose.test.yml up -d
sleep 10
curl -f http://localhost:8000/health
docker-compose -f docker-compose.test.yml down

# Verify image builds
docker build -t leadfactory:test .
```

### Rollback Strategy
Delete deploy.yml workflow

### Feature Flag
No feature flag required

---

## P0-012: Postgres on VPS Container

## HUMAN REVIEW REQUIRED
This task requires decisions about:
- Backup strategy and retention policy
- Database credentials management
- Volume backup procedures

### Business Logic (Why This Matters)
Local DB on VPS avoids external dependency while you evaluate Supabase.

### Outcome-Focused Acceptance Criteria
- [ ] Postgres 15 container runs with named volume
- [ ] App connects via `DATABASE_URL`
- [ ] `alembic upgrade head` completes on deploy
- [ ] Data survives container restart
- [ ] Backup strategy documented

### Integration Points
- Extend `.github/workflows/deploy.yml`
- Docker network configuration
- Named volume for persistence

**Critical Path**: May create new files under `.github/**`, `docs/**`; may edit only deployment files.

### Tests to Pass
- Database container starts
- App connects successfully
- Data persists across restart

### Validation Commands
```bash
# Test postgres container locally
docker run -d \
  --name test-db \
  -e POSTGRES_PASSWORD=testpass \
  -v test-pgdata:/var/lib/postgresql/data \
  postgres:15

# Test connection
docker exec test-db psql -U postgres -c "SELECT 1"

# Cleanup
docker stop test-db
docker rm test-db
docker volume rm test-pgdata
```

### Rollback Strategy
- Stop postgres container
- Keep volume for data recovery
- `pg_dump` restore instructions in docs

### Feature Flag
No feature flag required

---

## P1-010: SEMrush Client & Metrics

### Business Logic (Why This Matters)
SEO snapshot is a client-value driver and upsell hook.

### Outcome-Focused Acceptance Criteria
- [ ] Stubbed unit tests pass
- [ ] Live smoke test fetches all 6 metrics
- [ ] Metrics appear in PDF "SEO Snapshot" section
- [ ] Cost tracking logs $0.10 per call
- [ ] Rate limit enforced at 10 req/sec

### Integration Points
- Create `d0_gateway/providers/semrush.py`
- Update `d0_gateway/factory.py`
- Add to assessment coordinator

**Critical Path**: May create new files under `tests/**`, `d0_gateway/providers/**`; may edit only gateway files.

### Tests to Pass
- `tests/unit/d0_gateway/test_semrush_client.py`
- `tests/smoke/test_smoke_semrush.py`

### Metrics to Implement
1. Site Health Score (0-100)
2. Domain Authority 
3. Backlink Toxicity Score
4. Organic Traffic Estimate
5. Ranking Keywords Count
6. Technical Issues Count

### Validation Commands
```bash
# Unit tests with stubs
USE_STUBS=true pytest tests/unit/d0_gateway/test_semrush_client.py -xvs

# Smoke test (requires API key)
ENABLE_SEMRUSH=true pytest tests/smoke/test_smoke_semrush.py -xvs

# Wave B validation (95% coverage)
make validate-wave-b
```

### Rollback Strategy
Set `ENABLE_SEMRUSH=false`

### Feature Flag
`ENABLE_SEMRUSH` (see docs/feature_flags.md)

---

## P1-020: Lighthouse Headless Audit

### Business Logic (Why This Matters)
Core Web Vitals & accessibility scores are industry benchmarks demanded by prospects.

### Outcome-Focused Acceptance Criteria
- [ ] Headless Chrome runs via Playwright
- [ ] Audit completes in ≤ 30 seconds
- [ ] Returns 5 scores (Perf, A11y, BP, SEO, PWA)
- [ ] Results cached for 7 days
- [ ] Graceful timeout handling

### Integration Points
- Create `d3_assessment/lighthouse.py`
- Add Playwright to requirements
- Update assessment coordinator

**Critical Path**: May create new files under `tests/**`, `d3_assessment/**`; may edit only assessment files.

### Tests to Pass
- `tests/unit/d3_assessment/test_lighthouse.py`
- `tests/integration/test_lighthouse_integration.py`

### Validation Commands
```bash
# Run lighthouse tests
pytest tests/unit/d3_assessment/test_lighthouse.py -xvs

# Test timeout handling
pytest tests/integration/test_lighthouse_integration.py::test_timeout -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
- Remove lighthouse.py
- Uninstall Playwright
- Set `ENABLE_LIGHTHOUSE=false`

### Feature Flag
`ENABLE_LIGHTHOUSE`

---

## P1-030: Visual Rubric Analyzer

### Business Logic (Why This Matters)
Visual trust cues correlate with conversion; automated scoring yields scalable insights.

### Outcome-Focused Acceptance Criteria
- [ ] Screenshot captured via ScreenshotOne API
- [ ] 9 rubric dimensions scored (0-100)
- [ ] Scores persisted to database
- [ ] PDF shows color-coded bar chart
- [ ] Deterministic stub for testing

### Integration Points
- Create `d3_assessment/visual_analyzer.py`
- Integrate ScreenshotOne API
- Update assessment model

**Critical Path**: May create new files under `tests/**`, `d3_assessment/**`; may edit only assessment files.

### Scoring Dimensions
1. Modern Design
2. Visual Hierarchy
3. Trustworthiness
4. Mobile Responsiveness
5. Page Speed Perception
6. Brand Consistency
7. CTA Prominence
8. Content Density
9. Professional Appearance

### Validation Commands
```bash
# Run visual tests
pytest tests/unit/d3_assessment/test_visual_analyzer.py -xvs

# Test scoring consistency
pytest tests/unit/d3_assessment/test_visual_rubric.py::test_deterministic -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Set `ENABLE_VISUAL_ANALYSIS=false`

### Feature Flag
`ENABLE_VISUAL_ANALYSIS`

---

## P1-040: LLM Heuristic Audit

### Business Logic (Why This Matters)
Narrative feedback differentiates the report and feeds email personalisation.

### Outcome-Focused Acceptance Criteria
- [ ] Returns 7 structured metric fields
- [ ] JSON response validates against schema
- [ ] Cost ~$0.03 logged per audit
- [ ] Timeout at 30 seconds
- [ ] Deterministic stub mode

### Integration Points
- Create `d3_assessment/llm_audit.py`
- Extend LLM insights module
- Add audit results model

**Critical Path**: May create new files under `tests/**`, `d3_assessment/**`; may edit only assessment files.

### Metrics to Extract
1. UVP Clarity Score (0-100)
2. Contact Info Completeness
3. CTA Clarity Score
4. Social Proof Presence
5. Readability Score
6. Mobile Viewport (boolean)
7. Intrusive Popup (boolean)

### Validation Commands
```bash
# Test with stubs
USE_STUBS=true pytest tests/unit/d3_assessment/test_llm_audit.py -xvs

# Test schema validation
pytest tests/unit/d3_assessment/test_llm_heuristic.py::test_schema -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Set `ENABLE_LLM_AUDIT=false`

### Feature Flag
`ENABLE_LLM_AUDIT`

---

## P1-050: Gateway Cost Ledger

### Business Logic (Why This Matters)
Without per-call cost tracking you cannot manage profit or guardrails.

### Outcome-Focused Acceptance Criteria
- [ ] Every external API call inserts ledger row
- [ ] `cost_usd` field populated accurately
- [ ] Daily aggregation view works
- [ ] No performance impact (<5ms overhead)
- [ ] Old records cleaned up after 90 days

### Integration Points
- Create `gateway_cost_ledger` table migration
- Update `BaseAPIClient._make_request()`
- Add cost calculation methods

**Critical Path**: May create new files under `tests/**`, `alembic/versions/**`; may edit only gateway base class.

### Schema
```sql
CREATE TABLE gateway_cost_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR NOT NULL,
    operation VARCHAR NOT NULL,
    cost_usd DECIMAL(10, 4) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    business_id UUID,
    response_time_ms INTEGER
);

CREATE INDEX idx_cost_ledger_daily 
ON gateway_cost_ledger(provider, timestamp);
```

### Validation Commands
```bash
# Run cost ledger tests
pytest tests/unit/d0_gateway/test_cost_ledger.py -xvs

# Test aggregation
pytest tests/integration/test_cost_tracking.py::test_daily_aggregation -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
- Drop gateway_cost_ledger table
- Remove cost tracking code

### Feature Flag
`ENABLE_COST_TRACKING`

---

## P1-060: Cost Guardrails

### Business Logic (Why This Matters)
Prevent invoice shock and keep unit economics predictable.

### Outcome-Focused Acceptance Criteria
- [ ] Flow halts when spend exceeds cap
- [ ] Soft limits log warnings at 80%
- [ ] Hard limits stop execution at 100%
- [ ] Admin override via token
- [ ] Costs reset at midnight UTC

### Integration Points
- Create `d11_orchestration/guardrails.py`
- Update Prefect flows
- Add config for limits

**Critical Path**: May create new files under `tests/**`, `d11_orchestration/**`; may edit only orchestration files.

### Limits
- Daily total: $100
- Per-lead: $2.50
- Per-provider daily: $50
- Hourly spike: $20

### Validation Commands
```bash
# Test guardrails
pytest tests/unit/d11_orchestration/test_cost_guardrails.py -xvs

# Test override
ADMIN_OVERRIDE_TOKEN=test pytest tests/integration/test_guardrail_integration.py::test_override -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Set all limits to None in config

### Feature Flag
`ENABLE_COST_GUARDRAILS`

---

## P1-070: DataAxle Client

### Business Logic (Why This Matters)
Purchased enrichment fills firmographic gaps essential for lead resale.

### Outcome-Focused Acceptance Criteria
- [ ] OAuth2 authentication works
- [ ] Returns ≥10 firmographic fields
- [ ] Rate limit 3000/hour enforced
- [ ] Cost $0.10/record tracked
- [ ] Match confidence score included

### Integration Points
- Create `d0_gateway/providers/dataaxle.py`
- Update factory registration
- Add to enrichment flow

**Critical Path**: May create new files under `tests/**`, `d0_gateway/providers/**`; may edit only gateway files.

### Tests to Pass
- `tests/unit/d0_gateway/test_dataaxle_client.py`
- `tests/smoke/test_smoke_dataaxle.py`

### Validation Commands
```bash
# Test with stubs
USE_STUBS=true pytest tests/unit/d0_gateway/test_dataaxle_client.py -xvs

# Smoke test (requires contract)
ENABLE_DATAAXLE=true pytest tests/smoke/test_smoke_dataaxle.py -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Set `ENABLE_DATAAXLE=false`

### Feature Flag
`ENABLE_DATAAXLE` (pending contract)

---

## P1-080: Bucket Enrichment Flow

### Business Logic (Why This Matters)
Processing by vertical maximises ROI under budget caps.

### Outcome-Focused Acceptance Criteria
- [ ] Runs nightly at 2 AM UTC via Prefect
- [ ] Processes highest-value verticals first
- [ ] Respects all cost guardrails
- [ ] Emails summary report
- [ ] Handles partial failures gracefully

### Integration Points
- Create `flows/bucket_enrichment_flow.py`
- Add Prefect scheduling
- Update targeting models

**Critical Path**: May create new files under `tests/**`, `flows/**`; may edit only flow files.

### Bucket Priority
1. Healthcare (high-value)
2. Professional Services
3. SaaS (medium-value)
4. Restaurants (low-value)

### Implementation Note
```python
# Concurrency protection required
from distributed import Lock

@flow
def bucket_enrichment_flow():
    # Prevent double-charging from parallel runs
    with Lock("budget_guard"):
        process_buckets()
```

### Validation Commands
```bash
# Test flow logic
pytest tests/unit/d11_orchestration/test_bucket_flow.py -xvs

# Test integration
pytest tests/integration/test_bucket_enrichment_flow.py -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Disable Prefect schedule

### Feature Flag
Controlled by provider flags

---

## P2-010: Unit Economics Views

### Business Logic (Why This Matters)
Transparency on CPL/CAC drives pricing and spend decisions.

### Outcome-Focused Acceptance Criteria
- [ ] `/analytics/unit_econ` endpoint returns metrics
- [ ] Includes CPL, CAC, ROI calculations
- [ ] Response cached 24 hours
- [ ] CSV export supported
- [ ] Date range filtering works

### Integration Points
- Create SQL views via migration
- Add `api/analytics.py` endpoints
- Create analytics models

**Critical Path**: May create new files under `tests/**`, `api/**`, `alembic/versions/**`; may edit only analytics files.

### Metrics
- Cost per Lead (CPL)
- Customer Acquisition Cost (CAC)
- Return on Investment (ROI)
- Lifetime Value (LTV)
- Burn Rate

### Validation Commands
```bash
# Test views
pytest tests/unit/d10_analytics/test_unit_economics.py -xvs

# Test API
pytest tests/integration/test_analytics_api.py -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Drop unit economics views

### Feature Flag
Part of core analytics

---

## P2-020: Unit Economics PDF Section

### Business Logic (Why This Matters)
Buyers want a visually digestible cost story.

### Outcome-Focused Acceptance Criteria
- [ ] New 2-page section in PDF reports
- [ ] Pie, bar, and gauge charts render
- [ ] PDF diff < 5% (configurable via PDF_DIFF_TOLERANCE)
- [ ] Mobile-friendly layout
- [ ] Data freshness timestamp shown

### Integration Points
- Update PDF template
- Add cost data to context
- Create chart generation

**Critical Path**: May create new files under `tests/**`, `templates/**`; may edit only report files.

### Charts
- Cost breakdown pie chart
- ROI projection line graph
- Benchmark comparison bars
- Budget utilization gauge

### Validation Commands
```bash
# Test PDF generation
pytest tests/unit/d6_reports/test_economics_section.py -xvs

# Test rendering
pytest tests/unit/d6_reports/test_pdf_unit_econ_section.py -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Remove economics section from template

### Feature Flag
Tied to unit economics data availability

---

## P2-030: Email Personalization V2

### Business Logic (Why This Matters)
Higher personalisation lifts open & click rates.

### Outcome-Focused Acceptance Criteria
- [ ] Generates 5 subject line variants
- [ ] Generates 3 body copy variants
- [ ] Placeholders filled correctly
- [ ] Deterministic mode for tests
- [ ] SendGrid sandbox testing works

### Integration Points
- Update `d8_personalization/generator.py`
- Create new templates
- Add A/B test support

**Critical Path**: May create new files under `tests/**`, `templates/**`; may edit only personalization files.

### Personalization Factors
- Industry pain points
- Metric-based urgency
- Competitive comparisons
- Seasonal relevance
- Business maturity

### Validation Commands
```bash
# Test generation
pytest tests/unit/d8_personalization/test_llm_personalization.py -xvs

# Test templates
pytest tests/unit/d9_delivery/test_email_personalisation_v2.py -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Revert to V1 templates

### Feature Flag
Gradual rollout via A/B testing

---

## P2-040: Orchestration Budget Stop

## HUMAN REVIEW REQUIRED
This task requires decisions about:
- 2FA implementation approach
- Admin override security
- Monthly reset timing

### Business Logic (Why This Matters)
Monthly burn must not exceed planned spend.

### Outcome-Focused Acceptance Criteria
- [ ] Flows transition to Failed when over budget
- [ ] State preserved for manual resume
- [ ] Email alerts sent to admin
- [ ] Auto-resume on month boundary
- [ ] Override requires admin token (2FA future)

### Integration Points
- Add to all Prefect flows
- Create admin UI (future)
- Add monitoring alerts

**Critical Path**: May create new files under `tests/**`, `flows/**`; may edit only orchestration files.

### Stop Conditions
- Monthly budget exceeded
- Unusual spike (>$20/hour)
- Provider errors >10%
- Manual admin stop

### Admin Override (MVP)
```python
# Temporary solution until 2FA
if settings.ADMIN_OVERRIDE_TOKEN == provided_token:
    allow_override()
```

### Validation Commands
```bash
# Test budget stop
pytest tests/integration/test_budget_stop.py -xvs

# Test auto-resume
pytest tests/integration/test_budget_stop.py::test_monthly_reset -xvs

# Wave B validation
make validate-wave-b
```

### Rollback Strategy
Remove budget stop decorator

### Feature Flag
Part of cost guardrails system

---

## Shared Context (Applies to All Tasks)

### Critical Success Factors
1. **Wave Separation**: All P0 tasks must complete before any P1/P2 tasks begin
2. **Coverage Requirements**: Wave A = 80%, Wave B = 95%
3. **Docker Consistency**: All tests must pass in Docker containers
4. **File Modification Rules**: 
   - May create new files under `tests/**`, `docs/**`
   - May only edit files in specified integration points
5. **Documentation Updates**: Update CHANGELOG.md for each completed task

### Common Validation
See `docs/validation_commands.md` for standard scripts.

### DO NOT IMPLEMENT (From CURRENT_STATE.md)
- **Yelp Integration**: All Yelp-related code/tests/migrations
- **Mac Mini Deployment**: Use VPS + Docker only
- **Top 10% Filtering**: Analyze 100% of purchased data
- **$199 Pricing**: Use $399 launch price
- **Simple Email Templates**: Use LLM-powered personalization
- **Basic scoring only**: Implement full multi-metric assessment

### Environment Setup
- Python 3.11.0 (exact version)
- Docker 20.10+ 
- `USE_STUBS=true` for development
- Virtual environment required
- All secrets in `.env` file

### Feature Flags
See `docs/feature_flags.md` for complete list and defaults.

### Error Handling Protocol
1. On test failure → log full error
2. Run rollback strategy
3. Update progress.json with "failed" status
4. Halt execution
5. Alert via logs (Slack integration future)

---

**END OF SUPER PRP**