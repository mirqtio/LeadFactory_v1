# LeadFactory Implementation Plan

## Overview

Two-phase implementation to stabilize the existing LeadFactory codebase, then expand with Phase 0.5 features from PRD v1.2.

**Wave A**: Fix broken tests, wire up orchestration, dockerize, and deploy the v1 happy path (GBP → PageSpeed → Tech → Score → PDF → Email).

**Wave B**: Add rich metrics providers (SEMrush, Lighthouse, Visual Analysis, LLM Audit) and cost controls.

## Shared Constraints

- Python 3.11.0 required (match CI environment)
- All tests must pass in Docker container, not just locally
- No breaking changes to existing database schema
- Feature flags for all new providers: `if settings.ENABLE_SEMRUSH:`
- Cost tracking required for every external API call
- All new code must have >80% test coverage (target 95% in Wave B)
- Use existing gateway pattern from `d0_gateway/base.py`
- Respect rate limits defined in provider configs
- All sensitive data must be masked in logs
- CI must remain green after each PRP merge

## CI Contract & Merge Requirements

**No PR merges unless ALL of the following pass:**
```bash
docker build -f Dockerfile.test -t leadfactory-test .
docker run leadfactory-test pytest -q
docker run leadfactory-test ruff check .
docker run leadfactory-test mypy .
```

**Additional Requirements:**
- Implementers must iterate until all tests pass in Docker environment
- `xfail` markers are NOT allowed in Wave A (P0) tasks
- If CI fails post-merge, immediate fix or revert required
- Visual regression tests must pass for UI-related changes (via Storybook/Chromatic)

## PRP Completion Validation

**MANDATORY: No PRP is considered complete until it passes validation:**

Every PRP implementation MUST achieve a 100% validation score before merge. The implementer must:

1. **Request Validation**: When you believe the PRP is complete, invoke the PRP Completion Validator:
   - Provide the original PRP document
   - Show all code changes, test results, and documentation
   - Include evidence of CI passing and rollback testing

2. **Address All Gaps**: The validator will identify any gaps between PRP requirements and implementation:
   - Missing acceptance criteria
   - Incomplete test coverage  
   - Performance targets not met
   - Missing validation frameworks
   - Documentation gaps

3. **Iterate Until Perfect**: Continue the cycle of:
   - Receive validation feedback with specific gaps
   - Fix all identified issues
   - Request re-validation
   - Repeat until achieving 100/100 score

4. **Final Completion**: A PRP is only complete when:
   - Validation score: 100/100
   - Zero HIGH or CRITICAL severity gaps
   - All CI checks passing
   - Rollback procedure tested and documented

**Validation Dimensions (see .claude/prompts/prp_completion_validator.md):**
- Acceptance Criteria (30%): Every criterion fully implemented and tested
- Technical Implementation (25%): Code quality, architecture, performance
- Test Coverage (20%): Coverage targets met, all test types present
- Validation Framework (15%): Pre-commit hooks, CI gates, monitoring
- Documentation (10%): API docs, configuration, rollback procedures

**Automatic Failures:**
- Missing security tests
- Performance regression
- Breaking existing functionality
- CI not passing
- Coverage below 70%

## Security Baseline

All PRPs must enforce these security requirements:

**API Security:**
- Strict CSP headers on all new routes: `Content-Security-Policy: default-src 'self'`
- CORS configuration limited to approved domains only
- Rate limiting on all public endpoints (100 req/min default)
- Input validation with Pydantic schemas on all endpoints

**Dependency Security:**
- Dependabot alerts must be resolved before merge
- Security scanning via `bandit` in pre-commit hooks
- No new dependencies with known CVEs (Trivy scan in CI)

**Data Protection:**
- PII must be masked in logs using existing `mask_sensitive_data()` utility
- Audit logs must be immutable (enforced at DB level)
- Encryption at rest for sensitive data (via SQLAlchemy encrypted fields)

**Authentication & Authorization:**
- All mutating endpoints must use `RoleChecker` dependency (from P0-026)
- API keys must be stored in environment variables, never in code
- Session tokens expire after 24 hours

## Success Criteria

**Wave A Complete When:**
- All KEEP tests passing (60 core test files)
- Docker image builds and runs tests successfully
- Prefect pipeline processes a business end-to-end
- Application deployed to VPS and responding to health checks
- PDF reports generate without errors
- Emails send via SendGrid in production

**Wave B Complete When:**
- All Phase 0.5 xfail markers removed
- Cost tracking operational with daily spend < $100
- All 6 SEMrush metrics populating
- Lighthouse scores captured for all businesses
- Visual rubric scoring 9 dimensions
- LLM audit providing 7 heuristic scores
- Unit economics dashboard accessible

## Wave A - Stabilize (Priority P0)

### P0-000 Prerequisites Check
**Dependencies**: None  
**Goal**: Ensure development environment is properly configured  
**Integration Points**: 
- `.env` file creation
- Virtual environment setup
- Database initialization

**Tests to Pass**:
- `pytest --collect-only` succeeds without errors
- `python -m py_compile **/*.py` has no syntax errors
- `docker --version` shows 20.10+
- `docker-compose --version` shows 2.0+

**Example**: see examples/REFERENCE_MAP.md → P0-000  
**Reference**: Setup documentation in README.md

**Acceptance Criteria**:
- [ ] Document system dependencies in README
- [ ] Create setup.sh script for new developers
- [ ] Verify all requirements installable
- [ ] Database migrations run cleanly

**Rollback**: Delete setup.sh if created

### P0-001 Fix D4 Coordinator
**Dependencies**: P0-000  
**Goal**: Repair enrichment coordinator merge/cache logic  
**Integration Points**:
- `d4_enrichment/coordinator.py`
- `d4_enrichment/models.py`

**Tests to Pass**:
- `pytest tests/unit/d4_enrichment/test_d4_coordinator.py -v`

**Example**: see examples/REFERENCE_MAP.md → P0-001  
**Reference**: PRD section "D4 Enrichment Coordinator – merge strategy"

**Acceptance Criteria**:
- [ ] Remove xfail marker from test file
- [ ] Fix merge_enrichment_data method
- [ ] Fix cache key generation
- [ ] All 12 coordinator tests passing

**Rollback**: `git revert` to restore previous coordinator logic

### P0-002 Wire Prefect Full Pipeline
**Dependencies**: P0-001  
**Goal**: Create end-to-end orchestration flow  
**Integration Points**:
- Create `flows/full_pipeline_flow.py`
- Import all coordinator classes
- Wire sequential flow with error handling

**Tests to Pass**:
- New: `tests/smoke/test_full_pipeline_flow.py`
- Must process a business from targeting through delivery

**Example**: see examples/REFERENCE_MAP.md → P0-002  
**Reference**: Prefect docs - https://docs.prefect.io/latest/concepts/flows/

**Acceptance Criteria**:
- [ ] Flow chains: Target → Source → Assess → Score → Report → Deliver
- [ ] Error handling with retries
- [ ] Metrics logged at each stage
- [ ] Integration test creates PDF and email record

**Rollback**: Delete flows/full_pipeline_flow.py

### P0-003 Dockerize CI
**Dependencies**: P0-002  
**Goal**: Create working Docker test environment  
**Integration Points**:
- Create `Dockerfile.test`
- Update `.dockerignore`
- Update `.github/workflows/test.yml`

