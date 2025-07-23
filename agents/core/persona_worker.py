#!/usr/bin/env python3
"""
Persona-enhanced reliable worker with SuperClaude integration
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .reliable_worker import ReliableWorker


class PersonaWorker(ReliableWorker):
    """Enhanced worker with SuperClaude persona integration"""

    # Persona mapping for each agent role
    PERSONA_MAP = {
        "pm": {
            "primary": "backend",
            "secondary": ["analyzer", "architect"],
            "priorities": "Reliability > security > performance > features > convenience",
        },
        "dev": {
            "primary": "backend",
            "secondary": ["refactorer", "performance"],
            "priorities": "Code quality > test coverage > performance > features",
        },
        "validator": {
            "primary": "qa",
            "secondary": ["security", "performance"],
            "priorities": "Prevention > detection > correction > comprehensive coverage",
        },
        "validation": {
            "primary": "qa",
            "secondary": ["security", "performance"],
            "priorities": "Prevention > detection > correction > comprehensive coverage",
        },
        "integration": {
            "primary": "devops",
            "secondary": ["analyzer", "qa"],
            "priorities": "Automation > observability > reliability > scalability > manual processes",
        },
        "integrator": {
            "primary": "devops",
            "secondary": ["analyzer", "qa"],
            "priorities": "Automation > observability > reliability > scalability > manual processes",
        },
    }

    def __init__(self, role: str, agent_id: str, model: str = None):
        super().__init__(role, agent_id, model)
        self.persona_config = self.PERSONA_MAP.get(role, {})

    def build_persona_prompt(self) -> str:
        """Build SuperClaude persona activation prompt"""
        if not self.persona_config:
            return ""

        primary = self.persona_config.get("primary", "")
        secondary = self.persona_config.get("secondary", [])
        priorities = self.persona_config.get("priorities", "")

        prompt = f"""
=== SUPERCLAUDE PERSONA ACTIVATION ===
Primary Persona: {primary}
Secondary Personas: {', '.join(secondary)}
Priority Hierarchy: {priorities}

You are operating with the SuperClaude framework activated.
Apply the decision frameworks and quality standards of your assigned personas.
"""

        # Add persona-specific guidance
        if primary == "backend":
            prompt += """
Backend Persona Active:
- Ensure 99.9% reliability with fault-tolerance
- Implement security by default with defense in depth
- Maintain data integrity with ACID compliance
- Response time <200ms for API calls
"""
        elif primary == "qa":
            prompt += """
QA Persona Active:
- Build quality in rather than testing it in
- Test all scenarios including edge cases
- Prioritize testing based on risk and impact
- Ensure 80%+ test coverage (100% for critical paths)
"""
        elif primary == "devops":
            prompt += """
