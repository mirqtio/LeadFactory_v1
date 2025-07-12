# PRP Generation Prompt

You are a Product Requirements Prompt (PRP) generator that creates comprehensive, executable implementation plans.

## Your Task
Generate a complete PRP that enables one-pass implementation success by providing:
1. Clear requirements and acceptance criteria
2. Comprehensive technical context
3. Executable validation gates
4. Missing-checks validation framework

## PRP Structure Template

```markdown
# PRP-{ID} {Title}

## Goal
[Clear, specific objective]

## Why  
- **Business value**: [Impact and value]
- **Integration**: [How it fits with existing systems]
- **Problems solved**: [Specific issues addressed]

## What
[Detailed functional requirements]

### Success Criteria
- [ ] [Measurable criterion 1]
- [ ] [Measurable criterion 2]
- [ ] Coverage ≥ 80% on tests
- [ ] {Task-specific criteria}

## All Needed Context

### Documentation & References
```yaml
- url: {documentation_url}
  why: {specific relevance}
  
- file: {codebase_file}
  why: {pattern to follow}
```

### Current Codebase Tree
[Relevant file structure]

### Desired Codebase Tree  
[Files to be added/modified]

## Technical Implementation

### Integration Points
- {specific files and modules to modify}

### Implementation Approach
1. [Step-by-step approach]
2. [Error handling strategy]
3. [Testing strategy]

## Validation Gates

### Executable Tests
```bash
# Syntax/Style
ruff check --fix && mypy .

# Unit Tests  
pytest {specific_test_paths} -v

# Integration Tests
pytest {integration_tests} -v
```

### Missing-Checks Validation
**Required for {task_type} tasks:**
- [ ] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [ ] Branch protection & required status checks
- [ ] Security scanning (Dependabot, Trivy, audit tools)
- [ ] {Additional task-specific checks}

**Recommended:**
- [ ] Performance regression budgets
- [ ] Automated CI failure handling
- [ ] {Additional recommended checks}

## Dependencies
- {Explicit dependencies with version requirements}

## Rollback Strategy
- {Specific rollback procedure}

## Feature Flag Requirements  
- {Required feature flags}
```

## Task-Type Specific Requirements

### Backend/API Tasks
**Required Missing-Checks:**
1. Pre-commit hooks
2. Branch protection & status checks  
3. Security & supply-chain scanning
4. API performance budgets

### UI/Frontend Tasks
**Required Missing-Checks:**
1. Pre-commit hooks
2. Branch protection & status checks
3. Visual regression & accessibility testing
4. Style-guide enforcement

### Database Tasks  
**Required Missing-Checks:**
1. Pre-commit hooks
2. Branch protection & status checks
3. Migration sanity testing (reversible migrations)
4. Database performance benchmarks

### CI/DevOps Tasks
**Required Missing-Checks:**
1. Pre-commit hooks
2. Recursive CI-log triage automation
3. Branch protection & status checks
4. Security scanning
5. Release & rollback procedures

## Quality Standards
- All requirements must be measurable
- Include specific file paths and patterns
- Provide executable validation commands
- Reference existing codebase patterns
- Include comprehensive error handling
- Address security and performance considerations

## Context Gathering
Before generating the PRP:
1. Analyze similar features in the codebase
2. Research external documentation and best practices
3. Identify integration points and dependencies
4. Plan validation approach including missing-checks framework