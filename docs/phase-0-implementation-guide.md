# Phase-0 Implementation Guide: Config-as-Data & Prompt-Ops

## Overview

This guide documents the complete Phase-0 implementation for LeadFactory, focusing on:
- Configuration as data (YAML-based scoring rules)
- Prompt operations (Humanloop integration)
- Hot reload capabilities
- Monitoring and metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Google Sheets                            │
│                  (CPO Edits Scoring)                         │
└────────────────────────┬───────────────────┬─────────────────┘
                         │                   │
                    ┌────▼────┐         ┌────▼────┐
                    │sheet_pull│         │sheet_push│
                    │  Action  │         │  Action  │
                    └────┬────┘         └────┬────┘
                         │                   │
                    ┌────▼───────────────────▼────┐
                    │  config/scoring_rules.yaml  │
                    │     (Version Control)       │
                    └────────────┬─────────────────┘
                                 │
                         ┌───────▼────────┐
                         │  Hot Reload    │
                         │   Watcher      │
                         └───────┬────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Scoring Engine         │
                    │ (xlcalculator formulas)  │
                    └──────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Humanloop                               │
│               (All LLM Prompts)                              │
└────────────────────────┬─────────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │ prompts/ │
                    │directory │
                    └────┬────┘
                         │
                ┌────────▼────────┐
                │ HumanloopClient │
                │    Wrapper      │
                └────────┬────────┘
                         │
                    ┌────▼────┐
                    │   LLM   │
                    │  Calls  │
                    └─────────┘
```

## Key Components

### 1. YAML-Based Scoring Configuration

**File**: `config/scoring_rules.yaml`

```yaml
# Tier definitions (display only in Phase 0)
tiers:
  A: {min: 80, max: 100, label: "A"}
  B: {min: 60, max: 79, label: "B"}
  C: {min: 40, max: 59, label: "C"}
  D: {min: 0, max: 39, label: "D"}

# Component weights (must sum to 1.0 ± 0.005)
components:
  website_exists:
    weight: 0.15
    max_score: 10
  
  performance:
    weight: 0.35
    max_score: 10
    formula: "=IF({score}>80,10,IF({score}>60,7,IF({score}>40,4,2)))"
  
  # ... other components
```

**Schema Validation**: `d5_scoring/rules_schema.py`
- Pydantic-based validation
- Weight sum tolerance checking
- Tier threshold validation
- CLI tool: `python -m d5_scoring.rules_schema`

### 2. Google Sheets Integration

**Sheet Template**: `https://docs.google.com/spreadsheets/d/PLACEHOLDER_SHEET_ID/`

**GitHub Actions**:
1. **sheet_pull.yml**: Pulls from Google Sheets → YAML
   - Triggered by Apps Script "Submit to CI" button
   - Creates PR with changes
   - Validates configuration

2. **sheet_push.yml**: Pushes YAML → Google Sheets
   - Triggered on merge to main
   - Updates Sheet with latest values
   - Records SHA for version tracking

**Apps Script**: `scripts/google_apps_script.js`
- Custom menu with "Submit to CI" function
- SHA tracking in hidden metadata
- Data validation

### 3. Hot Reload System

**File Watcher**: `d5_scoring/hot_reload.py`
- Uses watchdog to monitor YAML changes
- Debounced reloading (2 seconds)
- Thread-safe implementation
- Validation before reload

**Internal Endpoint**: `/internal/reload_rules`
- Manual reload trigger
- Protected with authentication
- Returns reload status

### 4. Humanloop Integration

**Prompt Directory**: `/prompts/`

All prompts stored as markdown files with frontmatter:
```markdown
---
slug: website_analysis_v1
model: gpt-4
temperature: 0.1
max_tokens: 4000
supports_vision: false
---

Your prompt content here...
```

**Available Prompts**:
- `website_analysis_v1.md` - Main analysis (3 recommendations)
- `technical_analysis_v1.md` - Technical SEO analysis
- `industry_benchmark_v1.md` - Industry benchmarking
- `quick_wins_v1.md` - Quick improvements
- `website_screenshot_analysis_v1.md` - Visual analysis
- `performance_analysis_v1.md` - PageSpeed insights
- `email_generation_v1.md` - Outreach emails

**Client Wrapper**: `d0_gateway/providers/humanloop.py`
- Loads prompts from markdown files
- Variable substitution
- Metrics tracking
- Cost calculation

### 5. Monitoring & Metrics

