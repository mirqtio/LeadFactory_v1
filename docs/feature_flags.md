# Feature Flags Documentation

## Overview
This document defines all feature flags used in the LeadFactory application. These flags control feature rollout and protect production from incomplete implementations.

## Wave A Flags (Core Functionality)

```python
# Always enabled in production
ENABLE_EMAILS = True  # Core email delivery feature

# Development/testing flags
USE_STUBS = False  # MUST be False in production, True for testing
```

## Wave B Flags (Progressive Rollout)

```python
# External API providers
ENABLE_SEMRUSH = False         # SEMrush integration (P1-010)
ENABLE_LIGHTHOUSE = False      # Lighthouse audits (P1-020)
ENABLE_VISUAL_ANALYSIS = False # Visual rubric scoring (P1-030)
ENABLE_LLM_AUDIT = False      # LLM heuristic analysis (P1-040)
ENABLE_DATAAXLE = False       # DataAxle enrichment (P1-070)

# Cost management
ENABLE_COST_TRACKING = False   # Cost ledger (P1-050)
ENABLE_COST_GUARDRAILS = False # Budget limits (P1-060)

# Cost guardrail settings
DAILY_BUDGET_CAP = 100.00     # USD per day limit
PER_LEAD_CAP = 2.50          # USD per lead limit
HOURLY_SPIKE_CAP = 20.00     # USD per hour limit
PER_PROVIDER_DAILY_CAP = 50.00 # USD per provider per day
```

## Usage in Code

### Checking Feature Flags

```python
from core.config import settings

if settings.ENABLE_SEMRUSH:
    # SEMrush code path
    metrics = await semrush_client.get_metrics(domain)
else:
    # Fallback or skip
    metrics = {}
```

### Runtime Assertions

```python
# In core/config.py
if settings.ENVIRONMENT == "production" and settings.USE_STUBS:
    raise RuntimeError("Cannot run production with USE_STUBS=true")
```

## Environment Variables

Add to `.env.example`:

```bash
# Core flags
ENABLE_EMAILS=true
USE_STUBS=false

# Wave B flags (all false by default)
ENABLE_SEMRUSH=false
ENABLE_LIGHTHOUSE=false
ENABLE_VISUAL_ANALYSIS=false
ENABLE_LLM_AUDIT=false
ENABLE_DATAAXLE=false
ENABLE_COST_TRACKING=false
ENABLE_COST_GUARDRAILS=false

# Guardrail settings
DAILY_BUDGET_CAP=100.00
PER_LEAD_CAP=2.50
HOURLY_SPIKE_CAP=20.00
PER_PROVIDER_DAILY_CAP=50.00
```

## Rollout Schedule

| Flag | Target Date | Dependencies |
|------|------------|--------------|
| ENABLE_COST_TRACKING | After P1-050 | Gateway cost ledger |
| ENABLE_SEMRUSH | After P1-010 | Cost tracking |
| ENABLE_LIGHTHOUSE | After P1-020 | Cost tracking |
| ENABLE_VISUAL_ANALYSIS | After P1-030 | Cost tracking |
| ENABLE_LLM_AUDIT | After P1-040 | Cost tracking |
| ENABLE_COST_GUARDRAILS | After P1-060 | All cost tracking |
| ENABLE_DATAAXLE | After contract | Legal approval |

## Testing

### Unit Tests
```python
@pytest.fixture
def enable_semrush(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SEMRUSH", True)
```

### Integration Tests
```bash
# Test with feature enabled
ENABLE_SEMRUSH=true pytest tests/integration/test_semrush.py
```

## Monitoring

Track feature flag usage in logs:
```python
logger.info("Feature flag check", extra={
    "feature": "SEMRUSH",
    "enabled": settings.ENABLE_SEMRUSH,
    "request_id": request_id
})
```