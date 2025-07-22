# Legacy Lint Configuration Backup

This directory contains backup copies of legacy linting configuration files as part of the PRP-1061 dual-tooling transition strategy.

## PRP-1061 Dual-Tooling Strategy

During the transition to Ruff (one sprint), both legacy tools and Ruff run in parallel to ensure compatibility and provide fallback options.

### Preserved Configurations

- **`.flake8`** - Original flake8 configuration with comprehensive ignore list
- **Legacy pyproject.toml sections** - Black and isort configurations preserved in main pyproject.toml

### Migration Strategy

**Phase**: Side-by-side execution for one sprint
**Primary Tool**: Ruff (configured in pyproject.toml)
**Legacy Tools**: flake8, black, isort (available for rollback)

### Rollback Process

If quality gate failures exceed threshold (>10%) or performance degradation occurs (>200%), the system can roll back to legacy tools:

1. Set `ENABLE_RUFF_ENFORCEMENT=false`
2. Set `QUALITY_GATE_STRICT_MODE=false`
3. Restore legacy configs from this directory
4. Clear Redis evidence keys
5. Notify development team

### Quality Comparison

Both tool sets enforce the same core quality standards:
- **Line length**: 120 characters
- **Import sorting**: Consistent organization
- **Code formatting**: Black-compatible style
- **Error detection**: Syntax errors, unused imports, naming conventions

### Performance Comparison

- **Ruff**: ~10x faster than flake8, unified linting + formatting
- **Legacy**: Proven stability, three separate tools (flake8 + black + isort)

### Cleanup

After successful transition (one sprint), this directory can be removed and references updated.