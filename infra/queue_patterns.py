"""
Reliable Queue Patterns using modern BLMOVE operations.

Implements battle-tested Redis queue patterns with per-worker backup queues,
atomic operations, and reliable message delivery guarantees. Replaces deprecated
BRPOPLPUSH with BLMOVE for Redis 7.2.x LTS compatibility.
"""
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import redis.asyncio as redis
from pydantic import BaseModel

from core.config import get_settings
from core.logging import get_logger
from infra.redis_queue import QueueMessage, RedisQueueBroker


class ReliableQueuePattern:
    """
    Reliable queue pattern with per-worker backup queues.

    Uses modern BLMOVE operations for atomic message transfer between queues,
    ensuring no message loss during processing. Implements hostname:PID naming
    pattern for worker isolation and automatic cleanup.
    """

    def __init__(self, broker: RedisQueueBroker, worker_id: Optional[str] = None):
        """
        Initialize reliable queue pattern.

        Args:
            broker: Redis queue broker instance
            worker_id: Worker identifier (defaults to broker's worker_id)
        """
        self.broker = broker
        self.worker_id = worker_id or broker.worker_id
        self.logger = get_logger("queue_patterns", domain="infra")

        # Async Redis connection for BLMOVE operations
        self.async_redis = redis.from_url(broker.redis_url, decode_responses=True)

    async def atomic_dequeue_with_backup(
        self, source_queue: str, backup_queue: str, timeout: float = 10.0
    ) -> Optional[QueueMessage]:
        """
        Atomically move message from source to backup queue using BLMOVE.

        Modern replacement for deprecated BRPOPLPUSH operation.

        Args:
            source_queue: Source queue name
            backup_queue: Backup queue name
            timeout: Blocking timeout in seconds

        Returns:
            QueueMessage or None if timeout
        """
        source_key = self.broker._get_queue_key(source_queue)
        backup_key = self.broker._get_queue_key(backup_queue)

        try:
            # Use BLMOVE for atomic right-to-left transfer
            message_data = await self.async_redis.blmove(source_key, backup_key, timeout, "RIGHT", "LEFT")

            if not message_data:
                return None

            try:
                message = QueueMessage.model_validate_json(message_data)
                self.logger.debug(f"Atomically moved message {message.id} from {source_queue} to {backup_queue}")
                return message

            except Exception as e:
                self.logger.error(f"Failed to parse message: {e}")
                # Move malformed message to DLQ
                await self._move_to_dlq_async(source_queue, message_data, "malformed_message")
                return None

        except redis.RedisError as e:
            self.logger.error(f"Redis error during atomic dequeue: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during atomic dequeue: {e}")
            raise

    async def _move_to_dlq_async(self, queue_name: str, message_data: str, reason: str):
        """Move message to DLQ asynchronously"""
        dlq_key = self.broker._get_dlq_key(queue_name)
        dlq_entry = {"timestamp": time.time(), "reason": reason, "message": message_data, "worker_id": self.worker_id}

        await self.async_redis.lpush(dlq_key, json.dumps(dlq_entry))

    async def process_backup_queue(self, backup_queue: str, processor_func: callable) -> int:
        """
        Process messages from backup queue with error handling.

        Args:
            backup_queue: Backup queue name
            processor_func: Async function to process messages

        Returns:
            Number of messages processed
        """
        backup_key = self.broker._get_queue_key(backup_queue)
        processed = 0

        while True:
            # Get message from backup queue (non-blocking)
            message_data = await self.async_redis.rpop(backup_key)

            if not message_data:
                break  # No more messages

            try:
                message = QueueMessage.model_validate_json(message_data)

                # Process message
                success = await processor_func(message)

                if success:
                    processed += 1
                    self.logger.debug(f"Processed backup message {message.id}")
                else:
                    # Requeue for retry
                    await self.async_redis.lpush(backup_key, message_data)
                    self.logger.warning(f"Requeued backup message {message.id} for retry")
                    break  # Stop processing to avoid infinite loop

            except Exception as e:
                self.logger.error(f"Error processing backup message: {e}")
                # Move to DLQ
                await self._move_to_dlq_async(backup_queue, message_data, f"processing_error: {e}")

        return processed

    async def cleanup_worker_queues(self, worker_id: Optional[str] = None) -> int:
        """
        Cleanup queues for a specific worker (useful for graceful shutdown).

        Args:
            worker_id: Worker to cleanup (defaults to self.worker_id)

        Returns:
            Number of messages moved back to main queues
        """
        target_worker = worker_id or self.worker_id
        moved_count = 0

        # Find all backup queues for this worker
        pattern = f"{self.broker.queue_prefix}*{self.broker.inflight_suffix}:{target_worker}"
        backup_keys = await self.async_redis.keys(pattern)

        for backup_key in backup_keys:
            # Extract original queue name
            queue_name = backup_key.replace(f"{self.broker.queue_prefix}", "")
            queue_name = queue_name.replace(f"{self.broker.inflight_suffix}:{target_worker}", "")

            source_key = self.broker._get_queue_key(queue_name)

            # Move all messages back to main queue
            while True:
                message_data = await self.async_redis.rpop(backup_key)
                if not message_data:
                    break

                await self.async_redis.lpush(source_key, message_data)
                moved_count += 1

        if moved_count > 0:
            self.logger.info(f"Moved {moved_count} messages back to main queues for worker {target_worker}")

        return moved_count

    async def get_worker_backup_stats(self) -> Dict[str, int]:
        """Get statistics for all backup queues for this worker"""
        pattern = f"{self.broker.queue_prefix}*{self.broker.inflight_suffix}:{self.worker_id}"
        backup_keys = await self.async_redis.keys(pattern)

        stats = {}
        for backup_key in backup_keys:
            queue_name = backup_key.replace(f"{self.broker.queue_prefix}", "")
            queue_name = queue_name.replace(f"{self.broker.inflight_suffix}:{self.worker_id}", "")

            count = await self.async_redis.llen(backup_key)
            stats[queue_name] = count

        return stats


