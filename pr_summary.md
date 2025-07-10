# CI: Add lockfile & coverage-gated workflow

## Summary
This PR implements a comprehensive CI/CD pipeline with dependency locking and coverage enforcement as specified in the requirements.

## Changes Made

### 1. Dependency Management
- Added `requirements.lock` with SHA hashes using pip-tools for reproducible builds
- Added new dependencies:
  - `beautifulsoup4>=4.12.0` - Required by assessment modules
  - `psutil>=5.9.0` - Required by performance tests
  - `google-api-python-client>=2.100.0` - Required by Google Sheets integration
- Updated `pydantic>=2.7` to ensure compatibility

### 2. CI Workflow
- Created `.github/workflows/ci.yml` with:
  - Python 3.11 environment
  - Lockfile-based dependency installation with hash verification
  - Full test suite execution
  - Coverage reporting with 90% threshold enforcement
  - Proper module-based coverage configuration

### 3. Test Fixes
- Fixed Pydantic v2 compatibility (`regex` → `pattern` in Field)
- Fixed SQLAlchemy reserved attribute issues (`metadata` → `event_metadata`)
- Fixed import errors (e.g., `APIGatewayFacade` → `GatewayFacade`)
- Fixed test assertions to match updated config values
- Added missing `timeout` marker to pytest configuration

### 4. Build Configuration
- Added `Dockerfile.test` for containerized testing
- Added `sync-lock` rule to Makefile for lockfile regeneration
- Created `scripts/enforce_cov.py` for coverage threshold checking

### 5. Documentation
- Added comprehensive CHANGELOG.md with version 0.1.1
- Created `.venv_setup.md` with local development instructions

## Testing
- All CI-specific tests pass
- Coverage enforcement script works correctly
- Lockfile generation and hash verification tested

## Next Steps
1. Merge this PR to enable CI/CD pipeline
2. Monitor GitHub Actions for successful builds
3. Create GitHub issue for S-2 (Google Sheet sync setup) as specified

## Definition of Done
✅ Lockfile with hashes created and tested
✅ CI workflow configured with Python 3.11 and coverage gate
✅ All test issues resolved
✅ Documentation updated
✅ Ready for merge to main