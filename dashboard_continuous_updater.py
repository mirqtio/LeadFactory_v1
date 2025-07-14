#!/usr/bin/env python3
"""
Continuous dashboard updater that runs in the background and updates the AI CTO dashboard
with real CI status every 30 seconds.
"""

import os
import signal
import subprocess
import sys
import time


def signal_handler(sig, frame):
    """Handle graceful shutdown."""
    print("\n👋 Dashboard updater stopped.")
    sys.exit(0)


def run_update():
    """Run the dashboard update script."""
    try:
        subprocess.run([sys.executable, "update_dashboard_ci_status.py"], capture_output=True, text=True)
        return True
    except Exception as e:
        print(f"❌ Error updating dashboard: {e}")
        return False


def main():
    """Main loop for continuous updates."""
    signal.signal(signal.SIGINT, signal_handler)

    print("🚀 Starting continuous dashboard updater...")
    print("   Updates every 30 seconds. Press Ctrl+C to stop.")

    update_count = 0

    while True:
        update_count += 1
        print(f"\n🔄 Update #{update_count} at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        if run_update():
            print("✅ Dashboard updated successfully")
        else:
            print("❌ Dashboard update failed")

        # Wait 30 seconds before next update
        time.sleep(30)


if __name__ == "__main__":
    main()
