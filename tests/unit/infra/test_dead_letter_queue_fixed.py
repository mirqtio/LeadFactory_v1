"""
Fixed unit tests for infra.dead_letter_queue - Essential DLQ functionality tests.

Focus on core dead letter queue features to achieve coverage requirements.
"""
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from infra.dead_letter_queue import DeadLetterQueue, DLQEntry, RetryPolicy
from infra.redis_queue import QueueMessage, RedisQueueBroker


@pytest.fixture
def mock_broker():
    """Mock queue broker for testing"""
    broker = MagicMock(spec=RedisQueueBroker)
    broker.redis_url = "redis://localhost:6379/0"
    broker.queue_prefix = "test_"
    broker.worker_id = "test-worker"
    return broker


@pytest.fixture
def mock_async_redis():
    """Mock async Redis client for testing"""
    mock_client = AsyncMock()

    # Create a proper async context manager mock for pipeline
    class AsyncContextManagerMock:
        def __init__(self):
            self.lpush = AsyncMock()
            self.setex = AsyncMock()
            self.execute = AsyncMock(return_value=[1, True])

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock pipeline to accept any arguments and return the context manager
    def create_pipeline(*args, **kwargs):
        return AsyncContextManagerMock()

    mock_client.pipeline = Mock(side_effect=create_pipeline)
    mock_client.zadd = AsyncMock(return_value=1)
    mock_client.lrange = AsyncMock(return_value=[])
    return mock_client


@pytest.fixture
def dlq(mock_broker, mock_async_redis):
    """Create DeadLetterQueue instance with mocked dependencies"""
    with patch("redis.asyncio.from_url", return_value=mock_async_redis):
        dlq_instance = DeadLetterQueue(mock_broker)
        yield dlq_instance


class TestRetryPolicy:
    """Test RetryPolicy model"""

    def test_retry_policy_defaults(self):
        """Test retry policy with default values"""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.initial_delay_seconds == 1
        assert policy.max_delay_seconds == 300
        assert policy.backoff_multiplier == 2.0
        assert policy.jitter_enabled is True


