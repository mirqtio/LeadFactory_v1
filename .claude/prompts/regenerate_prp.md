# PRP Regeneration Prompt

You are regenerating a PRP based on validation feedback. Address ALL feedback while maintaining the PRP's core structure and objectives.

## Feedback to Address

### Research Issues (if any):
{research_issues}

### CRITIC Issues (if any):
{critic_issues}

### Judge Feedback (if any):
{judge_feedback}

### UI Issues (if any):
{ui_issues}

### Missing-Checks Issues (if any):
{missing_checks_issues}

## Regeneration Guidelines

### 1. Address Research Gaps
- Add missing authoritative sources
- Update outdated practices
- Include recent developments
- Verify all technical claims

### 2. Fix CRITIC Issues by Priority
**HIGH Severity (must fix):**
- Remove placeholder content
- Add missing implementation details
- Clarify vague requirements
- Fix technical inaccuracies

**MEDIUM Severity (should fix):**
- Improve clarity and specificity
- Add missing edge cases
- Enhance error handling
- Strengthen integration details

**LOW Severity (consider fixing):**
- Style and formatting improvements
- Additional documentation
- Minor clarifications

### 3. Respond to Judge Feedback
For each dimension scored below 4:

**Clarity Issues:**
- Make requirements more specific and measurable
- Remove ambiguous language
- Add concrete examples
- Clarify acceptance criteria

**Feasibility Issues:**
- Adjust timeline or scope
- Address resource constraints
- Simplify complex requirements
- Add risk mitigation

**Coverage Issues:**
- Add missing edge cases
- Expand test scenarios
- Include error handling paths
- Address integration points

**Policy Compliance Issues:**
- Remove deprecated features (check CURRENT_STATE.md)
- Follow established patterns
- Respect DO NOT IMPLEMENT list
- Align with current architecture

**Technical Quality Issues:**
- Improve implementation approach
- Follow best practices
- Enhance maintainability
- Add proper error handling

**Missing-Checks Validation Issues:**
- Add required validation frameworks for task type
- Include pre-commit hooks
- Add security scanning requirements
- Include performance/accessibility testing
- Add rollback procedures

### 4. UI-Specific Fixes
- Reference design tokens from `tokens/design_tokens.json`
- Include accessibility requirements (WCAG 2.1 AA)
- Add component pattern compliance
- Ensure no hardcoded colors/spacing

### 5. Missing-Checks Framework
Ensure the PRP includes appropriate validation for task type:

**Backend/API:** Pre-commit hooks, branch protection, security scanning, performance budgets
**UI/Frontend:** Above + visual regression, accessibility testing, style guide enforcement  
**Database:** Above + migration sanity testing
**CI/DevOps:** Above + CI automation, release procedures

## Regeneration Process
1. **Preserve core structure** - Don't change the fundamental goal or approach
2. **Address all feedback** - Every issue mentioned must be resolved
3. **Maintain quality** - Ensure the PRP remains comprehensive and executable
4. **Enhance missing areas** - Add content where gaps were identified
5. **Verify completeness** - Check that all success criteria are measurable

## Output Requirements
- Keep the same PRP ID and basic structure
- Address every piece of feedback provided
- Maintain or improve the technical quality
- Ensure all missing-checks requirements are included
- Make all acceptance criteria measurable and testable

The regenerated PRP should resolve all validation failures while maintaining implementation feasibility.