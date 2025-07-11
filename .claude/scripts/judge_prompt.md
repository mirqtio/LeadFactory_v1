# LLM-as-Judge Scoring Prompt

You are an independent JUDGE evaluating a Product Requirements Prompt (PRP) for quality. Score each dimension from 1-5 based on the rubric below.

## Scoring Rubric

### 1. Clarity (1-5)
- 5: Crystal clear, zero ambiguity, junior dev could implement
- 4: Clear with minor clarifications needed
- 3: Generally clear but some vague areas
- 2: Multiple unclear sections
- 1: Confusing, contradictory, or incomprehensible

### 2. Feasibility (1-5)
- 5: Completely achievable with given constraints and timeline
- 4: Achievable with minor adjustments
- 3: Mostly feasible but some concerns
- 2: Significant feasibility issues
- 1: Unrealistic or impossible

### 3. Coverage (1-5)
- 5: All edge cases covered, comprehensive test criteria
- 4: Good coverage with minor gaps
- 3: Adequate coverage of main paths
- 2: Missing important scenarios
- 1: Insufficient coverage

### 4. Policy Compliance (1-5)
- 5: Perfect adherence to CURRENT_STATE.md rules
- 4: Compliant with trivial oversights
- 3: Generally compliant
- 2: Minor policy violations
- 1: Major violations of DO NOT IMPLEMENT

### 5. Technical Quality (1-5)
- 5: Excellent patterns, best practices, maintainable
- 4: Good technical approach
- 3: Acceptable technical design
- 2: Some poor technical choices
- 1: Bad practices or anti-patterns

## Response Format

```
SCORES:
- Clarity: X/5
- Feasibility: X/5
- Coverage: X/5
- Policy Compliance: X/5
- Technical Quality: X/5

OVERALL: X.X/5 (average)

STRENGTHS:
- [List 2-3 key strengths]

CONCERNS:
- [List any scores below 4 with brief explanation]

RECOMMENDATION: PASS/FAIL (require ≥4.0 average and no dimension <3)
```

## Example PRPs for Calibration

### 5/5 Example (Gold Standard)
- Every requirement has measurable criteria
- Dependencies explicitly listed with version numbers
- Test cases cover happy path + 3 edge cases
- Rollback strategy detailed
- No banned features referenced

### 3/5 Example (Borderline)
- Main requirements clear but acceptance vague
- Missing some dependencies
- Basic test coverage
- Generic rollback plan
- No policy violations

### 1/5 Example (Fail)
- Requirements like "make it fast"
- No clear acceptance criteria
- Missing critical dependencies
- No test plan
- References deprecated Yelp integration

Evaluate the PRP below: