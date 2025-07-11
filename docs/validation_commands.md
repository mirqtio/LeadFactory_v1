# Standard Validation Commands

## Overview

This document contains the canonical validation command sequences used by the orchestrator and developers to verify task completion.

## Wave A Validation (80% Coverage)

```bash
# Standard Wave A validation script
bash scripts/validate_wave_a.sh
```

### Manual Wave A validation:
```bash
# 1. Run KEEP test suite (excluding slow and future tests)
pytest -m "not phase_future and not slow" -q

# 2. Check unit test coverage (80% required)
coverage run -m pytest tests/unit
coverage report --fail-under=80

# 3. Verify Python syntax
python -m py_compile $(git ls-files "*.py")

# 4. Optional Docker validation
docker build -f Dockerfile.test -t leadfactory-test .
docker run --rm leadfactory-test pytest -q
```

## Wave B Validation (95% Coverage)

```bash
# Standard Wave B validation script
bash scripts/validate_wave_b.sh
```

### Manual Wave B validation:
```bash
# 1. Run full test suite
pytest -q

# 2. Check unit test coverage (95% required)
coverage run -m pytest tests/unit
coverage report --fail-under=95

# 3. Verify Python syntax
python -m py_compile $(git ls-files "*.py")

# 4. Mandatory Docker validation for Wave B
make docker-test
```

## Task-Specific Validations

### Database Tasks (P0-004, P0-007, P0-012)
```bash
# Check migrations
alembic check
alembic upgrade head

# Verify database connectivity
docker-compose exec postgres pg_isready
```

### Docker Tasks (P0-003, P0-011, P0-012)
```bash
# Build test image
docker build -f Dockerfile.test -t leadfactory-test .

# Run tests in container
docker run --rm leadfactory-test make validate-standard
```

### Deployment Tasks (P0-011, P0-012)
```bash
# Post-deploy smoke tests
pytest tests/smoke/test_health.py --base-url=https://leadfactory.example.com

# Health check
curl -f https://leadfactory.example.com/health || exit 1
```

## Rollback Validation

After running rollback:
```bash
# Verify rollback succeeded
make rollback TASK_ID=<task>

# Re-run validation to ensure system still works
make validate-standard
```

## Common Validation Patterns

### Check for Deprecated Code
```bash
# Ensure no Yelp references
grep -r "yelp" --exclude-dir=.git --exclude-dir=migrations . | wc -l
# Should return 0
```

### Verify Dependencies
```bash
# Check all dependencies installable
pip install -r requirements.txt
pip check
```

### Lint and Format
```bash
# Run linting
make lint

# Check formatting
black . --check
isort . --check
```

## Orchestrator JSON Output

The orchestrator expects validation results in this format:
```json
{
  "event": "validation_complete",
  "prp": "P0-001",
  "status": "passed",
  "coverage": 82.5,
  "tests_passed": 145,
  "tests_failed": 0,
  "timestamp": "2025-07-11T10:30:00Z"
}
```

On failure:
```json
{
  "event": "validation_failed",
  "prp": "P0-001",
  "status": "failed",
  "reason": "Coverage below threshold: 78% < 80%",
  "timestamp": "2025-07-11T10:30:00Z"
}
```

## Environment-Specific Validations

### Development
```bash
# Ensure stubs are used
grep "USE_STUBS=true" .env || echo "WARNING: Stubs not enabled!"
```

### Production
```bash
# Ensure stubs are NOT used
if grep -q "USE_STUBS=true" .env.production; then
  echo "ERROR: Stubs enabled in production!"
  exit 1
fi
```

## Performance Validation

### Check response times
```bash
# API response time < 500ms
time curl -s http://localhost:8000/health > /dev/null
```

### Memory usage
```bash
# Check for memory leaks
docker stats --no-stream leadfactory_app
```

## Security Validation

### Check for exposed secrets
```bash
# Scan for potential secrets
git secrets --scan

# Verify no API keys in code
grep -r "sk-" --exclude-dir=.git . || true
grep -r "SG." --exclude-dir=.git . || true
```