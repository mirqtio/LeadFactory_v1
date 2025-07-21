"""
Dead Letter Queue (DLQ) implementation with configurable retry logic.

Handles failed message processing with exponential backoff retry mechanisms,
message TTL and cleanup, DLQ monitoring, and manual message replay capabilities.
Integrates with Redis key-expiry notifications for automatic timeout handling.
"""

import time
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel, Field

from core.logging import get_logger
from infra.redis_queue import QueueMessage, RedisQueueBroker


class DLQEntry(BaseModel):
    """Dead Letter Queue entry with failure metadata"""

    id: str
    original_message: QueueMessage
    failure_reason: str
    failure_timestamp: datetime
    retry_count: int
    worker_id: str
    can_replay: bool = Field(default=True)
    dlq_ttl_hours: int = Field(default=168)  # 7 days default


class RetryPolicy(BaseModel):
    """Retry policy configuration"""

    max_retries: int = Field(default=3)
    initial_delay_seconds: int = Field(default=1)
    max_delay_seconds: int = Field(default=300)  # 5 minutes
    backoff_multiplier: float = Field(default=2.0)
    jitter_enabled: bool = Field(default=True)


class DeadLetterQueue:
    """
    Dead Letter Queue implementation with advanced retry and monitoring.

    Features:
    - Configurable retry policies with exponential backoff
    - Message TTL and automatic cleanup
    - Manual and automatic message replay
    - Integration with Redis key-expiry notifications
    - Comprehensive monitoring and alerting
    """

    def __init__(self, broker: RedisQueueBroker, retry_policy: RetryPolicy | None = None):
        """
        Initialize Dead Letter Queue.

        Args:
            broker: Redis queue broker instance
            retry_policy: Retry policy configuration
        """
        self.broker = broker
        self.retry_policy = retry_policy or RetryPolicy()
        self.logger = get_logger("dead_letter_queue", domain="infra")

        # Async Redis connection
        self.async_redis = redis.from_url(broker.redis_url, decode_responses=True)

        # DLQ key patterns
        self.dlq_prefix = f"{broker.queue_prefix}dlq:"
        self.retry_schedule_prefix = f"{broker.queue_prefix}retry_schedule:"
        self.dlq_metadata_prefix = f"{broker.queue_prefix}dlq_meta:"

    def _get_dlq_key(self, queue_name: str) -> str:
        """Get DLQ key for queue"""
        return f"{self.dlq_prefix}{queue_name}"

    def _get_retry_schedule_key(self, queue_name: str) -> str:
        """Get retry schedule key for queue"""
        return f"{self.retry_schedule_prefix}{queue_name}"

    def _get_dlq_metadata_key(self, message_id: str) -> str:
        """Get DLQ metadata key for message"""
        return f"{self.dlq_metadata_prefix}{message_id}"

    async def add_to_dlq(self, queue_name: str, message: QueueMessage, failure_reason: str, worker_id: str) -> bool:
        """
        Add message to Dead Letter Queue.

        Args:
            queue_name: Original queue name
            message: Failed message
            failure_reason: Reason for failure
            worker_id: Worker that processed the message

        Returns:
            True if added successfully
        """
        try:
            dlq_entry = DLQEntry(
                id=message.id,
                original_message=message,
                failure_reason=failure_reason,
                failure_timestamp=datetime.utcnow(),
                retry_count=message.retry_count,
                worker_id=worker_id,
            )

            dlq_key = self._get_dlq_key(queue_name)
            metadata_key = self._get_dlq_metadata_key(message.id)

            # Add to DLQ list and store metadata
            async with self.async_redis.pipeline(transaction=True) as pipe:
                pipe.lpush(dlq_key, dlq_entry.model_dump_json())
                pipe.setex(metadata_key, dlq_entry.dlq_ttl_hours * 3600, dlq_entry.model_dump_json())
                await pipe.execute()

            self.logger.warning(f"Added message {message.id} to DLQ for {queue_name}: {failure_reason}")

            # Update DLQ statistics
            await self._update_dlq_stats(queue_name, "added")

            return True

        except Exception as e:
            self.logger.error(f"Failed to add message {message.id} to DLQ: {e}")
            return False

    async def schedule_retry(self, queue_name: str, message: QueueMessage, delay_seconds: int | None = None) -> bool:
        """
        Schedule message for retry with exponential backoff.

        Args:
            queue_name: Target queue name
            message: Message to retry
            delay_seconds: Custom delay (overrides policy)

        Returns:
            True if scheduled successfully
        """
        try:
            if delay_seconds is None:
                delay_seconds = self._calculate_retry_delay(message.retry_count)

            retry_time = time.time() + delay_seconds
            retry_key = self._get_retry_schedule_key(queue_name)

            # Store in sorted set for time-based retrieval
            result = await self.async_redis.zadd(retry_key, {message.model_dump_json(): retry_time})

            if result:
                self.logger.info(f"Scheduled retry for message {message.id} in {delay_seconds}s")
                await self._update_dlq_stats(queue_name, "scheduled_retry")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to schedule retry for message {message.id}: {e}")
            return False

    def _calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate retry delay with exponential backoff and jitter"""
        import random

        # Exponential backoff
        delay = min(
            self.retry_policy.initial_delay_seconds * (self.retry_policy.backoff_multiplier**retry_count),
            self.retry_policy.max_delay_seconds,
        )

        # Add jitter to prevent thundering herd
        if self.retry_policy.jitter_enabled:
            jitter = random.uniform(0.5, 1.5)
            delay *= jitter

        return int(delay)

    async def process_scheduled_retries(self, queue_name: str) -> int:
        """
        Process scheduled retries for a queue.

        Args:
            queue_name: Queue to process retries for

        Returns:
            Number of messages moved back to main queue
        """
        retry_key = self._get_retry_schedule_key(queue_name)
        current_time = time.time()
        processed = 0

        try:
            # Get messages ready for retry
            ready_messages = await self.async_redis.zrangebyscore(retry_key, "-inf", current_time, withscores=True)

            if not ready_messages:
                return 0

            main_queue_key = self.broker._get_queue_key(queue_name)

            for message_data, _ in ready_messages:
                try:
                    message = QueueMessage.model_validate_json(message_data)

                    # Check if message should be retried
                    if message.retry_count < message.max_retries:
                        # Move back to main queue
                        await self.async_redis.lpush(main_queue_key, message_data)
                        await self.async_redis.zrem(retry_key, message_data)
                        processed += 1

                        self.logger.info(f"Retried message {message.id} (attempt {message.retry_count + 1})")
                        await self._update_dlq_stats(queue_name, "retried")
                    else:
                        # Max retries exceeded, move to DLQ
                        await self.add_to_dlq(queue_name, message, "max_retries_exceeded", self.broker.worker_id)
                        await self.async_redis.zrem(retry_key, message_data)

                except Exception as e:
                    self.logger.error(f"Error processing retry message: {e}")
                    await self.async_redis.zrem(retry_key, message_data)

            if processed > 0:
                self.logger.info(f"Processed {processed} scheduled retries for {queue_name}")

            return processed

        except Exception as e:
            self.logger.error(f"Error processing scheduled retries: {e}")
            return 0

    async def replay_dlq_message(self, queue_name: str, message_id: str) -> bool:
        """
        Manually replay a message from DLQ.

        Args:
            queue_name: Target queue name
            message_id: Message ID to replay

        Returns:
            True if replayed successfully
        """
        try:
            # Get message metadata
            metadata_key = self._get_dlq_metadata_key(message_id)
            metadata_json = await self.async_redis.get(metadata_key)

            if not metadata_json:
                self.logger.error(f"DLQ metadata not found for message {message_id}")
                return False

            dlq_entry = DLQEntry.model_validate_json(metadata_json)

            if not dlq_entry.can_replay:
                self.logger.error(f"Message {message_id} is marked as non-replayable")
                return False

            # Reset retry count for manual replay
            message = dlq_entry.original_message
            message.retry_count = 0

            # Move back to main queue
            main_queue_key = self.broker._get_queue_key(queue_name)
            await self.async_redis.lpush(main_queue_key, message.model_dump_json())

            # Remove from DLQ
            dlq_key = self._get_dlq_key(queue_name)
            await self.async_redis.lrem(dlq_key, 1, dlq_entry.model_dump_json())
            await self.async_redis.delete(metadata_key)

            self.logger.info(f"Manually replayed message {message_id} to {queue_name}")
            await self._update_dlq_stats(queue_name, "replayed")

            return True

        except Exception as e:
            self.logger.error(f"Failed to replay message {message_id}: {e}")
            return False

    async def get_dlq_messages(self, queue_name: str, limit: int = 100) -> list[DLQEntry]:
        """
        Get messages from DLQ for inspection.

        Args:
            queue_name: Queue name
            limit: Maximum number of messages to return

        Returns:
            List of DLQ entries
        """
        dlq_key = self._get_dlq_key(queue_name)
        entries = []

        try:
            # Get recent DLQ entries
            dlq_data_list = await self.async_redis.lrange(dlq_key, 0, limit - 1)

            for dlq_data in dlq_data_list:
                try:
                    entry = DLQEntry.model_validate_json(dlq_data)
                    entries.append(entry)
                except Exception as e:
                    self.logger.error(f"Failed to parse DLQ entry: {e}")

            return entries

        except Exception as e:
            self.logger.error(f"Failed to get DLQ messages: {e}")
            return []

    async def cleanup_expired_dlq_messages(self, queue_name: str) -> int:
        """
        Clean up expired DLQ messages.

        Args:
            queue_name: Queue name

        Returns:
            Number of messages cleaned up
        """
        dlq_key = self._get_dlq_key(queue_name)
        cleaned = 0

        try:
            # Get all DLQ messages
            dlq_data_list = await self.async_redis.lrange(dlq_key, 0, -1)
            current_time = datetime.utcnow()

            for dlq_data in dlq_data_list:
                try:
                    entry = DLQEntry.model_validate_json(dlq_data)

                    # Check if expired
                    expiry_time = entry.failure_timestamp + timedelta(hours=entry.dlq_ttl_hours)

                    if current_time > expiry_time:
                        # Remove from DLQ
                        await self.async_redis.lrem(dlq_key, 1, dlq_data)

                        # Remove metadata
                        metadata_key = self._get_dlq_metadata_key(entry.id)
                        await self.async_redis.delete(metadata_key)

                        cleaned += 1

                except Exception as e:
                    self.logger.error(f"Error checking DLQ entry expiry: {e}")

            if cleaned > 0:
                self.logger.info(f"Cleaned up {cleaned} expired DLQ messages from {queue_name}")
                await self._update_dlq_stats(queue_name, "cleaned")

            return cleaned

        except Exception as e:
            self.logger.error(f"Error during DLQ cleanup: {e}")
            return 0

    async def get_dlq_stats(self, queue_name: str) -> dict[str, Any]:
        """Get DLQ statistics for a queue"""
        dlq_key = self._get_dlq_key(queue_name)
        retry_key = self._get_retry_schedule_key(queue_name)

        stats = {
            "queue_name": queue_name,
            "dlq_count": await self.async_redis.llen(dlq_key),
            "scheduled_retries": await self.async_redis.zcard(retry_key),
            "added_total": await self._get_dlq_stat(queue_name, "added"),
            "retried_total": await self._get_dlq_stat(queue_name, "retried"),
            "replayed_total": await self._get_dlq_stat(queue_name, "replayed"),
            "cleaned_total": await self._get_dlq_stat(queue_name, "cleaned"),
        }

        return stats

    async def _update_dlq_stats(self, queue_name: str, operation: str):
        """Update DLQ statistics"""
        stats_key = f"dlq_stats:{queue_name}:{operation}"
        await self.async_redis.incr(stats_key)

    async def _get_dlq_stat(self, queue_name: str, operation: str) -> int:
        """Get DLQ statistic count"""
        stats_key = f"dlq_stats:{queue_name}:{operation}"
        count = await self.async_redis.get(stats_key)
        return int(count) if count else 0

    async def setup_key_expiry_notifications(self) -> bool:
        """
        Setup Redis key-expiry notifications for automatic timeout handling.

        Requires: notify-keyspace-events Ex in Redis config

        Returns:
            True if setup successfully
        """
        try:
            # Check if keyspace notifications are enabled
            config = await self.async_redis.config_get("notify-keyspace-events")

            if not config or "Ex" not in config.get("notify-keyspace-events", ""):
                self.logger.warning("Key-expiry notifications not enabled. Set notify-keyspace-events Ex")
                return False

            self.logger.info("Key-expiry notifications available for automatic timeout handling")
            return True

        except Exception as e:
            self.logger.error(f"Failed to check key-expiry notification config: {e}")
            return False

    async def handle_inflight_timeout(self, expired_key: str) -> bool:
        """
        Handle expired inflight message (called by key-expiry notification).

        Args:
            expired_key: Redis key that expired

        Returns:
            True if handled successfully
        """
        try:
            # Parse queue name from expired key
            if self.broker.inflight_suffix not in expired_key:
                return False

            # Extract queue name and worker ID
            parts = expired_key.replace(f"{self.broker.queue_prefix}", "").split(self.broker.inflight_suffix)
            if len(parts) != 2:
                return False

            queue_name = parts[0]
            worker_id = parts[1].lstrip(":")

            # Check if there are any messages in the expired inflight queue
            inflight_count = await self.async_redis.llen(expired_key)

            if inflight_count > 0:
                self.logger.warning(f"Detected {inflight_count} timed-out messages from worker {worker_id}")

                # Move messages back to main queue for retry
                main_queue_key = self.broker._get_queue_key(queue_name)

                while True:
                    message_data = await self.async_redis.rpop(expired_key)
                    if not message_data:
                        break

                    try:
                        message = QueueMessage.model_validate_json(message_data)

                        # Increment retry count
                        message.retry_count += 1

                        if message.retry_count <= message.max_retries:
                            # Schedule for retry
                            await self.schedule_retry(queue_name, message)
                        else:
                            # Move to DLQ
                            await self.add_to_dlq(
                                queue_name, message, f"timeout_after_{message.timeout_seconds}s", worker_id
                            )

                    except Exception as e:
                        self.logger.error(f"Error processing timed-out message: {e}")

                return True

            return False

        except Exception as e:
            self.logger.error(f"Error handling inflight timeout: {e}")
            return False
