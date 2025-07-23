#!/usr/bin/env python3
"""
Enhanced Validator Agent with SuperClaude persona integration
"""
import json
from typing import Any, Dict, Optional

from ..core.persona_worker import PersonaWorker


class ValidatorAgentV2(PersonaWorker):
    """Enhanced Validator Agent with QA persona and quality focus"""

    def __init__(self, agent_id: str):
        super().__init__("validator", agent_id, model="claude-3-5-sonnet-20241022")

    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build validator-specific context with QA persona"""
        pm_evidence = {
            "tests_passed": prp_data.get("tests_passed", "unknown"),
            "coverage_pct": prp_data.get("coverage_pct", "0"),
            "lint_passed": prp_data.get("lint_passed", "unknown"),
            "implementation_complete": prp_data.get("implementation_complete", "unknown"),
            "files_modified": json.loads(prp_data.get("files_modified", "[]")),
        }

        system_prompt = f"""You are a Senior QA Engineer (Validator role) reviewing PRP {prp_id}.

Your primary persona is QA with these priorities:
- Prevention > Detection > Correction > Comprehensive Coverage
- Build quality in rather than testing it in
- Test all scenarios including edge cases
- Risk-based testing prioritization
- 100% requirement coverage validation

Secondary personas:
- Security: Threat modeling and vulnerability assessment
- Performance: Optimization and bottleneck detection

PRP Details:
- ID: {prp_id}
- Title: {prp_data.get('title', 'No title')}
- Implemented by: {prp_data.get('pm_completed_by', 'unknown')}

PM Evidence:
- Tests Passed: {pm_evidence['tests_passed']}
- Coverage: {pm_evidence['coverage_pct']}%
- Lint Passed: {pm_evidence['lint_passed']}
- Files Modified: {', '.join(pm_evidence['files_modified'])}

Success Criteria to Validate:
{prp_data.get('success_criteria', 'No criteria found')}

Validation Checklist:
1. Verify all success criteria are met
2. Review code quality and maintainability
3. Check test coverage and quality
4. Perform security review (OWASP Top 10)
5. Analyze performance implications
6. Validate error handling and edge cases
7. Ensure documentation is adequate
8. Check for breaking changes

Available commands:
- Code review: cat, grep, git diff
- Testing: pytest -v, coverage report
- Security: bandit, safety check
- Performance: python -m cProfile
- Quality: flake8, black --check, mypy

If validation passes, output:
```json
{{"key": "validation_passed", "value": "true"}}
{{"key": "quality_score", "value": "90"}}
{{"key": "security_review", "value": "passed"}}
{{"key": "performance_review", "value": "passed"}}
{{"key": "breaking_changes", "value": "none"}}
```

If validation fails, output:
```json
{{"key": "validation_passed", "value": "false"}}
{{"key": "validation_issues", "value": ["issue1", "issue2"]}}
{{"key": "recommended_fixes", "value": ["fix1", "fix2"]}}
```
"""

        user_prompt = f"""Please perform a comprehensive validation of PRP {prp_id}.

Start by reviewing the modified files and understanding what was implemented.
Then systematically validate against all success criteria.

Modified files to review:
{chr(10).join(pm_evidence['files_modified'])}

Begin with examining the implementation."""

        return {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}

    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if validation is complete"""
        # Must have validation result
        if "validation_passed" not in evidence:
            return False

        # If passed, need quality metrics
        if evidence.get("validation_passed") == "true":
            return "quality_score" in evidence

        # If failed, need issues and recommendations
        if evidence.get("validation_passed") == "false":
            return "validation_issues" in evidence

        return False

    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Process validator-specific response patterns"""
        result = super().process_response(prp_id, response)

        # QA persona specific monitoring
        if "edge case" in response.lower() or "corner case" in response.lower():
            self.logger.info("Validator examining edge cases")

        if "security" in response.lower() and any(vuln in response.lower() for vuln in ["injection", "xss", "csrf"]):
            self.logger.info("Validator performing security analysis")

        if "performance" in response.lower() and any(
            term in response.lower() for term in ["bottleneck", "optimization", "latency"]
        ):
            self.logger.info("Validator analyzing performance")

        # Auto-detect validation failure patterns
        failure_indicators = [
            "does not meet",
            "fails to",
            "missing requirement",
            "incomplete implementation",
            "security vulnerability",
            "performance regression",
        ]

        if any(indicator in response.lower() for indicator in failure_indicators):
            if "validation_passed" not in result.get("evidence", {}):
                result["evidence"]["validation_passed"] = "false"
                self.logger.warning("Auto-detected validation failure indicators")

        return result

    def handle_completion(self, prp_id: str, evidence: Dict[str, str]):
        """Handle validation completion with QA standards"""
        # Apply QA persona standards
        if evidence.get("validation_passed") == "true":
            # Ensure quality score meets standards
            try:
                score = int(evidence.get("quality_score", "0"))
                if score < 80:
                    self.logger.warning(f"Quality score {score} below QA standard of 80")
                    evidence["validation_passed"] = "false"
                    evidence["validation_notes"] = f"Quality score {score} below minimum 80"
            except ValueError:
                pass

        # Log validation decision
        if evidence.get("validation_passed") == "true":
            self.logger.info(f"✅ Validation PASSED for {prp_id}")
        else:
            self.logger.warning(f"❌ Validation FAILED for {prp_id}")

        super().handle_completion(prp_id, evidence)
