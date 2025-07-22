#!/usr/bin/env python3
"""
Orchestrator Messaging Integration
Handles tmux-based messaging between orchestrator and agents
"""
import json
import subprocess
from typing import Optional


class OrchestratorMessaging:
    """Handle tmux messaging for orchestrator"""

    def __init__(self, session: str = "leadstack"):
        self.session = session
        self.send_script = "/Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh"

    def send_to_agent(self, window: str, pane: str, message: str) -> bool:
        """Send message to specific agent window/pane"""
        try:
            # Use the send-claude-message.sh script
            cmd = [self.send_script, f"{window}:{pane}", message]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"❌ Failed to send message to {window}:{pane}: {result.stderr}")
                return False

            # Send Enter key as separate command
            enter_cmd = ["tmux", "send-keys", "-t", f"{self.session}:{window}.{pane}", "Enter"]
            subprocess.run(enter_cmd)

            return True

        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return False

    def notify_pm_assignment(self, pm_window: str, prp_id: str) -> bool:
        """Notify PM about PRP assignment"""
        message = f"📋 ASSIGNMENT: You have been assigned PRP {prp_id}. Check Redis for details and begin development."
        return self.send_to_agent(pm_window, "0", message)

    def notify_validator_handoff(self, prp_id: str, pm_agent: str) -> bool:
        """Notify validator about PRP ready for validation"""
        message = f"✅ HANDOFF: PRP {prp_id} from {pm_agent} is ready for validation. Please review."
        return self.send_to_agent("validator", "0", message)

    def notify_integrator_handoff(self, prp_id: str) -> bool:
        """Notify integrator about PRP ready for integration"""
        message = f"🔄 INTEGRATION: PRP {prp_id} passed validation and is ready for integration to main."
        return self.send_to_agent("integrator", "0", message)

    def request_agent_status(self, window: str) -> bool:
        """Request status update from agent"""
        message = "📊 STATUS REQUEST: Please provide your current status and PRP progress."
        return self.send_to_agent(window, "0", message)

    def notify_timeout_warning(self, window: str, prp_id: str, minutes_remaining: int) -> bool:
        """Warn agent about approaching timeout"""
        message = (
            f"⏰ TIMEOUT WARNING: PRP {prp_id} has {minutes_remaining} minutes before timeout. Please update status."
        )
        return self.send_to_agent(window, "0", message)

    def escalate_to_orchestrator(self, issue: str, context: dict) -> bool:
        """Escalate issue to orchestrator"""
        message = f"🚨 ESCALATION: {issue}\nContext: {json.dumps(context, indent=2)}"
        return self.send_to_agent("orchestrator", "0", message)

    def broadcast_system_status(self, status_report: str) -> bool:
        """Broadcast system status to all agents"""
        agents = [
            ("dev-1", "0"),
            ("dev-2", "0"),
            ("dev-3", "0"),
            ("validator", "0"),
            ("integrator", "0"),
        ]

        success = True
        for window, pane in agents:
            if not self.send_to_agent(window, pane, f"📊 SYSTEM STATUS:\n{status_report}"):
                success = False

        return success

    def coordinate_handoff(self, from_agent: str, to_agent: str, prp_id: str, evidence: dict) -> bool:
        """Coordinate handoff between agents"""
        # Notify receiving agent
        handoff_msg = f"📦 HANDOFF: Receiving PRP {prp_id} from {from_agent}\nEvidence: {json.dumps(evidence, indent=2)}"

        to_window = self._agent_to_window(to_agent)
        if not to_window:
            return False

        return self.send_to_agent(to_window, "0", handoff_msg)

    def _agent_to_window(self, agent: str) -> Optional[str]:
        """Map agent name to tmux window"""
        mapping = {
            "pm-1": "dev-1",
            "pm-2": "dev-2",
            "pm-3": "dev-3",
            "validator": "validator",
            "integrator": "integrator",
            "orchestrator": "orchestrator",
        }
        return mapping.get(agent)


# Example usage in orchestrator
if __name__ == "__main__":
    messaging = OrchestratorMessaging()

    # Test PM assignment
    messaging.notify_pm_assignment("dev-1", "P0-001")

    # Test status request
    messaging.request_agent_status("dev-2")

    # Test escalation
    messaging.escalate_to_orchestrator(
        "PM-1 not responding", {"agent": "pm-1", "last_update": "10 minutes ago", "prp": "P0-001"}
    )