**Tests to Pass**:
- `docker build -f Dockerfile.test -t leadfactory-test .` succeeds
- `docker run leadfactory-test pytest -q` shows 0 failures
- Entire KEEP suite must pass inside the Docker image

**Example**: see examples/REFERENCE_MAP.md → P0-003  
**Reference**: GitHub Actions Docker docs - https://docs.github.com/actions/publishing-images

**Acceptance Criteria**:
- [ ] Multi-stage Dockerfile with test target
- [ ] All Python dependencies installed
- [ ] Postgres service in docker-compose.test.yml
- [ ] Stub server accessible from container
- [ ] CI builds and runs tests in container

**Rollback**: Remove Dockerfile.test and revert CI workflow

### P0-004 Database Migrations Current
**Dependencies**: P0-003  
**Goal**: Ensure schema matches models  
**Integration Points**:
- `alembic/versions/`
- All model files in `*/models.py`

**Tests to Pass**:
- `alembic upgrade head` runs cleanly
- `alembic check` shows no pending changes
- New: `tests/unit/test_migrations.py` - runs alembic upgrade and asserts autogenerate diff is empty

**Example**: see examples/REFERENCE_MAP.md → P0-004  
**Reference**: Alembic docs "autogenerate" section

**Acceptance Criteria**:
- [ ] All model changes captured in migrations
- [ ] No duplicate migrations
- [ ] Migrations run in correct order
- [ ] Rollback tested for each migration

**Rollback**: Use `alembic downgrade` to previous revision

### P0-005 Environment & Stub Wiring
**Dependencies**: P0-004  
**Goal**: Proper test/prod environment separation  
**Integration Points**:
- `core/config.py`
- `stubs/server.py`
- All test fixtures

**Tests to Pass**:
- All tests pass with `USE_STUBS=true`
- No real API calls in test suite
- `tests/integration/test_stub_server.py` passes

**Example**: see examples/REFERENCE_MAP.md → P0-005  
**Reference**: README § "Running stub server locally"

**Acceptance Criteria**:
- [ ] Stub server auto-starts in tests
- [ ] Environment variables documented
- [ ] Secrets never logged
- [ ] Feature flags for each provider

**Rollback**: Revert config.py changes

### P0-006 Green KEEP Test Suite
**Dependencies**: P0-005  
**Goal**: All core tests passing  
**Integration Points**:
- 60 test files marked as KEEP
- Remove/fix all xfail markers

**Tests to Pass**:
```bash
pytest -m "not slow and not phase_future" --tb=short
```
- New: `tests/test_marker_policy.py` - collects tests and asserts no un-marked failures

**Example**: see examples/REFERENCE_MAP.md → P0-006  
**Reference**: CLAUDE.md "Test policy" block

**Acceptance Criteria**:
- [ ] 0 test failures
- [ ] 0 error collections  
- [ ] <5 minute total runtime
- [ ] Coverage >80% on core modules (Wave A target)

**Rollback**: Re-add xfail markers to unblock CI

### P0-007 Health Endpoint
**Dependencies**: P0-006  
**Goal**: Production monitoring endpoint  
**Integration Points**:
- `api/health.py`
- Main FastAPI app

**Tests to Pass**:
- `tests/unit/test_health_endpoint.py`
- Deploy workflow health check
- Already covered in P0-004 smoke test

**Example**: see examples/REFERENCE_MAP.md → P0-007  
**Reference**: FastAPI docs health check patterns

**Acceptance Criteria**:
- [ ] Returns 200 with JSON status
- [ ] Checks database connectivity
- [ ] Checks Redis connectivity
- [ ] Returns version info
- [ ] <100ms response time

**Rollback**: Remove /health route from API

### P0-008 Test Infrastructure Cleanup
**Dependencies**: P0-007  
**Goal**: Fix test discovery and marking issues  
**Integration Points**:
- `conftest.py`
- `pytest.ini`
- CI workflow files

**Tests to Pass**:
- `pytest --collect-only` shows correct test counts
- CI runs in <10 minutes
- `pytest -m "slow" -q` runs zero slow tests in CI

**Example**: see examples/REFERENCE_MAP.md → P0-008  
**Reference**: pytest documentation on markers

**Acceptance Criteria**:
- [ ] Phase 0.5 tests auto-marked as xfail
- [ ] Slow tests excluded from PR builds
- [ ] Import errors in ignored files fixed
- [ ] Test collection time <5 seconds

**Rollback**: Revert conftest.py and pytest.ini changes

### P0-009 Remove Yelp Remnants
**Dependencies**: P0-008  
**Goal**: Complete Yelp provider removal  
**Integration Points**:
- Any remaining Yelp imports
- Database columns mentioning Yelp
- Stub server endpoints

**Tests to Pass**:
- `grep -r "yelp" --include="*.py" .` returns only comments
- New: `tests/test_yelp_purge.py` - verifies no active Yelp code

**Example**: see examples/REFERENCE_MAP.md → P0-009  
**Reference**: Git grep documentation

**Acceptance Criteria**:
- [ ] No Yelp imports in codebase
- [ ] Migrations to drop Yelp columns
- [ ] Documentation updated
- [ ] Stub server Yelp routes removed

**Rollback**: Not applicable - Yelp already removed

### P0-010 Fix Missing Dependencies
**Dependencies**: P0-009  
**Goal**: Align local and CI environments  
**Integration Points**:
- `requirements.txt`
- `requirements-dev.txt`
- CI cache configuration

**Tests to Pass**:
- Fresh virtualenv install works
- CI and local tests have same results
- CI green on a fresh Docker build
- `pip check` passes in CI

**Example**: see examples/REFERENCE_MAP.md → P0-010  
**Reference**: pip-tools documentation for dependency management

**Acceptance Criteria**:
- [ ] All imports resolve correctly
- [ ] Version pins for all packages
- [ ] No conflicting dependencies
- [ ] CI cache working properly

**Rollback**: Restore previous requirements.txt

### P0-011 Deploy to VPS
**Dependencies**: P0-010  
**Goal**: Automated deployment pipeline  
**Integration Points**:
- Create `.github/workflows/deploy.yml`
- Add production Dockerfile
- Configure GitHub secrets

**Tests to Pass**:
- Deployment workflow runs without errors
- `curl https://vps-ip/health` returns 200
- New: `tests/smoke/test_health.py` passes

**Example**: see examples/REFERENCE_MAP.md → P0-011  
**Reference**: VPS hardening checklist from "Move LeadFactory to VPS" thread

**Acceptance Criteria**:
- [ ] GHCR image pushed on main branch
- [ ] SSH key authentication working
- [ ] Docker installed on VPS if missing
- [ ] Container runs with restart policy
- [ ] Nginx reverse proxy configured

**Rollback**: Delete deploy.yml workflow

### P0-012 Postgres on VPS Container
**Dependencies**: P0-011  
**Goal**: Database container with persistent storage  
**Integration Points**:
- Extend `.github/workflows/deploy.yml`
- Docker network for app-db communication
- Named volume for data persistence

**Tests to Pass**:
- Database container runs with named volume
- App container connects successfully
- `alembic upgrade head` completes in deployment

