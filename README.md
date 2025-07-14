# LeadFactory MVP

AI-powered website audit platform that generates revenue through automated audit report sales.

## System Requirements

- **Python**: 3.11.x (match CI environment)
- **Docker**: ≥ 20.10
- **Docker Compose**: ≥ 2.0
- **PostgreSQL**: 15 (via Docker)
- **Operating System**: Linux/macOS (Windows via WSL2)

### Prerequisites Validation

Before development, validate your environment meets all requirements:

```bash
# Run comprehensive validation
python -m core.prerequisites

# Run specific checks
python -m core.prerequisites --check python
python -m core.prerequisites --check docker
python -m core.prerequisites --check database

# Get JSON output for automation
python -m core.prerequisites --json

# Quiet mode (minimal output)
python -m core.prerequisites --quiet
```

The prerequisites validation checks:
- Python version (3.11.x)
- Docker & Docker Compose versions
- Database connectivity
- Environment variables
- Python dependencies installation
- Pytest test collection
- CI toolchain (pytest, ruff, mypy)

## Quick Start

```bash
# Setup
docker build -f Dockerfile.test -t leadfactory-test .

# Run tests
docker run --rm leadfactory-test

# Start development
docker-compose up
```

## Architecture

- **12 domains** (D0-D11) for modular development
- **CI-first** development with Docker-based testing
- **250,000 businesses** processed daily through data provider APIs
- **$199 audit reports** with Stripe payment processing

### Phase 0.5 Enhancements

- **Data Axle Integration**: Business data enrichment ($0.05/match)
- **Hunter.io Fallback**: Email discovery when needed ($0.01/email)
- **Bucket Intelligence**: Geo/vertical segmentation for targeting
- **Cost Controls**: Daily budget limits with automatic guardrails
- **Analytics Views**: Real-time unit economics and ROI tracking

## Development

### Tests

**CI Test Strategy (PRP-014 Optimized)**

Our CI runs a strategic subset of tests to maintain fast feedback loops while ensuring quality:

- **Runtime Target**: ≤ 5 minutes (P90)
- **Coverage Target**: ≥ 80%
- **Flake Rate**: < 2%

**Test Execution Strategy:**

1. **Every Push/PR** (`.github/workflows/test.yml`):
   - Unit tests for critical business logic (d5_scoring, d6_reports, governance, lead_explorer)
   - Essential integration tests (health, database, stub server)
   - Parallel execution with pytest-xdist
   - Total runtime: <5 minutes

2. **Nightly** (`.github/workflows/test-nightly.yml`):
   - Complete test suite including slow tests (>1s)
   - External API tests
   - Performance benchmarks
   - Full regression coverage

**Test Categories:**
- `@pytest.mark.critical` - Must-run tests for core functionality
- `@pytest.mark.slow` - Tests taking >1s, deferred to nightly
- `@pytest.mark.flaky` - Unstable tests excluded from CI
- `@pytest.mark.external` - Tests requiring external APIs (nightly only)

**Running Tests:**
```bash
# CI tests (fast, critical path)
pytest -n auto -m "not slow and not flaky" --timeout=300

# Critical tests only
pytest -m critical

# All tests including slow ones
pytest -n auto --timeout=600

# Single test file with coverage
pytest tests/unit/test_core.py -v --cov=. --cov-report=term
```

**Test Organization:**
- `tests/unit/` - Fast, isolated unit tests (strategic subset in CI)
- `tests/integration/` - API and database tests (critical only in CI)
- `tests/performance/` - Performance benchmarks (nightly only)
- `tests/smoke/` - Basic functionality tests (health checks in CI)

All code must pass tests in Docker before committing:

```bash
# Run specific test
docker run --rm leadfactory-test pytest tests/unit/test_models.py

# Run all tests with coverage
docker run --rm leadfactory-test
```

## Documentation

- `PRD.md` - Complete product specifications
- `PRD_Update.md` - Phase 0.5 enhancement details
- `docs/phase_05_providers.md` - Data Axle & Hunter integration guide
- `docs/runbook.md` - Production operations guide
- `docs/testing_guide.md` - Testing best practices

## Phase 0.5 Configuration

Add to `.env`:

```bash
# Data Axle
DATA_AXLE_API_KEY=your-key-here

# Hunter.io  
HUNTER_API_KEY=your-key-here

# Cost Control
COST_BUDGET_USD=1000
```

## Monitoring

### Cost Tracking
```sql
-- View daily API costs
SELECT * FROM unit_economics_day ORDER BY date DESC;

-- Check bucket performance
SELECT * FROM bucket_performance WHERE roi > 0 ORDER BY roi DESC;
```

### Prefect Flows
- **bucket_enrichment**: Nightly at 3 AM UTC
- **cost_guardrail**: Hourly spending monitor
- **profit_snapshot**: Daily at 6 AM UTC