class TestDLQEntry:
    """Test DLQEntry model"""

    def test_dlq_entry_creation(self):
        """Test creating DLQ entry"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"})

        entry = DLQEntry(
            id="dlq-1",
            original_message=message,
            failure_reason="processing_failed",
            failure_timestamp=datetime.utcnow(),
            retry_count=2,
            worker_id="worker-1",
        )

        assert entry.id == "dlq-1"
        assert entry.original_message == message
        assert entry.failure_reason == "processing_failed"
        assert entry.retry_count == 2
        assert entry.worker_id == "worker-1"
        assert entry.can_replay is True
        assert entry.dlq_ttl_hours == 168  # 7 days default


class TestDeadLetterQueue:
    """Test DeadLetterQueue class"""

    def test_initialization(self, dlq, mock_broker):
        """Test DLQ initialization"""
        assert dlq.broker == mock_broker
        assert isinstance(dlq.retry_policy, RetryPolicy)

    def test_custom_retry_policy(self, mock_broker, mock_async_redis):
        """Test DLQ with custom retry policy"""
        custom_policy = RetryPolicy(max_retries=5, initial_delay_seconds=2)
        with patch("redis.asyncio.from_url", return_value=mock_async_redis):
            dlq_instance = DeadLetterQueue(mock_broker, custom_policy)

        assert dlq_instance.retry_policy.max_retries == 5
        assert dlq_instance.retry_policy.initial_delay_seconds == 2

    def test_calculate_retry_delay_exponential_backoff(self, dlq):
        """Test retry delay calculation with exponential backoff"""
        # Disable jitter for predictable testing
        dlq.retry_policy.jitter_enabled = False

        delays = []
        for retry_count in range(5):
            delay = dlq._calculate_retry_delay(retry_count)
            delays.append(delay)

        # Should increase exponentially without jitter
        assert delays[0] == 1  # 1 * 2^0 = 1
        assert delays[1] == 2  # 1 * 2^1 = 2
        assert delays[2] == 4  # 1 * 2^2 = 4
        assert delays[3] == 8  # 1 * 2^3 = 8

    def test_calculate_retry_delay_max_cap(self, dlq):
        """Test retry delay respects maximum cap"""
        # Very high retry count should be capped
        delay = dlq._calculate_retry_delay(20)
        assert delay <= dlq.retry_policy.max_delay_seconds * 1.5  # Allow jitter overhead

    def test_calculate_retry_delay_no_jitter(self, dlq):
        """Test retry delay without jitter"""
        dlq.retry_policy.jitter_enabled = False

        delay0 = dlq._calculate_retry_delay(0)
        delay1 = dlq._calculate_retry_delay(1)
        delay2 = dlq._calculate_retry_delay(2)

        assert delay0 == 1  # 1 * 2^0
        assert delay1 == 2  # 1 * 2^1
        assert delay2 == 4  # 1 * 2^2

    @pytest.mark.asyncio
    async def test_add_to_dlq_success(self, dlq, mock_async_redis):
        """Test successfully adding message to DLQ"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"})

        # Mock _update_dlq_stats to avoid additional complexity
        with patch.object(dlq, "_update_dlq_stats", new_callable=AsyncMock):
            result = await dlq.add_to_dlq("test_queue", message, "processing_failed", "worker-1")

        assert result is True
        mock_async_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_dlq_redis_error(self, dlq, mock_async_redis):
        """Test adding to DLQ with Redis error"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"})

        mock_async_redis.pipeline.side_effect = Exception("Redis error")

        result = await dlq.add_to_dlq("test_queue", message, "processing_failed", "worker-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_schedule_retry_success(self, dlq, mock_async_redis):
        """Test successfully scheduling retry"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"}, retry_count=1)

        mock_async_redis.zadd.return_value = 1

        with patch("time.time", return_value=1000.0):
            result = await dlq.schedule_retry("test_queue", message, delay_seconds=30)

        assert result is True
        mock_async_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_retry_with_calculated_delay(self, dlq, mock_async_redis):
        """Test scheduling retry with calculated delay"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"}, retry_count=2)

        mock_async_redis.zadd.return_value = 1

        result = await dlq.schedule_retry("test_queue", message)  # No delay specified

        assert result is True
        mock_async_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_dlq_messages(self, dlq, mock_async_redis):
        """Test getting DLQ messages"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"})
        dlq_entry = DLQEntry(
            id="dlq-1",
            original_message=message,
            failure_reason="test_failure",
            failure_timestamp=datetime.utcnow(),
            retry_count=1,
            worker_id="worker-1",
        )

        mock_async_redis.lrange.return_value = [dlq_entry.model_dump_json()]

        messages = await dlq.get_dlq_messages("test_queue", limit=10)

        assert len(messages) == 1
        assert messages[0].id == "dlq-1"
        assert messages[0].failure_reason == "test_failure"

    @pytest.mark.asyncio
    async def test_get_dlq_messages_malformed(self, dlq, mock_async_redis):
        """Test getting DLQ messages with malformed data"""
        mock_async_redis.lrange.return_value = ["invalid-json", "also-invalid"]

        messages = await dlq.get_dlq_messages("test_queue")

        assert len(messages) == 0  # Malformed messages filtered out


class TestDeadLetterQueueEdgeCases:
    """Test edge cases and error scenarios"""

    def test_calculate_retry_delay_edge_cases(self, dlq):
        """Test retry delay calculation edge cases"""
        # Zero retry count with jitter disabled should give initial delay
        dlq.retry_policy.jitter_enabled = False
        delay = dlq._calculate_retry_delay(0)
        assert delay == 1  # Should be exactly initial_delay (1) when jitter disabled

        # Negative retry count (shouldn't happen but handle gracefully)
        # With jitter disabled: 1 * 2^(-1) = 1 * 0.5 = 0.5, then int(0.5) = 0
        delay = dlq._calculate_retry_delay(-1)
        assert delay >= 0  # Should not be negative, but can be 0

    @pytest.mark.asyncio
    async def test_dlq_operations_with_redis_exceptions(self, dlq, mock_async_redis):
        """Test DLQ operations handle Redis exceptions gracefully"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"})

        # Test add_to_dlq with exception
        mock_async_redis.pipeline.side_effect = Exception("Redis connection lost")
        result = await dlq.add_to_dlq("test_queue", message, "test_failure", "worker-1")
        assert result is False

        # Test schedule_retry with exception
        mock_async_redis.zadd.side_effect = Exception("Redis error")
        result = await dlq.schedule_retry("test_queue", message)
        assert result is False

        # Test get_dlq_messages with exception
        mock_async_redis.lrange.side_effect = Exception("Redis error")
        messages = await dlq.get_dlq_messages("test_queue")
        assert len(messages) == 0
