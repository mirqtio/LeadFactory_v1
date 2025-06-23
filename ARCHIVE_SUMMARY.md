# Project Organization Summary

## Files Moved to Archive

### Documentation (archive/documentation/)
- CI_STATUS_SUMMARY.md
- DEPLOYMENT_CHECKLIST.md
- DEPLOYMENT_INSTRUCTIONS.md
- DEPLOYMENT_STATUS.md
- GRAFANA_STATUS.md
- HOW_TO_FIX_ALL_TESTS.md
- PHASE_05_IMPLEMENTATION_GUIDE.md
- PRD_Update.md
- PRODUCTION_READY_SUMMARY.md
- SMOKE_TEST_RESULTS.md
- TASK_PLAN_SUMMARY.md
- TEST_RESULTS_SUMMARY.md

### Deployment (archive/deployment/)
- DEPLOYMENT.md
- LOCAL_DOCKER_DEPLOYMENT.md
- leadfactory.service

### Testing (archive/testing/)
- api_smoke_test_*.json
- deployment_test_*.json
- test.db

### Analysis (archive/analysis/)
- gap_analysis_phase05.md
- gap_remediation_tasks.json

### Miscellaneous (archive/misc/)
- audit_script_output.log
- griffe/
- leadfactory_value_model_v2*.tar.gz
- taskmaster_plan.json

## Files Organized into Subdirectories

### Docker Files (docker/)
- docker-compose.production.yml
- docker-compose.secrets.yml
- docker-compose.test.yml
- Dockerfile.stub
- Dockerfile.test

### Scoring Rules (config/scoring/)
- scoring_rules_medical.yaml
- scoring_rules_restaurant.yaml

### Nginx Config (nginx/)
- nginx.conf

## Cleaned Up
- Removed __pycache__
- Removed .pytest_cache
- Removed leadfactory.egg-info
- Removed duplicate .env.test

## Root Directory Now Contains

Essential files only:
- Configuration files (.env, .env.example, *.ini, *.yml)
- Core Python files (main.py, setup.py)
- Requirements files
- Main documentation (README.md, PRD.md, CLAUDE.md)
- Build files (Dockerfile, Makefile)
- All module directories (d0_gateway, d1_targeting, etc.)
- Supporting directories (alembic, config, core, docs, scripts, tests, etc.)