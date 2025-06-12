# LeadFactory Issue Resolution Plan

## Overview
This document outlines the plan to resolve all issues identified during smoke testing and achieve 100% production readiness.

## Issues Identified

### 1. Database Configuration Issues
- **Problem**: Password mismatch between application and PostgreSQL container
- **Impact**: No tables created, data cannot be persisted
- **Severity**: CRITICAL

### 2. Environment Variable Configuration
- **Problem**: Real API keys from .env not being passed to containers
- **Impact**: External API calls fail, using stub data only
- **Severity**: HIGH

### 3. Missing API Endpoints
- **Problem**: Some endpoints return 404/405 errors
- **Impact**: Incomplete feature coverage
- **Severity**: MEDIUM

### 4. Database Migration Issues
- **Problem**: Alembic migrations contain PostgreSQL-specific syntax incompatible with SQLite
- **Impact**: Cannot run migrations in test environment
- **Severity**: MEDIUM

## Resolution Plan

### Phase 1: Critical Infrastructure (Immediate)

#### 1.1 Fix Database Configuration
```bash
# Step 1: Update docker-compose.production.yml to use consistent passwords
# Step 2: Ensure POSTGRES_PASSWORD is set from .env
# Step 3: Update DATABASE_URL to match
```

**Tasks:**
- [ ] Add POSTGRES_PASSWORD to .env file
- [ ] Update docker-compose.production.yml to use ${POSTGRES_PASSWORD}
- [ ] Ensure DATABASE_URL uses matching credentials
- [ ] Test database connection
- [ ] Run database migrations successfully

#### 1.2 Fix Environment Variable Propagation
```bash
# Step 1: Create .env.production with all required variables
# Step 2: Update docker-compose to properly load env vars
# Step 3: Verify all services have correct credentials
```

**Tasks:**
- [ ] Create comprehensive .env.production file
- [ ] Update docker-compose.production.yml env_file directive
- [ ] Add validation script to check all required env vars
- [ ] Test external API connections with real keys

### Phase 2: Application Fixes (Today)

#### 2.1 Implement Missing API Endpoints
```python
# Priority endpoints to implement:
# - POST /api/v1/campaigns
# - POST /api/v1/targets/search  
# - GET /api/v1/storefront/products
# - GET /api/v1/analytics/metrics (fix 405 error)
```

**Tasks:**
- [ ] Review OpenAPI spec for missing endpoints
- [ ] Implement campaign management endpoints
- [ ] Implement target search functionality
- [ ] Fix analytics metrics endpoint method
- [ ] Add comprehensive error handling

#### 2.2 Fix Database Migrations
```python
# Make migrations database-agnostic or add conditional logic
```

**Tasks:**
- [ ] Review all migration files for PostgreSQL-specific syntax
- [ ] Add database type detection in migrations
- [ ] Create separate migration paths for PostgreSQL and SQLite
- [ ] Test migrations on both databases

### Phase 3: Testing & Validation (Tomorrow)

#### 3.1 Comprehensive Integration Testing
```bash
# Run full test suite with real services
```

**Tasks:**
- [ ] Create integration test environment with real databases
- [ ] Run smoke tests against all external APIs
- [ ] Validate data persistence across all domains
- [ ] Ensure metrics flow to Datadog
- [ ] Test error handling and recovery

#### 3.2 Performance Testing
```bash
# Ensure system can handle production load
```

**Tasks:**
- [ ] Run load tests with Locust
- [ ] Monitor resource usage during tests
- [ ] Identify and fix bottlenecks
- [ ] Validate rate limiting works correctly

### Phase 4: Production Readiness (Day 3)

#### 4.1 Security Hardening
```bash
# Ensure all secrets are properly managed
```

**Tasks:**
- [ ] Audit all environment variables for secrets
- [ ] Implement secret rotation capability
- [ ] Add API key encryption at rest
- [ ] Enable HTTPS for all endpoints
- [ ] Run security scan with Bandit

#### 4.2 Monitoring & Alerting
```bash
# Complete observability setup
```

**Tasks:**
- [ ] Configure Datadog dashboards for all metrics
- [ ] Set up alerts for critical thresholds
- [ ] Implement structured logging
- [ ] Add custom business metrics
- [ ] Create runbook for common issues

