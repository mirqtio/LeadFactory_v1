# PRP-1061 - Coverage / Lint Bot

**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 3 days
**Dependencies**: PRP-1059

## Goal & Success Criteria

Implement automated quality gate enforcement that blocks low-quality changes at the dev_queue with comprehensive Ruff linting and 80%+ coverage validation, generating visual coverage badges and evidence-based promotion criteria.

**Specific Goal**: Create SuperClaude profile-based quality enforcement bot that automatically validates code quality and test coverage before allowing PRP progression through the Redis queue system.

## Context & Background

- **Business value**: Prevents low-quality code from entering development workflow, maintaining production readiness standards and reducing technical debt accumulation by 50%+ through automated enforcement
- **Integration**: Works with PRP-1059 (Lua Promotion Script) Redis queue system to enforce quality gates before development work begins, providing atomic evidence-based promotion criteria
- **Problems solved**: 
  - Manual quality checks causing inconsistent enforcement and developer productivity loss
  - Coverage regression allowing untested code into production builds
  - Inconsistent linting standards across development team
  - Lack of automated quality enforcement in development pipeline leading to CI failures

**Current State**: Existing quality checks use manual `make lint` and `make format` commands with flake8, black, and isort. Coverage tracking exists but lacks enforcement thresholds and automated badge generation.

**Research Context**: Based on 2024 best practices for Ruff linting, pytest-cov automation, pre-commit hooks integration, and coverage badge generation patterns from research findings in `.claude/research_cache/research_PRP-1061.txt`.

## Technical Approach

### Implementation Strategy

**Phase 1: Ruff Configuration Migration**
- Analyze existing flake8/black/isort configuration in Makefile and create unified Ruff config
- Replace multi-tool approach with single `pyproject.toml` configuration
- Configure zero-tolerance rules: E501 (line length), F401 (unused imports), PD* (pandas-vet rules)
- Enable auto-fixing for safe corrections with strict mode for critical errors

**Phase 2: Coverage Enforcement System**
- Extend existing pytest-cov configuration with `--cov-fail-under=80` threshold enforcement
- Generate XML reports for badge integration using shields.io JSON endpoint pattern
- Implement coverage badge generation script using tj-actions/coverage-badge-py patterns
- Create automated badge updates with GitHub Actions integration

**Phase 3: SuperClaude Profile Integration**
- Create `profiles/lint.yaml` with quality enforcement workflow and Redis evidence framework
- Integrate with `/refactor --mode=lint` command invocation following existing profile patterns
- Implement evidence-based Redis promotion with `lint_clean=true` and `coverage_pct` keys
- Configure performance targets: <2 minutes for p95 quality validation

### Integration Points

- `profiles/lint.yaml` - SuperClaude profile for quality enforcement workflows
- `pyproject.toml` - Unified tool configuration replacing flake8/black/isort setup  
- `scripts/coverage_badge.py` - Badge generation script following GitHub Actions patterns
- `scripts/quality_gate.py` - Quality validation orchestration with Redis evidence integration
- Integration with PRP-1059 Lua promotion script for atomic evidence-based promotion
- Existing `scripts/bpci-fast.sh` patterns for CI validation consistency

### Code Structure

```
profiles/
├── lint.yaml                   # SuperClaude quality enforcement profile

scripts/
├── coverage_badge.py           # Coverage badge generation 
├── quality_gate.py            # Quality validation orchestration
└── quality_validation.py      # Ruff and coverage enforcement logic

tests/unit/profiles/
├── test_lint_profile.py        # Unit tests for lint profile functionality
├── test_coverage_enforcement.py # Coverage validation tests
└── test_quality_gate.py       # Quality gate integration tests

pyproject.toml                  # Unified Ruff and pytest-cov configuration
.pre-commit-config.yaml        # Pre-commit hooks with Ruff integration
```

### Error Handling Strategy

