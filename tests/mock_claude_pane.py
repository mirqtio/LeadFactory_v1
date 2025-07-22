#!/usr/bin/env python3
"""
Mock Claude pane for deterministic testing of shim interactions
"""
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class MockClaudePane:
    """
    Mock Claude pane that simulates various agent behaviors deterministically
    """

    def __init__(self, pane_name: str, agent_type: str):
        self.pane_name = pane_name
        self.agent_type = agent_type
        self.output_buffer: List[str] = []
        self.input_history: List[str] = []
        self.behavior_mode = "normal"
        self.current_prp: Optional[str] = None
        self.response_delay = 0.1  # Simulate typing delay

        # Predefined behaviors for different scenarios
        self.behaviors = {
            "normal": self._normal_behavior,
            "slow": self._slow_behavior,
            "malformed_evidence": self._malformed_evidence_behavior,
            "incomplete_evidence": self._incomplete_evidence_behavior,
            "crash": self._crash_behavior,
            "question_asking": self._question_asking_behavior,
            "timeout": self._timeout_behavior,
            "rapid_output": self._rapid_output_behavior,
        }

    def set_behavior(self, mode: str):
        """Set the behavior mode for this mock pane"""
        if mode not in self.behaviors:
            raise ValueError(f"Unknown behavior mode: {mode}")
        self.behavior_mode = mode

    def send_input(self, text: str) -> None:
        """Simulate sending input to the pane"""
        self.input_history.append(text)

        # Parse for PRP assignment
        prp_match = re.search(r"(P\d+-\d+)", text)
        if prp_match:
            self.current_prp = prp_match.group(1)

        # Generate response based on behavior mode
        response = self.behaviors[self.behavior_mode](text)
        if response:
            self._add_output(response)

    def capture_output(self, num_lines: int = 50) -> str:
        """Capture the last N lines of output"""
        return "\n".join(self.output_buffer[-num_lines:])

    def clear_output(self):
        """Clear the output buffer"""
        self.output_buffer = []

    def _add_output(self, text: str):
        """Add text to output buffer with optional delay"""
        if self.response_delay > 0:
            time.sleep(self.response_delay)

        # Split into lines and add to buffer
        lines = text.split("\n")
        self.output_buffer.extend(lines)

        # Keep buffer size reasonable
        if len(self.output_buffer) > 1000:
            self.output_buffer = self.output_buffer[-500:]

    def _normal_behavior(self, input_text: str) -> str:
        """Normal successful agent behavior"""
        if not self.current_prp:
            return "No PRP assigned yet."

        responses = []
        responses.append(f"Working on {self.current_prp}...")
        responses.append("Running tests...")
        responses.append("Tests passed ✓")
        responses.append("Coverage: 85%")
        responses.append("")

        # Add proper evidence footer
        evidence = {
            "tests_passed": "true",
            "coverage_pct": "85",
            "lint_passed": "true",
            "timestamp": datetime.utcnow().isoformat(),
        }
        responses.append("=== EVIDENCE_COMPLETE ===")
        responses.append(json.dumps(evidence, indent=2))

        return "\n".join(responses)

    def _slow_behavior(self, input_text: str) -> str:
        """Slow response behavior"""
        self.response_delay = 2.0  # Much slower
        return self._normal_behavior(input_text)

    def _malformed_evidence_behavior(self, input_text: str) -> str:
        """Generate malformed evidence JSON"""
        if not self.current_prp:
            return "No PRP assigned yet."

        responses = []
        responses.append(f"Working on {self.current_prp}...")
        responses.append("Running tests...")
        responses.append("Tests passed ✓")
        responses.append("")

        # Malformed JSON
        responses.append("=== EVIDENCE_COMPLETE ===")
        responses.append("{")
        responses.append('  "tests_passed": true,  // Note: using boolean instead of string')
        responses.append('  "coverage_pct": 85,    // Note: using number instead of string')
        responses.append('  "lint_passed": "true"')
        responses.append("  // Missing closing brace")

        return "\n".join(responses)

    def _incomplete_evidence_behavior(self, input_text: str) -> str:
        """Generate incomplete evidence (missing required fields)"""
        if not self.current_prp:
            return "No PRP assigned yet."

        responses = []
        responses.append(f"Working on {self.current_prp}...")
        responses.append("Running tests...")
        responses.append("Some tests failed")
        responses.append("")

        # Missing required fields
        evidence = {
            "tests_passed": "false",  # Failed
            # Missing coverage_pct
            "timestamp": datetime.utcnow().isoformat(),
        }
        responses.append("=== EVIDENCE_COMPLETE ===")
        responses.append(json.dumps(evidence, indent=2))

        return "\n".join(responses)

    def _crash_behavior(self, input_text: str) -> str:
        """Simulate agent crash"""
        responses = []
        responses.append(f"Working on {self.current_prp}...")
        responses.append("Running tests...")
        responses.append("Segmentation fault (core dumped)")
        # No evidence footer
        return "\n".join(responses)

    def _question_asking_behavior(self, input_text: str) -> str:
        """Simulate agent asking questions"""
        if "ANSWER:" in input_text:
            # Agent received an answer
            responses = []
            responses.append("Thank you for the clarification.")
            responses.append("Continuing with implementation...")
            return "\n".join(responses) + "\n" + self._normal_behavior(input_text)

        # Ask a question
        responses = []
        responses.append(f"Working on {self.current_prp}...")
        responses.append("I need clarification:")
        responses.append("❓ QUESTION: Should I use PostgreSQL or SQLite for this feature?")
        responses.append("Waiting for response...")
        return "\n".join(responses)

    def _timeout_behavior(self, input_text: str) -> str:
        """Simulate timeout - no response"""
        # Don't respond at all
        return ""

    def _rapid_output_behavior(self, input_text: str) -> str:
        """Generate rapid output to test buffer handling"""
        responses = []
        responses.append(f"Starting work on {self.current_prp}")

        # Generate lots of output quickly
        for i in range(100):
            responses.append(f"Processing step {i}/100...")
            if i % 10 == 0:
                responses.append(f"Progress: {i}% complete")

        # Still add proper evidence at the end
        responses.extend(self._normal_behavior(input_text).split("\n")[-6:])
        return "\n".join(responses)


