# Create PRP

## Feature file: $ARGUMENTS

Generate a complete PRP for general feature implementation with thorough research. Ensure context is passed to the AI agent to enable self-validation and iterative refinement. Read the feature file first to understand what needs to be created, how the examples provided help, and any other considerations.

The AI agent only gets the context you are appending to the PRP and training data. Assuma the AI agent has access to the codebase and the same knowledge cutoff as you, so its important that your research findings are included or referenced in the PRP. The Agent has Websearch capabilities, so pass urls to documentation and examples.

## Research Process

1. **Codebase Analysis**
   - Search for similar features/patterns in the codebase
   - Identify files to reference in PRP
   - Note existing conventions to follow
   - Check test patterns for validation approach

2. **External Research**
   - Search for similar features/patterns online
   - Library documentation (include specific URLs)
   - Implementation examples (GitHub/StackOverflow/blogs)
   - Best practices and common pitfalls

3. **User Clarification** (if needed)
   - Specific patterns to mirror and where to find them?
   - Integration requirements and where to find them?

## PRP Generation

Using PRPs/templates/prp_base.md as template:

### Critical Context to Include and pass to the AI agent as part of the PRP
- **Documentation**: URLs with specific sections
- **Code Examples**: Real snippets from codebase
- **Gotchas**: Library quirks, version issues
- **Patterns**: Existing approaches to follow

### Implementation Blueprint
- Start with pseudocode showing approach
- Reference real files for patterns
- Include error handling strategy
- list tasks to be completed to fullfill the PRP in the order they should be completed

### Validation Gates (Must be Executable) eg for python
```bash
# Syntax/Style
ruff check --fix && mypy .

# Unit Tests
uv run pytest tests/ -v

```

### Missing-Checks Validation Framework
Every PRP must include comprehensive post-execution validation covering these 9 areas:

1. **Local Test Suite Pre-commit Hook**: Pre-commit hooks preventing broken commits
2. **Recursive CI-log Triage Loop**: Automated CI failure handling and retry
3. **Branch Protection & Required Status Checks**: GitHub API configuration
4. **Security & Supply-chain Guard-rails**: Dependency scanning, CVE detection
5. **Performance/Regression Budgets**: Benchmark baselines and budget gates
6. **Visual Regression & Accessibility Loops**: UI consistency and WCAG compliance (UI tasks)
7. **Database Migration Sanity**: Reversible migration testing (DB tasks)
8. **Style-guide Enforcement**: Automated brand consistency checks (UI tasks)
9. **Release & Rollback Discipline**: Safe deployment with rollback procedures

**Required by Task Type**:
- **Backend/API**: #1, #3, #4 (+ #2, #5 recommended)
- **UI/Frontend**: #1, #3, #6, #8 (+ #4, #5 recommended)  
- **Database**: #1, #3, #7 (+ #4, #5 recommended)
- **CI/DevOps**: #1, #2, #3, #4, #9 (+ #5 recommended)

*** CRITICAL AFTER YOU ARE DONE RESEARCHING AND EXPLORING THE CODEBASE BEFORE YOU START WRITING THE PRP ***

*** ULTRATHINK ABOUT THE PRP AND PLAN YOUR APPROACH THEN START WRITING THE PRP ***

## Output
Save as: `PRPs/{feature-name}.md`

## Quality Checklist
- [ ] All necessary context included
- [ ] Validation gates are executable by AI
- [ ] References existing patterns
- [ ] Clear implementation path
- [ ] Error handling documented
- [ ] Missing-checks validation framework included for task type
- [ ] Post-execution validation comprehensive (not just "tests pass")
- [ ] Security, performance, and accessibility considerations addressed

Score the PRP on a scale of 1-10 (confidence level to succeed in one-pass implementation using claude codes)

Remember: The goal is one-pass implementation success through comprehensive context.