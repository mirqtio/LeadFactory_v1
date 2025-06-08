# LeadFactory MVP Task Plan Summary

## Overview

This document summarizes the comprehensive task plan for building the LeadFactory MVP following CI-first development principles. The plan contains 100 tasks organized into 15 phases, designed to deliver a revenue-generating system within 48-72 hours.

## Key Principles

### CI-First Development
- **Every task includes tests** that must pass in Docker before committing
- **Docker environment matches CI exactly** - no "works on my machine" issues
- **All tests run in containers** using the same Python 3.11.0 and dependencies
- **GitHub Actions verify every commit** before merging

### Test-Driven Approach
1. Write tests first (or alongside implementation)
2. Run tests in Docker: `docker run --rm leadfactory-test pytest tests/...`
3. Verify CI compatibility: `python scripts/ci_check.py`
4. Commit only when all tests pass in Docker
5. Push and verify GitHub Actions succeed

## Phase Breakdown

### Phase 1: Foundation (Tasks 001-009)
**Goal**: Setup project structure, CI pipeline, and test environment
- Project structure and dependencies
- Database models with SQLAlchemy 2.0.23
- Stub server for external APIs
- GitHub Actions CI workflow
- Docker compose for local development

### Phase 2: D0 Gateway (Tasks 010-019)
**Goal**: Unified API facade with rate limiting and circuit breakers
- Base gateway architecture
- Token bucket rate limiter with Redis
- Circuit breaker pattern
- Response caching system
- Provider implementations (Yelp, PageSpeed, OpenAI)

### Phase 3: D1 Targeting (Tasks 020-024)
**Goal**: Geo × vertical campaign management
- Target universe models
- Batch scheduler with quota allocation
- Geo hierarchy validation
- API endpoints

### Phase 4: D2 Sourcing (Tasks 025-029)
**Goal**: Yelp data acquisition
- Business models and deduplication
- Pagination handling (1000 result limit)
- Quota enforcement (5k/day)

### Phase 5: D3 Assessment (Tasks 030-039)
**Goal**: Website analysis pipeline
- PageSpeed Core Web Vitals
- Tech stack detection
- LLM-powered insights (GPT-4o-mini)
- Parallel assessment coordination

### Phase 6: D4 Enrichment (Tasks 040-044)
**Goal**: Google Business Profile data
- Fuzzy matching system
- Phone/name/address similarity
- Confidence scoring

### Phase 7: D5 Scoring (Tasks 045-049)
**Goal**: Lead qualification engine
- YAML-based scoring rules
- Weighted calculations
- A/B/C/D tier assignment
- Vertical-specific overrides

### Phase 8: D6 Reports (Tasks 050-054)
**Goal**: PDF report generation
- Finding prioritization
- HTML to PDF conversion (Playwright)
- Conversion-optimized templates

### Phase 9: D7 Storefront (Tasks 055-059)
**Goal**: Stripe payment flow
- Checkout session creation
- Webhook processing
- Purchase tracking
- Report delivery trigger

### Phase 10: D8 Personalization (Tasks 060-064)
**Goal**: Email content generation
- Subject line patterns
- LLM-powered personalization
- Spam score checking
- A/B variants

### Phase 11: D9 Delivery (Tasks 065-069)
**Goal**: SendGrid email delivery
- Compliance headers
- Bounce/complaint handling
- Suppression list
- Click tracking

### Phase 12: D10 Analytics (Tasks 070-074)
**Goal**: Metrics and reporting
- Funnel tracking
- Cost analysis
- Materialized views
- API endpoints

### Phase 13: D11 Orchestration (Tasks 075-079)
**Goal**: Pipeline coordination
- Prefect workflows
- A/B experiment management
- Error handling and retries

### Phase 14: Integration Testing (Tasks 080-089)
**Goal**: End-to-end verification
- Complete flow testing
- Performance benchmarks
- Security verification
- 80%+ code coverage

### Phase 15: Deployment (Tasks 090-100)
**Goal**: Production launch
- Configuration setup
- External API verification
- Initial campaigns
- First batch execution

## Execution Guidelines

### For Each Task:

1. **Read the task details** in `taskmaster_plan.json`
2. **Check dependencies** - ensure prerequisite tasks are complete
3. **Create test files first** as specified in `test_requirements`
4. **Implement the feature** following acceptance criteria
5. **Run Docker tests** using the commands provided
6. **Fix any failures** until all tests pass
7. **Commit with CI verification**

### Critical Path

The following tasks are on the critical path and block subsequent work:
- Task 001: Project setup
- Task 002: Database models
- Task 010: Gateway base
- Task 076: Pipeline orchestration
- Task 093: Production deployment

### Time Estimates

- **Total estimated hours**: ~150 hours
- **With AI assistance**: 48-72 hours possible
- **Phases can overlap** where dependencies allow
- **Focus on critical path** first

## Success Metrics

### Technical Success
- All tests passing in Docker
- CI pipeline green
- <2% error rate in production
- <30s report generation

### Business Success
- 5,000 businesses processed daily
- 100+ emails sent
- 0.25-0.6% conversion rate
- First revenue within 72 hours

## Common Commands

```bash
# Run tests for a specific domain
docker run --rm leadfactory-test pytest tests/unit/d0_gateway/

# Run all tests
docker run --rm leadfactory-test pytest

# Check CI compatibility
python scripts/ci_check.py

# Run specific test file
docker run --rm leadfactory-test pytest tests/unit/d0_gateway/test_base.py -xvs

# Generate coverage report
docker run --rm leadfactory-test pytest --cov=. --cov-report=html

# Start local environment
docker-compose up -d

# View logs
docker-compose logs -f

# Run pipeline locally
python -m d11_orchestration.pipeline --date today --limit 10
```

## Getting Started

1. Create project directory and initialize git
2. Copy the PRD and task plan files
3. Start with Task 001: Setup project structure
4. Use TaskMaster MCP to track progress
5. Follow CI-first principles religiously
6. Aim for first test email within 48 hours

Remember: **Every line of code must be tested in Docker before committing!**