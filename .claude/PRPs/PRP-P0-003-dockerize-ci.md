# PRP: Dockerize CI

## Task ID: P0-003
## Wave: A

## Business Logic (Why This Matters)
"Works on my machine" disparities disappear when tests always run in the same image. Containerized CI ensures consistent test execution across local development and GitHub Actions, eliminating environment-specific failures.

## Overview
Create a complete Docker test environment and modify CI workflow to build and run all tests inside Docker containers, ensuring the KEEP test suite passes in the containerized environment.

## Dependencies
- P0-002 (Wire Prefect Pipeline)

**Note**: Depends on P0-002 completing successfully in the same CI run.

## Outcome-Focused Acceptance Criteria
GitHub Actions logs show:
- Docker image successfully built from Dockerfile.test
- All tests executed inside the Docker container
- KEEP suite green inside container
- Coverage ≥ 80% maintained
- Image pushed to GitHub Container Registry (GHCR)

### Task-Specific Acceptance Criteria
- [ ] Multi-stage Dockerfile.test with proper test target
- [ ] All Python dependencies correctly installed in container
- [ ] Postgres service configured in docker-compose.test.yml
- [ ] Stub server accessible from test container
- [ ] CI workflow modified to build image and run tests inside container
- [ ] Test output and coverage reports extracted from container
- [ ] Container logs preserved in CI artifacts

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (test execution time within 20% of baseline)
- [ ] Only modify files within specified integration points (no scope creep)

## Integration Points
- Create `Dockerfile.test` (multi-stage build optimized for tests)
- Create `docker-compose.test.yml` (orchestrate test services)
- Update `.dockerignore` (exclude unnecessary files from build)
- Update `.github/workflows/test.yml` (run tests in Docker)
- Update `.github/workflows/main.yml` (ensure main workflow uses Docker)

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
```bash
# Docker build succeeds
docker build -f Dockerfile.test -t leadfactory-test .

# Tests run successfully inside container
docker run --rm leadfactory-test pytest -q

# Full KEEP suite passes in container
docker run --rm leadfactory-test pytest -m "not slow and not phase_future" --tb=short

# Coverage maintained
docker run --rm leadfactory-test pytest --cov=leadfactory --cov-report=term-missing

# Integration with services works
docker-compose -f docker-compose.test.yml run --rm test pytest tests/integration/
```

## Example: Dockerfile.test for CI

```dockerfile
# Multi-stage build for test environment
FROM python:3.11.0-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Test stage
FROM base as test

# Copy application code
COPY . .

# Set environment variables for testing
ENV PYTHONPATH=/app
ENV USE_STUBS=true
ENV DATABASE_URL=postgresql://postgres:postgres@postgres:5432/leadfactory_test

# Run tests as default command
CMD ["pytest", "-m", "not slow and not phase_future", "--tb=short", "--cov=leadfactory", "--cov-report=term-missing"]
```

## Example: docker-compose.test.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: leadfactory_test
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  test:
    build:
      context: .
      dockerfile: Dockerfile.test
      target: test
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/leadfactory_test
      USE_STUBS: "true"
      PYTHONPATH: /app
    volumes:
      - ./coverage:/app/coverage
    command: pytest -m "not slow and not phase_future" --tb=short --cov=leadfactory --cov-report=html:coverage/html --cov-report=term
```

## Example: Updated .github/workflows/test.yml

```yaml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build test image
      run: docker build -f Dockerfile.test -t leadfactory-test .
    
    - name: Run tests in Docker
      run: |
        docker-compose -f docker-compose.test.yml run --rm test \
          pytest -m "not slow and not phase_future" \
          --tb=short \
          --cov=leadfactory \
          --cov-report=term-missing \
          --cov-report=xml:coverage.xml \
          --junitxml=junit.xml
    
    - name: Extract test results
      if: always()
      run: |
        docker cp $(docker-compose -f docker-compose.test.yml ps -q test):/app/coverage.xml ./coverage.xml || true
        docker cp $(docker-compose -f docker-compose.test.yml ps -q test):/app/junit.xml ./junit.xml || true
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: |
          junit.xml
          coverage.xml
    
    - name: Clean up
      if: always()
      run: docker-compose -f docker-compose.test.yml down -v
