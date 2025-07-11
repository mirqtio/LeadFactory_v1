# SUPER PRP: Combined Review Document - All Tasks (FINAL)

**IMPORTANT ORCHESTRATOR RULES**:
1. **Linear Execution Only**: Process PRPs strictly in the order listed below. No parallelism.
2. **Failure Protocol**: On test failure → run `make rollback TASK_ID=<task>` → halt execution → alert via logs: `{"event":"halt","prp":"<task>","reason":"<error>","timestamp":"<ISO8601>"}`
3. **Human Review Required**: Tasks marked with `## HUMAN REVIEW REQUIRED` need manual approval before proceeding
4. **Environment Safety**: Deploy workflow MUST fail if `USE_STUBS=true` in production (enforced in .github/workflows/deploy.yml)
5. **Retry Policy**: MAX_RETRIES=1 for all tasks. On second failure, rollback and halt.
6. **Timeouts**: Global timeout constants in settings (e.g., TIMEOUT_LH=30 for Lighthouse)

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

## Shared Context (All PRPs)

1. **Python 3.11.0** is required (use pyenv if needed)
2. **Docker 20.10+** and **Docker Compose 2.0+** required
3. **USE_STUBS=true** for all development and testing
4. **Coverage requirements**: Wave A = 80%, Wave B = 95%
5. **Documentation updates**: Always update README.md for new features, API changes in docs/api.md, feature flags in docs/feature_flags.md
6. **No deprecated features**: See CURRENT_STATE.md DO NOT IMPLEMENT section
7. **Linear execution**: Tasks must complete in order, no parallelism
8. **Standard validation**: Use `make validate-standard` (Wave A) or `make validate-wave-b` (Wave B)
9. **Rollback command**: `make rollback TASK_ID=<task-id>` (uses scripts/rollback.sh)
10. **Error handling**: MAX_RETRIES=1, then rollback. Log format: `{"event":"<type>","prp":"<id>","reason":"<msg>"}`

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
# setup.sh content (illustrative only - adapt to actual needs)
#!/bin/bash
set -e

echo "Setting up LeadFactory development environment..."

# Check Python version
python3 --version | grep -q "3.11" || echo "WARNING: Python 3.11 required"

# Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy env file
cp .env.example .env

# Run migrations
alembic upgrade head

echo "✓ Setup complete!"
```

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git clean -fdx && git checkout .`

---

## P0-001: Fix D4 Coordinator

### Business Logic (Why This Matters)
Accurate enrichment merge prevents stale or duplicate provider data in assessments.

### Outcome-Focused Acceptance Criteria
- [ ] `test_d4_coordinator.py::test_merge_enrichments` passes consistently
- [ ] No duplicate provider data in merged results
- [ ] Timestamp ordering preserved (newest first)
- [ ] All provider types handled correctly

### Integration Points
- `src/d4_enrichment/coordinator.py`
- `tests/unit/d4_enrichment/test_d4_coordinator.py`

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

### Tests to Pass
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py -xvs`

### Implementation Guide
Focus on the `merge_enrichments()` method. The issue is likely in how duplicate providers are handled or how timestamps are compared.

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d4_enrichment/coordinator.py tests/unit/d4_enrichment/test_d4_coordinator.py`

---

## P0-002: Wire Prefect Full Pipeline

### Business Logic (Why This Matters)
End-to-end pipeline automation ensures consistent assessment generation without manual intervention.

### Outcome-Focused Acceptance Criteria
- [ ] `test_full_pipeline_flow.py` creates a complete assessment
- [ ] Flow handles all stages: crawl → assess → score → report → deliver
- [ ] Failure in any stage triggers appropriate rollback
- [ ] Monitoring dashboard shows flow status

### Integration Points
- `flows/full_pipeline_flow.py`
- `tests/smoke/test_full_pipeline_flow.py`
- `src/d10_orchestration/`

**Critical Path**: Only modify files within these directories.

### Tests to Pass
- `pytest tests/smoke/test_full_pipeline_flow.py -xvs`
- Prefect UI shows successful flow execution