class BatchQueuePattern:
    """
    Batch processing pattern for high-throughput scenarios.

    Processes multiple messages in batches to improve throughput while
    maintaining reliability guarantees.
    """

    def __init__(self, broker: RedisQueueBroker, batch_size: int = 10):
        """
        Initialize batch queue pattern.

        Args:
            broker: Redis queue broker instance
            batch_size: Number of messages to process in each batch
        """
        self.broker = broker
        self.batch_size = batch_size
        self.logger = get_logger("batch_queue_patterns", domain="infra")

        # Async Redis connection
        self.async_redis = redis.from_url(broker.redis_url, decode_responses=True)

    async def dequeue_batch(self, queue_name: str, batch_size: Optional[int] = None) -> List[QueueMessage]:
        """
        Dequeue multiple messages in a batch.

        Args:
            queue_name: Queue to dequeue from
            batch_size: Override default batch size

        Returns:
            List of messages (up to batch_size)
        """
        size = batch_size or self.batch_size
        queue_key = self.broker._get_queue_key(queue_name)
        messages = []

        # Use pipeline for efficiency
        async with self.async_redis.pipeline(transaction=True) as pipe:
            for _ in range(size):
                pipe.rpop(queue_key)
            results = await pipe.execute()

        for message_data in results:
            if message_data:
                try:
                    message = QueueMessage.model_validate_json(message_data)
                    messages.append(message)
                except Exception as e:
                    self.logger.error(f"Failed to parse batch message: {e}")
                    await self._move_to_dlq_async(queue_name, message_data, "malformed_message")

        if messages:
            self.logger.debug(f"Dequeued batch of {len(messages)} messages from {queue_name}")

        return messages

    async def _move_to_dlq_async(self, queue_name: str, message_data: str, reason: str):
        """Move message to DLQ asynchronously"""
        dlq_key = self.broker._get_dlq_key(queue_name)
        dlq_entry = {"timestamp": time.time(), "reason": reason, "message": message_data}

        await self.async_redis.lpush(dlq_key, json.dumps(dlq_entry))

    async def acknowledge_batch(self, queue_name: str, messages: List[QueueMessage]) -> int:
        """
        Acknowledge a batch of messages.

        Args:
            queue_name: Source queue name
            messages: Messages to acknowledge

        Returns:
            Number of messages successfully acknowledged
        """
        inflight_key = self.broker._get_inflight_key(queue_name)
        acknowledged = 0

        # Use pipeline for efficiency
        async with self.async_redis.pipeline(transaction=True) as pipe:
            for message in messages:
                pipe.lrem(inflight_key, 1, message.model_dump_json())
            results = await pipe.execute()

        acknowledged = sum(1 for result in results if result > 0)

        if acknowledged > 0:
            self.logger.debug(f"Acknowledged batch of {acknowledged} messages from {queue_name}")

        return acknowledged