**Example**: see examples/REFERENCE_MAP.md → P0-012  
**Reference**: Docker Compose networking documentation

**Acceptance Criteria**:
- [ ] Deploy workflow pulls postgres:15 image
- [ ] Database runs with named volume for persistence
- [ ] App uses DATABASE_URL=postgresql://lf:strongpassword@db/leadfactory
- [ ] Migrations run after database is ready
- [ ] Database backup strategy documented

**Rollback**: Stop postgres container, keep volume for data recovery

### P0-013 CI/CD Pipeline Stabilization
**Dependencies**: P0-012 (must preserve prior fixes and compatibility)  
**Goal**: Fix all CI/CD issues to achieve green builds across all workflows  
**Integration Points**:
- `.github/workflows/*.yml` – CI configuration files
- `Dockerfile` – Final production container definition
- `Dockerfile.test` – CI-only test image
- `requirements.txt` / `requirements-dev.txt` – Dependency boundaries and separation

**Tests to Pass**:
- Linting workflow completes without errors
- Minimal test suite runs without failure
- Docker build completes in CI
- Deploy workflow runs migrations successfully (CI + manual verification)

**Example**: see examples/REFERENCE_MAP.md → P0-013  
**Reference**: GitHub Actions documentation, Docker best practices

**Business Logic**: A stable CI/CD pipeline is critical for reliable deployment, preventing regressions, and maintaining development velocity. Without consistently passing CI, we cannot safely release changes or rely on automation for testing and deploys.

**Acceptance Criteria**:
- [ ] All GitHub Actions workflows pass: `lint`, `test-minimal`, `test`, `docker`, and `deploy`
- [ ] Production Docker image builds successfully with all required dependencies
- [ ] Alembic migrations run successfully inside the production container
- [ ] Test dependencies are properly separated from production dependencies
- [ ] No linting errors block CI

**Rollback**: Revert workflow, Docker, or dependency changes that break existing successful builds

### P0-014 Test Suite Re-Enablement and Coverage Plan
**Dependencies**: P0-013 (must have green CI before extending)  
**Goal**: Reintroduce full KEEP test coverage, optimize test structure for CI reliability, and establish a path to restore coverage ≥70%.  
**Integration Points**:
- `tests/` structure and pytest config
- `.github/workflows/test.yml` (if matrix strategy added)
- `conftest.py` or `pytest.ini` marker logic
- Formula evaluator test modules

**Tests to Pass**:
- KEEP suite runs end-to-end in CI (with `xfail` isolation)
- Test matrix doesn't exceed runner timeout limit
- Phase 0.5 formula logic does not regress

**Example**: see examples/REFERENCE_MAP.md → P0-014  
**Reference**: pytest documentation on test collection optimization

**Business Logic**: Phase 0.5 tooling, especially for the CPO, requires confidence in rule, config, and evaluator correctness. Rebuilding full test coverage allows those tools to validate pipeline behavior safely.

**Acceptance Criteria**:
- [ ] All KEEP tests either run, are `xfail`, or are conditionally skipped with markers
- [ ] CI test collection time remains under 30 seconds
- [ ] GitHub Actions workflows pass with full test suite enabled or split
- [ ] Test time reduced via selective markers or job matrix
- [ ] Formula evaluator test structure supports partial implementation

**Rollback**: If test re-enable breaks CI, fallback to prior ignore list, isolate failing files, and track re-enable path in PR.

### P0-015 Test Coverage Enhancement to 80%
**Dependencies**: P0-014 (must have test suite running before enhancing coverage)  
**Goal**: Increase test coverage from 57% to 80% while maintaining CI runtime under 5 minutes  
**Integration Points**:
- All modules with <40% coverage (gateway providers, targeting, batch runner)
- Test infrastructure: mock factories, fixtures, utilities
- Coverage configuration in `.coveragerc`
- CI coverage gates in `.github/workflows/test.yml`

**Tests to Pass**:
- `pytest --cov=. --cov-report=term-missing` shows ≥80% coverage
- All CI checks remain green (no regressions)
- CI runtime stays under 5 minutes
- No flaky tests in 10 consecutive runs

**Example**: see examples/REFERENCE_MAP.md → P0-015  
**Reference**: pytest-cov documentation, testing best practices guide

**Business Logic**: Production readiness requires high test coverage to prevent regressions, ensure code quality, and maintain confidence in deployments. The 80% target balances thoroughness with development velocity.

**Acceptance Criteria**:
- [ ] Overall test coverage ≥80% (currently 57.37%)
- [ ] All gateway providers have >70% coverage with mock HTTP responses
- [ ] D1 targeting modules (geo_validator, quota_tracker, batch_scheduler) reach >70%
- [ ] Batch runner modules achieve >70% coverage
- [ ] Mock factory system created for external dependencies
- [ ] Test utilities for async operations implemented
- [ ] CI enforces 80% coverage requirement (fails if below)
- [ ] Coverage report published to PR comments
- [ ] No critical business logic paths below 70% coverage
- [ ] Performance: test suite completes in <5 minutes

**Rollback**: Lower coverage requirement to 70% if 80% proves infeasible within timeline

### P0-020 Design System Token Extraction
**Dependencies**: P0-014 (requires stable CI for UI task validation)  
**Goal**: Extract machine-readable design tokens from HTML style guide for UI component validation  
**Integration Points**:
- Create `design/design_tokens.json` (≤2KB)
- Move `design/styleguide.html` to proper location
- Update design system references in documentation

**Tests to Pass**:
- `pytest tests/unit/design/test_design_tokens.py` (token validation)
- Design token JSON schema validation
- Style guide accessibility compliance tests

**Example**: see examples/REFERENCE_MAP.md → P0-020  
**Reference**: Anthrasite Design System HTML guide, CSS custom properties documentation

**Business Logic**: UI tasks in Wave B require validated design tokens to prevent hardcoded colors, spacing, and typography values. Extracting tokens from the comprehensive HTML style guide ensures consistency across all UI components and enables automated style guide enforcement.

**Acceptance Criteria**:
- [ ] Design tokens extracted to `design/design_tokens.json` 
- [ ] All colors, spacing, typography, and animation values tokenized
- [ ] JSON schema validates token structure and naming conventions
- [ ] Style guide moved to `design/styleguide.html` with updated references
- [ ] Token validation prevents hardcoded hex values in UI code
- [ ] WCAG 2.1 AA contrast ratios documented and validated
- [ ] Design system documentation updated with token usage examples
- [ ] Storybook setup with design token addon for visual documentation
- [ ] Chromatic integration for visual regression testing (fail on color delta > ΔE 5)
- [ ] Token enforcement linter preventing hardcoded colors/spacing in `src/`
- [ ] CI job validates token extraction matches source styleguide
- [ ] Pre-commit hook blocks hardcoded hex/rgb values unless prefixed `--synthesis-`

**CI Token Regeneration Check**:
```yaml
jobs:
  token_regen:
    steps:
      - run: python scripts/extract_tokens.py > design/design_tokens.auto.json
      - run: diff -q design/design_tokens.json design/design_tokens.auto.json
```

**Rollback**: Remove design tokens file and revert to inline CSS values

