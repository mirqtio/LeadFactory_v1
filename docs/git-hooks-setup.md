# Git Hooks Setup

This document explains the git hooks configuration for the LeadFactory project.

## Overview

We use a two-stage validation system:
1. **Pre-commit**: Quick validation (lint + format + core tests)
2. **Pre-push**: Full BPCI validation (simulates entire CI pipeline)

## Hook Configuration

### Pre-commit Hook
- **Location**: `.git/hooks/pre-commit`
- **Purpose**: Runs quick validation to catch basic issues before committing
- **What it runs**: `make quick-check`
  - Code formatting (Black, isort)
  - Linting (Flake8)
  - Core unit tests
- **Bypass**: `git commit --no-verify` (not recommended)

### Pre-push Hook
- **Location**: `.git/hooks/pre-push`
- **Purpose**: Runs full BPCI validation to ensure CI will pass
- **What it runs**: `make pre-push` → `make bpci`
  - All linting and formatting
  - All unit tests
  - Docker build
  - Integration tests
  - Everything that runs in CI
- **Bypass**: `git push --no-verify` (strongly discouraged)

## Pre-commit Framework

We also use the pre-commit framework (`.pre-commit-config.yaml`) for additional checks:
- Basic file checks (trailing whitespace, file size, etc.)
- YAML/JSON validation
- Code formatting (Black, isort)
- Quick linting

### Installing Pre-commit Framework
```bash
pip install pre-commit
pre-commit install
```

## Manual Setup

If the hooks aren't working, ensure they're executable:
```bash
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-push
```

## Development Workflow

1. **During development**: Make changes freely
2. **Before commit**: Pre-commit hook runs quick validation
3. **Before push**: Pre-push hook runs full BPCI validation
4. **Result**: CI should always pass if hooks pass

## Make Commands

- `make quick-check`: Quick validation (used by pre-commit)
- `make pre-push`: Full BPCI validation (used by pre-push)
- `make bpci`: Run the Bootstrap Pre-CI system
- `make format`: Auto-format code
- `make lint`: Run linting checks

## Troubleshooting

### Hook not running
- Check permissions: `ls -la .git/hooks/`
- Ensure executable: `chmod +x .git/hooks/pre-*`

### Hook failing
- Run the make command manually to see detailed output
- Fix issues one by one
- Use `--no-verify` only as last resort

### Pre-commit framework issues
- Update: `pre-commit autoupdate`
- Clean: `pre-commit clean`
- Reinstall: `pre-commit install --force`