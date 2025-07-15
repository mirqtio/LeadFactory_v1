# Standard Validation Commands

## Overview

This document contains the canonical validation command sequences used by developers to verify code quality and prevent CI failures.

## Primary Validation - BPCI (Bulletproof CI)

The primary validation system is BPCI, which runs the exact same Docker-based test environment as GitHub CI:

```bash
# Run full CI validation locally
make bpci
```

This command:
- Builds the test Docker image
- Starts PostgreSQL and stub server containers
- Runs the complete test suite
- Generates coverage and JUnit reports
- Provides clear pass/fail status

## Quick Validation

For rapid iteration during development:

```bash
# Fast validation (30 seconds)
make quick-check
```

This runs:
- Code formatting (black + isort)
- Linting (flake8)
- Basic unit tests

## Docker-based Test Validation

For running tests in Docker without full BPCI:

```bash
# Build and run tests in Docker
make docker-test
```

## Coverage Validation

### Check Test Coverage (80% minimum)
```bash
# Run tests with coverage
coverage run -m pytest tests/unit
coverage report --fail-under=80

# Generate HTML coverage report
coverage html
open htmlcov/index.html
```

### High Coverage Target (95%)
```bash
# For critical modules requiring 95% coverage
coverage run -m pytest tests/unit
coverage report --fail-under=95
```

## Python Syntax Validation

```bash
# Verify all Python files compile
python -m py_compile $(git ls-files "*.py")

# Check for import errors
python -m compileall . -q
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
docker run --rm leadfactory-test

# Or use BPCI for full validation
make bpci
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
make bpci
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