### P0-021 Lead Explorer
**Dependencies**: P0-020  
**Goal**: Give the CPO a /leads console that supports full CRUD and an audit-log, plus a Quick-Add form that immediately kicks off async enrichment  
**Integration Points**:
- CRUD API & UI – list, create, update, soft-delete leads
- Quick-Add – email + domain → enrichment task queued
- Badging – is_manual + "manual / test" chip in table rows
- Audit Trail – every mutation → audit_log_leads row

**Tests to Pass**:
- POST/GET/PUT/DELETE endpoints return 2xx & validate schemas
- Quick-Add sets enrichment_status=in_progress and persists task-id
- CPO console table shows manual badge; filters by is_manual
- ≥80% coverage on lead_explorer code
- CI green, KEEP suite unaffected

**Example**: see examples/REFERENCE_MAP.md → P0-021  
**Reference**: FastAPI SQL databases tutorial - https://fastapi.tiangolo.com/tutorial/sql-databases/

**Business Logic**: Manual seeding keeps demos moving and lets business users validate downstream flows before automated sources are live.

**Acceptance Criteria**:
- [ ] CRUD endpoints implemented with proper validation
- [ ] Quick-Add form queues enrichment tasks correctly
- [ ] Manual leads display "manual / test" badge
- [ ] Audit trail captures all mutations
- [ ] Test coverage ≥80% on lead_explorer module
- [ ] Playwright smoke test: opens page → filters → creates lead → sees badge
- [ ] Visual regression test via Chromatic/Storybook for lead table UI
- [ ] Background task queue explicitly uses Prefect (specify in docs)
- [ ] CI recursion: PR must pass all tests in Docker before merge
- [ ] Viewer role gets 403 on mutations (tie-in with P0-026 governance)
- [ ] Pagination performance test with 10k mock leads

**Rollback**: Remove lead_explorer module and revert API routes

### P0-022 Batch Report Runner
**Dependencies**: P0-021  
**Goal**: Enable the CPO to pick any set of leads, preview cost, and launch a bulk report run with real-time progress  
**Integration Points**:
- Lead table with filters + multi-select
- Template/version picker (default = latest)
- Cost Preview = lead-count × blended rate (from costs.json)
- Start run → WebSocket progress bar (≥1 msg / 2s)
- Resilient: failing lead ≠ failing batch

**Tests to Pass**:
- Preview within ±5% of actual spend
- Batch status endpoints < 500ms
- Progress pushes throttle correctly
- Failed leads logged; batch continues
- ≥80% coverage on batch_runner

**Example**: see examples/REFERENCE_MAP.md → P0-022  
**Reference**: FastAPI WebSockets tutorial - https://fastapi.tiangolo.com/tutorial/websockets/

**Business Logic**: Bulk processing is the CPO's core "job-to-be-done" and must respect cost guardrails.

**Acceptance Criteria**:
- [ ] Lead multi-select with filters working
- [ ] Cost preview accurate within ±5%
- [ ] WebSocket progress updates every 2 seconds
- [ ] Failed leads don't stop batch processing
- [ ] Test coverage ≥80% on batch_runner module
- [ ] Cost guardrail stub check (raises if ENABLE_COST_GUARDRAILS=true)
- [ ] Playwright test: opens WebSocket, asserts 5+ progress messages during stub run
- [ ] Stale batch auto-cleanup via cron job (mark FAILED after 24h)
- [ ] CI must be green in Docker before merge (explicit iteration requirement)
- [ ] Visual regression test for progress bar UI component

**Rollback**: Remove batch_runner module and WebSocket endpoints

### P0-023 Lineage Panel
**Dependencies**: P0-022  
**Goal**: Persist and surface the {lead_id, pipeline_run_id, template_version_id} triplet for every PDF, with click-through to raw inputs  
**Integration Points**:
- SQLAlchemy report_lineage table (+ migration)
- Write lineage row at end of PDF generation
- /lineage API + console panel
- Read-only JSON viewer for pipeline logs
- Download gzipped raw-input bundle (≤2MB)

**Tests to Pass**:
- 100% of new PDFs have lineage row
- Log viewer loads < 500ms
- Download obeys size ceiling
- ≥80% coverage on lineage_panel

**Example**: see examples/REFERENCE_MAP.md → P0-023  
**Reference**: Python gzip documentation - https://docs.python.org/3/library/gzip.html

**Business Logic**: Enables lightning-fast debugging, compliance audits, and transparent customer support.

**Acceptance Criteria**:
- [ ] Report lineage table created with proper schema
- [ ] Every PDF generation creates lineage record
- [ ] JSON log viewer loads quickly
- [ ] Raw input downloads compressed and size-limited
- [ ] Test coverage ≥80% on lineage_panel module
- [ ] PII redaction for sensitive fields (email, phone) in raw inputs
- [ ] Encryption at rest for lineage data using SQLAlchemy encrypted fields
- [ ] Backfill script: `python scripts/backfill_lineage.py --days=30`
- [ ] Read-only API role enforced, DELETE/UPDATE returns 405
- [ ] Visual regression test for JSON viewer UI
- [ ] CI schema diff check ensures lineage capture doesn't break

**Rollback**: Drop report_lineage table and remove API endpoints

### P0-024 Template Studio
**Dependencies**: P0-023  
**Goal**: Web-based Jinja2 editor with live preview and GitHub PR workflow — no developer required for daily copy tweaks  
**Integration Points**:
- List all templates + git SHA/version
- Monaco editor (CDN) with Jinja2 syntax
- Preview pane (lead_id=1) renders < 500ms
- "Propose changes" → new branch, commit, GH PR; diff viewer

**Tests to Pass**:
- Git metadata appears in list
- Valid auth required for mutations; viewers are read-only
- PR body includes semantic commit msg
- Diff view shows additions/deletions
- ≥80% coverage on template_studio

**Example**: see examples/REFERENCE_MAP.md → P0-024  
**Reference**: Monaco Editor API - https://microsoft.github.io/monaco-editor/api/index.html, GitHub Create PR API - https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request

**Business Logic**: Web-based template editing empowers non-developers to make copy changes without deployment friction.

**Acceptance Criteria**:
- [ ] Template list shows git metadata
- [ ] Monaco editor supports Jinja2 syntax highlighting
- [ ] Preview renders in under 500ms
- [ ] GitHub PR created with proper diff
- [ ] Test coverage ≥80% on template_studio module
- [ ] Strict CSP header: `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net`
- [ ] GitHub Action PR bot runs `pytest d6_reports/templates` on new templates
- [ ] Visual regression test for template preview frame
- [ ] Rate limiting: max 20 preview requests/sec returns 429
- [ ] Jinja2 autoescape enabled, double-escaped content flagged in tests
- [ ] OWASP ZAP scan in CI for XSS vulnerabilities

**Rollback**: Remove template_studio module and UI components

### P0-025 Scoring Playground
**Dependencies**: P0-024  
**Goal**: Safely experiment with YAML weight vectors in Google Sheets, see deltas on a 100-lead sample, and raise a PR with new weights  
**Integration Points**:
- "Import weights" → copies current YAML to Sheet weights_preview
- UI grid shows live Sheet edits (Sheets API)
- "Re-score sample 100" → delta table in console
- "Propose diff" → updates YAML + GitHub PR

