# Task Todo List Template

## Pre-Implementation
- [ ] Understand requirements fully
- [ ] Check current CI status (must be green to start)
- [ ] Plan implementation approach

## Implementation
- [ ] Write the main feature code
- [ ] Write comprehensive tests
- [ ] Test locally to ensure it works
- [ ] Update documentation if needed

## Git & CI Verification
- [ ] Commit all changes with clear message
- [ ] Push to GitHub main branch
- [ ] Check GitHub Actions - ALL must be green:
  - [ ] Test Suite - PASSING ✅
  - [ ] Docker Build - PASSING ✅
  - [ ] Linting and Code Quality - PASSING ✅
  - [ ] Deploy to VPS - PASSING ✅
  - [ ] Minimal Test Suite - PASSING ✅

## Completion Criteria
- [ ] ALL CI checks are GREEN (no exceptions)
- [ ] If any CI check fails:
  - [ ] Fix the issue
  - [ ] Push the fix
  - [ ] Re-verify ALL CI is green
- [ ] Only mark task complete when EVERY CI check passes

⚠️ REMEMBER: A task is NOT complete if ANY CI check is failing!