DevOps Persona Active:
- Infrastructure as Code principles
- Observability by default (monitoring, logging, alerting)
- Design for failure with automated recovery
- Zero-downtime deployments with rollback capability
"""

        return prompt

    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build context with persona enhancement"""
        # Get base context from parent
        context = super().build_context(prp_id, prp_data)

        # Enhance system prompt with persona
        persona_prompt = self.build_persona_prompt()
        if persona_prompt and context.get("messages"):
            for msg in context["messages"]:
                if msg["role"] == "system":
                    msg["content"] = persona_prompt + "\n\n" + msg["content"]
                    break

        return context

    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Enhanced response processing with better evidence extraction"""
        # Extract evidence using multiple strategies
        evidence = self.extract_evidence_multi_strategy(response)

        # Check for task completion markers
        completion_markers = [
            "deployment complete",
            "successfully deployed",
            "deployment successful",
            "deployment failed",
            "ci failed",
            "tests failed",
        ]

        is_complete = any(marker in response.lower() for marker in completion_markers)

        # Check for evidence completeness
        if evidence:
            is_complete = is_complete or self.check_completion_criteria(prp_id, evidence)

        # Extract questions
        question = None
        if "QUESTION:" in response:
            lines = response.split("\n")
            for line in lines:
                if line.strip().startswith("QUESTION:"):
                    question = line.replace("QUESTION:", "").strip()
                    break

        return {"complete": is_complete, "evidence": evidence, "needs_qa": question is not None, "question": question}

    def extract_evidence_multi_strategy(self, response: str) -> Dict[str, str]:
        """Extract evidence using multiple parsing strategies"""
        evidence = {}

        # Strategy 1: Standard JSON blocks
        evidence.update(self.extract_evidence(response))

        # Strategy 2: Look for deployment markers in plain text
        if "successfully deployed" in response.lower() or "deployment complete" in response.lower():
            evidence["deployed"] = "true"
            evidence["ci_passed"] = "true"

        if "deployment failed" in response.lower() or "ci failed" in response.lower():
            evidence["deployed"] = "false"
            evidence["ci_passed"] = "false"

        # Strategy 3: Extract structured data from response
        if "commit sha:" in response.lower():
            lines = response.split("\n")
            for line in lines:
                if "commit sha:" in line.lower():
                    sha = line.split(":")[-1].strip()
                    if sha:
                        evidence["commit_sha"] = sha

        # Strategy 4: Look for PR numbers
        import re

        pr_match = re.search(r"PR #?(\d+)", response, re.IGNORECASE)
        if pr_match:
            evidence["pr_number"] = pr_match.group(1)

        # Strategy 5: Extract URLs
        url_match = re.search(r"https?://[^\s]+", response)
        if url_match and "deployment_url" not in evidence:
            evidence["deployment_url"] = url_match.group(0).rstrip(".")

        return evidence

    def handle_completion(self, prp_id: str, evidence: dict):
        """Enhanced completion handling with validation"""
        self.logger.info(f"Completing {prp_id} with evidence: {evidence}")

        # Validate evidence based on persona standards
        if self.persona_config.get("primary") == "qa":
            # QA persona requires comprehensive validation
            if "validation_passed" not in evidence:
                self.logger.warning("QA persona: Missing validation status")
                evidence["validation_passed"] = "false"
                evidence["validation_notes"] = "Incomplete validation evidence"

        elif self.persona_config.get("primary") == "devops":
            # DevOps persona requires deployment verification
            if "deployed" not in evidence and "ci_passed" in evidence:
                # If CI passed but no explicit deployment status, infer it
                evidence["deployed"] = evidence["ci_passed"]

        # Call parent completion handler
        super().handle_completion(prp_id, evidence)

    def get_prp_data(self, prp_id: str) -> Dict[str, str]:
        """Get PRP data from Redis"""
        data = self.redis_client.hgetall(f"prp:{prp_id}")
        return {k.decode(): v.decode() for k, v in data.items()}

    def get_conversation_history(self, prp_id: str) -> List[Dict[str, Any]]:
        """Get conversation history from Redis"""
        history_key = f"prp:{prp_id}:history:{self.role}"
        history = []

        # Get all history entries
        entries = self.redis_client.lrange(history_key, 0, -1)
        for entry in entries:
            try:
                data = json.loads(entry)
                history.append(data)
            except:
                pass

        return history

    def build_continuation_context(self, prp_id: str, previous_response: str) -> Dict[str, Any]:
        """Build context for continuation with persona awareness"""
        prp_data = self.get_prp_data(prp_id)
        history = self.get_conversation_history(prp_id)

        # Build messages including history
        messages = []

        # Add system message with persona
        system_prompt = (
            self.build_persona_prompt()
            + f"""
Continue processing PRP {prp_id}.

Remember to output evidence when you complete major milestones.
If you encounter issues, use QUESTION: to ask for help.
"""
        )
        messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        for entry in history[-5:]:  # Last 5 turns
            if entry.get("role") == "assistant":
                messages.append({"role": "assistant", "content": entry["content"]})
            elif entry.get("role") == "user":
                messages.append({"role": "user", "content": entry["content"]})

        # Add continuation prompt
        messages.append({"role": "user", "content": "Please continue with the task. What's the next step?"})

        return {"messages": messages}