**Tests to Pass**:
- Sum(weights) must equal 1 ± 0.005 else error
- Delta table renders < 1s (cached sample)
- PR includes before/after YAML diff
- ≥80% coverage on scoring_playground

**Example**: see examples/REFERENCE_MAP.md → P0-025  
**Reference**: Google Sheets API Python Quickstart - https://developers.google.com/sheets/api/quickstart/python

**Business Logic**: Allows safe experimentation with scoring weights using familiar spreadsheet interface.

**Acceptance Criteria**:
- [ ] Weights import to Google Sheets correctly
- [ ] Weight sum validation enforced
- [ ] Delta calculations render quickly
- [ ] GitHub PR includes proper YAML diff
- [ ] Test coverage ≥80% on scoring_playground module
- [ ] Sheets quota guard: stop polling after 3 quota errors, show UI toast
- [ ] Optimistic locking: PR branch includes SHA of YAML at import time
- [ ] CI fails if base YAML changed during concurrent edits
- [ ] Sample leads anonymized or consent verified for PII protection
- [ ] Performance regression test with 10x sample size behind feature flag
- [ ] Rate limit on Sheets API calls (max 100/min)

**Rollback**: Remove scoring_playground module and Sheets integration

### P0-026 Governance
**Dependencies**: P0-025  
**Goal**: Ship single-tenant RBAC ("Admin" vs "Viewer") and a global immutable audit-trail covering every mutation in the CPO console  
**Integration Points**:
- Role table + enum (admin, viewer)
- Router dependency that checks role before any POST/PUT/DELETE
- audit_log_global table: {user_id, action, object_type, object_id, ts, details}
- Viewer gets 403 on all mutating endpoints

**Tests to Pass**:
- All mutating endpoints blocked for viewer role in tests
- 100% of successful mutations insert audit row
- Tamper-proof: content hash & checksum stored
- ≥80% coverage on governance module

**Example**: see examples/REFERENCE_MAP.md → P0-026  
**Reference**: FastAPI Advanced Dependencies - https://fastapi.tiangolo.com/advanced/advanced-dependencies/

**Business Logic**: RBAC and audit trails ensure proper access control and compliance for enterprise deployments.

**Acceptance Criteria**:
- [ ] Role-based access control implemented
- [ ] Viewers receive 403 on mutations
- [ ] All mutations create audit log entries
- [ ] Audit logs include tamper-proof checksums
- [ ] Test coverage ≥80% on governance module
- [ ] Automated test sweep iterates all routers, asserts POST/PUT/DELETE have RoleChecker
- [ ] Log retention policy: 365 days → S3 cold storage via cron job
- [ ] CI test verifies rotation job doesn't delete within retention window
- [ ] Admin escalation flow documented, viewer→admin upgrade audited
- [ ] Cross-module compatibility test: run KEEP suite with ENABLE_RBAC=false
- [ ] < 100ms performance overhead verified in load tests

**Rollback**: Drop role and audit_log_global tables, remove RBAC middleware

## Wave B - Expand (Priority P1-P2)

### P1-010 SEMrush Client & Metrics
**Dependencies**: All P0-*  
**Goal**: Add SEMrush provider with 6 key metrics  
**Integration Points**:
- Create `d0_gateway/providers/semrush.py`
- Update `d0_gateway/factory.py`
- Add to assessment coordinator

**Tests to Pass**:
- `tests/unit/d0_gateway/test_semrush_client.py`
- `tests/smoke/test_smoke_semrush.py` (with API key)

**Example**: see examples/REFERENCE_MAP.md → P1-010  
**Reference**: SEMrush "Domain Overview API" doc PDF (docs/api/semrush_domain.pdf)

**Metrics to Implement**:
1. Site Health Score (0-100)
2. Backlink Toxicity Score (0-100) 
3. Organic Traffic Estimate
4. Ranking Keywords Count
5. Domain Authority Score
6. Technical Issues by Category

**Acceptance Criteria**:
- [ ] Client extends BaseAPIClient
- [ ] Cost tracking: $0.10 per API call
- [ ] Rate limit: 10 requests/second
- [ ] Stub responses for all endpoints
- [ ] Metrics appear in PDF report

**Rollback**: Feature flag ENABLE_SEMRUSH=false

### P1-020 Lighthouse Headless Audit
**Dependencies**: P1-010  
**Goal**: Browser-based performance testing  
**Integration Points**:
- Create `d3_assessment/lighthouse.py`
- Add Playwright to requirements
- Update assessment coordinator

**Tests to Pass**:
- `tests/unit/d3_assessment/test_lighthouse.py`
- `tests/integration/test_lighthouse_integration.py`
- `tests/unit/d4_enrichment/test_lighthouse_runner.py`

**Example**: see examples/REFERENCE_MAP.md → P1-020  
**Reference**: Google Lighthouse CLI JSON schema (docs/schemas/lighthouse_v10.json)

**Metrics to Capture**:
- Performance Score (0-100)
- Accessibility Score (0-100)
- Best Practices Score (0-100)
- SEO Score (0-100)
- PWA Score (0-100)

**Acceptance Criteria**:
- [ ] Runs headless Chrome via Playwright
- [ ] 30-second timeout per audit
- [ ] Caches results for 7 days
- [ ] Falls back gracefully on timeout
- [ ] Detailed metrics in JSON format

**Rollback**: Remove lighthouse.py and uninstall Playwright

### P1-030 Visual Rubric Analyzer
**Dependencies**: P1-020  
**Goal**: Score visual design quality (1-9 scale)  
**Integration Points**:
- Create `d3_assessment/visual_analyzer.py`
- Integrate ScreenshotOne API
- Store scores in assessment model

**Tests to Pass**:
- `tests/unit/d3_assessment/test_visual_analyzer.py`
- `tests/unit/d3_assessment/test_visual_rubric.py`
- Visual regression tests

**Example**: see examples/REFERENCE_MAP.md → P1-030  
**Reference**: Design brief "Visual Rubric Definitions" (Notion doc link)

**Scoring Dimensions**:
1. Modern Design (1-9)
2. Visual Hierarchy (1-9)
3. Trustworthiness (1-9)
4. Mobile Responsiveness (1-9)
5. Page Speed Perception (1-9)
6. Brand Consistency (1-9)
7. CTA Prominence (1-9)
8. Content Density (1-9)
9. Professional Appearance (1-9)

**Acceptance Criteria**:
- [ ] Screenshot capture via API
- [ ] OpenAI Vision API scoring
- [ ] Deterministic stub for tests
- [ ] Scores persist to database
- [ ] Visual report section in PDF

**Rollback**: Feature flag ENABLE_VISUAL_ANALYSIS=false

### P1-040 LLM Heuristic Audit  
**Dependencies**: P1-030  
**Goal**: GPT-4 powered content analysis  
**Integration Points**:
- Create `d3_assessment/llm_audit.py`
- Extend LLM insights module
- Add audit results model

**Tests to Pass**:
- `tests/unit/d3_assessment/test_llm_audit.py`
- `tests/unit/d3_assessment/test_llm_heuristic.py`
- Deterministic stub responses

**Example**: see examples/REFERENCE_MAP.md → P1-040  
**Reference**: Prompt template draft in /docs/prompts/heuristic_audit.md