### Implementation Example
```python
# flows/full_pipeline_flow.py (illustrative only)
from prefect import flow, task
from leadfactory import crawler, assessor, scorer, reporter, deliverer

@flow(name="full_pipeline")
def full_pipeline_flow(business_url: str):
    crawl_result = crawler.crawl(business_url)
    assessment = assessor.assess(crawl_result)
    score = scorer.calculate_score(assessment)
    report = reporter.generate_pdf(score)
    deliverer.send_email(report)
    return report
```

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `prefect deployment pause full_pipeline && git checkout HEAD -- flows/`

---

## P0-003: Dockerize CI

### Business Logic (Why This Matters)
Container-based CI ensures consistent test environments and catches "works on my machine" issues.

### Outcome-Focused Acceptance Criteria
- [ ] `Dockerfile.test` builds successfully with all dependencies
- [ ] KEEP test suite passes inside Docker container
- [ ] CI uses Docker for all test runs
- [ ] Build cache reduces subsequent build times

### Integration Points
- `Dockerfile.test`
- `.github/workflows/test.yml`
- `docker-compose.ci.yml`

**Critical Path**: Only modify CI/Docker files.

### Tests to Pass
- `docker build -f Dockerfile.test -t leadfactory-test .`
- `docker run --rm leadfactory-test pytest -m "not slow"`

### Implementation Note
Add pip cache mounting for faster builds:
```dockerfile
# In Dockerfile.test
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -r requirements-dev.txt
```

### Validation Commands
```bash
# Run Docker validation
docker build -f Dockerfile.test -t leadfactory-test .
docker run --rm leadfactory-test make validate-standard
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- Dockerfile.test .github/workflows/`

---

## P0-004: Database Migrations Current

### Business Logic (Why This Matters)
Schema consistency prevents runtime errors and data corruption.

### Outcome-Focused Acceptance Criteria
- [ ] `alembic upgrade head` runs without errors
- [ ] `test_migrations.py` validates schema matches models
- [ ] No pending migrations needed
- [ ] Rollback migrations tested

### Integration Points
- `alembic/versions/`
- `src/models/`
- `tests/unit/test_migrations.py`

**Critical Path**: Database schema changes only.

### Tests to Pass
- `alembic upgrade head`
- `alembic check`
- `pytest tests/unit/test_migrations.py`

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `alembic downgrade -1 && pg_dump leadfactory > backup_$(date +%s).sql`

---

## P0-005: Environment & Stub Wiring

### Business Logic (Why This Matters)
Proper stub configuration enables cost-free development and reliable testing.

### Outcome-Focused Acceptance Criteria
- [ ] `USE_STUBS=true` routes all external calls to stub server
- [ ] Stub server returns realistic responses
- [ ] `.env.example` contains all required variables
- [ ] No real API calls in test mode

### Integration Points
- `stubs/`
- `.env.example`
- `src/config.py`
- `tests/integration/test_stub_server.py`

**Critical Path**: Configuration and stub implementation only.

### Tests to Pass
- `USE_STUBS=true pytest tests/integration/test_stub_server.py`
- No external API calls logged during tests

### Key Action
Create comprehensive `.env.example` with ALL feature flags from CURRENT_STATE.md.

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- stubs/ .env.example src/config.py`

---

## P0-006: Green KEEP Test Suite

### Business Logic (Why This Matters)
KEEP tests represent core functionality that must never break.

### Outcome-Focused Acceptance Criteria
- [ ] `pytest -m "not slow and not phase_future"` shows 0 failures
- [ ] All KEEP tests run in < 60 seconds
- [ ] No flaky tests
- [ ] Coverage ≥ 80%

### Integration Points
- All test files
- Source files with failing tests

**Critical Path**: Fix tests without changing core business logic.

### Tests to Pass
- `pytest -m "not slow and not phase_future" -q`
- `coverage run -m pytest tests/unit && coverage report --fail-under=80`

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- tests/`

---

## P0-007: Health Endpoint

### Business Logic (Why This Matters)
Health checks enable automated monitoring and graceful deployments.

### Outcome-Focused Acceptance Criteria
- [ ] `/health` returns 200 with system status
- [ ] Database connectivity checked
- [ ] External service status included
- [ ] Response time < 500ms

