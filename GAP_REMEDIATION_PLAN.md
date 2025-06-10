# LeadFactory MVP - Gap Remediation Plan

## Overview

This document outlines the 15 tasks identified to address gaps between the current implementation and the PRD specifications. All original 100 tasks have been completed, but a comprehensive review identified critical architectural violations and missing components.

## Gap Summary

### 🔴 Critical Issues (P0 - Must Fix)
1. **Gateway Pattern Violations**: Multiple domains making direct API calls instead of using D0 Gateway
2. **Missing Provider Registration**: SendGrid and Stripe providers not registered in gateway

### 🟡 High Priority Issues (P1)
1. **Test Coverage Below 80%**: Currently at 63.1%, missing coverage for critical components
2. **CI/CD Configuration**: Linting/type checking failures don't fail builds

### 🟢 Medium Priority Issues (P2)
1. **Missing Email Template**: audit_teaser.html referenced in PRD but not implemented
2. **CI Integration Tests**: Skipped to save time but should be enabled

## Task Breakdown

### Phase 1: Gateway Pattern Fixes (6 tasks, ~12 hours)

| Task ID | Title | Priority | Est. Hours |
|---------|-------|----------|------------|
| GAP-001 | Register SendGrid and Stripe providers in Gateway Factory | P0 | 1 |
| GAP-002 | Add SendGrid methods to Gateway Facade | P0 | 2 |
| GAP-003 | Add Stripe methods to Gateway Facade | P0 | 2 |
| GAP-004 | Refactor D2 Sourcing to use Gateway | P0 | 3 |
| GAP-005 | Refactor D7 Storefront to use Gateway | P0 | 3 |
| GAP-006 | Refactor D9 Delivery to use Gateway | P0 | 3 |

### Phase 2: Test Coverage Improvements (6 tasks, ~16 hours)

| Task ID | Title | Priority | Est. Hours |
|---------|-------|----------|------------|
| GAP-007 | Add tests for Gateway base components | P1 | 3 |
| GAP-008 | Add tests for Circuit Breaker | P1 | 2 |
| GAP-009 | Add tests for Rate Limiter | P1 | 2 |
| GAP-010 | Add tests for D7 Checkout Manager | P1 | 3 |
| GAP-011 | Add tests for D7 Webhook Processing | P1 | 3 |
| GAP-012 | Add tests for D9 Compliance module | P1 | 2 |

### Phase 3: Missing Features and CI Fixes (3 tasks, ~2.5 hours)

| Task ID | Title | Priority | Est. Hours |
|---------|-------|----------|------------|
| GAP-013 | Create missing email template | P2 | 1 |
| GAP-014 | Fix CI linting and type checking | P1 | 0.5 |
| GAP-015 | Enable integration tests in CI with timeouts | P2 | 1 |

## Execution Plan

### Step 1: Start with P0 Tasks
All P0 tasks must be completed first as they fix critical architectural violations. These tasks ensure that all external API calls go through the D0 Gateway as specified in the PRD.

### Step 2: Improve Test Coverage
P1 test coverage tasks should be completed next to bring coverage above the 80% threshold. Focus on critical components that currently have 0% coverage.

### Step 3: Minor Improvements
P2 tasks can be completed last as they are nice-to-have improvements that don't affect core functionality.

## Success Criteria

1. **No Direct API Calls**: All domains use D0 Gateway for external APIs
2. **Test Coverage ≥ 80%**: Meets PRD requirement
3. **CI/CD Enforcement**: Linting and type checking failures fail builds
4. **All Tests Pass**: In Docker environment matching production

## Quick Start

```bash
# Get the next gap task to work on
python3 planning/get_next_gap_task.py

# Check progress
python3 planning/get_next_gap_task.py --progress

# Start working on a task
python3 planning/get_next_gap_task.py --update GAP-001 in_progress

# Complete a task
python3 planning/get_next_gap_task.py --update GAP-001 completed
```

## Timeline

Total estimated time: 32.5 hours

With focused effort, all gap remediation tasks can be completed in 2-3 days:
- Day 1: Complete all P0 tasks (Gateway pattern fixes)
- Day 2: Complete P1 test coverage tasks
- Day 3: Complete remaining P1 and P2 tasks

## Notes

- Each task should be a separate commit for easy rollback
- Test thoroughly in Docker before marking complete
- Update coverage metrics after each test task
- Verify integration tests still pass after gateway refactoring