**Metrics to Extract**:
1. UVP Clarity Score (0-100)
2. Contact Info Completeness (0-100)
3. CTA Clarity Score (0-100)
4. Social Proof Presence (0-100)
5. Readability Score (0-100)
6. Mobile Viewport Detection (boolean)
7. Intrusive Popup Detection (boolean)

**Acceptance Criteria**:
- [ ] Structured prompt template
- [ ] JSON response parsing
- [ ] Cost: ~$0.03 per audit
- [ ] Timeout handling
- [ ] Metrics in assessment record

**Rollback**: Feature flag ENABLE_LLM_AUDIT=false

### P1-050 Gateway Cost Ledger
**Dependencies**: P1-040  
**Goal**: Track all external API costs  
**Integration Points**:
- Create migration for `gateway_cost_ledger` table
- Update `BaseAPIClient._make_request()`
- Add cost calculation methods

**Tests to Pass**:
- `tests/unit/d0_gateway/test_cost_ledger.py`
- `tests/integration/test_cost_tracking.py`

**Example**: see examples/REFERENCE_MAP.md → P1-050  
**Reference**: Cost model table spec in /docs/schemas/cost_ledger.sql

**Schema**:
```sql
- provider (string)
- operation (string)  
- cost_usd (decimal)
- request_id (uuid)
- business_id (uuid, nullable)
- timestamp (datetime)
- response_time_ms (integer)
```

**Acceptance Criteria**:
- [ ] Every API call logged
- [ ] Costs calculated per provider
- [ ] Daily aggregation views
- [ ] No performance impact
- [ ] Cleanup job for old records

**Rollback**: Drop gateway_cost_ledger table

### P1-060 Cost Guardrails
**Dependencies**: P1-050  
**Goal**: Prevent runaway API costs  
**Integration Points**:
- Create `d11_orchestration/guardrails.py`
- Update Prefect flows
- Add config for limits

**Tests to Pass**:
- `tests/unit/d11_orchestration/test_cost_guardrails.py`
- `tests/integration/test_guardrail_integration.py`

**Example**: see examples/REFERENCE_MAP.md → P1-060  
**Reference**: Phase 0.5 Orchestration PRD § "Budget Enforcement"

**Limits to Implement**:
- Daily total: $100
- Per-lead: $2.50  
- Per-provider daily: $50
- Hourly spike: $20

**Acceptance Criteria**:
- [ ] Soft limits log warnings
- [ ] Hard limits halt execution
- [ ] Admin override capability
- [ ] Slack notifications
- [ ] Costs reset at midnight UTC

**Rollback**: Set all guardrail limits to None

### P1-070 DataAxle Client
**Dependencies**: P1-060  
**Goal**: Business data enrichment provider  
**Integration Points**:
- Create `d0_gateway/providers/dataaxle.py`
- Update factory registration
- Add to enrichment flow

**Tests to Pass**:
- `tests/unit/d0_gateway/test_dataaxle_client.py`
- `tests/smoke/test_smoke_dataaxle.py`

**Example**: see examples/REFERENCE_MAP.md → P1-070  
**Reference**: DataAxle API doc excerpt (docs/api/dataaxle.pdf)

**Endpoints**:
- Business Search (by name + location)
- Business Enrichment (by ID)
- Bulk Export (up to 1000)

**Acceptance Criteria**:
- [ ] OAuth2 authentication
- [ ] Rate limit: 3000/hour
- [ ] Cost: $0.10 per record
- [ ] 15+ data fields returned
- [ ] Match confidence scoring

**Rollback**: Feature flag ENABLE_DATAAXLE=false

### P1-080 Bucket Enrichment Flow
**Dependencies**: P1-070  
**Goal**: Process businesses by industry segment  
**Integration Points**:
- Create `flows/bucket_enrichment_flow.py`
- Add scheduling to Prefect
- Update targeting models

**Tests to Pass**:
- `tests/unit/d11_orchestration/test_bucket_flow.py`
- `tests/integration/test_bucket_enrichment.py`
- `tests/integration/test_bucket_enrichment_flow.py`

**Example**: see examples/REFERENCE_MAP.md → P1-080  
**Reference**: D1 Targeting PRD § "Nightly bucket enrichment"

**Bucket Strategy**:
- Healthcare: High-value, strict budget
- SaaS: Medium-value, normal budget
- Restaurants: Low-value, minimal budget
- Professional Services: High-value

**Acceptance Criteria**:
- [ ] Runs nightly at 2 AM UTC
- [ ] Respects cost guardrails
- [ ] Processes highest-value first
- [ ] Emails summary report
- [ ] Handles partial failures

**Rollback**: Disable Prefect schedule

### P2-010 Unit Economics Views
**Dependencies**: All P1-*  
**Goal**: Cost/revenue analytics API  
**Integration Points**:
- Create SQL views in migration
- Add `api/analytics.py` endpoints
- Create analytics models

**Tests to Pass**:
- `tests/unit/d10_analytics/test_unit_economics.py`
- `tests/unit/d10_analytics/test_unit_econ_views.py`
- `tests/integration/test_analytics_api.py`

**Example**: see examples/REFERENCE_MAP.md → P2-010  
**Reference**: Analytics spec /docs/schemas/unit_econ_views.sql

**Metrics to Calculate**:
- Cost per Lead (CPL)
- Customer Acquisition Cost (CAC)
- Burn Rate (daily/monthly)
- Revenue per Lead
- ROI by Channel
- LTV Projections

**Acceptance Criteria**:
- [ ] Read-only endpoints
- [ ] 24-hour cache
- [ ] JSON and CSV export
- [ ] Date range filtering
- [ ] Cohort analysis support

**Rollback**: Drop unit economics views

### P2-020 Unit Economics PDF Section
**Dependencies**: P2-010  
**Goal**: Add cost insights to reports  
**Integration Points**:
- Update PDF template
- Add cost data to context
- Create visualization charts

**Tests to Pass**:
- `tests/unit/d6_reports/test_economics_section.py`
- `tests/unit/d6_reports/test_pdf_unit_econ_section.py`
- PDF snapshot tests

**Example**: see examples/REFERENCE_MAP.md → P2-020  
**Reference**: Figma mockup PDF docs/design/pdf_unit_econ_mock.pdf

**Visualizations**:
- Cost breakdown pie chart
- ROI projection graph
- Benchmark comparisons
- Budget utilization gauge

**Acceptance Criteria**:
- [ ] New 2-page section
- [ ] Charts render correctly
- [ ] Conditional display logic
- [ ] Mobile-friendly layout
- [ ] Data freshness indicator

**Rollback**: Remove economics section from PDF template

### P2-030 Email Personalization V2
**Dependencies**: P2-020  
**Goal**: LLM-powered email content  
**Integration Points**:
- Update `d8_personalization/generator.py`
- Create new email templates
- Add A/B test variants

**Tests to Pass**:
- `tests/unit/d8_personalization/test_llm_personalization.py`
- `tests/unit/d9_delivery/test_email_personalisation_v2.py`
- Email rendering tests

**Example**: see examples/REFERENCE_MAP.md → P2-030  
**Reference**: Marketing copy prompt bank /docs/prompts/email_personalization.md