### Integration Points
- `src/api/health.py`
- `tests/smoke/test_health.py`

**Critical Path**: API endpoint addition only.

### Tests to Pass
- `pytest tests/smoke/test_health.py`
- `curl http://localhost:8000/health` returns JSON

### Implementation Example
```python
# src/api/health.py (illustrative only)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": check_db_connection(),
        "version": get_version()
    }
```

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/api/health.py`

---

## P0-008: Test Infrastructure Cleanup

### Business Logic (Why This Matters)
Clean test infrastructure prevents false positives and speeds up development.

### Outcome-Focused Acceptance Criteria
- [ ] All slow tests marked with `@pytest.mark.slow`
- [ ] Phase 0.5+ tests marked with `@pytest.mark.phase_future`
- [ ] Test execution time reduced by 50%
- [ ] Parallel test execution enabled

### Integration Points
- `pytest.ini`
- `conftest.py`
- All test files

**Critical Path**: Test infrastructure only, no business logic changes.

### Tests to Pass
- `pytest -m "not slow" --duration=10` shows reasonable times
- `pytest --collect-only -m phase_future` shows future tests

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- pytest.ini conftest.py`

---

## P0-009: Remove Yelp Remnants

### Business Logic (Why This Matters)
Yelp integration was deprecated; remnants cause confusion and potential errors.

### Outcome-Focused Acceptance Criteria
- [ ] Zero references to "yelp" in codebase (except migration history)
- [ ] No Yelp-related tests
- [ ] No Yelp columns in active schema
- [ ] Documentation updated

### Integration Points
- All source files
- All test files
- Database migrations

**Critical Path**: Remove only, do not add new functionality.

### Tests to Pass
- `grep -r "yelp" --exclude-dir=.git --exclude-dir=migrations . | wc -l` returns 0
- All tests still pass

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: Not applicable - Yelp should not be restored

---

## P0-010: Fix Missing Dependencies

### Business Logic (Why This Matters)
Missing dependencies cause deployment failures and developer friction.

### Outcome-Focused Acceptance Criteria
- [ ] `pip install -r requirements.txt` succeeds in fresh environment
- [ ] `pip check` shows no conflicts
- [ ] All imports resolve correctly
- [ ] Lock file updated

### Integration Points
- `requirements.txt`
- `requirements-dev.txt`
- `setup.py`

**Critical Path**: Dependency files only.

### Tests to Pass
- `pip install -r requirements.txt && pip check`
- `python -c "import leadfactory"`

### Validation Commands
```bash
# Run standard Wave A validation
bash scripts/validate_wave_a.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- requirements*.txt`

---

## P0-011: Deploy to VPS

### Business Logic (Why This Matters)
Production deployment validates the entire system works outside development.

### Outcome-Focused Acceptance Criteria
- [ ] GitHub Actions deploys to VPS on merge to main
- [ ] Health endpoint accessible from internet
- [ ] SSL/TLS configured
- [ ] Monitoring enabled

### Integration Points
- `.github/workflows/deploy.yml`
- `deploy/`
- VPS configuration

**Critical Path**: Deployment configuration only.

### Tests to Pass
- Deploy workflow runs successfully
- `curl https://leadfactory.example.com/health` returns 200

### Validation Commands
```bash
# Post-deploy smoke test
pytest tests/smoke/test_health.py --base-url=https://leadfactory.example.com
```

### Rollback Strategy
**Rollback**: `ssh vps "cd /app && git checkout previous-tag && docker-compose restart"`

---

## P0-012: Postgres on VPS Container
## ⚠️ HUMAN REVIEW REQUIRED

**Human Review Gate**: Database deployment requires approval. Reviewer must verify:
- [ ] Backup strategy in place
- [ ] Connection security (SSL required)
- [ ] Resource limits set
- [ ] Persistent volume configured

**Approval method**: Comment `/approve P0-012` on PR or use `leadfactory approve-deployment P0-012`

### Business Logic (Why This Matters)
Containerized Postgres ensures consistent database deployment and easier scaling.

