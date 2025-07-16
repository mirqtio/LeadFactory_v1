#!/usr/bin/env python3
"""
User Prompt Submit Hook for PRP Status Management
Intercepts and validates PRP status change requests from user prompts
"""

import os
import re
import sys
from typing import Dict, List, Optional, Tuple

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prp_state_manager import PRPStateManager, PRPStatus


class PRPUserPromptHook:
    """User prompt hook for PRP status management"""

    def __init__(self):
        self.prp_manager = PRPStateManager()
        self.prp_keywords = [
            "start",
            "begin",
            "execute",
            "implement",
            "complete",
            "finish",
            "done",
            "validate",
            "prp",
            "requirement",
            "plan",
        ]

    def _extract_prp_references(self, prompt: str) -> List[str]:
        """Extract PRP IDs from user prompt"""
        # Look for PRP patterns
        patterns = [
            r"\b(P[0-9]+-[0-9]+)\b",  # P1-020, P2-000, etc.
            r"PRP[\s-]*(P[0-9]+-[0-9]+)",  # PRP P1-020
        ]

        prp_ids = []
        for pattern in patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                prp_id = match.group(1).upper()
                if prp_id not in prp_ids:
                    prp_ids.append(prp_id)

        return prp_ids

    def _detect_status_change_intent(self, prompt: str) -> Optional[str]:
        """Detect if user is requesting a status change"""
        prompt_lower = prompt.lower()

        # Start/Begin patterns - expanded to match common user commands
        start_patterns = [
            r"start\s+(P[0-9]+-[0-9]+)",
            r"begin\s+(P[0-9]+-[0-9]+)",
            r"execute\s+(P[0-9]+-[0-9]+)",
            r"implement\s+(P[0-9]+-[0-9]+)",
            r"work\s+on\s+(P[0-9]+-[0-9]+)",
            r"(P[0-9]+-[0-9]+).*execute",
            r"(P[0-9]+-[0-9]+).*implement",
            r"(P[0-9]+-[0-9]+).*start",
            r"(P[0-9]+-[0-9]+).*begin",
            r"continue\s+with\s+(P[0-9]+-[0-9]+)",
            r"proceed\s+with\s+(P[0-9]+-[0-9]+)",
            r"move\s+to\s+(P[0-9]+-[0-9]+)",
            r"next.*execute\s+(P[0-9]+-[0-9]+)",
        ]

        for pattern in start_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return "start"

        # Complete patterns - expanded
        complete_patterns = [
            r"complete\s+(P[0-9]+-[0-9]+)",
            r"finish\s+(P[0-9]+-[0-9]+)",
            r"done\s+with\s+(P[0-9]+-[0-9]+)",
            r"(P[0-9]+-[0-9]+)\s+is\s+complete",
            r"(P[0-9]+-[0-9]+).*complete",
            r"(P[0-9]+-[0-9]+).*finished",
            r"(P[0-9]+-[0-9]+).*done",
            r"finalize\s+(P[0-9]+-[0-9]+)",
            r"wrap\s+up\s+(P[0-9]+-[0-9]+)",
        ]

        for pattern in complete_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return "complete"

        # Validate patterns
        validate_patterns = [
            r"validate\s+(P[0-9]+-[0-9]+)",
            r"verify\s+(P[0-9]+-[0-9]+)",
            r"check\s+(P[0-9]+-[0-9]+)",
            r"status\s+(P[0-9]+-[0-9]+)",
            r"(P[0-9]+-[0-9]+).*status",
            r"(P[0-9]+-[0-9]+).*validate",
            r"(P[0-9]+-[0-9]+).*verify",
        ]

        for pattern in validate_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return "validate"

        return None

    def _validate_prp_start_request(self, prp_id: str) -> Tuple[bool, str]:
        """Validate request to start a PRP"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            return False, f"PRP {prp_id} not found"

        if prp.status != PRPStatus.VALIDATED:
            return False, (
                f"Cannot start PRP {prp_id} (current status: {prp.status.value}). "
                f"PRP must be in 'validated' state to start. "
                f"Current state allows these transitions: {self._get_allowed_transitions(prp.status)}"
            )

        # Check if there are other PRPs in progress
        in_progress_prps = self.prp_manager.get_in_progress_prps()
        if in_progress_prps:
            in_progress_ids = [prp.prp_id for prp in in_progress_prps]
            return False, (
                f"Cannot start PRP {prp_id} while other PRPs are in progress: {', '.join(in_progress_ids)}. "
                f"Complete current PRPs before starting new ones."
            )

        return True, f"PRP {prp_id} can be started"

    def _validate_prp_complete_request(self, prp_id: str) -> Tuple[bool, str]:
        """Validate request to complete a PRP"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            return False, f"PRP {prp_id} not found"

        if prp.status != PRPStatus.IN_PROGRESS:
            return False, (
                f"Cannot complete PRP {prp_id} (current status: {prp.status.value}). "
                f"PRP must be in 'in_progress' state to complete."
            )

        # Check completion requirements
        valid, message = self.prp_manager.validate_transition(prp_id, PRPStatus.COMPLETE)
        if not valid:
            return False, f"PRP {prp_id} completion blocked: {message}"

        return True, f"PRP {prp_id} can be completed"

    def _get_allowed_transitions(self, current_status: PRPStatus) -> List[str]:
        """Get allowed transitions from current status"""
        transitions = {
            PRPStatus.NEW: ["validated"],
            PRPStatus.VALIDATED: ["in_progress"],
            PRPStatus.IN_PROGRESS: ["complete"],
            PRPStatus.COMPLETE: [],
        }
        return transitions.get(current_status, [])

    def _generate_status_response(self, prp_ids: List[str]) -> str:
        """Generate status response for requested PRPs"""
        response_parts = []

        for prp_id in prp_ids:
            prp = self.prp_manager.get_prp(prp_id)
            if prp:
                response_parts.append(
                    f"**{prp_id}**: {prp.title} - Status: `{prp.status.value}` "
                    f"(Allowed transitions: {', '.join(self._get_allowed_transitions(prp.status)) or 'none'})"
                )
            else:
                response_parts.append(f"**{prp_id}**: Not found")

        return "\\n".join(response_parts)

    def _should_intercept_prompt(self, prompt: str) -> bool:
        """Check if prompt should be intercepted for PRP management"""
        prompt_lower = prompt.lower()

        # Check for PRP ID patterns
        has_prp_id = bool(self._extract_prp_references(prompt))

        # Check for status change intent
        has_status_intent = self._detect_status_change_intent(prompt) is not None

        # If we have both PRP ID and status intent, intercept
        # Remove the keyword requirement as it's too restrictive
        return has_prp_id and has_status_intent

    def process_prompt(self, prompt: str) -> Tuple[bool, str]:
        """Process user prompt for PRP management"""
        # Debug: Check components
        prp_ids = self._extract_prp_references(prompt)
        intent = self._detect_status_change_intent(prompt)

        # Check if this prompt should be intercepted
        if not self._should_intercept_prompt(prompt):
            return False, f"Prompt not intercepted - PRPs found: {prp_ids}, Intent: {intent}"

        # Extract PRP IDs
        prp_ids = self._extract_prp_references(prompt)
        if not prp_ids:
            return False, "No PRP IDs found in prompt"

        # Detect intent
        intent = self._detect_status_change_intent(prompt)
        if not intent:
            return False, "No clear status change intent detected"

        # Process each PRP
        results = []
        blocked = False

        for prp_id in prp_ids:
            if intent == "start":
                valid, message = self._validate_prp_start_request(prp_id)
                if valid:
                    # Transition PRP to in_progress
                    success, transition_message = self.prp_manager.transition_prp(prp_id, PRPStatus.IN_PROGRESS)
                    if success:
                        results.append(f"✅ {prp_id}: {transition_message}")
                    else:
                        results.append(f"❌ {prp_id}: {transition_message}")
                        blocked = True
                else:
                    results.append(f"❌ {prp_id}: {message}")
                    blocked = True

            elif intent == "complete":
                valid, message = self._validate_prp_complete_request(prp_id)
                if valid:
                    results.append(f"⚠️ {prp_id}: Ready for completion validation. Run BPCI and commit to complete.")
                else:
                    results.append(f"❌ {prp_id}: {message}")
                    blocked = True

            elif intent == "validate":
                # Provide status information
                results.append(self._generate_status_response([prp_id]))

        # Generate response
        response = "\\n".join(results)

        if blocked:
            response += "\\n\\n**Action Required**: Fix the issues above before proceeding."

        return True, response


def main():
    """Main entry point for user prompt hook"""
    if len(sys.argv) < 2:
        print("Usage: python user_prompt_hook.py <prompt>")
        return

    prompt = " ".join(sys.argv[1:])

    try:
        hook = PRPUserPromptHook()
        intercepted, response = hook.process_prompt(prompt)

        if intercepted:
            print("🔒 PRP Management Hook Activated")
            print(response)
        else:
            print("✅ Prompt processed - no PRP management actions needed")

    except Exception as e:
        print(f"❌ PRP User Prompt Hook ERROR: {e}")


if __name__ == "__main__":
    main()