**Personalization Factors**:
- Industry-specific pain points
- Metric-based urgency
- Competitive comparisons
- Seasonal relevance
- Business maturity stage

**Acceptance Criteria**:
- [ ] 5 subject line variants
- [ ] 3 body copy variants
- [ ] Deterministic test mode
- [ ] Preview in admin UI
- [ ] Click tracking enabled

**Rollback**: Revert to V1 email templates

### P2-040 Orchestration Budget Stop
**Dependencies**: P2-030  
**Goal**: Monthly spend circuit breaker  
**Integration Points**:
- Add to all Prefect flows
- Create admin override UI
- Add monitoring alerts

**Tests to Pass**:
- `tests/integration/test_budget_stop.py`
- Flow halt verification

**Example**: see examples/REFERENCE_MAP.md → P2-040  
**Reference**: Prefect recipe "Fail flow on budget" (docs/prefect_budget_stop.md)

**Stop Conditions**:
- Monthly budget exceeded
- Unusual spike detected
- Provider errors >10%
- Manual admin stop

**Acceptance Criteria**:
- [ ] Graceful flow shutdown
- [ ] State preserved for resume
- [ ] Email notifications
- [ ] Auto-resume next month
- [ ] Override requires 2FA

**Rollback**: Remove budget stop decorator from flows

## Wave C - Critical Fixes & UI Completion

These tasks address critical security issues and complete missing UI components discovered during validation.

### P3-001 Fix RBAC for All API Endpoints

**Dependencies**: P0-026
**Goal**: Apply RoleChecker to ALL mutation endpoints across the entire API surface, not just governance endpoints
**Integration Points**:
- All API routers in `api/` directory
- All domain routers (`d1_targeting`, `d3_assessment`, etc.)
- Lead Explorer, Batch Runner, Template Studio, Scoring Playground APIs

**Tests to Pass**:
- Integration test verifying 403 responses for viewers on ALL mutations
- Automated sweep test counting protected vs unprotected endpoints
- Security audit test validating no unprotected mutations exist

**Acceptance Criteria**:
- [ ] Every POST/PUT/PATCH/DELETE endpoint requires authentication
- [ ] Viewers receive 403 on ALL mutation attempts
- [ ] Admins can perform all operations
- [ ] No performance regression from auth checks
- [ ] Zero unprotected mutation endpoints

**Rollback**: Remove RoleChecker dependencies from API routes

### P3-002 Complete Lineage Integration

**Dependencies**: P0-023
**Goal**: Integrate lineage capture into actual PDF generation flow to achieve 100% capture rate
**Integration Points**:
- `d6_reports/pdf_converter.py`
- `d6_reports/generator.py`
- Alembic migrations

**Tests to Pass**:
- Integration test verifying every PDF generation creates lineage record
- Performance test confirming <100ms overhead
- Migration test for lineage tables

**Acceptance Criteria**:
- [ ] 100% of new PDFs have lineage row captured
- [ ] LineageCapture integrated into ReportGenerator
- [ ] SQLAlchemy event listeners properly implemented
- [ ] Migration applied to create lineage tables
- [ ] Feature flag ENABLE_REPORT_LINEAGE working

**Rollback**: Feature flag to disable lineage capture

### P3-003 Fix Lead Explorer Audit Trail

**Dependencies**: P0-021
**Goal**: Fix the critical SQLAlchemy audit event listener bug preventing audit logging
**Integration Points**:
- `lead_explorer/audit.py`
- Database audit tables

**Tests to Pass**:
- All audit trail tests passing
- Integration test verifying audit logs created for all operations
- Tamper-proof checksum verification test

**Acceptance Criteria**:
- [ ] Audit event listeners use after_flush_postexec
- [ ] All CRUD operations create audit logs
- [ ] SHA-256 checksums prevent tampering
- [ ] Failed operations also logged
- [ ] No SQLAlchemy flush errors

**Rollback**: Disable audit event listeners

### P3-004 Create Batch Runner UI

**Dependencies**: P0-022
**Goal**: Create web UI for Batch Report Runner with lead selection and progress tracking
**Integration Points**:
- `static/batch_runner/index.html`
- Mount point in `main.py`
- WebSocket integration

**Tests to Pass**:
- UI renders correctly
- WebSocket connection established
- Progress updates received every 2 seconds
- Cost preview displays accurately

**Acceptance Criteria**:
- [ ] Lead multi-select interface with filters
- [ ] Template/version picker
- [ ] Cost preview with ±5% accuracy
- [ ] Real-time progress via WebSocket
- [ ] Cancel batch functionality
- [ ] Mobile responsive design

**Rollback**: Remove static mount point

### P3-005 Complete Test Coverage

**Dependencies**: All P0-*
**Goal**: Achieve ≥80% test coverage on all modules that failed validation
**Integration Points**:
- All modules with <80% coverage
- CI/CD pipeline configuration

**Tests to Pass**:
- Coverage report shows ≥80% for all modules
- CI enforces coverage requirements
- No test failures

**Acceptance Criteria**:
- [ ] d4_coordinator: ≥80% coverage
- [ ] batch_runner: ≥80% coverage
- [ ] All other modules: ≥80% coverage
- [ ] CI fails if coverage drops below 80%
- [ ] Property-based tests for critical functions

**Rollback**: Not applicable - test improvements only

### P3-006 Replace Mock Integrations

**Dependencies**: P0-024, P0-025
**Goal**: Replace mock GitHub and Google Sheets APIs with real implementations
**Integration Points**:
- Template Studio GitHub integration
- Scoring Playground Google Sheets integration
- Environment configuration

**Tests to Pass**:
- Integration tests with real APIs (using test accounts)
- Rate limit handling tests
- Error recovery tests

**Acceptance Criteria**:
- [ ] PyGithub creates real pull requests
- [ ] gspread integrates with actual Google Sheets
- [ ] Proper OAuth2 flow for Google
- [ ] GitHub app authentication working
- [ ] Rate limits respected

**Rollback**: Feature flags to revert to mock implementations

### P3-007 Fix CI Docker Test Execution

**Dependencies**: P0-003
**Goal**: Update main CI workflow to actually run tests inside Docker containers
**Integration Points**:
- `.github/workflows/test.yml`
- Docker test configuration

**Tests to Pass**:
- All tests pass inside Docker container
- KEEP suite completes in <5 minutes
- Coverage reports generated from Docker

**Acceptance Criteria**:
- [ ] test.yml builds Docker test image
- [ ] All pytest commands run inside container
- [ ] Docker-compose manages test dependencies
- [ ] Coverage data extracted from container
- [ ] No direct pytest execution on runner

**Rollback**: Revert workflow changes

## Wave D - UI Consolidation

These PRPs consolidate all UI components into a unified React application with shared design system.

### P0-027 Global Navigation Shell

**Dependencies**: P0-026
**Goal**: Create a unified React shell application that hosts all LeadFactory UI features with consistent navigation and authentication
**Integration Points**:
- New React app at `/app/*` routes
- Integration with existing authentication from P0-026
- Mounting points for all feature UIs

**Tests to Pass**:
- Shell renders with proper navigation
- Authentication guards work correctly
- Route lazy-loading functions
- Bundle size stays under limits

