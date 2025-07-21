# P3-007 - Fix CI Docker Test Execution
**Priority**: P3
**Status**: Not Started
**Estimated Effort**: 2 days
**Dependencies**: P0-003

## Goal & Success Criteria
Update main CI workflow to actually run tests inside Docker containers instead of directly on the GitHub Actions runner, ensuring test environment consistency and proper Docker integration.

### Success Criteria
1. All pytest commands execute inside Docker containers, not on runner
2. Coverage reports successfully extracted from Docker containers
3. Test execution time remains under 5 minutes (current target)
4. Coverage threshold enforcement (≥80%) continues to work
5. Docker image building and test execution integrated into workflow
6. Proper artifact extraction for coverage reports and test results
7. All existing test job dependencies and parallelism preserved

## Context & Background

### Business Value
- Eliminates environment-specific test failures and ensures consistent test execution across all environments (local, CI, production)
- Aligns with existing Dockerfile.test and Docker-based deployment strategy established in P0-003
- Enables proper Docker integration for CI/CD pipeline

### Problems Solved
- Current test.yml runs pytest directly on runner instead of inside Docker containers
- Environment inconsistencies between local Docker testing and CI execution
- Missing coverage report extraction from Docker containers
- Potential dependency conflicts between runner and container environments

### Current State
The existing test.yml workflow executes pytest commands directly on the GitHub Actions runner, which creates environment inconsistencies and doesn't validate the Docker-based deployment environment.

## Technical Approach

### Implementation Strategy
Transform the existing test.yml workflow to execute all test commands inside Docker containers while maintaining current performance targets and coverage reporting.

### Key Components
1. **Docker Container Integration**
   - Build test image in each job using existing Dockerfile.test
   - Mount temporary directories for coverage and test artifacts
   - Configure proper environment variables in container

2. **Coverage Report Extraction**
   - Use Docker volume mounting: `-v /tmp:/tmp`
   - Extract coverage.xml and coverage.html from container
   - Maintain existing codecov integration

3. **Performance Optimization**
   - Use Docker build cache for faster image builds
   - Optimize container startup time
   - Maintain parallel job execution

### Integration Points
- `.github/workflows/test.yml` - Primary workflow file to modify
- `Dockerfile.test` - Test container configuration to enhance
- Coverage reporting system - Extract reports from container
- GitHub Actions job orchestration - Maintain parallel execution

### Documentation & References
```yaml
- url: https://docs.docker.com/build/ci/github-actions/
  why: Official Docker CI/CD integration patterns for GitHub Actions

- url: https://docs.docker.com/build/ci/github-actions/test-before-push/
  why: Best practice pattern for testing Docker images before push

- url: https://github.com/pytest-dev/pytest-cov
  why: Coverage tool configuration for extracting reports from containers

- url: https://docs.github.com/en/actions/creating-actions/creating-a-docker-container-action
  why: GitHub Actions Docker container integration guidance

- file: .github/workflows/docker.yml
  why: Existing Docker build workflow pattern to extend

- file: Dockerfile.test
  why: Test container configuration to leverage

- file: .github/workflows/test.yml
  why: Current test workflow to transform
```

## Acceptance Criteria
1. All pytest commands execute inside Docker containers, not on runner
2. Coverage reports successfully extracted from Docker containers  
3. Test execution time remains under 5 minutes (current target)
4. Coverage threshold enforcement (≥80%) continues to work
5. Docker image building and test execution integrated into workflow
6. Proper artifact extraction for coverage reports and test results
7. All existing test job dependencies and parallelism preserved
8. Container cleanup occurs automatically after test completion
9. Error handling preserves existing failure reporting and logging
10. Performance optimization maintains current build speed targets

## Dependencies
- P0-003 Dockerize CI (must be complete for Docker infrastructure)
- docker/build-push-action@v6 (GitHub Action)
- docker/setup-buildx-action@v3 (GitHub Action)
- pytest-cov>=4.0.0 (Coverage extraction)
- Existing test.yml workflow structure

## Testing Strategy

### Unit Tests
- Test workflow changes on feature branch first
- Validate coverage report extraction works correctly
- Ensure all existing tests pass in Docker environment
- Verify performance targets are maintained

### Integration Tests
- End-to-end workflow validation
- Coverage report generation and extraction
- Multi-job parallel execution testing
- Docker container lifecycle management

### Performance Tests
- Build time regression testing
- Container startup time optimization
- Memory usage monitoring
- Parallel job execution efficiency

### Executable Validation Commands
```bash
# Build test image successfully
docker build -f Dockerfile.test -t leadfactory-test .

# Run unit tests in container
docker run --rm -v /tmp:/tmp -e DATABASE_URL=sqlite:///tmp/test.db -e USE_STUBS=true -e ENVIRONMENT=test -e SECRET_KEY=test-secret-key-for-ci -e PYTHONPATH=/app leadfactory-test pytest tests/unit -m "not slow and not flaky and not external" --cov=. --cov-report=xml --cov-report=html

# Verify coverage extraction
test -f coverage.xml && echo "Coverage report extracted successfully"

# Run integration tests in container
docker run --rm -e DATABASE_URL=sqlite:///tmp/test.db -e USE_STUBS=true -e ENVIRONMENT=test -e SECRET_KEY=test-secret-key-for-ci -e PYTHONPATH=/app leadfactory-test pytest tests/integration -k "test_health or test_database or test_stub_server"

# Verify Docker container cleanup
docker ps -a | grep leadfactory-test || echo "Containers cleaned up properly"
```

## Rollback Plan

### Immediate Rollback
1. Revert `.github/workflows/test.yml` to previous version
2. Keep `Dockerfile.test` changes (they won't affect existing workflow)
3. Maintain backup of original workflow file in commit history
4. Use feature flags or workflow conditions for gradual rollout

### Rollback Conditions
- Test execution time exceeds 7 minutes (40% degradation)
- Coverage extraction fails for more than 2 consecutive runs
- Docker build failures exceed 10% of total runs
- Critical test failures not present in runner-based execution

### Rollback Procedure
```bash
# Immediate rollback command
git revert <commit-hash> --no-edit
git push origin main

# Verify rollback success
curl -X POST https://api.github.com/repos/owner/repo/actions/workflows/test.yml/dispatches
```

## Validation Framework

### Required for CI/DevOps tasks:
- [ ] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [ ] Recursive CI-log triage automation for Docker failures
- [ ] Branch protection & required status checks
- [ ] Security scanning (Docker image vulnerability scanning)
- [ ] Release & rollback procedures for workflow changes

### Recommended:
- [ ] Docker build caching optimization
- [ ] Container resource limits to prevent OOM
- [ ] Automated workflow testing on feature branches
- [ ] Performance regression monitoring for build times

### Security Considerations
- Use non-root user in Docker containers (already configured)
- Limit container resource usage
- No sensitive environment variables in container
- Use official Python base images only
- Scan Docker images for vulnerabilities in separate workflow

### Performance Considerations
- Docker image build time: Target <2 minutes with proper caching
- Container startup time: Target <30 seconds
- Test execution time: Maintain current <5 minute total target
- Coverage extraction: Minimal overhead with volume mounting
- Container cleanup: Automatic with `--rm` flag

### Error Handling Strategy
- Graceful fallback if Docker build fails
- Proper cleanup of Docker containers and volumes
- Maintain existing timeout and failure policies
- Preserve test failure reporting and logging

### Feature Flag Requirements
- `CI_USE_DOCKER_TESTS` - Environment variable to enable/disable Docker test execution
- Conditional workflow steps based on flag for safe rollout
- Maintain existing runner-based tests as fallback option

