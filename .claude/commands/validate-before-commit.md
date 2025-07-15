# Validate Before Commit

## Description
Mandatory validation command that Claude Code must run before every commit to prevent CI failures.

## Usage
Always run one of these commands before committing any code changes:

### Quick Validation (30 seconds)
```bash
make quick-check
```
Use for: Small changes, bug fixes, documentation updates

### Complete Pre-Push Validation (5-10 minutes)  
```bash
make pre-push
```
Use for: Feature additions, significant changes, before any push

### Full CI Simulation (15+ minutes)
```bash
make ci-local
```
Use for: Major changes, debugging CI issues, final verification

## Mandatory Rules

🚨 **NEVER COMMIT WITHOUT VALIDATION**
- Running these commands is MANDATORY before every commit
- If validation fails, fix issues before proceeding
- These commands catch problems locally instead of breaking CI

🚨 **VALIDATION FAILURE = STOP WORK**
- If `make quick-check` fails: Fix formatting/linting issues first
- If `make pre-push` fails: The push would break CI - fix all issues
- If `make ci-local` fails: Comprehensive debugging needed

## Benefits

✅ **Prevents CI Failures**: Catches issues locally before they reach GitHub
✅ **Faster Debugging**: Get immediate feedback instead of waiting for CI
✅ **Eliminates Frustration**: No more push → wait → fail → debug cycles
✅ **Perfect Parity**: Local validation mirrors GitHub CI exactly

## What Gets Validated

- **Code Formatting**: Black, isort automatic fixes
- **Linting**: Flake8, mypy, bandit security checks  
- **Tests**: Unit tests, integration tests (where safe)
- **Database**: Migration checks, model validation
- **Docker**: Container builds, multi-service tests
- **Environment**: Configuration validation

## Emergency Override

⚠️ **There is NO emergency override** - validation is always required.
The system is designed to be fast enough for all workflows.

## Setup

Run once to install the bulletproof CI system:
```bash
./scripts/setup_bulletproof_ci.sh
```

This installs pre-commit hooks and pre-push validation automatically.