# LeadFactory MVP

AI-powered website audit platform that generates revenue through automated audit report sales.

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
