# PRP-1060 - Acceptance + Deploy Runner Persona

**Priority**: P0
**Status**: new
**Estimated Effort**: 3 days
**Dependencies**: PRP-1059 (Lua Promotion Script)

## Goal

Implement containerized acceptance testing and SSH deployment automation through SuperClaude profiles system, enabling reliable end-to-end pipeline from branch merge through production deployment with comprehensive evidence validation.

**Specific Goal**: Create `profiles/acceptance.yaml` configuration and GHCR-based container runner for `/acceptance` command integration with evidence validation performance targets of <3min for p95 PRP completion.

## Why

- **Business value**: Enables fully automated deployment pipeline with acceptance testing, reducing deployment risk and time-to-production from manual hours to automated minutes
- **Integration**: Builds on PRP-1059 (Lua Promotion Script) to provide automated deployment capabilities with evidence validation for production readiness
- **Problems solved**: 
  - Eliminates manual deployment process prone to human error and inconsistency
  - Provides automated acceptance testing before production deployment
  - Ensures evidence validation and rollback capabilities for failed deployments
  - Enables continuous delivery with quality gates and performance monitoring

## What

**Core Implementation**: SuperClaude profile-based acceptance testing runner with GHCR containerization, SSH deployment automation, and comprehensive evidence validation framework.

### Success Criteria

- [ ] Acceptance profile `profiles/acceptance.yaml` created with `/acceptance` command integration
- [ ] GHCR container `ghcr.io/leadfactory/acceptance-runner:latest` built and published
- [ ] SSH deployment automation configured using .env DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY_PATH
- [ ] VPS deployment script `~/bin/deploy.sh` implemented with health checks
- [ ] Evidence validation sets `acceptance_passed=true` and `deploy_ok=true` in Redis
- [ ] Performance target: <3min for p95 PRP completion achieved
- [ ] Rollback mechanism implemented for failed deployments
- [ ] Coverage ≥ 80% on tests including container build and SSH deployment
- [ ] Integration with PRP-1059 Lua promotion script for atomic state transitions

## All Needed Context

### Documentation & References

```yaml
- url: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
  why: Official GHCR documentation for container publishing and authentication

- url: https://runcloud.io/blog/setup-docker-github-actions-ci-cd
  why: GitHub Actions CI/CD pipeline patterns for Docker deployment

- url: https://dev.to/ikurotime/deploy-docker-containers-in-vps-with-github-actions-2e28
  why: VPS Docker deployment automation via SSH

- url: https://docs.servicestack.net/ssh-docker-compose-deploment
  why: SSH Docker deployment best practices and security patterns

- url: https://github.com/NomenAK/SuperClaude
  why: SuperClaude framework profiles and persona integration patterns

- file: examples/deploy_workflow.yml
  why: Existing GHCR and SSH deployment workflow patterns to follow

- file: .env.example
  why: Environment variable patterns for deployment configuration

- file: .claude/PRPs/PRP-1059-lua-promotion-script.md
  why: Redis evidence validation and atomic promotion dependency
```

### Current Codebase Tree

```
.
├── examples/
│   ├── deploy_workflow.yml           # Existing GHCR/SSH patterns
│   └── docker_postgres_deploy.yml    # Docker deployment examples
├── .env.example                      # Environment configuration patterns
├── docker-compose.yml                # Container orchestration
├── Dockerfile                        # Application container build
├── scripts/
│   ├── deploy.sh                     # Deployment script patterns
│   └── verify_deployment.sh          # Health check patterns
└── infra/
    └── redis_queue.py                # Queue integration from PRP-1058
```

### Desired Codebase Tree

```
profiles/
├── acceptance.yaml                   # SuperClaude acceptance profile
└── __init__.py                      # Profile module initialization

containers/
├── acceptance/
│   ├── Dockerfile                   # Acceptance runner container
│   ├── requirements.txt             # Container dependencies
│   ├── entrypoint.sh               # Container startup script
│   └── acceptance_runner.py         # Acceptance testing logic
└── scripts/
    └── build_containers.sh          # Container build automation

deployment/
├── ssh_deployer.py                  # SSH deployment automation
├── health_checker.py               # Post-deployment verification
└── evidence_validator.py           # Evidence collection and validation

tests/unit/acceptance/
├── test_acceptance_profile.py       # Profile configuration tests
├── test_ssh_deployer.py            # SSH deployment tests
└── test_evidence_validator.py      # Evidence validation tests

tests/integration/
└── test_acceptance_pipeline.py     # End-to-end acceptance testing
```

## Technical Implementation

### Integration Points

- `profiles/acceptance.yaml` - SuperClaude profile configuration for `/acceptance` command
- `containers/acceptance/` - GHCR-based acceptance runner container
- `deployment/ssh_deployer.py` - SSH deployment automation module
- `deployment/evidence_validator.py` - Evidence validation and Redis integration
- Existing `infra/redis_queue.py` patterns for evidence storage
- Integration with `.env` configuration for deployment credentials

### Implementation Approach

**Phase 1: Profile Configuration**
- Create SuperClaude profile `profiles/acceptance.yaml` for `/acceptance` command
- Configure container invocation and evidence validation requirements
- Implement profile loading and validation in core framework
- Test profile activation and command routing

**Phase 2: Container Development**
- Design acceptance runner container with testing frameworks
- Build GHCR container with Docker multi-stage build for optimization
- Implement acceptance testing logic with FastAPI, pytest, and Playwright
- Configure container authentication and environment variable management