- **Lint Failures**: Detailed error reporting with line-by-line annotations and auto-fix suggestions
- **Coverage Failures**: Specific uncovered lines identification with improvement recommendations
- **Performance Degradation**: Timeout handling with partial validation results and degraded mode
- **Redis Connection**: Graceful degradation with local validation fallback when Redis unavailable
- **Badge Generation**: Fallback to previous badge version if generation fails

## Acceptance Criteria

1. Profile `profiles/lint.yaml` functional with `/refactor --mode=lint` command integration
2. Ruff linting with zero tolerance for E501, F401, PD* errors implemented and enforced
3. pytest-cov enforcement with `--cov-fail-under 80` threshold configured and validated
4. Evidence keys `lint_clean=true` and `coverage_pct` (integer) set in Redis for promotion validation
5. Coverage badge SVG artifact generation (`coverage_badge.svg`) automated with shields.io integration
6. Integration with PRP-1059 Lua promotion script for atomic evidence-based quality gate enforcement
7. Unit tests for lint enforcement and coverage validation achieving 100% coverage on core logic
8. Coverage ≥ 80% on all bot components with comprehensive test suite validation

## Dependencies

- **PRP-1059 (Lua Promotion Script)**: Required for Redis evidence-based promotion and atomic state transitions
- **ruff>=0.1.0**: Modern Python linter and formatter replacing flake8/black/isort
- **pytest-cov>=4.0.0**: Coverage measurement and enforcement with fail-under threshold support
- **pre-commit>=3.0.0**: Git hooks framework for immediate quality feedback during development
- **coverage-badge or genbadge**: SVG badge generation library for automated coverage visualization

## Testing Strategy

**Unit Tests**: Quality gate logic verification with mock Redis and subprocess testing
- Test Ruff configuration validation and error handling for all configured rule categories
- Verify coverage threshold enforcement with various coverage percentage scenarios
- Validate Redis evidence key setting and retrieval for promotion workflow integration

**Integration Tests**: End-to-end quality gate workflows with real tooling and Redis connections
- Test complete quality validation workflows from profile invocation to evidence setting
- Verify integration with PRP-1059 promotion script for atomic evidence validation
- Test badge generation and file system artifact creation

**Performance Tests**: Quality gate timing validation under load to meet <2 minute p95 targets
- Benchmark Ruff execution time on large codebases (10K+ lines)
- Performance testing for coverage calculation and reporting generation
- Redis evidence setting performance validation for high-throughput scenarios

**Test Frameworks**: pytest, pytest-benchmark, pytest-mock for comprehensive validation coverage

## Rollback Plan

**Step 1: Immediate Quality Gate Disable**
- Disable feature flags: `ENABLE_RUFF_ENFORCEMENT=false`, `QUALITY_GATE_STRICT_MODE=false`
- Revert to existing `make lint` and `make format` manual validation commands
- Switch Redis evidence validation to manual approval mode

**Step 2: Tool Configuration Rollback**
- Restore previous flake8/black/isort configuration from backup
- Revert `pyproject.toml` changes and restore individual tool configs
- Disable pre-commit hook enforcement for Ruff-based validation

**Step 3: Evidence Framework Rollback**
- Remove Redis evidence keys: `lint_clean` and `coverage_pct` from promotion logic
- Restore previous PRP promotion criteria to manual validation workflow
- Monitor system performance and validation accuracy after rollback

**Trigger Conditions**: Quality gate failures >10%, performance degradation >200%, evidence validation errors >5%, developer productivity metrics decline >25%

## Validation Framework

**Pre-commit Validation**:
```bash
ruff check profiles/ scripts/ --fix && ruff format profiles/ scripts/
pytest tests/unit/profiles/ -v --cov=profiles/ --cov=scripts/quality_gate.py
```

**Integration Validation**:
```bash
pytest tests/integration/test_quality_gate_integration.py -v
python scripts/quality_gate.py --validate --dry-run
```

**Production Validation**:
- Quality gate performance monitoring (≤2 minute p95 target)
- Coverage badge generation automation testing
- Redis evidence validation integration testing
- SuperClaude profile security and performance review