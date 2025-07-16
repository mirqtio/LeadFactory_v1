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

### Pre-push Validation

**IMPORTANT**: Always run validation before pushing to prevent CI failures:

```bash
# Quick validation (30 seconds) - for small changes
make quick-check

# Full CI validation (5-10 minutes) - before pushing
make bpci
```

The `make bpci` command runs the **Bulletproof CI** system (`scripts/bpci.sh`) which:
- Builds the exact same Docker test environment as GitHub CI
- Starts PostgreSQL and stub server containers
- Runs the complete test suite with coverage
- Ensures your code will pass GitHub CI

### Tests

**Optimized Test Suite (P0-016 Improvements)**

Our test suite has been completely overhauled for reliability and performance, achieving:
- **50-62% faster execution** through intelligent parallelization
- **Zero flaky tests** with proper synchronization utilities
- **100% test categorization** with automatic marker validation
- **Dynamic resource allocation** preventing port conflicts

**Quick Start:**
```bash
# Fast validation before pushing (30 seconds)
make quick-check

# Full CI validation locally (5-10 minutes)
make bpci

# Run tests by category
pytest -m critical              # 9 must-run tests
pytest -m "unit and not slow"   # Fast unit tests
pytest -m d5_scoring           # Domain-specific tests
```

**Test Execution Strategies:**

1. **Parallel Execution** (50-62% faster):
   ```bash
   pytest -n auto              # Use all CPU cores
   pytest -n auto --dist worksteal  # Optimal work distribution
   ```

2. **Marker-Based Selection**:
   - `@pytest.mark.critical` - Must-run tests (9 tests)
   - `@pytest.mark.slow` - Tests >1s (20 tests, run nightly)
   - `@pytest.mark.unit/integration/e2e/smoke` - Test types
   - `@pytest.mark.d0_gateway` through `d11_orchestration` - Domain tests

3. **CI Optimization**:
   ```bash
   # Fast CI suite (<5 minutes)
   pytest -n auto -m "not slow and not flaky" --timeout=300
   
   # Nightly comprehensive suite
   pytest -n auto --timeout=600
   ```

**Test Infrastructure:**
- **Parallel Safety**: Isolated databases, Redis, and temp directories per worker
- **Dynamic Ports**: Automatic port allocation (15000-25000 range)
- **Synchronization**: Replaced `time.sleep()` with deterministic waiting
- **Marker Validation**: Automatic categorization enforcement

**Common Commands:**
```bash
# Validate test markers
pytest --validate-markers

# Show marker report
pytest --show-marker-report

# Run with detailed timing
pytest --durations=10

# Debug parallel execution
pytest -n auto --max-worker-restart=0
```

For comprehensive testing documentation, see:
- `docs/TEST_SUITE_GUIDE.md` - Complete test suite documentation
- `docs/testing_guide.md` - Testing best practices
- `tests/README.md` - Test structure and fixtures

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
