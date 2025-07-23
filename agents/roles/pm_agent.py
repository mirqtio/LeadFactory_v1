#!/usr/bin/env python3
"""
PM/Developer Agent - Implements features and writes code
"""
import json
import os
from typing import Dict, Any, Optional

from ..core.base_worker import AgentWorker


class PMAgent(AgentWorker):
    """Project Manager / Developer Agent"""
    
    def __init__(self, agent_id: str):
        super().__init__("pm", agent_id, model="claude-3-5-sonnet-20241022")
        
    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build initial context for PM agent"""
        # Load relevant code files based on PRP
        code_context = self.load_relevant_code(prp_data)
        
        # Check for previous attempts
        retry_count = int(prp_data.get("retry_count", "0"))
        last_error = prp_data.get("last_error", "")
        
        system_prompt = f"""You are a senior software developer implementing PRP {prp_id}.

Your task is to implement the requirements specified in the PRP. You have access to the full codebase.

Current working directory: {os.getcwd()}

PRP Details:
- ID: {prp_id}
- Title: {prp_data.get('title', 'No title')}
- Priority: {prp_data.get('priority', 'medium')}
- Status: {prp_data.get('status', 'new')}

{'Previous attempt failed with: ' + last_error if retry_count > 0 else ''}

Workflow:
1. Understand the requirements thoroughly
2. Review existing code to understand patterns and conventions
3. Implement the solution following project standards
4. Write comprehensive tests
5. Run validation: `make quick-check`
6. Document your changes

When you need clarification, ask using:
QUESTION: Your specific question here

When implementation is complete, output evidence as JSON blocks:
```json
{{"key": "tests_passed", "value": "true"}}
{{"key": "coverage_pct", "value": "85"}}
{{"key": "lint_passed", "value": "true"}}
{{"key": "implementation_complete", "value": "true"}}
{{"key": "files_modified", "value": "file1.py,file2.py,test_file.py"}}
```

IMPORTANT: Do NOT push to GitHub. The integrator agent will handle that.
"""
        
        # Get PRP content
        prp_content = prp_data.get('content', '')
        if not prp_content and 'source_file' in prp_data:
            # Try to load from source file
            try:
                with open(prp_data['source_file'], 'r') as f:
                    prp_content = f.read()
            except:
                prp_content = "Could not load PRP content from source file"
        
        user_prompt = f"""Please implement PRP {prp_id}.

PRP Content:
{prp_content}

Relevant Code Context:
{code_context}

Begin by analyzing the requirements and planning your implementation approach."""
        
        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
    
    def load_relevant_code(self, prp_data: Dict[str, str]) -> str:
        """Load relevant code files based on PRP"""
        # This is a simplified version - in production you'd use embeddings
        # or other techniques to find relevant files
        
        relevant_files = []
        
        # Always include key files
        key_files = [
            "CLAUDE.md",
            ".claude/prompts/prp_completion_validator.md",
            "Makefile",
            "requirements.txt"
        ]
        
        for file_path in key_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        relevant_files.append(f"\n=== {file_path} ===\n{content[:2000]}...")
                except:
                    pass
        
        # Look for files mentioned in PRP
        prp_content = prp_data.get('content', '')
        if '.py' in prp_content or '.js' in prp_content:
            # Extract file references (simplified)
            import re
            file_refs = re.findall(r'[\w/]+\.\w+', prp_content)
            for ref in file_refs[:5]:  # Limit to avoid token explosion
                if os.path.exists(ref):
                    try:
                        with open(ref, 'r') as f:
                            content = f.read()
                            relevant_files.append(f"\n=== {ref} ===\n{content[:2000]}...")
                    except:
                        pass
        
        return "\n".join(relevant_files) if relevant_files else "No specific code files identified as relevant."
    
    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if PM task is complete"""
        required_evidence = [
            "implementation_complete",
            "tests_passed",
            "lint_passed"
        ]
        
        for key in required_evidence:
            if key not in evidence or evidence[key] != "true":
                return False
        
        # Check coverage if provided
        if "coverage_pct" in evidence:
            try:
                coverage = int(evidence["coverage_pct"])
                if coverage < 70:  # Minimum coverage threshold
                    self.logger.warning(f"Coverage too low: {coverage}%")
                    return False
            except:
                pass
        
        return True
    
    def get_next_queue(self) -> Optional[str]:
        """PM agents promote to validation queue"""
        # Use validator_queue to avoid conflicts with running agents
        return "validator_queue"
    
    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Process PM-specific response patterns"""
        result = super().process_response(prp_id, response)
        
        # Check for common PM patterns
        if "make quick-check" in response.lower():
            self.logger.info("PM is running validation")
            
        if "git commit" in response.lower() or "git push" in response.lower():
            self.logger.warning("PM attempting git operations - should be reminded not to push")
            
        # Extract file modifications
        if "files_modified" in result.get("evidence", {}):
            files = result["evidence"]["files_modified"].split(",")
            self.redis_client.hset(f"prp:{prp_id}", "modified_files", json.dumps(files))
        
        return result