### Outcome-Focused Acceptance Criteria
- [ ] Postgres runs in Docker container on VPS
- [ ] Data persists across container restarts
- [ ] Automated backups configured
- [ ] Connection pooling enabled

### Integration Points
- `docker-compose.production.yml`
- Database connection strings
- Backup scripts

**Critical Path**: Infrastructure configuration only.

### Tests to Pass
- `docker-compose -f docker-compose.production.yml up -d postgres`
- `alembic upgrade head` succeeds
- Data persists after `docker-compose restart postgres`

### Validation Commands
```bash
# Verify database is accessible
docker-compose -f docker-compose.production.yml exec postgres pg_isready
```

### Rollback Strategy
**Rollback**: `docker-compose down postgres && docker volume rm leadfactory_postgres_data` (CAUTION: Data loss!)

---

## P1-010: SEMrush Client & Metrics

### Business Logic (Why This Matters)
SEMrush provides critical SEO metrics not available from free sources.

### Outcome-Focused Acceptance Criteria
- [ ] SEMrush client returns 6 required metrics
- [ ] Rate limiting implemented (10 req/sec)
- [ ] Cost tracking per API call
- [ ] Graceful degradation on API errors

### Integration Points
- `src/d0_gateway/semrush_client.py`
- `tests/unit/d0_gateway/test_semrush_client.py`

**Critical Path**: Gateway layer only.

### Tests to Pass
- `pytest tests/unit/d0_gateway/test_semrush_client.py`
- Mock responses return expected schema

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d0_gateway/semrush_client.py`

---

## P1-020: Lighthouse Headless Audit

### Business Logic (Why This Matters)
Lighthouse provides comprehensive performance metrics beyond basic PageSpeed.

### Outcome-Focused Acceptance Criteria
- [ ] Lighthouse runs headlessly via Playwright
- [ ] 5 category scores captured
- [ ] Timeout at 30 seconds (TIMEOUT_LH=30)
- [ ] Results cached for 24 hours

### Integration Points
- `src/d3_assessment/lighthouse_runner.py`
- `tests/unit/d3_assessment/test_lighthouse_runner.py`

**Critical Path**: Assessment layer only.

### Tests to Pass
- `pytest tests/unit/d3_assessment/test_lighthouse_runner.py`
- Lighthouse completes in < 30 seconds

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d3_assessment/lighthouse_runner.py`

---

## P1-030: Visual Rubric Analyzer

### Business Logic (Why This Matters)
Visual analysis catches UX issues that metrics miss.

### Outcome-Focused Acceptance Criteria
- [ ] Screenshot captured via ScreenshotOne
- [ ] 9 visual dimensions scored 1-5
- [ ] OpenAI Vision API processes image
- [ ] Results include confidence scores

### Integration Points
- `src/d3_assessment/visual_analyzer.py`
- `tests/unit/d3_assessment/test_visual_analyzer.py`

**Critical Path**: Assessment layer only.

### Tests to Pass
- `pytest tests/unit/d3_assessment/test_visual_analyzer.py`
- Visual scores match expected ranges

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d3_assessment/visual_analyzer.py`

---

## P1-040: LLM Heuristic Audit

### Business Logic (Why This Matters)
LLM analysis provides nuanced insights about content quality and messaging.

### Outcome-Focused Acceptance Criteria
- [ ] Humanloop integration working
- [ ] 7 heuristic dimensions evaluated
- [ ] Prompt versioning enabled
- [ ] Cost per analysis < $0.50

### Integration Points
- `src/d3_assessment/llm_auditor.py`
- Humanloop configuration

**Critical Path**: Assessment layer only.

### Tests to Pass
- `pytest tests/unit/d3_assessment/test_llm_auditor.py`
- Humanloop API mocked correctly

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d3_assessment/llm_auditor.py`

---

## P1-050: Gateway Cost Ledger

### Business Logic (Why This Matters)
Cost tracking prevents budget overruns and enables optimization.

### Outcome-Focused Acceptance Criteria
- [ ] Every API call logged with cost
- [ ] `gateway_cost_ledger` table created
- [ ] Daily/monthly aggregations available
- [ ] Cost alerts configured

