#!/usr/bin/env python3
"""
Tmux Background Monitor for Orchestrator
Belt and suspenders approach - monitors all agent windows every minute
Responds to agent needs while Redis coordination settles in
"""

import re
import subprocess
import time
from datetime import datetime


class TmuxMonitor:
    def __init__(self, session_name: str = "orchestrator"):
        """Initialize tmux monitor for orchestrator session."""
        self.session_name = session_name
        self.agent_windows = {1: "PM-1", 2: "PM-2", 3: "PM-3", 4: "Validator", 5: "Integration"}
        self.last_responses = {}
        self.response_triggers = {
            # Questions that need responses
            "question_patterns": [
                r"\?.*$",  # Lines ending with ?
                r"what.*should.*i",  # "what should I do"
                r"how.*do.*i",  # "how do I"
                r"need.*guidance",
                r"waiting.*for",
                r"blocked.*on",
                r"approval.*needed",
                r"ready.*for.*handoff",
                r"completed.*ready",
                r"should.*i.*proceed",
            ],
            # Status indicators that need acknowledgment
            "status_patterns": [
                r"✅.*complete",
                r"🚨.*critical",
                r"⚠️.*warning",
                r"🔄.*progress",
                r"ready.*for.*validation",
                r"handoff.*ready",
                r"mission.*accomplished",
            ],
            # Error indicators that need immediate response
            "error_patterns": [
                r"error:",
                r"failed:",
                r"exception:",
                r"traceback",
                r"❌",
                r"cannot.*proceed",
                r"stuck.*on",
            ],
        }

    def capture_window(self, window_num: int) -> str | None:
        """Capture content of specified tmux window."""
        try:
            cmd = f"tmux capture-pane -t {self.session_name}:{window_num} -p"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                return result.stdout.strip()
            print(f"❌ Failed to capture window {window_num}: {result.stderr}")
            return None

        except Exception as e:
            print(f"❌ Exception capturing window {window_num}: {e}")
            return None

    def send_message(self, window_num: int, message: str) -> bool:
        """Send message to specified tmux window."""
        try:
            # Send the message
            cmd1 = f'tmux send-keys -t {self.session_name}:{window_num} "{message}"'
            result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)

            # Send Enter
            cmd2 = f"tmux send-keys -t {self.session_name}:{window_num} Enter"
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)

            if result1.returncode == 0 and result2.returncode == 0:
                print(f"📤 Sent to {self.agent_windows.get(window_num)}: {message[:50]}...")
                return True
            print(f"❌ Failed to send to window {window_num}")
            return False

        except Exception as e:
            print(f"❌ Exception sending to window {window_num}: {e}")
            return False

    def analyze_content(self, content: str, agent_name: str) -> dict[str, any]:
        """Analyze window content for triggers requiring response."""
        analysis = {
            "needs_response": False,
            "urgency": "normal",
            "triggers": [],
            "suggested_response": None,
            "last_lines": [],
        }

        if not content:
            return analysis

        lines = content.split("\n")
        # Focus on last 10 lines for recent activity
        recent_lines = [line.strip() for line in lines[-10:] if line.strip()]
        analysis["last_lines"] = recent_lines

        # Check for response triggers
        for line in recent_lines:
            line_lower = line.lower()

            # Check error patterns (highest priority)
            for pattern in self.response_triggers["error_patterns"]:
                if re.search(pattern, line_lower):
                    analysis["needs_response"] = True
                    analysis["urgency"] = "critical"
                    analysis["triggers"].append(f"ERROR: {line}")
                    analysis[
                        "suggested_response"
                    ] = f"I see an error in {agent_name}. What specific help do you need to resolve: {line[:100]}?"

            # Check question patterns
            for pattern in self.response_triggers["question_patterns"]:
                if re.search(pattern, line_lower):
                    analysis["needs_response"] = True
                    analysis["urgency"] = "high" if analysis["urgency"] == "normal" else analysis["urgency"]
                    analysis["triggers"].append(f"QUESTION: {line}")
                    analysis[
                        "suggested_response"
                    ] = f"I see you have a question, {agent_name}. Let me help: {line[:100]}"

            # Check status patterns
            for pattern in self.response_triggers["status_patterns"]:
                if re.search(pattern, line_lower):
                    analysis["needs_response"] = True
                    analysis["triggers"].append(f"STATUS: {line}")
                    if "complete" in line_lower or "ready" in line_lower:
                        analysis[
                            "suggested_response"
                        ] = f"Acknowledged, {agent_name}. I see: {line[:100]}. Proceeding with next steps."

        return analysis

    def generate_contextual_response(self, agent_name: str, analysis: dict[str, any], window_num: int) -> str | None:
        """Generate contextual response based on agent and analysis."""
        if not analysis["needs_response"]:
            return None

        # Use suggested response if available
        if analysis["suggested_response"]:
            return analysis["suggested_response"]

        # Generate contextual responses based on agent role
        if agent_name == "PM-1":
            return "PM-1: I'm monitoring your P0-022 progress. What's your current status and any blockers?"
        if agent_name == "PM-2":
            return "PM-2: Checking in on your work. What's your current task status?"
        if agent_name == "PM-3":
            return "PM-3: I see activity. What's your P2-040 progress and next steps?"
        if agent_name == "Validator":
            return "Validator: I'm tracking validation work. What items need validation approval?"
        if agent_name == "Integration":
            return "Integration: Checking CI and integration status. Any issues or completions to report?"
        return f"{agent_name}: I see activity in your window. Please provide status update."

    def should_respond(self, agent_name: str, analysis: dict[str, any]) -> bool:
        """Determine if orchestrator should respond to this agent."""
        # Don't respond if no triggers
        if not analysis["needs_response"]:
            return False

        # Always respond to critical/high urgency
        if analysis["urgency"] in ["critical", "high"]:
            return True

        # Check if we responded recently to avoid spam
        last_response_time = self.last_responses.get(agent_name, 0)
        current_time = time.time()

        # Don't respond more than once every 5 minutes to same agent
        if current_time - last_response_time < 300:  # 5 minutes
            return False

        return True

    def monitor_single_cycle(self) -> dict[str, any]:
        """Perform single monitoring cycle of all windows."""
        cycle_report = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "agents_checked": 0,
            "responses_sent": 0,
            "alerts": [],
        }

        print(f"\n🔍 Tmux Monitor Cycle - {cycle_report['timestamp']}")

        for window_num, agent_name in self.agent_windows.items():
            cycle_report["agents_checked"] += 1

            # Capture window content
            content = self.capture_window(window_num)
            if content is None:
                cycle_report["alerts"].append(f"❌ Failed to capture {agent_name} window")
                continue

            # Analyze content
            analysis = self.analyze_content(content, agent_name)

            # Log activity
            if analysis["triggers"]:
                print(f"  📊 {agent_name}: {len(analysis['triggers'])} triggers ({analysis['urgency']})")
                for trigger in analysis["triggers"][:2]:  # Show first 2 triggers
                    print(f"    • {trigger[:80]}...")

            # Decide if response needed
            if self.should_respond(agent_name, analysis):
                response = self.generate_contextual_response(agent_name, analysis, window_num)
                if response and self.send_message(window_num, response):
                    cycle_report["responses_sent"] += 1
                    self.last_responses[agent_name] = time.time()
                    cycle_report["alerts"].append(f"📤 Responded to {agent_name}")

        return cycle_report

    def run_background_monitoring(self, duration_minutes: int = 60):
        """Run background monitoring for specified duration."""
        print(f"🚀 Starting tmux background monitoring for {duration_minutes} minutes")
        print(f"   Monitoring session: {self.session_name}")
        print(f"   Agent windows: {self.agent_windows}")
        print("   Check interval: 60 seconds")

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        cycle_count = 0
        total_responses = 0

        try:
            while time.time() < end_time:
                cycle_count += 1
                cycle_report = self.monitor_single_cycle()
                total_responses += cycle_report["responses_sent"]

                # Summary
                print(
                    f"  ✅ Cycle {cycle_count}: {cycle_report['agents_checked']} agents checked, {cycle_report['responses_sent']} responses sent"
                )

                # Show alerts
                for alert in cycle_report["alerts"]:
                    print(f"    {alert}")

                # Wait 60 seconds before next cycle
                print("  ⏳ Next check in 60 seconds...")
                time.sleep(60)

        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")

        # Final summary
        elapsed_minutes = (time.time() - start_time) / 60
        print("\n📊 Monitoring Summary:")
        print(f"   Duration: {elapsed_minutes:.1f} minutes")
        print(f"   Cycles completed: {cycle_count}")
        print(f"   Total responses sent: {total_responses}")
        print(f"   Average responses per cycle: {total_responses / cycle_count if cycle_count > 0 else 0:.1f}")


def main():
    """Main function for testing tmux monitor."""
    print("🧪 Testing Tmux Monitor")

    monitor = TmuxMonitor()

    # Test single cycle
    print("\n1. Testing single monitoring cycle:")
    report = monitor.monitor_single_cycle()
    print(f"   Result: {report}")

    # Ask user if they want to run background monitoring
    print("\n2. Background monitoring test:")
    print("   This will monitor all agent windows every minute.")
    print("   Press Ctrl+C to stop at any time.")

    try:
        # Run for 5 minutes as test
        monitor.run_background_monitoring(duration_minutes=5)
    except KeyboardInterrupt:
        print("\n✅ Test completed")


if __name__ == "__main__":
    main()