class PriorityQueuePattern:
    """
    Priority queue pattern using Redis Sorted Sets.

    Implements priority-based message processing where higher priority
    messages are processed first. Uses ZADD/ZRANGE for priority ordering.
    """

    def __init__(self, broker: RedisQueueBroker):
        """
        Initialize priority queue pattern.

        Args:
            broker: Redis queue broker instance
        """
        self.broker = broker
        self.logger = get_logger("priority_queue_patterns", domain="infra")

        # Async Redis connection
        self.async_redis = redis.from_url(broker.redis_url, decode_responses=True)

    async def enqueue_with_priority(self, queue_name: str, message: QueueMessage) -> bool:
        """
        Enqueue message with priority using sorted set.

        Args:
            queue_name: Target queue name
            message: Message with priority

        Returns:
            True if enqueued successfully
        """
        priority_key = f"{self.broker._get_queue_key(queue_name)}:priority"

        try:
            # Use negative priority for descending order (highest priority first)
            score = -message.priority
            result = await self.async_redis.zadd(priority_key, {message.model_dump_json(): score})

            if result:
                self.logger.debug(f"Enqueued priority message {message.id} with priority {message.priority}")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to enqueue priority message: {e}")
            return False

    async def dequeue_by_priority(self, queue_name: str, count: int = 1) -> List[QueueMessage]:
        """
        Dequeue highest priority messages.

        Args:
            queue_name: Queue to dequeue from
            count: Number of messages to dequeue

        Returns:
            List of messages ordered by priority (highest first)
        """
        priority_key = f"{self.broker._get_queue_key(queue_name)}:priority"
        messages = []

        try:
            # Get highest priority messages (lowest scores due to negation)
            message_data_list = await self.async_redis.zrange(priority_key, 0, count - 1, withscores=False)

            if message_data_list:
                # Remove from priority queue
                await self.async_redis.zrem(priority_key, *message_data_list)

                # Parse messages
                for message_data in message_data_list:
                    try:
                        message = QueueMessage.model_validate_json(message_data)
                        messages.append(message)
                    except Exception as e:
                        self.logger.error(f"Failed to parse priority message: {e}")
                        await self._move_to_dlq_async(queue_name, message_data, "malformed_message")

            if messages:
                self.logger.debug(f"Dequeued {len(messages)} priority messages from {queue_name}")

            return messages

        except Exception as e:
            self.logger.error(f"Failed to dequeue priority messages: {e}")
            return []

    async def _move_to_dlq_async(self, queue_name: str, message_data: str, reason: str):
        """Move message to DLQ asynchronously"""
        dlq_key = self.broker._get_dlq_key(queue_name)
        dlq_entry = {"timestamp": time.time(), "reason": reason, "message": message_data}

        await self.async_redis.lpush(dlq_key, json.dumps(dlq_entry))

    async def get_priority_stats(self, queue_name: str) -> Dict[str, Any]:
        """Get priority queue statistics"""
        priority_key = f"{self.broker._get_queue_key(queue_name)}:priority"

        total_count = await self.async_redis.zcard(priority_key)

        if total_count == 0:
            return {"total_count": 0, "priority_distribution": {}}

        # Get priority distribution
        all_messages = await self.async_redis.zrange(priority_key, 0, -1, withscores=True)

        priority_distribution = {}
        for message_data, score in all_messages:
            priority = int(-score)  # Convert back from negative score
            priority_distribution[priority] = priority_distribution.get(priority, 0) + 1

        return {"total_count": total_count, "priority_distribution": priority_distribution}


@asynccontextmanager
async def queue_worker_context(broker: RedisQueueBroker) -> AsyncGenerator[ReliableQueuePattern, None]:
    """
    Context manager for queue worker with automatic cleanup.

    Ensures worker backup queues are cleaned up on shutdown.
    """
    pattern = ReliableQueuePattern(broker)

    try:
        yield pattern
    finally:
        # Cleanup worker queues on shutdown
        moved = await pattern.cleanup_worker_queues()
        if moved > 0:
            logging.getLogger("queue_patterns").info(f"Cleaned up {moved} messages on worker shutdown")
