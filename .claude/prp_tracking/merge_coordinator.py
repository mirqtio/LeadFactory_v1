#!/usr/bin/env python3
"""
Merge Coordinator - Implements GPT o3's merge lock strategy
Provides serialized merge coordination with Redis locks
"""

import asyncio
import os
import subprocess
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from redis_cli import prp_redis, sync_redis
except ImportError:
    prp_redis = None
    sync_redis = None

from github_integration import GitHubIntegration


class MergeCoordinator:
    """
    Coordinates serialized merges with Redis locks
    Following GPT o3's recommendation for merge lock pattern
    """

    def __init__(self):
        self.github = GitHubIntegration()
        self.redis_available = prp_redis is not None

    async def request_merge(self, prp_id: str, branch_name: str = None) -> tuple[bool, str]:
        """
        Request permission to merge a PRP

        Args:
            prp_id: PRP identifier
            branch_name: Feature branch name (defaults to feat/{prp_id})

        Returns:
            (success, message)
        """
        if not self.redis_available:
            return True, "Redis not available - merge coordination disabled"

        if not branch_name:
            branch_name = f"feat/{prp_id.lower()}"

        try:
            # Check if merge lock is available
            current_owner = await prp_redis.get_merge_lock_owner()
            if current_owner and current_owner != prp_id:
                return False, f"Merge lock held by {current_owner}. Wait for completion."

            # Acquire merge lock
            lock_acquired = await prp_redis.acquire_merge_lock(prp_id, ttl=3600)  # 1 hour
            if not lock_acquired:
                current_owner = await prp_redis.get_merge_lock_owner()
                return False, f"Failed to acquire merge lock. Current owner: {current_owner}"

            return True, f"Merge lock acquired for {prp_id}. Proceed with merge."

        except Exception as e:
            return False, f"Error acquiring merge lock: {e}"

    async def perform_merge(self, prp_id: str, branch_name: str = None) -> tuple[bool, str]:
        """
        Perform the actual merge operation

        Args:
            prp_id: PRP identifier
            branch_name: Feature branch name

        Returns:
            (success, message)
        """
        if not branch_name:
            branch_name = f"feat/{prp_id.lower()}"

        try:
            # Verify we hold the lock
            if self.redis_available:
                lock_owner = await prp_redis.get_merge_lock_owner()
                if lock_owner != prp_id:
                    return False, f"Merge lock not held by {prp_id}. Current owner: {lock_owner}"

            # Switch to main branch
            result = subprocess.run(["git", "checkout", "main"], capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to checkout main: {result.stderr}"

            # Pull latest changes
            result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Failed to pull main: {result.stderr}"

            # Merge the feature branch
            result = subprocess.run(["git", "merge", "--no-ff", branch_name], capture_output=True, text=True)
            if result.returncode != 0:
                return False, f"Merge failed: {result.stderr}"

            # Push to origin
            result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
            if result.returncode != 0:
                # Rollback the merge
                subprocess.run(["git", "reset", "--hard", "HEAD~1"], capture_output=True)
                return False, f"Push failed: {result.stderr}"

            return True, f"Successfully merged {branch_name} to main"

        except Exception as e:
            return False, f"Merge error: {e}"

    async def validate_ci_and_release_lock(self, prp_id: str) -> tuple[bool, str]:
        """
        Validate CI status and release merge lock

        Args:
            prp_id: PRP identifier

        Returns:
            (success, message)
        """
        try:
            # Get current commit hash
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
            if result.returncode != 0:
                return False, "Failed to get current commit hash"

            commit_hash = result.stdout.strip()

            # Wait for CI to start (give it 30 seconds)
            await asyncio.sleep(30)

            # Validate CI status
            ci_valid, ci_message = self.github.validate_prp_completion(commit_hash)

            if self.redis_available:
                if ci_valid:
                    # CI passed - release lock
                    await prp_redis.release_merge_lock()
                    return True, f"CI validation passed. Merge lock released for {prp_id}."
                # CI failed - keep lock for debugging
                return False, f"CI validation failed: {ci_message}. Merge lock retained for debugging."
            return ci_valid, ci_message

        except Exception as e:
            return False, f"CI validation error: {e}"

    async def emergency_release_lock(self) -> tuple[bool, str]:
        """
        Emergency release of merge lock (admin function)

        Returns:
            (success, message)
        """
        if not self.redis_available:
            return True, "Redis not available - no lock to release"

        try:
            current_owner = await prp_redis.get_merge_lock_owner()
            if not current_owner:
                return True, "No merge lock currently held"

            released = await prp_redis.release_merge_lock()
            if released:
                return True, f"Emergency release: cleared lock held by {current_owner}"
            return False, "Failed to release merge lock"

        except Exception as e:
            return False, f"Emergency release error: {e}"

    async def get_merge_status(self) -> dict:
        """
        Get current merge coordination status

        Returns:
            Status dictionary
        """
        status = {"redis_available": self.redis_available, "lock_owner": None, "lock_ttl": None, "queue_length": 0}

        if self.redis_available:
            try:
                status["lock_owner"] = await prp_redis.get_merge_lock_owner()

                if status["lock_owner"]:
                    # Get TTL for the lock
                    ttl = await prp_redis.ttl("merge:lock")
                    status["lock_ttl"] = ttl if ttl > 0 else "no expiry"

                # Get integration queue length (if available)
                # This would need to be implemented in the queue system

            except Exception as e:
                status["error"] = str(e)

        return status


# CLI interface for merge coordination
async def main():
    """CLI interface for merge coordination"""
    if len(sys.argv) < 2:
        print("Usage: python merge_coordinator.py <command> [args]")
        print("Commands:")
        print("  request <prp_id> [branch]  - Request merge permission")
        print("  merge <prp_id> [branch]    - Perform merge operation")
        print("  validate <prp_id>          - Validate CI and release lock")
        print("  status                     - Show merge status")
        print("  emergency-release          - Emergency lock release")
        return

    coordinator = MergeCoordinator()
    command = sys.argv[1]

    try:
        if command == "request":
            if len(sys.argv) < 3:
                print("Usage: request <prp_id> [branch]")
                return

            prp_id = sys.argv[2]
            branch = sys.argv[3] if len(sys.argv) > 3 else None
            success, message = await coordinator.request_merge(prp_id, branch)
            print(f"{'✅' if success else '❌'} {message}")

        elif command == "merge":
            if len(sys.argv) < 3:
                print("Usage: merge <prp_id> [branch]")
                return

            prp_id = sys.argv[2]
            branch = sys.argv[3] if len(sys.argv) > 3 else None
            success, message = await coordinator.perform_merge(prp_id, branch)
            print(f"{'✅' if success else '❌'} {message}")

        elif command == "validate":
            if len(sys.argv) < 3:
                print("Usage: validate <prp_id>")
                return

            prp_id = sys.argv[2]
            success, message = await coordinator.validate_ci_and_release_lock(prp_id)
            print(f"{'✅' if success else '❌'} {message}")

        elif command == "status":
            status = await coordinator.get_merge_status()
            print("🔒 **Merge Coordination Status**")
            print(f"   Redis Available: {status['redis_available']}")
            print(f"   Lock Owner: {status['lock_owner'] or 'None'}")
            print(f"   Lock TTL: {status['lock_ttl'] or 'N/A'}")
            print(f"   Queue Length: {status['queue_length']}")

            if "error" in status:
                print(f"   ⚠️  Error: {status['error']}")

        elif command == "emergency-release":
            success, message = await coordinator.emergency_release_lock()
            print(f"{'✅' if success else '❌'} {message}")

        else:
            print(f"Unknown command: {command}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
