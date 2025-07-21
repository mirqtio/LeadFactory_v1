"""
Simple working unit tests for infra.queue_monitor to achieve coverage.

Focus on core queue monitoring functionality without asyncio complications.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from infra.queue_monitor import (
    QueueAlertThresholds,
    QueueHealthStatus,
    QueueMetrics,
    QueueMonitor,
    get_queue_monitor,
    reset_queue_monitor,
)
from infra.redis_queue import QueueStats, RedisQueueBroker


@pytest.fixture
def mock_broker():
    """Mock queue broker for testing"""
    broker = MagicMock(spec=RedisQueueBroker)
    broker.redis_url = "redis://localhost:6379/0"
    broker.queue_prefix = "test_"
    broker.worker_id = "test-worker"

    # Mock Redis client
    broker.redis = AsyncMock()

    # Mock get_queue_stats method
    broker.get_queue_stats = MagicMock()

    return broker


@pytest.fixture
def mock_metrics_collector():
    """Mock metrics collector for testing"""
    collector = MagicMock()
    collector.gauge = MagicMock()
    collector.increment = MagicMock()
    collector.histogram = MagicMock()
    return collector


@pytest.fixture
def monitor(mock_broker, mock_metrics_collector):
    """Create QueueMonitor instance with mocked dependencies"""
    with patch("infra.queue_monitor.get_metrics_collector", return_value=mock_metrics_collector):
        monitor_instance = QueueMonitor(mock_broker)
        yield monitor_instance


class TestQueueHealthStatus:
    """Test QueueHealthStatus model"""

    def test_queue_health_status_creation(self):
        """Test creating queue health status"""
        status = QueueHealthStatus(
            queue_name="test_queue",
            status="healthy",
            pending_count=5,
            inflight_count=2,
            dlq_count=0,
            processing_rate=50.0,
            avg_processing_time=1.5,
            error_rate=0.5,
            health_score=0.95,
        )

        assert status.queue_name == "test_queue"
        assert status.status == "healthy"
        assert status.health_score == 0.95


class TestQueueAlertThresholds:
    """Test QueueAlertThresholds model"""

    def test_queue_alert_thresholds_defaults(self):
        """Test queue alert thresholds with default values"""
        thresholds = QueueAlertThresholds(queue_name="test_queue")

        assert thresholds.queue_name == "test_queue"
        assert thresholds.pending_warning_threshold == 100
        assert thresholds.pending_critical_threshold == 500


class TestQueueMetrics:
    """Test QueueMetrics model"""

    def test_queue_metrics_creation(self):
        """Test creating queue metrics"""
        metrics = QueueMetrics(
            queue_name="test_queue",
            pending_count=10,
            inflight_count=3,
            dlq_count=1,
            enqueued_total=100,
            processed_total=95,
            failed_total=4,
            processing_rate_1min=25.0,
            processing_rate_5min=20.0,
            processing_rate_15min=18.0,
            avg_processing_time=2.5,
            min_processing_time=0.5,
            max_processing_time=10.0,
            p95_processing_time=8.0,
            error_rate=4.2,
            timeout_count=1,
            retry_count=2,
        )

        assert metrics.queue_name == "test_queue"
        assert metrics.processing_rate_1min == 25.0
        assert metrics.error_rate == 4.2


class TestQueueMonitor:
    """Test QueueMonitor class"""

    def test_initialization(self, monitor, mock_broker):
        """Test monitor initialization"""
        assert monitor.broker == mock_broker
        assert len(monitor.alert_thresholds) == 0
        assert monitor.max_history_size == 1440
        assert monitor.max_processing_times == 100

    def test_set_get_alert_thresholds(self, monitor):
        """Test setting and getting alert thresholds"""
        thresholds = QueueAlertThresholds(queue_name="test_queue", pending_warning_threshold=50)

        monitor.set_alert_thresholds("test_queue", thresholds)

        assert "test_queue" in monitor.alert_thresholds
        assert monitor.alert_thresholds["test_queue"].pending_warning_threshold == 50

        # Test getting default thresholds
        default_thresholds = monitor.get_alert_thresholds("new_queue")
        assert default_thresholds.queue_name == "new_queue"
        assert default_thresholds.pending_warning_threshold == 100  # Default

    def test_calculate_timing_metrics_empty(self, monitor):
        """Test timing metrics calculation with no data"""
        metrics = monitor._calculate_timing_metrics("empty_queue")

        expected = {"avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}
        assert metrics == expected

    def test_calculate_timing_metrics_with_data(self, monitor):
        """Test timing metrics calculation with processing times"""
        processing_times = [1.0, 2.0, 3.0, 4.0, 5.0]
        monitor.processing_times["test_queue"] = processing_times

        metrics = monitor._calculate_timing_metrics("test_queue")

        assert metrics["avg"] == 3.0  # Average of 1-5
        assert metrics["min"] == 1.0
        assert metrics["max"] == 5.0
        assert metrics["p95"] == 5.0

    def test_calculate_error_rate(self, monitor):
        """Test error rate calculation"""
        stats = QueueStats(
            queue_name="test_queue", pending_count=0, inflight_count=0, dlq_count=0, processed_total=95, failed_total=5
        )

        error_rate = monitor._calculate_error_rate(stats)
        assert error_rate == 5.0  # 5/100 = 5%

        # Test zero processed case
        stats_zero = QueueStats(
            queue_name="empty_queue", pending_count=0, inflight_count=0, dlq_count=0, processed_total=0, failed_total=0
        )

        error_rate_zero = monitor._calculate_error_rate(stats_zero)
        assert error_rate_zero == 0.0

    def test_store_metrics_history(self, monitor):
        """Test storing metrics history"""
        metrics1 = QueueMetrics(
            queue_name="test_queue",
            pending_count=5,
            inflight_count=1,
            dlq_count=0,
            enqueued_total=50,
            processed_total=45,
            failed_total=2,
            processing_rate_1min=10.0,
            processing_rate_5min=8.0,
            processing_rate_15min=7.0,
            avg_processing_time=2.0,
            min_processing_time=1.0,
            max_processing_time=5.0,
            p95_processing_time=4.0,
            error_rate=4.4,
            timeout_count=0,
            retry_count=1,
        )

        monitor._store_metrics_history("test_queue", metrics1)

        assert len(monitor.metrics_history["test_queue"]) == 1
        assert monitor.metrics_history["test_queue"][0] == metrics1

    def test_calculate_health_score_healthy(self, monitor):
        """Test health score calculation for healthy queue"""
        metrics = QueueMetrics(
            queue_name="test_queue",
            pending_count=50,  # Below warning threshold
            inflight_count=2,
            dlq_count=5,  # Below warning threshold
            enqueued_total=100,
            processed_total=95,
            failed_total=2,
            processing_rate_1min=25.0,  # Above warning threshold
            processing_rate_5min=20.0,
            processing_rate_15min=18.0,
            avg_processing_time=15.0,  # Below warning threshold
            min_processing_time=1.0,
            max_processing_time=30.0,
            p95_processing_time=25.0,
            error_rate=2.0,  # Below warning threshold
            timeout_count=0,
            retry_count=1,
        )

        thresholds = QueueAlertThresholds(queue_name="test_queue")

        score, status = monitor._calculate_health_score(metrics, thresholds)

        assert status == "healthy"
        assert score == 1.0

    def test_calculate_health_score_warning(self, monitor):
        """Test health score calculation with warning conditions"""
        metrics = QueueMetrics(
            queue_name="warning_queue",
            pending_count=150,  # Above warning threshold
            inflight_count=2,
            dlq_count=15,  # Above warning threshold
            enqueued_total=200,
            processed_total=180,
            failed_total=10,
            processing_rate_1min=5.0,  # Below warning threshold
            processing_rate_5min=4.0,
            processing_rate_15min=3.0,
            avg_processing_time=40.0,  # Above warning threshold
            min_processing_time=5.0,
            max_processing_time=60.0,
            p95_processing_time=55.0,
            error_rate=8.0,  # Above warning threshold
            timeout_count=2,
            retry_count=5,
        )

        thresholds = QueueAlertThresholds(queue_name="warning_queue")

        score, status = monitor._calculate_health_score(metrics, thresholds)

        assert status == "warning"
        assert score < 1.0

    def test_calculate_health_score_critical(self, monitor):
        """Test health score calculation with critical conditions"""
        metrics = QueueMetrics(
            queue_name="critical_queue",
            pending_count=600,  # Above critical threshold
            inflight_count=50,
            dlq_count=60,  # Above critical threshold
            enqueued_total=1000,
            processed_total=900,
            failed_total=80,
            processing_rate_1min=0.5,  # Below critical threshold
            processing_rate_5min=0.3,
            processing_rate_15min=0.2,
            avg_processing_time=150.0,  # Above critical threshold
            min_processing_time=30.0,
            max_processing_time=300.0,
            p95_processing_time=250.0,
            error_rate=20.0,  # Above critical threshold
            timeout_count=10,
            retry_count=20,
        )

        thresholds = QueueAlertThresholds(queue_name="critical_queue")

        score, status = monitor._calculate_health_score(metrics, thresholds)

        assert status == "critical"
        assert score < 0.5

    def test_record_processing_time_basic(self, monitor):
        """Test basic processing time recording without asyncio"""
        # Patch the async task creation to avoid runtime errors
        with patch("asyncio.create_task") as mock_create_task:
            monitor.record_processing_time("test_queue", 2.5)

            assert "test_queue" in monitor.processing_times
            assert monitor.processing_times["test_queue"] == [2.5]

            # Verify async task was attempted to be created
            mock_create_task.assert_called_once()


class TestGlobalMonitorFunctions:
    """Test global monitor management functions"""

    def test_get_queue_monitor(self):
        """Test getting global monitor instance"""
        reset_queue_monitor()  # Ensure clean state

        with (
            patch("infra.redis_queue.get_queue_broker") as mock_get_broker,
            patch("infra.queue_monitor.get_metrics_collector") as mock_get_collector,
        ):
            mock_broker = MagicMock(spec=RedisQueueBroker)
            mock_broker.redis_url = "redis://localhost:6379/0"
            mock_get_broker.return_value = mock_broker
            mock_get_collector.return_value = MagicMock()

            monitor1 = get_queue_monitor()
            monitor2 = get_queue_monitor()

            assert monitor1 is monitor2  # Same instance
            assert isinstance(monitor1, QueueMonitor)

    def test_reset_queue_monitor(self):
        """Test resetting global monitor instance"""
        with (
            patch("infra.redis_queue.get_queue_broker") as mock_get_broker,
            patch("infra.queue_monitor.get_metrics_collector") as mock_get_collector,
        ):
            mock_broker = MagicMock(spec=RedisQueueBroker)
            mock_broker.redis_url = "redis://localhost:6379/0"
            mock_get_broker.return_value = mock_broker
            mock_get_collector.return_value = MagicMock()

            monitor1 = get_queue_monitor()
            reset_queue_monitor()
            monitor2 = get_queue_monitor()

            assert monitor1 is not monitor2  # Different instances


class TestQueueMonitorEdgeCases:
    """Test edge cases and error scenarios"""

    def test_processing_times_max_size_trimming(self, monitor):
        """Test that processing times are trimmed to max size"""
        # Patch asyncio.create_task to avoid runtime error
        with patch("asyncio.create_task"):
            # Add more than max_processing_times (100)
            for i in range(110):
                monitor.record_processing_time("test_queue", float(i))

            # Should be trimmed to max size
            assert len(monitor.processing_times["test_queue"]) == 100

            # Should keep the most recent values
            times = monitor.processing_times["test_queue"]
            assert times[-1] == 109.0  # Last added value
            assert times[0] == 10.0  # First value after trimming

    def test_metrics_history_trimming(self, monitor):
        """Test that metrics history is trimmed to max size"""
        # Create dummy metrics
        base_metrics = QueueMetrics(
            queue_name="test_queue",
            pending_count=5,
            inflight_count=1,
            dlq_count=0,
            enqueued_total=50,
            processed_total=48,
            failed_total=1,
            processing_rate_1min=15.0,
            processing_rate_5min=12.0,
            processing_rate_15min=10.0,
            avg_processing_time=2.0,
            min_processing_time=1.0,
            max_processing_time=4.0,
            p95_processing_time=3.5,
            error_rate=2.1,
            timeout_count=0,
            retry_count=1,
        )

        # Add more than max_history_size (1440)
        for i in range(1450):
            metrics = base_metrics.model_copy()
            metrics.timestamp = datetime.utcnow()
            monitor._store_metrics_history("test_queue", metrics)

        # Should be trimmed to max size
        assert len(monitor.metrics_history["test_queue"]) == 1440
