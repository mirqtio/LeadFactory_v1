#!/usr/bin/env python3
"""
Integration Agent Protocol Implementation
Follows CLAUDE.md lines 65-72 specification
"""

import os
import subprocess
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redis_cli import SyncRedisHelper


class IntegrationAgent:
    """Redis-coordinated Integration Agent for multi-agent workflow"""

    def __init__(self):
        self.redis = SyncRedisHelper()
        self.current_prp = None

    def monitor_queue(self):
        """Monitor Redis integration queue for new PRPs"""
        queue_length = self.redis.llen("integration:queue")
        if queue_length > 0:
            print(f"🔄 Integration queue has {queue_length} PRPs waiting")
            return True
        return False

    def acquire_merge_lock(self, prp_id: str) -> bool:
        """Acquire merge lock for serialized operations"""
        lock_acquired = self.redis.set("merge:lock", prp_id, nx=True, ex=3600)  # 1 hour timeout
        if lock_acquired:
            self.redis.set("merge:lock:timestamp", datetime.now().isoformat())
            print(f"🔒 Acquired merge lock for {prp_id}")
            return True
        current_lock = self.redis.get("merge:lock")
        print(f"⚠️ Merge lock held by {current_lock}")
        return False

    def process_integration_queue(self):
        """Process next PRP from integration queue"""
        prp_id = self.redis.rpop("integration:queue")
        if not prp_id:
            return None

        print(f"📋 Processing {prp_id} from integration queue")

        # Acquire merge lock
        if not self.acquire_merge_lock(prp_id):
            # Re-queue if can't acquire lock
            self.redis.lpush("integration:queue", prp_id)
            return None

        self.current_prp = prp_id
        return prp_id

    def merge_feature_branch(self, prp_id: str) -> bool:
        """Merge feature branch using fast-forward/rebase"""
        try:
            # Determine feature branch name
            feature_branch = f"feature/{prp_id.lower()}-{prp_id.split('-')[1]}"

            print(f"🌿 Merging {feature_branch} to main")

            # Fetch latest changes
            subprocess.run(["git", "fetch", "origin"], check=True)

            # Switch to main and update
            subprocess.run(["git", "checkout", "main"], check=True)
            subprocess.run(["git", "pull", "origin", "main"], check=True)

            # Attempt fast-forward merge
            result = subprocess.run(["git", "merge", "--ff-only", feature_branch], capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ Fast-forward merge successful for {prp_id}")
                return True
            print("⚠️ Fast-forward failed, attempting rebase merge")
            # Try rebase merge
            subprocess.run(["git", "checkout", feature_branch], check=True)
            subprocess.run(["git", "rebase", "main"], check=True)
            subprocess.run(["git", "checkout", "main"], check=True)
            subprocess.run(["git", "merge", "--ff-only", feature_branch], check=True)
            print(f"✅ Rebase merge successful for {prp_id}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Merge failed for {prp_id}: {e}")
            return False

    def run_smoke_ci(self) -> bool:
        """Run fast smoke test suite (≤5 min) - NOT full BPCI"""
        try:
            print("🚀 Running smoke CI suite (≤5 min target)")

            # Run quick validation only
            result = subprocess.run(["make", "quick-check"], capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                print("✅ Smoke CI passed")
                return True
            print(f"❌ Smoke CI failed: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            print("⏰ Smoke CI timeout (>5 min)")
            return False
        except Exception as e:
            print(f"❌ Smoke CI error: {e}")
            return False

    def handle_failure_triage(self, prp_id: str, failure_type: str):
        """Triage failures: simple → fix, complex → ping PM"""
        if failure_type == "simple":
            print(f"🔧 Attempting to fix simple failure for {prp_id}")
            # Implement simple fixes (formatting, lint, etc.)
            return True
        print(f"📞 Complex failure - pinging PM for {prp_id}")
        # Notify PM via tmux messaging
        pm_session = self.get_pm_session(prp_id)
        if pm_session:
            subprocess.run(
                [
                    "/Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh",
                    f"{pm_session}:0",
                    f"Integration failure on {prp_id}. Your expertise needed for complex issue.",
                ]
            )
        return False

    def update_prp_state(self, prp_id: str, new_state: str):
        """Update PRP state in Redis and YAML"""
        self.redis.set(f"prp:{prp_id}:state", new_state)
        print(f"📊 Updated {prp_id} state: integration → {new_state}")

    def release_merge_lock(self):
        """Release merge lock and clean up"""
        self.redis.delete("merge:lock")
        self.redis.delete("merge:lock:timestamp")
        print("🔓 Released merge lock")

    def get_pm_session(self, prp_id: str) -> str:
        """Get PM session responsible for PRP"""
        # Check Redis for PRP assignment
        pm_assignment = self.redis.get(f"prp:{prp_id}:owner")
        return pm_assignment or "PM-1"  # Default fallback

    def integration_workflow(self):
        """Main integration workflow per CLAUDE.md specification"""
        print("🔄 Starting Integration Agent workflow monitoring...")

        while True:
            try:
                # 1. Monitor Redis integration queue
                if not self.monitor_queue():
                    time.sleep(10)  # Wait 10 seconds before checking again
                    continue

                # 2. Process next PRP from queue
                prp_id = self.process_integration_queue()
                if not prp_id:
                    continue

                # 3. Merge feature branch using fast-forward/rebase
                merge_success = self.merge_feature_branch(prp_id)
                if not merge_success:
                    self.handle_failure_triage(prp_id, "complex")
                    self.release_merge_lock()
                    continue

                # 4. Run smoke CI (≤5 min)
                ci_success = self.run_smoke_ci()
                if not ci_success:
                    # Rollback merge on CI failure
                    subprocess.run(["git", "reset", "--hard", "HEAD~1"])
                    self.handle_failure_triage(prp_id, "simple")
                    self.release_merge_lock()
                    continue

                # 5. Push to origin/main
                subprocess.run(["git", "push", "origin", "main"], check=True)

                # 6. Update PRP state: integration → validate
                self.update_prp_state(prp_id, "validate")

                # 7. Release merge lock
                self.release_merge_lock()

                print(f"✅ Successfully integrated {prp_id}")

            except KeyboardInterrupt:
                print("\n🛑 Integration Agent stopped")
                if self.current_prp:
                    self.release_merge_lock()
                break
            except Exception as e:
                print(f"❌ Integration Agent error: {e}")
                if self.current_prp:
                    self.release_merge_lock()
                time.sleep(5)


if __name__ == "__main__":
    agent = IntegrationAgent()

    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        # Start continuous monitoring
        agent.integration_workflow()
    else:
        # Single queue check
        if agent.monitor_queue():
            print("Integration queue has items")
        else:
            print("Integration queue empty")
