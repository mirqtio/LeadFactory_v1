#!/usr/bin/env python3
"""
Redis-Enhanced PRP State Manager
Extends the existing PRP state manager with Redis coordination while maintaining YAML as backup
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from prp_state_manager import PRPEntry, PRPStateManager, PRPStatus

# Add parent directory to path to import redis_cli
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)  # Go up one more level to project root
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from redis_cli import prp_redis, sync_redis
except ImportError:
    # Fallback: if redis_cli not available, disable Redis functionality
    prp_redis = None
    sync_redis = None


class RedisEnhancedStateManager(PRPStateManager):
    """
    Enhanced PRP state manager with Redis coordination
    Maintains existing YAML functionality while adding Redis for distributed coordination
    """

    def __init__(self, status_file: str = None, enable_redis: bool = True):
        super().__init__(status_file)
        self.enable_redis = enable_redis and (sync_redis is not None)
        self._redis_enabled = False

        if self.enable_redis:
            self._test_redis_connection()

    def _test_redis_connection(self) -> None:
        """Test if Redis is available"""
        if sync_redis is None:
            self._redis_enabled = False
            return

        try:
            # Set Redis URL if not already set
            if not os.getenv("REDIS_URL"):
                # Try common Redis URLs
                redis_urls = [
                    "redis://localhost:6379/0",  # Local Redis
                    "redis://redis:6379/0",  # Docker Compose Redis
                ]
                for url in redis_urls:
                    os.environ["REDIS_URL"] = url
                    try:
                        # Test the connection
                        test_result = sync_redis.set("test_connection", "test", ttl=10)
                        if test_result:
                            self._redis_enabled = True
                            sync_redis.delete("test_connection")  # Clean up test key
                            return
                    except Exception:
                        continue

                # If no URL worked, disable Redis
                self._redis_enabled = False
                return

            # Use sync helper for connection test
            result = sync_redis.set("test_connection", "test", ttl=10)
            if result:
                self._redis_enabled = True
                # Clean up test key (using del method which should exist)
                try:
                    sync_redis.delete("test_connection")
                except AttributeError:
                    # If delete method doesn't exist, just let the TTL expire
                    pass
            else:
                self._redis_enabled = False
        except Exception:
            self._redis_enabled = False

    def get_redis_status(self) -> dict:
        """Get current Redis connection status"""
        return {
            "enabled": self.enable_redis,
            "connected": self._redis_enabled,
            "url": os.getenv("REDIS_URL", "Not set"),
            "helper_available": sync_redis is not None,
        }

    async def _sync_to_redis(self, prp_id: str) -> None:
        """Sync PRP state to Redis"""
        if not self._redis_enabled:
            return

        try:
            prp = self.get_prp(prp_id)
            if prp:
                # Store PRP state in Redis
                await prp_redis.set_prp_state(
                    prp_id=prp_id, state=prp.status.value, owner=None  # Could be enhanced to track current PM
                )

                # Store additional metadata
                prp_metadata = {
                    "title": prp.title,
                    "validated_at": prp.validated_at,
                    "started_at": prp.started_at,
                    "completed_at": prp.completed_at,
                    "github_commit": prp.github_commit,
                    "ci_run_url": prp.ci_run_url,
                    "notes": prp.notes,
                    "last_synced": datetime.now(timezone.utc).isoformat(),
                }
                await prp_redis.set(f"{prp_id}:metadata", prp_metadata)

        except Exception as e:
            # Log error but don't fail the operation
            print(f"Warning: Failed to sync PRP {prp_id} to Redis: {e}")

    def _sync_to_redis_sync(self, prp_id: str) -> None:
        """Synchronous version of Redis sync for non-async contexts"""
        if not self._redis_enabled:
            return

        try:
            prp = self.get_prp(prp_id)
            if prp:
                # Store PRP state using sync helper
                prp_state_data = {
                    "state": prp.status.value,
                    "owner": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                sync_redis.set(f"prp:{prp_id}:state", prp_state_data)

                # Store metadata
                prp_metadata = {
                    "title": prp.title,
                    "validated_at": prp.validated_at,
                    "started_at": prp.started_at,
                    "completed_at": prp.completed_at,
                    "github_commit": prp.github_commit,
                    "ci_run_url": prp.ci_run_url,
                    "notes": prp.notes,
                    "last_synced": datetime.now(timezone.utc).isoformat(),
                }
                sync_redis.set(f"prp:{prp_id}:metadata", prp_metadata)

        except Exception as e:
            print(f"Warning: Failed to sync PRP {prp_id} to Redis: {e}")

    async def _publish_state_change(self, prp_id: str, old_status: str, new_status: str) -> None:
        """Publish state change event to Redis pub/sub"""
        if not self._redis_enabled:
            return

        try:
            event = {
                "prp_id": prp_id,
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "status_change",
            }

            # Add to events stream
            await prp_redis.lpush("events:status_changes", event)

        except Exception as e:
            print(f"Warning: Failed to publish state change for PRP {prp_id}: {e}")

    def transition_prp(
        self, prp_id: str, new_status: PRPStatus, commit_hash: str = None, notes: str = None
    ) -> Tuple[bool, str]:
        """Enhanced transition with Redis coordination"""

        # Get current status for event publishing
        current_prp = self.get_prp(prp_id)
        old_status = current_prp.status.value if current_prp else None

        # Check if another PRP is in progress (single PRP rule)
        if new_status == PRPStatus.IN_PROGRESS:
            in_progress_prps = self.get_in_progress_prps()
            if in_progress_prps and in_progress_prps[0].prp_id != prp_id:
                return False, f"Another PRP is already in progress: {in_progress_prps[0].prp_id}"

        # Perform the original transition
        success, message = super().transition_prp(prp_id, new_status, commit_hash, notes)

        if success:
            # Sync to Redis
            self._sync_to_redis_sync(prp_id)

            # Handle integration queue for completed PRPs
            if new_status == PRPStatus.COMPLETE and self._redis_enabled:
                try:
                    # Remove from integration queue if it was there
                    # (This would be more sophisticated in a real implementation)
                    pass
                except Exception as e:
                    print(f"Warning: Failed to update integration queue for PRP {prp_id}: {e}")

            # Publish state change event
            if old_status and self._redis_enabled:
                try:
                    # Use sync approach for events too
                    event = {
                        "prp_id": prp_id,
                        "old_status": old_status,
                        "new_status": new_status.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event_type": "status_change",
                    }
                    sync_redis.lpush("leadfactory:events:status_changes", event)
                except Exception as e:
                    print(f"Warning: Failed to publish state change event: {e}")

        return success, message

    async def async_transition_prp(
        self, prp_id: str, new_status: PRPStatus, commit_hash: str = None, notes: str = None
    ) -> Tuple[bool, str]:
        """Async version of transition with full Redis integration"""

        # Get current status for event publishing
        current_prp = self.get_prp(prp_id)
        old_status = current_prp.status.value if current_prp else None

        # Check for merge lock if transitioning to in_progress
        if new_status == PRPStatus.IN_PROGRESS and self._redis_enabled:
            lock_owner = await prp_redis.get_merge_lock_owner()
            if lock_owner and lock_owner != prp_id:
                return False, f"Merge lock held by another PRP: {lock_owner}"

        # Check single PRP rule
        if new_status == PRPStatus.IN_PROGRESS:
            in_progress_prps = self.get_in_progress_prps()
            if in_progress_prps and in_progress_prps[0].prp_id != prp_id:
                return False, f"Another PRP is already in progress: {in_progress_prps[0].prp_id}"

        # Perform the original transition
        success, message = super().transition_prp(prp_id, new_status, commit_hash, notes)

        if success:
            # Sync to Redis
            await self._sync_to_redis(prp_id)

            # Handle special transitions
            if new_status == PRPStatus.IN_PROGRESS and self._redis_enabled:
                # Add to integration queue for later processing
                await prp_redis.add_to_integration_queue(prp_id)

            elif new_status == PRPStatus.COMPLETE and self._redis_enabled:
                # Acquire merge lock for integration
                await prp_redis.acquire_merge_lock(prp_id, ttl=3600)  # 1 hour

            # Publish state change event
            if old_status:
                await self._publish_state_change(prp_id, old_status, new_status.value)

        return success, message

    async def get_redis_prp_state(self, prp_id: str) -> Optional[Dict]:
        """Get PRP state from Redis"""
        if not self._redis_enabled:
            return None

        return await prp_redis.get_prp_state(prp_id)

    async def get_integration_queue(self) -> List[str]:
        """Get current integration queue from Redis"""
        if not self._redis_enabled:
            return []

        try:
            # This would need to be implemented as a non-blocking queue check
            # For now, return empty list
            return []
        except Exception:
            return []

    async def get_merge_lock_status(self) -> Optional[str]:
        """Get current merge lock owner"""
        if not self._redis_enabled:
            return None

        return await prp_redis.get_merge_lock_owner()

    def get_redis_stats(self) -> Dict:
        """Get Redis connection and usage statistics"""
        stats = {
            "redis_enabled": self._redis_enabled,
            "redis_connection": "healthy" if self._redis_enabled else "unavailable",
        }

        if self._redis_enabled:
            try:
                # Get count of PRPs in Redis
                prp_keys = sync_redis.get("prp_keys_count") or 0
                stats["prps_in_redis"] = prp_keys
                stats["last_sync"] = sync_redis.get("last_full_sync") or "never"
            except Exception as e:
                stats["redis_error"] = str(e)

        return stats

    def sync_all_to_redis(self) -> Dict:
        """Sync all PRPs from YAML to Redis"""
        if not self._redis_enabled:
            return {"error": "Redis not available"}

        results = {"synced": 0, "errors": 0, "prps": []}

        try:
            all_prps = self.list_prps()
            for prp in all_prps:
                try:
                    self._sync_to_redis_sync(prp.prp_id)
                    results["synced"] += 1
                    results["prps"].append(prp.prp_id)
                except Exception as e:
                    results["errors"] += 1
                    print(f"Error syncing PRP {prp.prp_id}: {e}")

            # Update sync timestamp
            sync_redis.set("last_full_sync", datetime.now(timezone.utc).isoformat())
            sync_redis.set("prp_keys_count", results["synced"])

        except Exception as e:
            results["error"] = str(e)

        return results


# Create singleton instance
redis_state_manager = RedisEnhancedStateManager()


def get_redis_state_manager() -> RedisEnhancedStateManager:
    """Get the singleton Redis-enhanced state manager"""
    return redis_state_manager
