# Gold-Standard PRP Validation Pipeline

A lean but robust validation pipeline for Product Requirements Prompts (PRPs) that ensures quality before execution.

## Overview

This pipeline implements a 3-tier validation system with Claude-powered quality loops:

1. **Local Gates** (instant validation)
   - Schema validation via Pydantic
   - Policy compliance checks (OPA-style rules)
   - Python linting with Ruff (optional)

2. **CRITIC Self-Review** (Claude-powered)
   - LLM reviews its own PRP for issues
   - Suggests specific improvements
   - Automatic regeneration on failure

3. **LLM-as-Judge** (independent scoring)
   - 5-point rubric across key dimensions
   - Requires ≥4.0 average to pass
   - No external dependencies

## Quick Start

```bash
# Run validation tests
./run_prp_pipeline.sh test

# Generate PRPs with validation
./run_prp_pipeline.sh generate

# Execute with retry + CRITIC + Judge
./run_prp_pipeline.sh execute

# Check status
./run_prp_pipeline.sh status
```

## Validation Gates

### 1. Schema Validation (Pydantic)
- Validates PRP structure and required fields
- Checks ID format (P0-000), wave (A/B), etc.
- Instant feedback on malformed PRPs

### 2. Policy Guard (OPA-style)
- Simple regex rules for banned patterns
- Enforces DO NOT IMPLEMENT from CURRENT_STATE.md
- Examples: no Yelp integration, no deprecated paths

### 3. Lint Check (Ruff)
- Optional but recommended
- Runs on Python files in integration points
- 10-100x faster than traditional linters

### 4. CRITIC Self-Review
- Claude reviews the PRP for:
  - Clarity and completeness
  - Feasibility
  - Consistency
  - Policy compliance
- Generates specific improvement patches

### 5. LLM Judge
- Independent quality scoring (1-5):
  - Clarity
  - Feasibility  
  - Coverage
  - Policy Compliance
  - Technical Quality
- Pass threshold: ≥4.0 average, no dimension <3

## Retry Logic

- Automatic retry with exponential backoff (2s, 4s, 8s)
- CRITIC runs on retry attempts
- Maximum 3 attempts before marking as failed

## Files

- `recursive_prp_processor.py` - Main processor with validation
- `critic_prompt.md` - CRITIC agent prompt template
- `judge_prompt.md` - Judge scoring rubric
- `test_validation.py` - Validation test suite
- `run_prp_pipeline.sh` - CLI wrapper

## Extension Points

### Adding MCP Servers

The system is designed to work with MCP servers. To add:

1. Pull the MCP server image
2. Add to validation pipeline in `_validate_prp()`
3. Handle the response appropriately

Example MCP servers:
- `ruff-mcp` - Python linting
- `pydantic-mcp` - Schema validation  
- `opa-mcp` - Policy enforcement
- `playwright-mcp` - UI testing (future)

### Custom Policy Rules

Add new rules to `self.policy_rules` in PRPGenerator:

```python
self.policy_rules = [
    (r'pattern', 'Error message'),
    # Add more rules here
]
```

## Why This Approach Works

1. **Fast Local Gates** - Catch 80% of issues in <1 second
2. **Same Model Family** - Claude judging Claude avoids style conflicts
3. **No External Dependencies** - Everything runs with just Claude API
4. **Progressive Enhancement** - Start simple, add MCP servers as needed

## Cost Estimate

- Local gates: Free
- CRITIC review: ~$0.01 per PRP
- Judge scoring: ~$0.01 per PRP
- Total: ~$0.02 per PRP for gold-standard quality

For 10 PRPs: ~$0.20 total investment for dramatically better specs.