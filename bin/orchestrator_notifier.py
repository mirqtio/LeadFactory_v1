#!/usr/bin/env python3
"""
Orchestrator Notifier - Delivers processed orchestrator messages to tmux without queue competition
This is NOT a shim - it doesn't consume from queues, it only delivers notifications.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List

import redis


class OrchestratorNotifier:
    def __init__(self, session: str, redis_url: str):
        self.session = session
        self.window = "orchestrator"
        self.redis_client = redis.from_url(redis_url)
        self.running = True
        self.last_notification_time = datetime.utcnow()

        # Track delivered notifications to avoid duplicates
        self.delivered_notifications = set()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down orchestrator notifier...")
        self.running = False

    def send_to_tmux(self, message: str):
        """Send message to the orchestrator tmux pane"""
        try:
            # Send the message
            escaped_message = message.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
            cmd = ["tmux", "send-keys", "-t", f"{self.session}:{self.window}", escaped_message]
            subprocess.run(cmd, check=False, capture_output=True)

            # Send Enter as a separate command
            enter_cmd = ["tmux", "send-keys", "-t", f"{self.session}:{self.window}", "Enter"]
            subprocess.run(enter_cmd, check=False, capture_output=True)

            print(f"Notification sent to orchestrator: {message[:100]}...")
        except Exception as e:
            print(f"Error sending to tmux: {e}")

    def check_for_notifications(self):
        """Check Redis for orchestrator notifications to deliver"""
        # Check if orchestrator_loop has marked any notifications for delivery
        notifications_key = "orchestrator:pending_notifications"

        # Get all pending notifications
        notifications = self.redis_client.lrange(notifications_key, 0, -1)

        if notifications:
            # Process each notification
            for notification_data in notifications:
                try:
                    notification = json.loads(notification_data)
                    notification_id = notification.get("id", "")

                    # Skip if already delivered
                    if notification_id in self.delivered_notifications:
                        continue

                    # Format and send the notification
                    message = self.format_notification(notification)
                    if message:
                        self.send_to_tmux(message)
                        self.delivered_notifications.add(notification_id)

                        # Keep set size reasonable
                        if len(self.delivered_notifications) > 1000:
                            self.delivered_notifications = set(list(self.delivered_notifications)[-500:])

                except Exception as e:
                    print(f"Error processing notification: {e}")

            # Clear processed notifications
            self.redis_client.delete(notifications_key)

    def format_notification(self, notification: Dict) -> str:
        """Format notification for display in tmux"""
        msg_type = notification.get("type", "unknown")
        timestamp = notification.get("timestamp", datetime.utcnow().isoformat())

        # Format based on notification type
        if msg_type == "system_notification":
            return f"\n📢 SYSTEM: {notification.get('message', 'No message')}\n"

        elif msg_type == "new_prp":
            prp_id = notification.get("prp_id", "Unknown")
            return f"\n📥 NEW PRP: {prp_id} has been queued for assignment\n"

        elif msg_type == "agent_down":
            agent = notification.get("agent", "Unknown")
            last_activity = notification.get("last_activity", "Unknown")
            return f"\n🚨 AGENT DOWN: {agent} - Last activity: {last_activity}\n"

        elif msg_type == "bulk_prps_queued":
            prp_count = len(notification.get("prp_ids", []))
            queue = notification.get("queue", "Unknown")
            return f"\n📦 BULK PRPS: {prp_count} PRPs added to {queue}\n"

        elif msg_type == "deployment_failed":
            prp_id = notification.get("prp_id", "Unknown")
            error = notification.get("error", "Unknown error")
            return f"\n🚨 DEPLOYMENT FAILED: {prp_id}\nError: {error}\n"

        elif msg_type == "queue_scaling_needed":
            queue = notification.get("queue", "Unknown")
            depth = notification.get("depth", 0)
            return f"\n📊 SCALING NEEDED: {queue} has {depth} items\n"

        elif msg_type == "progress_report":
            report = notification.get("report", {})
            return self.format_progress_report(report)

        elif msg_type == "qa_handled":
            agent = notification.get("agent", "Unknown")
            question = notification.get("question", "Unknown")
            return f"\n❓ Q&A: {agent} asked: {question[:100]}...\n"

        else:
            # Generic notification
            return f"\n📌 {msg_type.upper()}: {json.dumps(notification, indent=2)}\n"

    def format_progress_report(self, report: Dict) -> str:
        """Format progress report for display"""
        queues = report.get("queues", {})
        active_prps = report.get("active_prps", [])

        message = "\n📊 PROGRESS REPORT\n"
        message += "=" * 50 + "\n"

        # Queue status
        message += "Queue Status:\n"
        for queue, metrics in queues.items():
            if queue.endswith(":inflight"):
                continue
            depth = metrics.get("depth", 0)
            inflight = metrics.get("inflight", 0)
            message += f"  {queue}: {depth} queued, {inflight} in progress\n"

        # Active PRPs
        message += f"\nActive PRPs: {len(active_prps)}\n"
        for prp in active_prps[:5]:  # Show first 5
            message += f"  - {prp['id']}: {prp['status']} - {prp.get('title', 'No title')[:40]}...\n"

        if len(active_prps) > 5:
            message += f"  ... and {len(active_prps) - 5} more\n"

        message += "=" * 50 + "\n"
        return message

    def periodic_status(self):
        """Send periodic status to orchestrator"""
        current_time = datetime.utcnow()

        # Every 10 minutes, send a status update
        if (current_time - self.last_notification_time).total_seconds() > 600:
            status_msg = f"\n💓 Orchestrator Notifier Active - {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            self.send_to_tmux(status_msg)
            self.last_notification_time = current_time

    def run(self):
        """Main run loop"""
        print(f"Starting Orchestrator Notifier...")
        print(f"Session: {self.session}, Window: {self.window}")

        # Send startup notification
        self.send_to_tmux("\n🚀 Orchestrator Notifier Connected - Ready to deliver notifications\n")

        while self.running:
            try:
                # Check for notifications
                self.check_for_notifications()

                # Send periodic status
                self.periodic_status()

                # Sleep briefly
                time.sleep(1)

            except Exception as e:
                print(f"Error in notifier loop: {e}")
                time.sleep(5)

        print("Orchestrator Notifier shutting down.")


def main():
    parser = argparse.ArgumentParser(description="Orchestrator Notifier - Delivers notifications to orchestrator tmux")
    parser.add_argument("--session", required=True, help="Tmux session name")
    parser.add_argument("--redis-url", required=True, help="Redis connection URL")

    args = parser.parse_args()

    # Set Redis URL in environment
    os.environ["REDIS_URL"] = args.redis_url

    notifier = OrchestratorNotifier(session=args.session, redis_url=args.redis_url)

    try:
        notifier.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
