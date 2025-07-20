# LeadFactory Remaining Implementation Plan

## Overview

This document contains the remaining incomplete PRPs from the LeadFactory implementation plan. The core stabilization work has been completed, and this represents the remaining expansion and enhancement work.

**Current Status**: Wave A stabilization is complete. This document shows remaining work for Wave B expansion, Wave C critical fixes, and Wave D UI consolidation.

**Total Remaining**: 27 PRPs across multiple waves focusing on rich metrics providers, cost controls, UI completion, and critical fixes.

## Remaining Work Summary

### Wave B - Expand (8 PRPs Remaining)
- P1-010: SEMrush Client & Metrics
- P1-020: Lighthouse Headless Audit  
- P1-030: Visual Rubric Analyzer
- P1-040: LLM Heuristic Audit
- P1-050: Gateway Cost Ledger
- P1-060: Cost Guardrails
- P1-070: DataAxle Client
- P1-080: Bucket Enrichment Flow

### Wave B - Analytics (4 PRPs Remaining)
- P2-010: Unit Economics Views
- P2-020: Unit Economics PDF Section  
- P2-030: Email Personalization V2
- P2-040: Orchestration Budget Stop

### Wave C - Critical Fixes (7 PRPs Remaining)
- P3-001: Fix RBAC for All API Endpoints
- P3-002: Complete Lineage Integration  
- P3-003: Fix Lead Explorer Audit Trail
- P3-004: Create Batch Runner UI
- P3-005: Complete Test Coverage
- P3-006: Replace Mock Integrations
- P3-007: Fix CI Docker Test Execution

### Wave D - UI Consolidation (8 PRPs Remaining)
- P0-027: Global Navigation Shell
- P0-028: Design-System UI Foundations
- P0-029: Lead Explorer UI
- P0-030: Lineage Panel UI
- P0-031: Batch Report Runner UI
- P0-032: Template Studio Polish
- P0-033: Scoring Playground Integration
- P0-034: Governance Console Polish

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

**Completion Status by Wave:**

**Wave A**: ✅ Complete - All 26 PRPs delivered
- KEEP test suite stable and passing
- Docker CI/CD pipeline operational  
- VPS deployment with persistent storage
- Core lead management and governance features

**Wave B**: ⏳ In Progress - 8 PRPs remaining
- Rich metrics providers (SEMrush, Lighthouse, Visual Analysis, LLM Audit)
- Cost tracking and guardrails
- Unit economics analytics

**Wave C**: 📋 Planned - 3 PRPs remaining
- Critical security and integration fixes
- Complete missing features from Wave A

**Wave D**: 📋 Planned - 8 PRPs remaining  
- Unified React UI consolidation
- Design system implementation

**Wave B Complete When:**
- All Phase 0.5 xfail markers removed
- Cost tracking operational with daily spend < $100
- All 6 SEMrush metrics populating
- Lighthouse scores captured for all businesses
- Visual rubric scoring 9 dimensions
- LLM audit providing 7 heuristic scores
- Unit economics dashboard accessible

## Wave A - Stabilization Complete

**Status**: All Wave A PRPs (P0-001 through P0-026) have been completed. Core stabilization including test fixes, orchestration, dockerization, deployment, and basic governance is now operational.

**Key Achievements**:
- Full KEEP test suite passing
- Docker CI/CD pipeline operational
- VPS deployment with persistent database
- Core UI components for lead management
- RBAC and audit trail systems
- Test coverage >80%

**Remaining Work**: Wave B expansion, Wave C critical fixes, and Wave D UI consolidation (see sections below).

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

**Dependencies**: Wave A is complete. Wave B, C, and D can now proceed according to their individual dependency chains.

**Testing Strategy**: 
- Each PRP must make its specific tests pass
- No PRP can break existing passing tests
- Integration tests run after each wave

**Rollback Plan**: Each PRP must be revertable via `git revert` without breaking prior PRPs.