### Phase 5: Documentation & Deployment (Day 4)

#### 5.1 Complete Documentation
```markdown
# Document all fixes and configurations
```

**Tasks:**
- [ ] Update README with setup instructions
- [ ] Document all environment variables
- [ ] Create troubleshooting guide
- [ ] Add architecture diagrams
- [ ] Write API documentation

#### 5.2 Production Deployment
```bash
# Deploy to production environment
```

**Tasks:**
- [ ] Create production deployment checklist
- [ ] Set up CI/CD pipeline
- [ ] Configure auto-scaling
- [ ] Implement blue-green deployment
- [ ] Run final smoke tests in production

## Implementation Scripts

### Script 1: Fix Database Setup
```bash
#!/bin/bash
# fix_database.sh

# Stop existing containers
docker compose -f docker-compose.production.yml down

# Update .env with database password
echo "POSTGRES_PASSWORD=leadfactory_prod_2024" >> .env

# Start fresh with correct configuration
docker compose -f docker-compose.production.yml up -d postgres
sleep 10

# Run migrations
docker compose -f docker-compose.production.yml run --rm leadfactory-api python -m alembic upgrade head

# Verify tables created
docker exec leadfactory-postgres psql -U leadfactory -d leadfactory -c "\dt"
```

### Script 2: Validate Environment
```python
#!/usr/bin/env python3
# validate_env.py

import os
import sys

REQUIRED_VARS = [
    "DATABASE_URL",
    "REDIS_URL", 
    "YELP_API_KEY",
    "GOOGLE_PAGESPEED_API_KEY",
    "OPENAI_API_KEY",
    "SENDGRID_API_KEY",
    "STRIPE_SECRET_KEY",
    "DATADOG_API_KEY",
    "DATADOG_APP_KEY",
    "SENTRY_DSN"
]

missing = []
for var in REQUIRED_VARS:
    if not os.getenv(var):
        missing.append(var)
        
if missing:
    print(f"❌ Missing environment variables: {', '.join(missing)}")
    sys.exit(1)
else:
    print("✅ All required environment variables are set")
```

### Script 3: Run Complete Test Suite
```bash
#!/bin/bash
# run_complete_tests.sh

# 1. Unit tests
echo "Running unit tests..."
docker compose -f docker-compose.test.yml run --rm test pytest tests/unit -v

# 2. Integration tests  
echo "Running integration tests..."
docker compose -f docker-compose.test.yml run --rm test pytest tests/integration -v

# 3. Smoke tests
echo "Running smoke tests..."
python tests/smoke_prod/realistic_smoke.py

# 4. Load tests
echo "Running load tests..."
docker compose -f docker-compose.test.yml run --rm test locust -f tests/performance/locustfile.py --headless -u 10 -r 2 -t 60s

echo "All tests complete!"
```

## Success Criteria

1. **Database**: All tables created, data persists correctly
2. **APIs**: All external APIs return real data (not stubs)
3. **Endpoints**: 100% of documented endpoints return valid responses
4. **Metrics**: Datadog shows LeadFactory-specific metrics
5. **Tests**: All test suites pass with >95% coverage
6. **Performance**: <200ms p95 response time under load
7. **Security**: No high/critical vulnerabilities in scan
8. **Monitoring**: All alerts configured and tested

## Timeline

- **Day 1** (Today): Fix critical infrastructure issues
- **Day 2**: Implement missing features and fix migrations  
- **Day 3**: Testing and performance optimization
- **Day 4**: Security, monitoring, and documentation
- **Day 5**: Production deployment and verification

## Risk Mitigation

1. **Rollback Plan**: Keep previous working version tagged
2. **Feature Flags**: Implement flags for new features
3. **Gradual Rollout**: Deploy to staging first
4. **Monitoring**: Watch metrics closely after deployment
5. **On-Call**: Have team ready for first 48 hours

## Notes

- All database passwords should be strong and unique
- API keys should never be committed to git
- Use environment-specific configuration files
- Test each fix in isolation before integration
- Document all changes in CHANGELOG.md