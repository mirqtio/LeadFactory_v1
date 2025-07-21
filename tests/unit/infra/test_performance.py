"""
Performance test suite for PRP-1058 Redis Queue Broker.

Tests performance requirements:
- 100+ messages/minute throughput
- <100ms latency for queue operations
- System behavior under load
"""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from infra.redis_queue import QueueMessage, RedisQueueBroker


@pytest.fixture
def mock_redis():
    """Mock Redis client for performance testing"""
    mock_client = MagicMock()

    # Mock basic operations to return immediately
    mock_client.lpush.return_value = 1
    mock_client.brpop.return_value = ("test_queue", '{"queue_name": "test_queue", "payload": {"test": "data"}}')
    mock_client.llen.return_value = 0
    mock_client.hgetall.return_value = {"processed_total": "100", "failed_total": "2"}
    mock_client.ping.return_value = True

    return mock_client


@pytest.fixture
def broker(mock_redis):
    """Create broker instance with mocked Redis"""
    with patch("redis.Redis.from_url", return_value=mock_redis):
        broker = RedisQueueBroker()
        yield broker


class TestRedisQueuePerformance:
    """Performance tests for Redis Queue Broker"""

    def test_enqueue_latency_requirement(self, broker):
        """Test that enqueue operations complete within 100ms"""
        message_payload = {"test": "performance_data"}

        # Measure enqueue latency
        start_time = time.time()
        for _ in range(10):  # Test multiple operations
            message_id = broker.enqueue("performance_test", message_payload)
            assert message_id is not None
        end_time = time.time()

        # Calculate average latency per operation
        avg_latency_ms = ((end_time - start_time) / 10) * 1000

        # Verify latency requirement: <100ms per operation
        assert avg_latency_ms < 100, f"Average enqueue latency {avg_latency_ms:.2f}ms exceeds 100ms requirement"

    def test_dequeue_latency_requirement(self, broker, mock_redis):
        """Test that dequeue operations complete within 100ms"""
        # Mock dequeue to return quickly
        mock_redis.brpop.return_value = ("test_queue", '{"queue_name": "test_queue", "payload": {"test": "data"}}')

        # Measure dequeue latency
        start_time = time.time()
        for _ in range(10):  # Test multiple operations
            result = broker.dequeue(["performance_test"], timeout=0.1)
            assert result is not None
        end_time = time.time()

        # Calculate average latency per operation
        avg_latency_ms = ((end_time - start_time) / 10) * 1000

        # Verify latency requirement: <100ms per operation
        assert avg_latency_ms < 100, f"Average dequeue latency {avg_latency_ms:.2f}ms exceeds 100ms requirement"

    def test_throughput_requirement(self, broker):
        """Test that system can handle 100+ messages per minute"""
        message_payload = {"test": "throughput_data", "timestamp": time.time()}

        # Test throughput over a shorter time period (extrapolated)
        test_duration_seconds = 6  # 10% of a minute for faster testing
        required_messages_in_test = 10  # 10% of 100 messages/minute

        start_time = time.time()
        messages_processed = 0

        # Process messages for the test duration
        while (time.time() - start_time) < test_duration_seconds:
            message_id = broker.enqueue("throughput_test", message_payload)
            if message_id:
                messages_processed += 1

        end_time = time.time()
        actual_duration = end_time - start_time

        # Calculate messages per minute
        messages_per_minute = (messages_processed / actual_duration) * 60

        # Verify throughput requirement: 100+ messages/minute
        assert messages_per_minute >= 100, f"Throughput {messages_per_minute:.1f} msg/min below 100 msg/min requirement"

    def test_concurrent_operations_performance(self, broker):
        """Test performance under concurrent load"""
        import threading

        message_payload = {"test": "concurrent_data"}
        results = []

        def enqueue_worker():
            """Worker function for concurrent enqueue operations"""
            start_time = time.time()
            for _ in range(10):
                message_id = broker.enqueue("concurrent_test", message_payload)
                assert message_id is not None
            end_time = time.time()
            results.append(end_time - start_time)

        # Create multiple threads for concurrent testing
        threads = []
        num_threads = 5

        for _ in range(num_threads):
            thread = threading.Thread(target=enqueue_worker)
            threads.append(thread)

        # Start all threads simultaneously
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        end_time = time.time()

        # Verify concurrent operations completed within reasonable time
        total_duration = end_time - start_time
        assert total_duration < 5.0, f"Concurrent operations took {total_duration:.2f}s, too slow"

        # Verify individual thread performance
        for thread_duration in results:
            thread_latency_ms = (thread_duration / 10) * 1000  # Per operation
            assert thread_latency_ms < 100, f"Thread latency {thread_latency_ms:.2f}ms exceeds requirement"

    def test_queue_stats_performance(self, broker, mock_redis):
        """Test that queue statistics retrieval is performant"""
        # Mock stats responses
        mock_redis.llen.return_value = 5
        mock_redis.hgetall.return_value = {
            "processed_total": "1000",
            "failed_total": "10",
            "last_processed": str(time.time()),
        }

        # Measure stats retrieval performance
        start_time = time.time()
        for _ in range(20):  # Test multiple stat retrievals
            stats = broker.get_queue_stats("performance_test")
            assert stats is not None
            assert stats.queue_name == "performance_test"
        end_time = time.time()

        # Calculate average latency per stats operation
        avg_latency_ms = ((end_time - start_time) / 20) * 1000

        # Verify stats retrieval is fast: <50ms per operation
        assert avg_latency_ms < 50, f"Average stats latency {avg_latency_ms:.2f}ms exceeds 50ms requirement"

    def test_health_check_performance(self, broker, mock_redis):
        """Test that health checks are performant"""
        mock_redis.ping.return_value = True

        # Measure health check performance
        start_time = time.time()
        for _ in range(50):  # Test multiple health checks
            health_status = broker.health_check()
            assert health_status["status"] == "healthy"
        end_time = time.time()

        # Calculate average latency per health check
        avg_latency_ms = ((end_time - start_time) / 50) * 1000

        # Verify health checks are very fast: <10ms per operation
        assert avg_latency_ms < 10, f"Average health check latency {avg_latency_ms:.2f}ms exceeds 10ms requirement"

    def test_memory_efficiency_under_load(self, broker):
        """Test memory usage remains reasonable under load"""
        import tracemalloc

        # Start memory tracing
        tracemalloc.start()

        # Perform memory-intensive operations
        message_payload = {"test": "memory_data", "large_field": "x" * 1000}  # 1KB payload

        initial_memory = tracemalloc.get_traced_memory()[0]

        # Process many messages
        for i in range(100):
            message_id = broker.enqueue("memory_test", {**message_payload, "id": i})
            assert message_id is not None

        final_memory = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()

        # Calculate memory increase
        memory_increase_mb = (final_memory - initial_memory) / (1024 * 1024)

        # Verify memory usage is reasonable: <10MB increase for 100 messages
        assert memory_increase_mb < 10, f"Memory increase {memory_increase_mb:.2f}MB too high"

    def test_error_handling_performance(self, broker, mock_redis):
        """Test that error handling doesn't significantly impact performance"""
        # Mock Redis to occasionally fail
        call_count = 0

        def mock_lpush_with_errors(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 10 == 0:  # Fail every 10th call
                raise Exception("Simulated Redis error")
            return 1

        mock_redis.lpush.side_effect = mock_lpush_with_errors

        message_payload = {"test": "error_handling_data"}

        # Measure performance with errors
        start_time = time.time()
        successful_operations = 0

        for _ in range(50):
            try:
                message_id = broker.enqueue("error_test", message_payload)
                if message_id:
                    successful_operations += 1
            except Exception:
                pass  # Expected for some operations

        end_time = time.time()

        # Verify error handling doesn't make operations too slow
        avg_latency_ms = ((end_time - start_time) / 50) * 1000
        assert avg_latency_ms < 150, f"Error handling latency {avg_latency_ms:.2f}ms too high"

        # Verify some operations succeeded despite errors
        assert successful_operations > 40, f"Too many operations failed: {successful_operations}/50"


class TestQueueMonitorPerformance:
    """Performance tests for Queue Monitor"""

    @pytest.fixture
    def mock_monitor_deps(self):
        """Mock dependencies for queue monitor"""
        from infra.queue_monitor import QueueMetrics

        mock_broker = MagicMock()
        # Use real QueueMetrics object instead of MagicMock for numeric operations
        test_metrics = QueueMetrics(
            queue_name="test_queue",
            pending_count=5,
            inflight_count=1,
            dlq_count=0,
            enqueued_total=100,
            processed_total=98,
            failed_total=2,
            processing_rate_1min=25.0,
            processing_rate_5min=20.0,
            processing_rate_15min=18.0,
            avg_processing_time=2.0,
            min_processing_time=1.0,
            max_processing_time=5.0,
            p95_processing_time=4.0,
            error_rate=2.0,
            timeout_count=0,
            retry_count=1,
        )
        mock_broker.get_queue_stats.return_value = test_metrics

        mock_collector = MagicMock()

        return mock_broker, mock_collector

    def test_health_assessment_performance(self, mock_monitor_deps):
        """Test queue health assessment performance"""
        mock_broker, mock_collector = mock_monitor_deps

        with patch("infra.queue_monitor.get_metrics_collector", return_value=mock_collector):
            from infra.queue_monitor import QueueMonitor

            monitor = QueueMonitor(mock_broker)

            # Measure health assessment performance
            start_time = time.time()
            test_metrics = mock_broker.get_queue_stats("test_queue")
            thresholds = monitor.get_alert_thresholds("test_queue")
            for _ in range(20):
                health_score, status = monitor._calculate_health_score(test_metrics, thresholds)
                assert 0.0 <= health_score <= 1.0
                assert status in ["healthy", "warning", "critical"]
            end_time = time.time()

            # Calculate average latency per assessment
            avg_latency_ms = ((end_time - start_time) / 20) * 1000

            # Verify health assessment is fast: <20ms per operation
            assert avg_latency_ms < 20, f"Health assessment latency {avg_latency_ms:.2f}ms too high"


@pytest.mark.integration
class TestEndToEndPerformance:
    """End-to-end performance tests"""

    def test_complete_message_lifecycle_performance(self, broker):
        """Test complete message lifecycle performance"""
        message_payload = {"test": "lifecycle_data", "priority": "high"}

        # Test complete lifecycle: enqueue -> dequeue -> acknowledge
        start_time = time.time()

        # Enqueue phase
        message_id = broker.enqueue("lifecycle_test", message_payload, priority=5)
        assert message_id is not None

        # Dequeue phase
        result = broker.dequeue(["lifecycle_test"], timeout=1.0)
        assert result is not None
        queue_name, message = result

        # Acknowledge phase
        ack_success = broker.acknowledge(queue_name, message)
        assert ack_success is True

        end_time = time.time()

        # Verify complete lifecycle is fast: <150ms total
        total_latency_ms = (end_time - start_time) * 1000
        assert total_latency_ms < 150, f"Complete lifecycle latency {total_latency_ms:.2f}ms too high"

    def test_system_performance_under_realistic_load(self, broker):
        """Test system performance under realistic production-like load"""
        # Simulate realistic message patterns
        message_types = [
            {"type": "user_action", "payload": {"user_id": 123, "action": "click"}},
            {"type": "system_event", "payload": {"event": "backup_complete"}},
            {"type": "notification", "payload": {"recipient": "user@example.com"}},
        ]

        # Test sustained operations
        start_time = time.time()
        operations_completed = 0

        for i in range(60):  # Simulate 1 minute of operations
            for msg_template in message_types:
                message_payload = {**msg_template["payload"], "sequence_id": i}

                # Enqueue message
                message_id = broker.enqueue(f"{msg_template['type']}_queue", message_payload)
                if message_id:
                    operations_completed += 1

                # Periodically check queue stats (realistic monitoring)
                if i % 10 == 0:
                    stats = broker.get_queue_stats(f"{msg_template['type']}_queue")
                    assert stats is not None

        end_time = time.time()
        actual_duration = end_time - start_time

        # Calculate operations per minute
        operations_per_minute = (operations_completed / actual_duration) * 60

        # Verify system can handle realistic load: 150+ operations/minute
        assert (
            operations_per_minute >= 150
        ), f"System throughput {operations_per_minute:.1f} ops/min below realistic requirement"

        # Verify operations completed within reasonable time
        assert actual_duration < 2.0, f"Realistic load test took {actual_duration:.2f}s, too slow"
