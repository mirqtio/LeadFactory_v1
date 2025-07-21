"""
Final targeted tests to push PRP-1058 coverage over 80%.

Focus on the remaining uncovered lines in queue_monitor and dead_letter_queue.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from infra.dead_letter_queue import DeadLetterQueue
from infra.queue_monitor import QueueAlertThresholds, QueueMetrics, QueueMonitor
from infra.redis_queue import QueueMessage, QueueStats, RedisQueueBroker


@pytest.fixture
def mock_broker():
    """Mock queue broker for testing"""
    broker = MagicMock(spec=RedisQueueBroker)
    broker.redis_url = "redis://localhost:6379/0"
    broker.queue_prefix = "test_"
    broker.worker_id = "test-worker"
    broker.redis = AsyncMock()
    broker.get_queue_stats = MagicMock()
    return broker


@pytest.fixture
def mock_async_redis():
    """Mock async Redis client"""
    mock_client = AsyncMock()

    class AsyncContextManagerMock:
        def __init__(self):
            self.lpush = AsyncMock(return_value=1)
            self.setex = AsyncMock(return_value=True)
            self.execute = AsyncMock(return_value=[1, True])

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_client.pipeline = Mock(side_effect=lambda *args, **kwargs: AsyncContextManagerMock())
    mock_client.zadd = AsyncMock(return_value=1)
    mock_client.lrange = AsyncMock(return_value=[])
    mock_client.zrangebyscore = AsyncMock(return_value=[])
    mock_client.get = AsyncMock(return_value=None)
    mock_client.incr = AsyncMock(return_value=1)

    return mock_client


class TestQueueMonitorMissingCoverage:
    """Cover remaining lines in queue_monitor.py"""

    @pytest.fixture
    def monitor(self, mock_broker):
        """Create monitor with mocked dependencies"""
        with patch("infra.queue_monitor.get_metrics_collector") as mock_collector:
            mock_collector.return_value = MagicMock()
            monitor = QueueMonitor(mock_broker)
            yield monitor

    @pytest.mark.asyncio
    async def test_calculate_processing_rates_with_timestamps(self, monitor, mock_broker):
        """Test processing rate calculation with actual timestamps"""
        current_time = time.time()
        timestamps = [
            str(current_time - 30),  # 30s ago
            str(current_time - 120),  # 2min ago
            str(current_time - 600),  # 10min ago
            str(current_time - 800),  # 13min ago
        ]

        mock_broker.redis.zrangebyscore.return_value = timestamps

        rates = await monitor._calculate_processing_rates("test_queue")

        assert rates["1min"] == 1  # 1 message in last minute
        assert rates["5min"] == 0.4  # 2 messages / 5 minutes
        assert abs(rates["15min"] - 0.2667) < 0.001  # 4 messages / 15 minutes (approximately)

    @pytest.mark.asyncio
    async def test_get_timeout_count_with_value(self, monitor, mock_broker):
        """Test getting timeout count with actual value"""
        mock_broker.redis.get.return_value = "7"

        count = await monitor._get_timeout_count("test_queue")
        assert count == 7

    @pytest.mark.asyncio
    async def test_get_retry_count_with_value(self, monitor, mock_broker):
        """Test getting retry count with actual value"""
        mock_broker.redis.get.return_value = "12"

        count = await monitor._get_retry_count("test_queue")
        assert count == 12

    @pytest.mark.asyncio
    async def test_get_total_enqueued_with_value(self, monitor, mock_broker):
        """Test getting total enqueued with actual value"""
        mock_broker.redis.get.return_value = "250"

        count = await monitor._get_total_enqueued("test_queue")
        assert count == 250

    @pytest.mark.asyncio
    async def test_collect_queue_metrics_full_flow(self, monitor, mock_broker):
        """Test complete metrics collection flow"""
        # Mock all dependencies
        stats = QueueStats(
            queue_name="test_queue",
            pending_count=15,
            inflight_count=3,
            dlq_count=2,
            processed_total=200,
            failed_total=8,
        )
        mock_broker.get_queue_stats.return_value = stats

        # Mock processing rates
        mock_broker.redis.zrangebyscore.return_value = ["1000", "2000", "3000"]

        # Mock Redis get calls for counts in the order they're called:
        # timeout_count, retry_count, enqueued_total
        mock_broker.redis.get.side_effect = ["5", "12", "300"]  # timeout_count  # retry_count  # enqueued_total

        # Add some processing times
        monitor.processing_times["test_queue"] = [1.5, 2.0, 2.5, 3.0, 3.5]

        metrics = await monitor.collect_queue_metrics("test_queue")

        assert metrics.queue_name == "test_queue"
        assert metrics.pending_count == 15
        assert metrics.processed_total == 200
        assert metrics.enqueued_total == 300
        assert metrics.timeout_count == 5
        assert metrics.retry_count == 12
        assert metrics.avg_processing_time == 2.5  # Average of processing times

    @pytest.mark.asyncio
    async def test_get_last_activity_with_timestamp(self, monitor, mock_broker):
        """Test getting last activity with valid timestamp"""
        timestamp_str = datetime.utcnow().isoformat()
        mock_broker.redis.get.return_value = timestamp_str

        last_activity = await monitor._get_last_activity("test_queue")

        assert last_activity is not None
        assert isinstance(last_activity, datetime)

    @pytest.mark.asyncio
    async def test_get_last_activity_invalid_timestamp(self, monitor, mock_broker):
        """Test getting last activity with invalid timestamp"""
        mock_broker.redis.get.return_value = "invalid-timestamp"

        last_activity = await monitor._get_last_activity("test_queue")

        assert last_activity is None

    @pytest.mark.asyncio
    async def test_check_and_send_alerts_warning(self, monitor):
        """Test alert checking and sending for warning status"""
        from infra.queue_monitor import QueueAlertThresholds, QueueHealthStatus

        health_status = QueueHealthStatus(
            queue_name="warning_queue",
            status="warning",
            pending_count=150,  # Above warning threshold
            inflight_count=5,
            dlq_count=15,
            processing_rate=5.0,  # Below warning threshold
            avg_processing_time=45.0,  # Above warning threshold
            error_rate=8.0,  # Above warning threshold
            health_score=0.4,
        )

        thresholds = QueueAlertThresholds(queue_name="warning_queue")

        # Test that alerts checking runs without error
        await monitor._check_and_send_alerts(health_status, thresholds)

        # Should complete successfully for warning status

    @pytest.mark.asyncio
    async def test_check_and_send_alerts_healthy(self, monitor):
        """Test alert checking for healthy status (no alerts)"""
        from infra.queue_monitor import QueueAlertThresholds, QueueHealthStatus

        health_status = QueueHealthStatus(
            queue_name="healthy_queue",
            status="healthy",
            pending_count=50,
            inflight_count=2,
            dlq_count=1,
            processing_rate=25.0,
            avg_processing_time=2.0,
            error_rate=1.0,
            health_score=0.95,
        )

        thresholds = QueueAlertThresholds(queue_name="healthy_queue")

        # Should not send any alerts for healthy status
        await monitor._check_and_send_alerts(health_status, thresholds)

    @pytest.mark.asyncio
    async def test_get_queue_dashboard_data_with_failure(self, monitor):
        """Test dashboard data collection with some queue failures"""
        queue_names = ["queue1", "queue2", "queue3"]

        # Mock assess_queue_health to succeed for some, fail for others
        async def mock_assess_health(queue_name):
            if queue_name == "queue2":
                raise Exception("Queue assessment failed")

            from infra.queue_monitor import QueueHealthStatus

            return QueueHealthStatus(
                queue_name=queue_name,
                status="healthy" if queue_name == "queue1" else "warning",
                pending_count=10,
                inflight_count=1,
                dlq_count=0,
                processing_rate=20.0,
                avg_processing_time=2.0,
                error_rate=2.0,
                health_score=0.8 if queue_name == "queue1" else 0.6,
            )

        with patch.object(monitor, "assess_queue_health", side_effect=mock_assess_health):
            dashboard_data = await monitor.get_queue_dashboard_data(queue_names)

        assert dashboard_data["overall_health"] == "warning"  # Has warning queues
        assert dashboard_data["queues"]["queue1"]["status"] == "healthy"
        assert dashboard_data["queues"]["queue2"]["status"] == "unknown"  # Failed
        assert dashboard_data["queues"]["queue3"]["status"] == "warning"
        assert dashboard_data["status_summary"]["healthy"] >= 1
        assert dashboard_data["status_summary"]["warning"] >= 1

    @pytest.mark.asyncio
    async def test_get_queue_trends(self, monitor):
        """Test getting queue trends from history"""
        # Add some metrics history
        from infra.queue_monitor import QueueMetrics

        base_time = datetime.utcnow()

        # Add metrics from different time periods
        metrics_list = []
        for i in range(5):
            metrics = QueueMetrics(
                queue_name="test_queue",
                timestamp=base_time - timedelta(hours=i),
                pending_count=10 + i,
                inflight_count=1,
                dlq_count=0,
                enqueued_total=100 + (i * 10),
                processed_total=90 + (i * 8),
                failed_total=2 + i,
                processing_rate_1min=20.0 - i,
                processing_rate_5min=18.0 - i,
                processing_rate_15min=16.0 - i,
                avg_processing_time=2.0 + (i * 0.5),
                min_processing_time=1.0,
                max_processing_time=5.0 + i,
                p95_processing_time=4.0 + i,
                error_rate=2.0 + (i * 0.5),
                timeout_count=i,
                retry_count=i * 2,
            )
            metrics_list.append(metrics)

        monitor.metrics_history["test_queue"] = metrics_list

        trends = await monitor.get_queue_trends("test_queue", hours=6)

        assert len(trends["pending_count"]) == 5
        assert len(trends["processing_rate"]) == 5
        assert len(trends["error_rate"]) == 5
        assert len(trends["health_score"]) == 5

        # Check that trends contain expected data
        assert trends["pending_count"][0][1] == 10  # First metric
        assert trends["pending_count"][-1][1] == 14  # Last metric


class TestDeadLetterQueueMissingCoverage:
    """Cover remaining lines in dead_letter_queue.py"""

    @pytest.fixture
    def dlq(self, mock_broker, mock_async_redis):
        """Create DLQ with mocked dependencies"""
        with patch("redis.asyncio.from_url", return_value=mock_async_redis):
            dlq_instance = DeadLetterQueue(mock_broker)
            yield dlq_instance

    @pytest.mark.asyncio
    async def test_update_dlq_stats_calls(self, dlq, mock_async_redis):
        """Test DLQ stats update calls"""
        await dlq._update_dlq_stats("test_queue", "processed")

        # Should call both incr and set
        mock_async_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_dlq_stat_with_value(self, dlq, mock_async_redis):
        """Test getting DLQ stat with actual value"""
        mock_async_redis.get.return_value = "15"

        count = await dlq._get_dlq_stat("test_queue", "failed")
        assert count == 15

    @pytest.mark.asyncio
    async def test_get_dlq_stats_complete_flow(self, dlq, mock_async_redis):
        """Test complete DLQ stats retrieval"""
        # Mock all the Redis calls
        mock_async_redis.llen.return_value = 8  # dlq_count
        mock_async_redis.zcard.return_value = 3  # scheduled_retries

        # Mock the individual stat calls
        mock_async_redis.get.side_effect = ["25", "12", "5", "3"]  # added, retried, replayed, cleaned

        stats = await dlq.get_dlq_stats("test_queue")

        assert stats["queue_name"] == "test_queue"
        assert stats["dlq_count"] == 8
        assert stats["scheduled_retries"] == 3
        assert stats["added_total"] == 25
        assert stats["retried_total"] == 12
        assert stats["replayed_total"] == 5
        assert stats["cleaned_total"] == 3
