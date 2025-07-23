#!/usr/bin/env python3
"""
Validator Agent - Reviews code and validates implementations
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional

from ..core.base_worker import AgentWorker


class ValidatorAgent(AgentWorker):
    """Validator Agent - QA and code review"""

    def __init__(self, agent_id: str):
        # Use validator role/queue to avoid conflicts with running validation_queue agents
        super().__init__("validator", agent_id, model="claude-3-5-sonnet-20241022")

    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build initial context for Validator agent"""
        # Load PM's work
        pm_history = self.load_pm_history(prp_id)
        modified_files = json.loads(prp_data.get("modified_files", "[]"))

        system_prompt = f"""You are a senior QA engineer and code reviewer validating PRP {prp_id}.

Your role is to thoroughly review the PM's implementation for:
1. Correctness - Does it meet all requirements?
2. Quality - Is the code well-written and maintainable?
3. Testing - Are there comprehensive tests with good coverage?
4. Security - Are there any security concerns?
5. Performance - Are there any performance issues?
6. Standards - Does it follow project conventions?

PRP Details:
- ID: {prp_id}
- Title: {prp_data.get('title', 'No title')}
- PM Evidence: tests_passed={prp_data.get('tests_passed')}, coverage={prp_data.get('coverage_pct')}%, lint_passed={prp_data.get('lint_passed')}

Modified Files: {', '.join(modified_files)}

Review Process:
1. Review the PM's implementation and conversation
2. Check the modified files for quality and correctness
3. Verify tests are comprehensive and meaningful
4. Run additional validation if needed
5. Provide specific feedback if improvements are needed

If you need clarification or additional information:
QUESTION: Your specific question here

When validation is complete and approved, output:
```json
{{"key": "validation_passed", "value": "true"}}
{{"key": "quality_score", "value": "90"}}
{{"key": "security_review", "value": "passed"}}
{{"key": "performance_review", "value": "passed"}}
```

If validation fails, output:
```json
{{"key": "validation_passed", "value": "false"}}
{{"key": "validation_issues", "value": "Issue 1: ..., Issue 2: ..."}}
{{"key": "required_changes", "value": "Change 1: ..., Change 2: ..."}}
```
"""

        # Load file contents for review
        file_contents = self.load_modified_files(modified_files)

        user_prompt = f"""Please validate the implementation for PRP {prp_id}.

PRP Requirements:
{prp_data.get('content', 'No content available')}

PM's Implementation Summary:
{pm_history}

Modified Files to Review:
{file_contents}

Begin your validation by reviewing the implementation against the requirements."""

        return {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}

    def load_pm_history(self, prp_id: str) -> str:
        """Load and summarize PM's work"""
        history = self.redis_client.lrange(f"prp:{prp_id}:history:pm", 0, -1)

        if not history:
            return "No PM history available"

        summary = []
        for entry in history[-3:]:  # Last 3 interactions
            try:
                data = json.loads(entry.decode() if isinstance(entry, bytes) else entry)
                response = data.get("response", "")
                # Extract key points
                if "implementation" in response.lower() or "complete" in response.lower():
                    summary.append(f"PM: {response[:500]}...")
            except:
                pass

        return "\n\n".join(summary) if summary else "Could not parse PM history"

    def load_modified_files(self, file_paths: list) -> str:
        """Load contents of modified files"""
        contents = []

        for file_path in file_paths[:10]:  # Limit to avoid token explosion
            try:
                with open(file_path.strip(), "r") as f:
                    content = f.read()
                    contents.append(f"\n=== {file_path} ===\n{content}")
            except Exception as e:
                contents.append(f"\n=== {file_path} ===\nError loading file: {e}")

        return "\n".join(contents) if contents else "No files loaded for review"

    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if validation task is complete"""
        # Must have explicit validation result
        if "validation_passed" not in evidence:
            return False

        if evidence["validation_passed"] == "true":
            # Passed validation - check for required fields
            return all(key in evidence for key in ["quality_score"])
        else:
            # Failed validation - check for required feedback
            return all(key in evidence for key in ["validation_issues", "required_changes"])

    def get_next_queue(self) -> Optional[str]:
        """Validator promotes to integration queue if passed"""
        # Check if validation passed
        prp_data = self.load_prp_data(self.current_prp)
        if prp_data.get("validation_passed") == "true":
            return "integration_queue"
        else:
            # Failed validation goes back to dev
            return "dev_queue"

    def handle_completion(self, prp_id: str, evidence: Dict[str, str]):
        """Handle validation completion"""
        if evidence.get("validation_passed") == "true":
            # Passed - continue normal flow
            super().handle_completion(prp_id, evidence)
        else:
            # Failed - send back to PM with feedback
            self.logger.info(f"Validation failed for {prp_id}, sending back to dev")

            # Add validation feedback
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={
                    "validation_failed_at": datetime.utcnow().isoformat(),
                    "validation_issues": evidence.get("validation_issues", ""),
                    "required_changes": evidence.get("required_changes", ""),
                    "validation_attempts": int(self.redis_client.hget(f"prp:{prp_id}", "validation_attempts") or 0) + 1,
                },
            )

            # Move back to dev queue
            self.redis_client.lrem(f"{self.queue}:inflight", 0, prp_id)
            self.redis_client.lpush("dev_queue", prp_id)
