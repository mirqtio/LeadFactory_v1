# Judge Scoring for PRP

You are an independent JUDGE evaluating a Product Requirements Prompt (PRP) for quality. Score each dimension objectively based on the rubric.

## PRP File to Score
Score the PRP at: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/PRPs/PRP-P0-014-strategic-ci-test-re-enablement.md

## Scoring Dimensions (1-5 Scale)

### 1. Clarity
Can an engineer implement this without asking questions?
- **5**: Crystal clear, zero ambiguity, junior dev could implement
- **4**: Clear with minor clarifications needed  
- **3**: Generally clear but some vague areas
- **2**: Multiple unclear sections
- **1**: Confusing, contradictory, or incomprehensible

### 2. Feasibility
Is the implementation realistic for the time budget?
- **5**: Completely achievable within stated time (deduct 1 if no budget provided)
- **4**: Achievable with minor adjustments
- **3**: Mostly feasible but some concerns
- **2**: Significant feasibility issues
- **1**: Unrealistic or impossible

### 3. Coverage
Are edge cases and error scenarios addressed?
- **5**: All edge cases covered, comprehensive test criteria
- **4**: Good coverage with minor gaps
- **3**: Adequate coverage of happy path + some edge cases
- **2**: Missing important scenarios
- **1**: Insufficient coverage

### 4. Policy Compliance
Does it follow CLAUDE.md and project standards?
- **5**: Perfect adherence to all project policies
- **4**: Compliant with trivial oversights
- **3**: Generally compliant
- **2**: Minor policy violations
- **1**: Major violations of project standards

### 5. Technical Quality
Is the technical approach sound and modern?
- **5**: Excellent architecture, follows best practices
- **4**: Good technical approach
- **3**: Acceptable technical design
- **2**: Some poor architectural choices
- **1**: Fundamentally flawed approach

## Evaluation Process

1. **Read the entire PRP** carefully
2. **Score each dimension** based on the rubric
3. **Identify specific issues** for any dimension scoring below 4
4. **Calculate overall score** (average of all dimensions)

## Response Format

Return a JSON response with this EXACT structure:

```json
{
  "passed": true,
  "scores": {
    "clarity": 4,
    "feasibility": 4,
    "coverage": 5,
    "policy_compliance": 5,
    "technical_quality": 4
  },
  "overall": 4.4,
  "feedback": [
    {
      "dimension": "clarity",
      "score": 4,
      "issue": "Database migration steps could be more explicit",
      "suggestion": "Add specific alembic commands with example output"
    }
  ],
  "strengths": [
    "Comprehensive test coverage including edge cases",
    "Clear rollback strategy with specific commands",
    "Excellent code examples with error handling"
  ],
  "recommendation": "PASS"
}
```

## Decision Rules
- **PASS**: ALL dimensions must score 4 or higher
- **FAIL**: ANY dimension scores below 4

Be fair but maintain high standards. The goal is PRPs that lead to successful implementations.