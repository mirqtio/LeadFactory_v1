# Rollback Register

This document consolidates all rollback procedures from PRPs for quick operational access.

## Quick Reference Table

| Task ID | Feature | Rollback Command/Procedure |
|---------|---------|---------------------------|
| P0-000 | Prerequisites Check | Delete setup.sh if created |
| P0-001 | Fix D4 Coordinator | `git revert` to restore previous coordinator logic |
| P0-002 | Wire Prefect Full Pipeline | Delete flows/full_pipeline_flow.py |
| P0-003 | Dockerize CI | Remove Dockerfile.test and revert CI workflow |
| P0-004 | Database Migrations | Use `alembic downgrade` to previous revision |
| P0-005 | Environment & Stub Wiring | Revert config.py changes |
| P0-006 | Green KEEP Test Suite | Re-add xfail markers to unblock CI |
| P0-007 | Health Endpoint | Remove /health route from API |
| P0-008 | Test Infrastructure | Revert conftest.py and pytest.ini changes |
| P0-009 | Remove Yelp Remnants | Not applicable - Yelp already removed |
| P0-010 | Fix Missing Dependencies | Restore previous requirements.txt |
| P0-011 | Deploy to VPS | Delete deploy.yml workflow |
| P0-012 | Postgres on VPS | Stop postgres container, keep volume for data recovery |
| P0-013 | CI/CD Stabilization | Revert workflow, Docker, or dependency changes that break existing successful builds |
| P0-014 | Test Suite Re-enablement | Fallback to prior ignore list, isolate failing files |
| P0-020 | Design System Tokens | Remove design tokens file and revert to inline CSS values |
| P0-021 | Lead Explorer | Remove lead_explorer module and revert API routes |
| P0-022 | Batch Report Runner | Remove batch_runner module and WebSocket endpoints |
| P0-023 | Lineage Panel | Drop report_lineage table and remove API endpoints |
| P0-024 | Template Studio | Remove template_studio module and UI components |
| P0-025 | Scoring Playground | Remove scoring_playground module and Sheets integration |
| P0-026 | Governance | Drop role and audit_log_global tables, remove RBAC middleware |
| P1-010 | SEMrush Client | Feature flag ENABLE_SEMRUSH=false |
| P1-020 | Lighthouse Audit | Remove lighthouse.py and uninstall Playwright |
| P1-030 | Visual Rubric | Feature flag ENABLE_VISUAL_ANALYSIS=false |
| P1-040 | LLM Heuristic | Feature flag ENABLE_LLM_AUDIT=false |
| P1-050 | Gateway Cost Ledger | Drop gateway_cost_ledger table |
| P1-060 | Cost Guardrails | Set all guardrail limits to None |
| P1-070 | DataAxle Client | Feature flag ENABLE_DATAAXLE=false |
| P1-080 | Bucket Enrichment | Disable Prefect schedule |
| P2-010 | Unit Economics Views | Drop unit economics views |
| P2-020 | Unit Economics PDF | Remove economics section from PDF template |
| P2-030 | Email Personalization | Revert to V1 email templates |
| P2-040 | Orchestration Budget | Remove budget stop decorator from flows |

## Detailed Rollback Procedures

### Database Rollbacks

For tasks involving database changes, always backup first:
```bash
# Backup current database
pg_dump leadfactory > backup_$(date +%Y%m%d_%H%M%S).sql

# For Alembic migrations
alembic downgrade -1  # Roll back one migration
alembic history      # View migration history
```

### Feature Flag Rollbacks

For feature-flagged functionality:
```bash
# Set in .env or environment
ENABLE_SEMRUSH=false
ENABLE_VISUAL_ANALYSIS=false
ENABLE_LLM_AUDIT=false
ENABLE_DATAAXLE=false
ENABLE_TEMPLATE_STUDIO=false
ENABLE_REPORT_LINEAGE=false
ENABLE_RBAC=false
```

### Docker/CI Rollbacks

For containerization or CI changes:
```bash
# Revert to previous Docker image
docker pull ghcr.io/leadfactory/app:stable
docker stop leadfactory && docker rm leadfactory
docker run -d --name leadfactory ghcr.io/leadfactory/app:stable

# Revert GitHub Actions workflow
git checkout main -- .github/workflows/
git commit -m "Revert CI workflows to stable"
git push
```

### API Route Rollbacks

For new API endpoints:
```python
# Comment out router registration in main.py
# app.include_router(lead_explorer_router, prefix="/api/leads")
# app.include_router(batch_runner_router, prefix="/api/batch")
# app.include_router(lineage_router, prefix="/api/lineage")
```

### Emergency Rollback Script

For critical failures requiring immediate rollback:
```bash
#!/bin/bash
# emergency_rollback.sh

# 1. Disable all new features
export ENABLE_SEMRUSH=false
export ENABLE_VISUAL_ANALYSIS=false
export ENABLE_LLM_AUDIT=false
export ENABLE_DATAAXLE=false
export ENABLE_TEMPLATE_STUDIO=false
export ENABLE_REPORT_LINEAGE=false
export ENABLE_RBAC=false

# 2. Rollback database
alembic downgrade 88e2723  # Last stable migration

# 3. Deploy previous stable version
docker pull ghcr.io/leadfactory/app:v1.0.0
docker-compose down
docker-compose up -d

# 4. Clear caches
redis-cli FLUSHALL

echo "Emergency rollback complete"
```

## Rollback Testing

Before implementing any PRP, test the rollback procedure:
1. Deploy the feature to staging
2. Execute the rollback procedure
3. Verify system returns to previous state
4. Document any issues in this register

## Contact for Rollback Support

- **On-call Engineer**: Check PagerDuty
- **Database Admin**: #database-support Slack channel
- **CI/CD Issues**: #devops Slack channel
- **Emergency**: Follow incident response procedure in runbooks/