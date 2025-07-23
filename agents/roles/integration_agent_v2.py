#!/usr/bin/env python3
"""
Enhanced Integration Agent with SuperClaude persona integration
"""
import json
import subprocess
from typing import Any, Dict, Optional

from ..core.persona_worker import PersonaWorker


class IntegrationAgentV2(PersonaWorker):
    """Enhanced Integration Agent with DevOps persona and automation focus"""

    def __init__(self, agent_id: str):
        # Use Sonnet 4 as requested by user for better effectiveness
        super().__init__("integration", agent_id, model="claude-3-5-sonnet-20241022")

    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build integration-specific context with DevOps persona"""
        modified_files = json.loads(prp_data.get("files_modified", "[]"))

        # Check git status
        git_status = self.get_git_status()
        current_branch = self.get_current_branch()

        system_prompt = f"""You are a Senior DevOps Engineer (Integration role) deploying PRP {prp_id}.

Your primary persona is DevOps with these priorities:
- Automation > Observability > Reliability > Scalability > Manual Processes
- Infrastructure as Code principles
- Observability by default (monitoring, logging, alerting)
- Design for failure with automated recovery
- Zero-downtime deployments with rollback capability

Secondary personas:
- Analyzer: Systematic investigation of CI/CD failures
- QA: Deployment validation and smoke testing

PRP Details:
- ID: {prp_id}
- Title: {prp_data.get('title', 'No title')}
- Validated by: {prp_data.get('validator_completed_by', 'unknown')}
- Quality Score: {prp_data.get('quality_score', 'N/A')}

Current Environment:
- Branch: {current_branch}
- Modified files: {', '.join(modified_files)}
- Git status preview: {git_status[:300]}...

Deployment Workflow:
1. Create feature branch: feat/{prp_id.lower()}-<short-description>
2. Stage and commit changes with descriptive message
3. Push to GitHub: git push origin <branch>
4. Create PR if needed: gh pr create
5. Monitor CI status: gh pr checks
6. Handle any CI failures with debugging
7. Once CI passes, deployment is automatic
8. Verify deployment success

Critical Requirements:
- Use atomic commits with clear messages
- Never force push or use --force flags
- Always verify CI status before proceeding
- Implement rollback plan if deployment fails

Available commands:
- Git: git status, git add, git commit, git push
- GitHub CLI: gh pr create, gh pr checks, gh pr merge
- Validation: make quick-check, make bpci-fast
- Monitoring: Check GitHub Actions logs

When you successfully complete the deployment:
```json
{{"key": "ci_passed", "value": "true"}}
{{"key": "deployed", "value": "true"}}
{{"key": "deployment_url", "value": "https://github.com/user/repo/actions/runs/123"}}
{{"key": "commit_sha", "value": "abc123def456"}}
{{"key": "pr_number", "value": "456"}}
```

If deployment fails:
```json
{{"key": "ci_passed", "value": "false"}}
{{"key": "deployed", "value": "false"}}
{{"key": "ci_failure_reason", "value": "Detailed reason for failure"}}
{{"key": "rollback_performed", "value": "true/false"}}
```

IMPORTANT: After committing and pushing, you MUST verify CI passes before marking as complete.
"""

        user_prompt = f"""Please deploy PRP {prp_id} following DevOps best practices.

Start by checking git status to see current state, then create atomic commits and push.
Monitor the CI pipeline and handle any failures.

Modified files that need deployment:
{chr(10).join(modified_files)}

Begin with: git status"""

        return {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}

    def get_git_status(self) -> str:
        """Get current git status"""
        try:
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5)
            return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
        except Exception as e:
            return f"Error getting git status: {e}"

    def get_current_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception as e:
            return "unknown"

    def get_next_queue(self) -> Optional[str]:
        """Integration is the final stage"""
        return None  # No next queue - marks as complete

    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if integration task is complete with DevOps standards"""
        # Must have deployment status
        if "deployed" not in evidence:
            return False

        # If successfully deployed
        if evidence.get("deployed") == "true":
            # DevOps standards require verification
            required = ["ci_passed", "commit_sha"]
            return all(key in evidence for key in required) and evidence.get("ci_passed") == "true"

        # If deployment failed
        if evidence.get("deployed") == "false":
            # Must have failure reason for observability
            return "ci_failure_reason" in evidence

        return False

    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Process integration-specific response patterns"""
        result = super().process_response(prp_id, response)

        # DevOps persona monitoring
        if "git commit" in response.lower():
            self.logger.info("DevOps: Creating atomic commit")

        if "git push" in response.lower():
            self.logger.info("DevOps: Pushing to remote repository")

        if "gh pr create" in response.lower():
            self.logger.info("DevOps: Creating pull request")

        if "gh pr checks" in response.lower():
            self.logger.info("DevOps: Monitoring CI pipeline")

        # Auto-detect CI status from response
        if "all checks have passed" in response.lower() or "ci: success" in response.lower():
            if "ci_passed" not in result.get("evidence", {}):
                result["evidence"]["ci_passed"] = "true"
                self.logger.info("Auto-detected CI success")

        if "checks failed" in response.lower() or "ci: failure" in response.lower():
            if "ci_passed" not in result.get("evidence", {}):
                result["evidence"]["ci_passed"] = "false"
                self.logger.warning("Auto-detected CI failure")

        # Extract commit SHA from response
        import re

        sha_match = re.search(r"commit ([a-f0-9]{7,40})", response.lower())
        if sha_match and "commit_sha" not in result.get("evidence", {}):
            result["evidence"]["commit_sha"] = sha_match.group(1)

        return result

    def handle_completion(self, prp_id: str, evidence: Dict[str, str]):
        """Handle integration completion with DevOps standards"""
        # Apply DevOps observability standards
        if evidence.get("deployed") == "true":
            self.logger.info(f"✅ Successfully deployed {prp_id}")
            self.logger.info(f"   Commit: {evidence.get('commit_sha', 'unknown')}")
            self.logger.info(f"   PR: #{evidence.get('pr_number', 'N/A')}")

            # Add deployment metadata
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={
                    "deployment_successful": "true",
                    "deployment_timestamp": self.get_timestamp(),
                    "deployment_url": evidence.get("deployment_url", ""),
                    "deployed_by": self.agent_id,
                },
            )
        else:
            self.logger.error(f"❌ Deployment failed for {prp_id}")
            self.logger.error(f"   Reason: {evidence.get('ci_failure_reason', 'Unknown')}")

            # Record failure for observability
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={
                    "deployment_successful": "false",
                    "deployment_failure_timestamp": self.get_timestamp(),
                    "deployment_failure_reason": evidence.get("ci_failure_reason", "Unknown"),
                    "rollback_performed": evidence.get("rollback_performed", "false"),
                },
            )

        super().handle_completion(prp_id, evidence)

    def get_timestamp(self) -> str:
        """Get current ISO timestamp"""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"
