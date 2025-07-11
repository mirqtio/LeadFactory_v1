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

## Implementation Notes

**PRP Generation**: Each ### section above becomes one PRP file with the naming convention `PRP-{priority}-{title-slug}.md`.

**Dependencies**: Wave B cannot start until ALL of Wave A is complete and deployed.

**Testing Strategy**: 
- Each PRP must make its specific tests pass
- No PRP can break existing passing tests
- Integration tests run after each wave

**Rollback Plan**: Each PRP must be revertable via `git revert` without breaking prior PRPs.