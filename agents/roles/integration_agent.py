#!/usr/bin/env python3
"""
Integration Agent - Handles CI/CD and deployment
"""
import json
import subprocess
from typing import Dict, Any, Optional

from ..core.base_worker import AgentWorker


class IntegrationAgent(AgentWorker):
    """Integration Agent - CI/CD and deployment"""
    
    def __init__(self, agent_id: str):
        super().__init__("integration", agent_id, model="claude-3-5-sonnet-20241022")
        
    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build initial context for Integration agent"""
        modified_files = json.loads(prp_data.get("modified_files", "[]"))
        
        # Check git status
        git_status = self.get_git_status()
        current_branch = self.get_current_branch()
        
        system_prompt = f"""You are a senior DevOps engineer handling the deployment of PRP {prp_id}.

Your responsibilities:
1. Ensure code is properly committed with descriptive messages
2. Push changes to the correct branch
3. Monitor CI/CD pipeline execution
4. Diagnose and resolve any CI failures
5. Verify successful deployment
6. Handle rollbacks if necessary

Current Environment:
- Branch: {current_branch}
- Modified files: {', '.join(modified_files)}
- Git status: {git_status[:500]}...

PRP Details:
- ID: {prp_id}
- Title: {prp_data.get('title', 'No title')}
- Validated by: {prp_data.get('validator_completed_by', 'unknown')}

CI/CD Workflow:
1. Create feature branch if needed: feat/{prp_id.lower()}-description
2. Commit changes with clear message
3. Push to GitHub
4. Monitor GitHub Actions CI
5. If CI fails, diagnose and fix
6. Once CI passes, merge to main (if applicable)
7. Verify deployment

Available commands:
- git status, git add, git commit, git push
- gh pr create, gh pr checks, gh pr merge
- make quick-check (local validation)
- make bpci-fast (comprehensive local CI)

If you need help or encounter issues:
QUESTION: Your specific question here

When deployment is complete, output:
```json
{{"key": "ci_passed", "value": "true"}}
{{"key": "deployed", "value": "true"}}
{{"key": "deployment_url", "value": "https://..."}}
{{"key": "commit_sha", "value": "abc123..."}}
{{"key": "pr_number", "value": "123"}}
```

If deployment fails, output:
```json
{{"key": "ci_passed", "value": "false"}}
{{"key": "ci_failure_reason", "value": "..."}}
{{"key": "ci_logs", "value": "..."}}
```
"""
        
        user_prompt = f"""Please handle the integration and deployment of PRP {prp_id}.

Start by checking the current git status and planning your approach to commit and deploy these changes.

Modified files that need to be committed:
{chr(10).join(modified_files)}

Begin with `git status` to see the current state."""
        
        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
    
    def get_git_status(self) -> str:
        """Get current git status"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
        except Exception as e:
            return f"Error getting git status: {e}"
    
    def get_current_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception as e:
            return "unknown"
    
    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if integration task is complete"""
        # Either successfully deployed or definitively failed
        if evidence.get("deployed") == "true":
            return "ci_passed" in evidence and "commit_sha" in evidence
        elif evidence.get("ci_passed") == "false":
            return "ci_failure_reason" in evidence
        
        return False
    
    def get_next_queue(self) -> Optional[str]:
        """Integration is the final stage"""
        return None  # No next queue - marks as complete
    
    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Process integration-specific patterns"""
        result = super().process_response(prp_id, response)
        
        # Monitor for specific integration activities
        if "git commit" in response.lower():
            self.logger.info("Integration agent committing changes")
            
        if "git push" in response.lower():
            self.logger.info("Integration agent pushing to GitHub")
            
        if "gh pr create" in response.lower():
            self.logger.info("Integration agent creating PR")
            
        if "ci failed" in response.lower() or "tests failed" in response.lower():
            self.logger.warning("CI failure detected")
            
        # Check if agent is trying to debug CI
        if any(phrase in response.lower() for phrase in ["checking logs", "debugging", "investigating failure"]):
            self.logger.info("Integration agent debugging CI failure")
        
        return result
    
    def handle_completion(self, prp_id: str, evidence: Dict[str, str]):
        """Handle integration completion"""
        if evidence.get("deployed") == "true":
            # Successful deployment
            self.logger.info(f"Successfully deployed {prp_id}")
            self.redis_client.hset(f"prp:{prp_id}", mapping={
                "deployment_successful": "true",
                "deployment_url": evidence.get("deployment_url", ""),
                "commit_sha": evidence.get("commit_sha", ""),
                "pr_number": evidence.get("pr_number", "")
            })
        else:
            # Failed deployment
            self.logger.error(f"Deployment failed for {prp_id}")
            self.redis_client.hset(f"prp:{prp_id}", mapping={
                "deployment_successful": "false",
                "ci_failure_reason": evidence.get("ci_failure_reason", "Unknown"),
                "ci_logs": evidence.get("ci_logs", "")[:1000]  # Truncate logs
            })
        
        # Always mark as complete (success or failure)
        super().handle_completion(prp_id, evidence)