**Phase 3: SSH Deployment Automation**
- Implement SSH deployment module using paramiko or fabric
- Configure secure key management using .env DEPLOY_KEY_PATH
- Create VPS deployment script `~/bin/deploy.sh` with health checks
- Implement rollback mechanisms for failed deployments

**Phase 4: Evidence Integration**
- Integrate with PRP-1059 Lua promotion script for evidence validation
- Implement Redis evidence storage with `acceptance_passed` and `deploy_ok` flags
- Configure performance monitoring and alerting for deployment pipeline
- Implement comprehensive logging and audit trails

### Error Handling Strategy

- **Container Build Failures**: Automated retry with exponential backoff, fallback to previous container version
- **SSH Connection Failures**: Connection retry logic, credential validation, network diagnostics
- **Deployment Failures**: Automatic rollback to previous version, health check validation
- **Evidence Validation Failures**: Atomic rollback using PRP-1059 Lua script, comprehensive error logging
- **Performance Degradation**: Monitoring alerts, automatic scaling, resource optimization

## Validation Gates

### Executable Tests

```bash
# Syntax/Style
ruff check profiles/ containers/ deployment/ --fix && mypy .

# Unit Tests
pytest tests/unit/acceptance/ -v --cov=profiles --cov=deployment/

# Integration Tests
pytest tests/integration/test_acceptance_pipeline.py -v

# Container Build Tests
docker build -t test-acceptance containers/acceptance/
docker run --rm test-acceptance pytest

# SSH Deployment Tests (with mock VPS)
pytest tests/integration/test_ssh_deployment.py -v
```

### Missing-Checks Validation

**Required for CI/DevOps tasks:**
- [ ] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [ ] Recursive CI-log triage automation for container build failures
- [ ] Branch protection & required status checks
- [ ] Security scanning (Dependabot, Trivy, container vulnerability scanning)
- [ ] Release & rollback procedures with automated testing
- [ ] Container security scanning and optimization
- [ ] SSH key rotation and access management

**Recommended:**
- [ ] Performance regression budgets for deployment pipeline
- [ ] Automated container registry cleanup and versioning
- [ ] Multi-environment deployment testing (staging → production)
- [ ] Disaster recovery testing and validation

## Dependencies

- **PRP-1059 (Lua Promotion Script)**: Required for atomic evidence validation and state transitions
- **GitHub Container Registry**: GHCR access for container publishing and distribution
- **Docker**: Version 20.10+ for multi-stage builds and container optimization
- **SSH Access**: VPS deployment target with configured SSH keys and sudo access
- **Redis Server**: Version 6.0+ for evidence storage integration with PRP-1059
- **SuperClaude Framework**: Profile system integration for `/acceptance` command routing

**Python Dependencies**:
- `paramiko>=2.11.0` - SSH connection and deployment automation
- `docker>=6.0.0` - Container management and building
- `pydantic>=1.10.0` - Configuration validation and evidence schemas
- `pytest-docker>=0.12.0` - Container testing framework

## Testing Strategy

**Unit Tests**: Component isolation testing with mocks
- Test profile configuration loading and validation
- Test SSH deployment logic with mock connections
- Test evidence validation schemas and Redis integration
- Test container build and configuration management

**Integration Tests**: End-to-end pipeline testing
- Test complete acceptance pipeline from profile activation to deployment
- Test container build, publish, and deployment workflow
- Test SSH deployment with real connection to test environment
- Test evidence validation and atomic state transitions

**Performance Tests**: Pipeline performance and reliability
- Benchmark deployment pipeline for <3min p95 performance target
- Load testing for concurrent deployment scenarios
- Container startup time optimization and resource usage profiling
- SSH connection performance and reliability testing

**Security Tests**: Deployment security and access control
- Test SSH key management and rotation procedures
- Test container security scanning and vulnerability management
- Test secret management and environment variable security
- Test deployment rollback and disaster recovery procedures

## Rollback Plan

**Step 1: Immediate Rollback**
- Revert to previous container version using GHCR tag rollback
- Disable acceptance profile: `ACCEPTANCE_PROFILE_ENABLED=false`
- Switch to manual deployment process with existing scripts
- Notify operations team of rollback status

**Step 2: Deployment Rollback**
- Execute VPS rollback using `~/bin/rollback.sh` script
- Restore previous application version from backup
- Validate health checks and system functionality
- Update load balancer and DNS if necessary

**Step 3: Evidence Cleanup**
- Clear failed evidence using PRP-1059 Lua script rollback
- Reset Redis state to previous known good configuration
- Update monitoring and alerting systems
- Document rollback reason and resolution steps

**Trigger Conditions**: Container build failures >3 attempts, SSH deployment failures >2 attempts, health check failures >5 minutes, performance degradation >5min p95

## Validation Framework

**Pre-commit Validation**:
```bash
ruff check profiles/ containers/ deployment/ --fix && mypy .
pytest tests/unit/acceptance/ -v --cov=profiles --cov=deployment/ --cov-fail-under=80
```

**Container Validation**:
```bash
docker build -t ghcr.io/leadfactory/acceptance-runner:test containers/acceptance/
docker run --rm ghcr.io/leadfactory/acceptance-runner:test pytest tests/
trivy image ghcr.io/leadfactory/acceptance-runner:test
```

**Deployment Validation**:
```bash
pytest tests/integration/test_acceptance_pipeline.py -v
pytest tests/performance/test_deployment_performance.py --benchmark-only
scripts/verify_deployment.sh --test-environment
```

**Production Validation**:
- Container security review (no privileged access, minimal attack surface)
- SSH deployment security audit (key rotation, access logging)
- Performance benchmarking (≤3min @ p95 deployment completion)
- Evidence validation integrity verification with PRP-1059 integration