### Integration Points
- `src/d0_gateway/cost_tracker.py`
- Database migrations
- `tests/unit/d0_gateway/test_cost_tracker.py`

**Critical Path**: Gateway layer and database only.

### Tests to Pass
- `pytest tests/unit/d0_gateway/test_cost_tracker.py`
- Cost entries created in database

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `alembic downgrade -1 && git checkout HEAD -- src/d0_gateway/cost_tracker.py`

---

## P1-060: Cost Guardrails

### Business Logic (Why This Matters)
Guardrails prevent runaway costs from bugs or attacks.

### Outcome-Focused Acceptance Criteria
- [ ] Daily budget cap enforced ($100 default)
- [ ] Per-lead cap enforced ($2.50 default)
- [ ] Provider-specific caps configurable
- [ ] Override mechanism with 2FA token (stored in Vault, rotated daily)

### Integration Points
- `src/d0_gateway/guardrails.py`
- Configuration system
- `tests/unit/d0_gateway/test_guardrails.py`

**Critical Path**: Gateway layer only.

### Tests to Pass
- `pytest tests/unit/d0_gateway/test_guardrails.py`
- Requests blocked when limits exceeded

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d0_gateway/guardrails.py && redis-cli FLUSHDB`

---

## P1-070: DataAxle Client

### Business Logic (Why This Matters)
DataAxle provides email/phone data essential for outreach.

### Outcome-Focused Acceptance Criteria
- [ ] DataAxle API integrated
- [ ] Email, phone, firmographics retrieved
- [ ] Data quality validation
- [ ] Cost tracking enabled

### Integration Points
- `src/d0_gateway/dataaxle_client.py`
- `tests/unit/d0_gateway/test_dataaxle_client.py`

**Critical Path**: Gateway layer only.

### Tests to Pass
- `pytest tests/unit/d0_gateway/test_dataaxle_client.py`
- Valid email/phone returned

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d0_gateway/dataaxle_client.py`

---

## P1-080: Bucket Enrichment Flow

### Business Logic (Why This Matters)
Batch processing reduces costs and improves efficiency.

### Outcome-Focused Acceptance Criteria
- [ ] Nightly batch job processes all pending enrichments
- [ ] Concurrency limited to 10 parallel requests
- [ ] Cost-aware scheduling (cheapest providers first)
- [ ] Failed items retried once

### Integration Points
- `flows/bucket_enrichment_flow.py`
- `src/d10_orchestration/batch_processor.py`

**Critical Path**: Orchestration layer only.

### Tests to Pass
- `pytest tests/unit/d10_orchestration/test_batch_processor.py`
- Batch completes within cost limits

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `prefect deployment pause bucket_enrichment && git checkout HEAD -- flows/`

---

## P2-010: Unit Economics Views

### Business Logic (Why This Matters)
Unit economics visibility enables data-driven optimization.

### Outcome-Focused Acceptance Criteria
- [ ] API endpoints for CPL, CAC, LTV metrics
- [ ] Historical trends available
- [ ] Cohort analysis supported
- [ ] Real-time dashboard

### Integration Points
- `src/api/unit_economics.py`
- `src/d7_analytics/economics_calculator.py`

**Critical Path**: API and analytics layers only.

### Tests to Pass
- `pytest tests/unit/api/test_unit_economics.py`
- Metrics calculate correctly

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/api/unit_economics.py src/d7_analytics/`

---

## P2-020: Unit Economics PDF Section

### Business Logic (Why This Matters)
Including economics in reports demonstrates ROI to customers.

### Outcome-Focused Acceptance Criteria
- [ ] PDF includes unit economics section
- [ ] Charts show projection curves
- [ ] Custom branding supported
- [ ] Export to Excel available

### Integration Points
- `src/d6_reports/economics_section.py`
- PDF generation pipeline

**Critical Path**: Reporting layer only.

### Tests to Pass
- `pytest tests/unit/d6_reports/test_economics_section.py`
- PDF generates with economics data

### Note on S3 Cleanup
If charts are uploaded to S3, rollback must include: `aws s3 rm s3://bucket/charts/ --recursive`

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d6_reports/economics_section.py`

---

## P2-030: Email Personalization V2

### Business Logic (Why This Matters)
Personalized emails dramatically improve conversion rates.

### Outcome-Focused Acceptance Criteria
- [ ] 5 subject line variants generated
- [ ] 3 body copy variants generated
- [ ] A/B testing framework integrated
- [ ] Performance tracking enabled

### Integration Points
- `src/d8_personalization/llm_personalizer.py`
- `src/d9_delivery/email_builder_v2.py`

**Critical Path**: Personalization and delivery layers only.

### Tests to Pass
- `pytest tests/unit/d8_personalization/test_llm_personalizer.py`
- Variants are meaningfully different

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d8_personalization/ src/d9_delivery/email_builder_v2.py`