```

## Reference Documentation
- Docker best practices for Python: https://docs.docker.com/language/python/
- GitHub Actions Docker documentation: https://docs.github.com/en/actions/creating-actions/dockerfile-support-for-github-actions
- pytest-docker documentation: https://github.com/avast/pytest-docker

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure P0-002 shows "completed"
- Verify CI is currently green before starting
- Ensure Docker is installed locally for testing

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running (check with `docker info`)
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

### Step 3: Implementation
1. Create `Dockerfile.test` with multi-stage build
2. Create `docker-compose.test.yml` for service orchestration
3. Update `.dockerignore` to exclude unnecessary files
4. Update `.github/workflows/test.yml` to use Docker
5. Update `.github/workflows/main.yml` to ensure consistency
6. Test locally with docker-compose
7. Ensure no deprecated features (see CURRENT_STATE.md)

### Step 4: Testing
- Build image locally: `docker build -f Dockerfile.test -t leadfactory-test .`
- Run tests in container: `docker-compose -f docker-compose.test.yml run --rm test`
- Verify KEEP suite passes
- Check coverage meets 80% threshold
- Ensure test artifacts are properly extracted

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- CI workflow must show tests running in Docker
- Coverage reports must be accessible
- Commit with descriptive message: `fix(P0-003): Dockerize CI - run all tests in containers`

## Validation Commands
```bash
# Build and test locally
docker build -f Dockerfile.test -t leadfactory-test .
docker-compose -f docker-compose.test.yml run --rm test

# Verify specific test suites
docker run --rm leadfactory-test pytest tests/unit/ -v
docker run --rm leadfactory-test pytest tests/integration/ -v
docker run --rm leadfactory-test pytest -m "not slow and not phase_future"

# Check coverage
docker run --rm leadfactory-test pytest --cov=leadfactory --cov-report=term-missing

# Run standard validation
bash scripts/validate_wave_a.sh

# Verify CI changes
act -j test  # If using act for local GitHub Actions testing
```

## Rollback Strategy
**Rollback Steps:**
1. Revert changes to `.github/workflows/test.yml` and `.github/workflows/main.yml`
2. Remove `Dockerfile.test` and `docker-compose.test.yml`
3. Restore original CI workflow
4. Ensure tests still pass in non-containerized environment

**Rollback Command:**
```bash
git revert HEAD --no-edit
git push origin main
```

## Security Considerations
- Use specific Python version tags (not `:latest`)
- Don't include secrets in Docker images
- Use `.dockerignore` to exclude sensitive files
- Run containers with minimal privileges
- Scan images for vulnerabilities in CI

## Performance Considerations
- Use Docker layer caching effectively
- Cache pip dependencies between builds
- Use multi-stage builds to minimize image size
- Consider using BuildKit for improved performance
- Monitor CI execution time to ensure < 20% regression

## Feature Flag Requirements
No new feature flag required - this is infrastructure improvement that doesn't affect application behavior.

## Success Criteria
- [ ] All specified tests passing in Docker containers
- [ ] CI workflow successfully builds and runs tests in Docker
- [ ] Coverage ≥ 80% maintained
- [ ] Test artifacts properly extracted and uploaded
- [ ] CI execution time within acceptable range
- [ ] No regression in test reliability
- [ ] Documentation updated to reflect new workflow

## Critical Context

### From CLAUDE.md (Project Instructions)
- Always create Pytest unit tests for new features
- Tests should live in a /tests folder mirroring the main app structure
- Ensure overall test coverage ≥ 80% after implementation
- Use python_dotenv and load_env() for environment variables

### From CURRENT_STATE.md (Current State vs PRD)
- Infrastructure: Ubuntu VPS + Docker (not Mac Mini)
- CI/CD: GitHub Actions → GHCR push → SSH deploy workflow
- Test Coverage Requirements: >80% coverage on core modules
- Integration tests: Must pass in Docker, not just locally

**IMPORTANT**: This PRP ensures that ALL tests, including the KEEP suite, run inside Docker containers in CI. This addresses the validation gap where the CI wasn't actually running tests in Docker.