**Acceptance Criteria**:
- [ ] Global navigation with all feature links
- [ ] Authentication integration with role-based menu items
- [ ] Lazy-loaded routes for each feature
- [ ] Dark mode support using design tokens
- [ ] Responsive mobile navigation

**Rollback**: Feature flag ENABLE_UNIFIED_SHELL

### P0-028 Design-System UI Foundations

**Dependencies**: P0-020
**Goal**: Create and publish a reusable @leadfactory/ui-core package containing all shared front-end assets, design tokens, Tailwind config, and core UI components
**Integration Points**:
- New monorepo package at `packages/ui-core`
- Process `design/design_tokens.json` into Tailwind preset
- Core components: Button, Card, Badge, Table, Modal, Stepper, Input, Dropdown
- Storybook 7 documentation
- Chromatic visual regression testing

**Tests to Pass**:
- npm run build produces ESM bundle < 50 kB gzipped
- Storybook documents ≥ 8 primitive components
- All styles derived from design tokens (no magic numbers)
- axe-core accessibility score ≥ 98
- Unit test coverage ≥ 90%

**Acceptance Criteria**:
- [ ] Published to GitHub Packages as consumable package
- [ ] All components keyboard accessible
- [ ] Visual regression tests via Chromatic
- [ ] Style Dictionary converts tokens to CSS properties
- [ ] TypeScript types for all components

**Rollback**: Revert package version

### P0-029 Lead Explorer UI

**Dependencies**: P0-021, P0-027, P0-028
**Goal**: Provide a fully-featured React interface for Lead Explorer API with CRUD, search, and audit trail review
**Integration Points**:
- Route at `/app/leads`
- Consumes `/api/v1/leads` endpoints
- Uses @leadfactory/ui-core DataTable component
- React Query for data fetching

**Tests to Pass**:
- Table renders with real API data
- Create/Update/Quick-Add operations succeed
- Audit trail CSV download works
- JS bundle < 250 kB gzipped
- Frontend test coverage ≥ 80%

**Acceptance Criteria**:
- [ ] Paginated searchable lead table with column reordering
- [ ] Bulk-select for soft deletion
- [ ] Slide-out drawer for create/update forms
- [ ] Quick-Add functionality
- [ ] Audit trail tab with CSV export
- [ ] localStorage persistence for table layout

**Rollback**: Feature flag ENABLE_LEAD_EXPLORER_UI

### P0-030 Lineage Panel UI

**Dependencies**: P0-023, P0-027, P0-028
**Goal**: Create user-friendly UI for report lineage feature with search, log viewing, and raw input downloading
**Integration Points**:
- Route at `/app/lineage`
- Virtualized results list for large datasets
- Lazy-loaded JSON log viewer
- Download raw inputs functionality

**Tests to Pass**:
- Log viewer streams first 50kB immediately
- JSON viewer handles large logs efficiently
- Download produces gzipped bundle ≤ 2MB
- JS bundle < 250 kB gzipped
- Frontend test coverage ≥ 80%

**Acceptance Criteria**:
- [ ] Search filters by lead, date, template version
- [ ] Virtualized list handles 5k+ rows
- [ ] JSON viewer with collapsible nodes
- [ ] Download raw inputs button
- [ ] Performance with large logs

**Rollback**: Feature flag ENABLE_LINEAGE_UI

### P0-031 Batch Report Runner UI

**Dependencies**: P0-022, P0-027, P0-028
**Goal**: Build intuitive multi-step UI for Batch Report Runner with selection, cost preview, and real-time monitoring
**Integration Points**:
- Route at `/app/batch`
- Multi-step wizard using Stepper component
- WebSocket for real-time progress
- History tab with rerun functionality

**Tests to Pass**:
- Cost preview within ±5% accuracy
- Cancel action propagates to backend
- URL state restoration doesn't trigger POSTs
- JS bundle < 250 kB gzipped
- Frontend test coverage ≥ 80%

**Acceptance Criteria**:
- [ ] Multi-step wizard for batch creation
- [ ] Real-time progress via WebSocket
- [ ] Cost preview before execution
- [ ] Cancel batch functionality
- [ ] History tab with rerun failed leads
- [ ] WebSocket reconnect logic

**Rollback**: Feature flag ENABLE_BATCH_RUNNER_UI

### P0-032 Template Studio Polish

**Dependencies**: P0-024, P0-027, P0-028
**Goal**: Migrate Template Studio to native React app with improved editor experience and Git integration
**Integration Points**:
- Route at `/app/templates`
- Monaco editor with Jinja2 support
- GitHub PR integration
- Preview with sample lead selector

**Tests to Pass**:
- Monaco editor loads Jinja2 language pack
- PR description includes Jira links
- Focus trap works correctly
- JS bundle < 250 kB gzipped
- Frontend test coverage ≥ 80%

**Acceptance Criteria**:
- [ ] Native React page (no iframe)
- [ ] Searchable template list
- [ ] Monaco editor with Jinja2 syntax
- [ ] Preview sample lead dropdown
- [ ] Auto-link Jira tickets in PRs
- [ ] Accessible focus management

**Rollback**: Feature flag ENABLE_TEMPLATE_STUDIO_UI

### P0-033 Scoring Playground Integration

**Dependencies**: P0-025, P0-027, P0-028
**Goal**: Seamlessly integrate Google Sheets-based Scoring Playground into global shell
**Integration Points**:
- Route at `/app/scoring`
- Delta chart visualization
- Weight table display
- Import weights functionality

**Tests to Pass**:
- Delta chart updates < 1 second
- Efficient polling with backoff
- JS bundle < 250 kB gzipped
- Frontend test coverage ≥ 80%
- Chart tooltip snapshot tests

**Acceptance Criteria**:
- [ ] Real-time delta visualization
- [ ] Weight table with editing
- [ ] Import current weights to sheet
- [ ] Polling with exponential backoff
- [ ] Clear upgrade path to SSE
- [ ] Accessible chart interactions

**Rollback**: Feature flag ENABLE_SCORING_UI

### P0-034 Governance Console Polish

**Dependencies**: P0-026, P0-027, P0-028
**Goal**: Build polished, secure UI for Governance module with visual RBAC enforcement and audit trail access
**Integration Points**:
- Route at `/app/governance`
- User management interface
- Audit log viewer
- Real-time WebSocket updates

**Tests to Pass**:
- Viewer role sees read-only UI
- Role changes broadcast via WebSocket
- CSV download respects filters
- JS bundle < 250 kB gzipped
- Frontend test coverage ≥ 80%

**Acceptance Criteria**:
- [ ] User list with role management
- [ ] Audit log with filtering
- [ ] Download CSV functionality
- [ ] Real-time role change updates
- [ ] Route-level guards for viewers
- [ ] Service token rotation button

**Rollback**: Feature flag ENABLE_GOVERNANCE_UI

## Implementation Notes

**PRP Generation**: Each ### section above becomes one PRP file with the naming convention `PRP-{priority}-{title-slug}.md`.

**Dependencies**: Wave B cannot start until ALL of Wave A is complete and deployed.

**Testing Strategy**: 
- Each PRP must make its specific tests pass
- No PRP can break existing passing tests
- Integration tests run after each wave

**Rollback Plan**: Each PRP must be revertable via `git revert` without breaking prior PRPs.