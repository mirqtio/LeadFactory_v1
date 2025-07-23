#!/usr/bin/env python3
"""
Enhanced PM Agent with SuperClaude persona integration
"""
import json
from typing import Any, Dict, Optional

from ..core.persona_worker import PersonaWorker


class PMAgentV2(PersonaWorker):
    """Enhanced PM Agent with backend persona and reliability focus"""

    def __init__(self, agent_id: str):
        super().__init__("pm", agent_id, model="claude-3-5-sonnet-20241022")

    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build PM-specific context with enhanced persona"""
        requirements = prp_data.get("requirements", "No requirements found")
        success_criteria = prp_data.get("success_criteria", "No criteria found")

        system_prompt = f"""You are a Senior Backend Engineer (PM role) implementing PRP {prp_id}.

Your primary persona is Backend Engineer with these priorities:
- Reliability > Security > Performance > Features > Convenience
- 99.9% uptime with fault-tolerance
- Security by default with defense in depth
- Data integrity with ACID compliance
- Response time <200ms for API calls

Secondary personas:
- Analyzer: Evidence-based investigation and root cause analysis
- Architect: Long-term thinking and system design

PRP Details:
- ID: {prp_id}
- Title: {prp_data.get('title', 'No title')}

Requirements:
{requirements}

Success Criteria:
{success_criteria}

Implementation Guidelines:
1. Analyze the existing codebase to understand current implementation
2. Design a solution that maintains backward compatibility
3. Implement with comprehensive error handling and logging
4. Write unit tests with 80%+ coverage (100% for critical paths)
5. Ensure all linting and formatting standards are met
6. Document your changes appropriately

Available commands:
- File operations: ls, find, grep, cat, etc.
- Python: python, pytest, coverage, black, flake8
- Git: git status, git diff (but DO NOT commit)
- Make: make quick-check, make test, make format

If you need architectural guidance or encounter blockers:
QUESTION: Your specific question here

When implementation is complete, output evidence:
```json
{{"key": "tests_passed", "value": "true"}}
{{"key": "coverage_pct", "value": "85"}}
{{"key": "lint_passed", "value": "true"}}
{{"key": "implementation_complete", "value": "true"}}
{{"key": "files_modified", "value": ["file1.py", "file2.py"]}}
```
"""

        user_prompt = f"""Please implement PRP {prp_id}: {prp_data.get('title', 'No title')}

Start by understanding the current codebase structure and the specific requirements.
Use the analyzer persona to investigate the existing implementation before making changes.
Apply architect persona thinking for any design decisions.

Begin with exploring the codebase to understand the context."""

        return {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}

    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if PM task is complete with backend standards"""
        required = ["tests_passed", "coverage_pct", "lint_passed", "implementation_complete"]

        # Check all required evidence exists
        if not all(key in evidence for key in required):
            return False

        # Backend persona requires high quality standards
        try:
            coverage = int(evidence.get("coverage_pct", "0"))
            if coverage < 80:
                self.logger.warning(f"Coverage {coverage}% below backend standard of 80%")
                return False
        except ValueError:
            return False

        # All evidence must be positive
        return (
            evidence.get("tests_passed") == "true"
            and evidence.get("lint_passed") == "true"
            and evidence.get("implementation_complete") == "true"
        )

    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Process PM-specific response patterns"""
        result = super().process_response(prp_id, response)

        # Extract modified files from response
        if "files_modified" not in result.get("evidence", {}):
            files = self.extract_modified_files(response)
            if files:
                result["evidence"]["files_modified"] = json.dumps(files)

        # Monitor for backend-specific activities
        if any(phrase in response.lower() for phrase in ["error handling", "fault tolerance", "rollback"]):
            self.logger.info("PM applying reliability patterns")

        if any(phrase in response.lower() for phrase in ["security", "authentication", "authorization"]):
            self.logger.info("PM applying security patterns")

        return result

    def extract_modified_files(self, response: str) -> list:
        """Extract list of modified files from response"""
        files = []

        # Look for file paths in various formats
        import re

        # Match file paths like path/to/file.py
        file_patterns = [
            r"(?:modified|created|updated|wrote to|editing)\s+([a-zA-Z0-9_/.-]+\.py)",
            r"```python\n#\s*([a-zA-Z0-9_/.-]+\.py)",
            r"File:\s*([a-zA-Z0-9_/.-]+\.py)",
        ]

        for pattern in file_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            files.extend(matches)

        # Deduplicate
        return list(set(files))