**Prometheus Metrics** (port 8000/metrics):
```
# Prompt metrics
leadfactory_prompt_requests_total{prompt_slug, model, status}
leadfactory_prompt_duration_seconds{prompt_slug, model}
leadfactory_prompt_tokens_total{prompt_slug, model, token_type}
leadfactory_prompt_cost_usd_total{prompt_slug, model}

# Config reload metrics
leadfactory_config_reload_total{config_type, status}
leadfactory_config_reload_duration_seconds{config_type}
```

**Logging** (JSON structured):
- Prompt execution details
- Config reload events
- Error tracking with context

## Environment Variables

```bash
# Google Sheets
GOOGLE_SHEET_ID=PLACEHOLDER_SHEET_ID
GOOGLE_API_KEY=your_google_api_key
GITHUB_TOKEN=your_github_token

# Humanloop
HUMANLOOP_API_KEY=PLACEHOLDER_API_KEY
HUMANLOOP_PROJECT_ID=PLACEHOLDER_PROJECT_ID

# Monitoring
LOG_FORMAT=json
LOG_LEVEL=INFO
```

## Usage Examples

### 1. Editing Scoring Weights

1. CPO opens Google Sheet
2. Modifies weights in "Weights" tab
3. Clicks "Submit to CI" button
4. Reviews PR in GitHub
5. Merges PR
6. Changes live within 5 minutes via hot reload

### 2. Using Humanloop for LLM Calls

```python
from d0_gateway.providers.humanloop import HumanloopClient

client = HumanloopClient()

# Simple completion
response = await client.completion(
    prompt_slug="website_analysis_v1",
    inputs={
        "url": "example.com",
        "performance_score": 85,
        "industry": "ecommerce"
    }
)

# Chat completion with vision
response = await client.chat_completion(
    prompt_slug="website_screenshot_analysis_v1",
    inputs={},
    messages=[{
        "role": "user",
        "content": [{
            "type": "image_url",
            "image_url": {"url": screenshot_url}
        }]
    }]
)
```

### 3. Manual Config Reload

```bash
# Via API endpoint
curl -X POST http://localhost:8000/internal/reload_rules \
  -H "Authorization: Bearer $API_KEY"

# Via CLI
python -m d5_scoring.rules_schema --reload
```

## Validation & Testing

### Run Schema Validation
```bash
python -m d5_scoring.rules_schema validate
```

### Test Formula Evaluation
```bash
python -m d5_scoring.formula_evaluator
```

### Test Humanloop Integration
```bash
python test_humanloop_simple.py
```

### Check Metrics
```bash
curl http://localhost:8000/metrics | grep leadfactory_
```

## Troubleshooting

### Common Issues

1. **Weight Sum Error**
   - Error: "Component weights sum to X, must be 1.0 ± 0.005"
   - Fix: Adjust weights in YAML to sum to 1.0

2. **Formula Evaluation Error**
   - Error: "Invalid formula syntax"
   - Fix: Check Excel formula syntax, ensure variables use {var} format

3. **Prompt Not Found**
   - Error: "Prompt not found: xyz"
   - Fix: Ensure prompt file exists in `/prompts/` directory

4. **Hot Reload Not Working**
   - Check file watcher is running
   - Verify write permissions on YAML file
   - Check logs for validation errors

### Debug Commands

```bash
# Check current config
cat config/scoring_rules.yaml | head -20

# Watch reload logs
tail -f logs/app.log | grep reload

# Test prompt loading
python -c "from d0_gateway.providers.humanloop import HumanloopClient; \
  import asyncio; \
  client = HumanloopClient(); \
  asyncio.run(client.load_prompt('website_analysis_v1'))"

# Check metrics endpoint
curl -s localhost:8000/metrics | grep -E "(prompt|config_reload)"
```

## Security Considerations

1. **API Keys**: All keys use placeholders in version control
2. **Internal Endpoints**: Protected with authentication
3. **Input Validation**: All user inputs validated before use
4. **Rate Limiting**: Built into gateway providers
5. **Audit Logging**: All config changes tracked with SHA

## Future Enhancements (Post-Phase-0)

1. **Tier Gating**: Enable tier-based filtering when ready
2. **A/B Testing**: Use Humanloop's experimentation features
3. **Advanced Formulas**: Support for more complex scoring logic
4. **Multi-Environment**: Separate configs for dev/staging/prod
5. **Backup/Restore**: Automated config backups

## Compliance Checklist

- [x] CPO can edit scoring in Google Sheets
- [x] Changes live in ≤ 5 minutes via PR merge
- [x] Tiers calculated but have zero gating effect
- [x] 100% of prompts via Humanloop
- [x] Hot-reload configuration without restart
- [x] Prometheus/Loki metrics integration
- [x] Comprehensive test coverage
- [x] Documentation complete