---

## P2-040: Orchestration Budget Stop
## ⚠️ HUMAN REVIEW REQUIRED

**Human Review Gate**: Budget stop mechanism requires approval. Reviewer must verify:
- [ ] Alert recipients configured correctly
- [ ] Override mechanism secure (2FA required)
- [ ] Graceful shutdown implemented
- [ ] Data integrity maintained

**Approval method**: Comment `/approve P2-040` on PR or use `leadfactory approve-feature P2-040`

### Business Logic (Why This Matters)
Hard budget stops prevent catastrophic cost overruns.

### Outcome-Focused Acceptance Criteria
- [ ] All orchestration halts at monthly budget limit
- [ ] Manual override requires 2FA token
- [ ] Graceful shutdown of in-flight operations
- [ ] Alert sent to stakeholders

### Integration Points
- `src/d10_orchestration/budget_monitor.py`
- All flow definitions

**Critical Path**: Orchestration layer only.

### Tests to Pass
- `pytest tests/unit/d10_orchestration/test_budget_monitor.py`
- Flows stop when budget exceeded

### Validation Commands
```bash
# Run standard Wave B validation
bash scripts/validate_wave_b.sh
```

### Rollback Strategy
**Rollback**: `git checkout HEAD -- src/d10_orchestration/budget_monitor.py`

---

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
# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
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
| **Active**         | Google Business Profile            | Hours, rating, review_count, photos                  | Free quota ≈ 500 calls/day.                                                                 |
|                    | PageSpeed Insights                 | FCP, LCP, CLS, TBT, TTI, Speed Index, Perf Score      | Runtime scores collected in Wave A.                                                         |
| **Planned (P0.5)** | Purchased CSV feed (DataAxle-like) | e-mail, phone, domain, NAICS, size codes              | Negotiation underway; expected $0.10 / record.                                             |
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
| Pricing               | $199 / report              | **$399 launch** price — will lower after experiments                                                                   |
| Conversion assumption | 0.25 – 0.6 %                | Conservative **0.2 %** of total leads (cold SMB benchmark 2 % → personalised 0.2 % assumption)                          |
| Outreach channels     | ESP cold mail only          | Phase rollout: ① manual low-volume inbox → ② warm-inbox automation → ③ ESP.<br>Parallel LinkedIn + optional snail-mail. |
| Revenue goal          | $25 k MRR in 6 weeks       | Target slips to **Q1 FY26**                                                                                             |

---

## Technical Architecture

| Layer         | Original PRD         | Current / Planned                                                           |
| ------------- | -------------------- | --------------------------------------------------------------------------- |
| Infra         | Bare-metal Mac-Mini  | **Ubuntu VPS** + Docker.  App + Stub server + Postgres containers (Wave A). |
| Database      | Yelp columns present | Yelp columns removed; new **gateway_cost_ledger** table scheduled Wave B. |
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
| **P0-008** | Test-infra cleanup          | slow-marker & phase_future auto-tag verified         |
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
| **P1-060** | Cost guardrails                 | Daily $100 cap, per-lead $2.50, provider caps                       |
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
| GBP API             | $0.00     |
| PageSpeed           | $0.005    |
| ScreenshotOne (PDF) | $0.002    |
| **Total Wave A**    | **$0.01** |

Budget guardrails (Wave B) keep spend < **$100/day** and **$2.50/lead**.

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
3. **Pricing elasticity** — test $399 vs $299 vs usage-based?
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