class MockTmuxServer:
    """
    Mock tmux server that manages multiple mock panes
    """

    def __init__(self):
        self.panes: Dict[str, MockClaudePane] = {}
        self.sessions: Dict[str, List[str]] = {}  # session -> list of windows

    def create_session(self, session_name: str):
        """Create a new tmux session"""
        if session_name not in self.sessions:
            self.sessions[session_name] = []

    def create_window(self, session_name: str, window_name: str, agent_type: str):
        """Create a new window with a mock Claude pane"""
        if session_name not in self.sessions:
            self.create_session(session_name)

        pane_id = f"{session_name}:{window_name}"
        self.panes[pane_id] = MockClaudePane(pane_id, agent_type)
        self.sessions[session_name].append(window_name)
        return self.panes[pane_id]

    def get_pane(self, session_name: str, window_name: str) -> Optional[MockClaudePane]:
        """Get a mock pane by session and window name"""
        pane_id = f"{session_name}:{window_name}"
        return self.panes.get(pane_id)

    def send_keys(self, session_name: str, window_name: str, text: str) -> bool:
        """Send keys to a specific pane"""
        pane = self.get_pane(session_name, window_name)
        if pane:
            pane.send_input(text)
            return True
        return False

    def capture_pane(self, session_name: str, window_name: str, num_lines: int = 50) -> str:
        """Capture output from a pane"""
        pane = self.get_pane(session_name, window_name)
        if pane:
            return pane.capture_output(num_lines)
        return ""

    def list_sessions(self) -> List[str]:
        """List all sessions"""
        return list(self.sessions.keys())

    def list_windows(self, session_name: str) -> List[str]:
        """List windows in a session"""
        return self.sessions.get(session_name, [])


def create_test_environment() -> MockTmuxServer:
    """Create a standard test environment with multiple agents"""
    server = MockTmuxServer()

    # Create main session
    server.create_session("main")

    # Create standard agent windows
    agents = [
        ("orchestrator", "orchestrator"),
        ("dev-1", "pm"),
        ("dev-2", "pm"),
        ("validator", "validator"),
        ("integrator", "integrator"),
    ]

    for window_name, agent_type in agents:
        server.create_window("main", window_name, agent_type)

    return server


if __name__ == "__main__":
    # Example usage
    server = create_test_environment()

    # Test normal behavior
    dev1 = server.get_pane("main", "dev-1")
    dev1.set_behavior("normal")
    server.send_keys("main", "dev-1", "Please work on P0-001")

    print("Normal behavior output:")
    print(server.capture_pane("main", "dev-1"))
    print("\n" + "=" * 50 + "\n")

    # Test malformed evidence
    dev2 = server.get_pane("main", "dev-2")
    dev2.set_behavior("malformed_evidence")
    server.send_keys("main", "dev-2", "Please work on P0-002")

    print("Malformed evidence output:")
    print(server.capture_pane("main", "dev-2"))
    print("\n" + "=" * 50 + "\n")

    # Test question asking
    validator = server.get_pane("main", "validator")
    validator.set_behavior("question_asking")
    server.send_keys("main", "validator", "Please validate P0-003")

    print("Question asking output:")
    print(server.capture_pane("main", "validator"))
