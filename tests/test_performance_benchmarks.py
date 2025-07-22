#!/usr/bin/env python3
"""
Performance benchmark tests for multi-agent system
Note: These are NOT load tests - they measure performance of existing volume
"""
import json
import os
import statistics
import time
from datetime import datetime
from typing import Dict, List, Tuple

import pytest
import redis


class PerformanceBenchmark:
    """Base class for performance benchmarks"""

    def __init__(self, name: str):
        self.name = name
        self.measurements: List[float] = []
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

    def measure(self, operation):
        """Measure execution time of an operation"""
        start = time.perf_counter()
        result = operation()
        end = time.perf_counter()
        elapsed = (end - start) * 1000  # Convert to milliseconds
        self.measurements.append(elapsed)
        return result

    def get_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        if not self.measurements:
            return {}

        return {
            "min_ms": min(self.measurements),
            "max_ms": max(self.measurements),
            "mean_ms": statistics.mean(self.measurements),
            "median_ms": statistics.median(self.measurements),
            "stdev_ms": statistics.stdev(self.measurements) if len(self.measurements) > 1 else 0,
            "p95_ms": sorted(self.measurements)[int(len(self.measurements) * 0.95)] if self.measurements else 0,
            "p99_ms": sorted(self.measurements)[int(len(self.measurements) * 0.99)] if self.measurements else 0,
        }

    def report(self):
        """Print performance report"""
        stats = self.get_stats()
        print(f"\n=== {self.name} Performance ===")
        print(f"Samples: {len(self.measurements)}")
        for key, value in stats.items():
            print(f"{key}: {value:.2f}")


class TestQueueOperationPerformance:
    """Benchmark queue operation performance"""

    def setup_method(self):
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        self.cleanup_test_data()

    def teardown_method(self):
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Clean up test data"""
        for key in self.redis_client.keys("PERF-*"):
            self.redis_client.delete(key)
        self.redis_client.delete("perf_test_queue")
        self.redis_client.delete("perf_test_queue:inflight")

    def test_queue_push_performance(self):
        """Benchmark LPUSH operations"""
        bench = PerformanceBenchmark("Queue LPUSH")

        # Test single PRP pushes (typical operation)
        for i in range(100):
            prp_id = f"PERF-PUSH-{i}"
            bench.measure(lambda: self.redis_client.lpush("perf_test_queue", prp_id))

        stats = bench.get_stats()
        bench.report()

        # Performance assertions for current volume
        assert stats["median_ms"] < 10, "LPUSH should complete in <10ms median"
        assert stats["p99_ms"] < 50, "LPUSH should complete in <50ms for 99th percentile"

    def test_queue_pop_performance(self):
        """Benchmark BRPOPLPUSH operations"""
        bench = PerformanceBenchmark("Queue BRPOPLPUSH")

        # Pre-populate queue
        for i in range(100):
            self.redis_client.lpush("perf_test_queue", f"PERF-POP-{i}")

        # Test atomic move operations
        for i in range(100):
            result = bench.measure(
                lambda: self.redis_client.brpoplpush("perf_test_queue", "perf_test_queue:inflight", timeout=1)
            )
            assert result is not None, "Should pop item"

        stats = bench.get_stats()
        bench.report()

        # Performance assertions
        assert stats["median_ms"] < 10, "BRPOPLPUSH should complete in <10ms median"
        assert stats["p99_ms"] < 50, "BRPOPLPUSH should complete in <50ms for 99th percentile"

    def test_queue_scan_performance(self):
        """Benchmark queue scanning operations"""
        bench = PerformanceBenchmark("Queue LRANGE Scan")

        # Pre-populate with typical queue size (10-50 PRPs)
        for i in range(30):
            self.redis_client.lpush("perf_test_queue", f"PERF-SCAN-{i}")

        # Test scanning operations
        for _ in range(50):
            items = bench.measure(lambda: self.redis_client.lrange("perf_test_queue", 0, -1))
            assert len(items) == 30, "Should get all items"

        stats = bench.get_stats()
        bench.report()

        # Performance assertions
        assert stats["median_ms"] < 5, "LRANGE should complete in <5ms median"
        assert stats["p99_ms"] < 20, "LRANGE should complete in <20ms for 99th percentile"


class TestEvidenceOperationPerformance:
    """Benchmark evidence collection performance"""

    def setup_method(self):
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        self.cleanup_test_data()

    def teardown_method(self):
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Clean up test data"""
        for key in self.redis_client.keys("prp:PERF-*"):
            self.redis_client.delete(key)

    def test_evidence_write_performance(self):
        """Benchmark evidence writing operations"""
        bench = PerformanceBenchmark("Evidence HSET")

        # Test typical evidence updates
        for i in range(100):
            prp_key = f"prp:PERF-EVIDENCE-{i}"
            evidence = {
                "tests_passed": "true",
                "coverage_pct": "85",
                "lint_passed": "true",
                "security_scan": "clean",
                "timestamp": datetime.utcnow().isoformat(),
            }

            bench.measure(lambda: self.redis_client.hset(prp_key, mapping=evidence))

        stats = bench.get_stats()
        bench.report()

        # Performance assertions
        assert stats["median_ms"] < 10, "HSET should complete in <10ms median"
        assert stats["p99_ms"] < 50, "HSET should complete in <50ms for 99th percentile"

    def test_evidence_read_performance(self):
        """Benchmark evidence reading operations"""
        bench = PerformanceBenchmark("Evidence HGETALL")

        # Pre-populate evidence
        for i in range(100):
            prp_key = f"prp:PERF-READ-{i}"
            self.redis_client.hset(
                prp_key,
                mapping={
                    "tests_passed": "true",
                    "coverage_pct": "85",
                    "lint_passed": "true",
                    "security_scan": "clean",
                    "retry_count": "0",
                    "status": "validation",
                    "assigned_to": "validator",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        # Test evidence retrieval
        for i in range(100):
            prp_key = f"prp:PERF-READ-{i}"
            data = bench.measure(lambda: self.redis_client.hgetall(prp_key))
            assert len(data) == 8, "Should get all fields"

        stats = bench.get_stats()
        bench.report()

        # Performance assertions
        assert stats["median_ms"] < 5, "HGETALL should complete in <5ms median"
        assert stats["p99_ms"] < 20, "HGETALL should complete in <20ms for 99th percentile"


class TestLuaScriptPerformance:
    """Benchmark Lua script performance"""

    def setup_method(self):
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        self.cleanup_test_data()

        # Load promotion script
        with open("scripts/promote.lua", "r") as f:
            self.promote_script = self.redis_client.register_script(f.read())

    def teardown_method(self):
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Clean up test data"""
        for key in self.redis_client.keys("prp:PERF-*"):
            self.redis_client.delete(key)
        self.redis_client.delete("perf_validation_queue")
        self.redis_client.delete("perf_integration_queue")

    def test_promotion_script_performance(self):
        """Benchmark atomic promotion operations"""
        bench = PerformanceBenchmark("Lua Promotion Script")

        # Test promotions
        for i in range(50):
            prp_id = f"PERF-PROMOTE-{i}"
            prp_key = f"prp:{prp_id}"

            # Set up PRP with evidence
            self.redis_client.hset(
                prp_key, mapping={"tests_passed": "true", "coverage_pct": "85", "lint_passed": "true"}
            )
            self.redis_client.lpush("perf_validation_queue", prp_id)

            # Measure promotion
            result = bench.measure(
                lambda: self.promote_script(keys=[prp_id, "perf_validation_queue", "perf_integration_queue"])
            )

            assert result in [b"PROMOTED", "PROMOTED"], "Should promote successfully"

        stats = bench.get_stats()
        bench.report()

        # Performance assertions for Lua scripts
        assert stats["median_ms"] < 15, "Lua script should complete in <15ms median"
        assert stats["p99_ms"] < 50, "Lua script should complete in <50ms for 99th percentile"


class TestAgentCoordinationPerformance:
    """Benchmark agent coordination operations"""

    def setup_method(self):
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        self.cleanup_test_data()

    def teardown_method(self):
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Clean up test data"""
        for key in self.redis_client.keys("agent:perf-*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("orchestrator:*"):
            self.redis_client.delete(key)

    def test_heartbeat_update_performance(self):
        """Benchmark heartbeat update operations"""
        bench = PerformanceBenchmark("Agent Heartbeat Update")

        # Set up agents
        agents = [f"perf-agent-{i}" for i in range(5)]
        for agent in agents:
            self.redis_client.hset(
                f"agent:{agent}", mapping={"status": "active", "last_activity": datetime.utcnow().isoformat()}
            )

        # Test heartbeat updates
        for _ in range(100):
            agent = agents[_ % len(agents)]
            bench.measure(
                lambda: self.redis_client.hset(f"agent:{agent}", "last_activity", datetime.utcnow().isoformat())
            )

        stats = bench.get_stats()
        bench.report()

        # Performance assertions
        assert stats["median_ms"] < 5, "Heartbeat update should complete in <5ms median"
        assert stats["p99_ms"] < 20, "Heartbeat update should complete in <20ms for 99th percentile"

    def test_agent_status_check_performance(self):
        """Benchmark agent status checking"""
        bench = PerformanceBenchmark("Agent Status Check")

        # Set up agents with various states
        for i in range(10):
            self.redis_client.hset(
                f"agent:perf-check-{i}",
                mapping={
                    "status": "active" if i % 2 == 0 else "agent_down",
                    "last_activity": datetime.utcnow().isoformat(),
                    "current_prp": f"PERF-CHECK-{i}" if i % 3 == 0 else "",
                },
            )

        # Test status checks
        for _ in range(100):

            def check_all_agents():
                statuses = []
                for i in range(10):
                    data = self.redis_client.hgetall(f"agent:perf-check-{i}")
                    statuses.append(data.get(b"status", b"unknown"))
                return statuses

            statuses = bench.measure(check_all_agents)
            assert len(statuses) == 10, "Should check all agents"

        stats = bench.get_stats()
        bench.report()

        # Performance assertions for batch operations
        assert stats["median_ms"] < 20, "Batch status check should complete in <20ms median"
        assert stats["p99_ms"] < 50, "Batch status check should complete in <50ms for 99th percentile"


class TestSystemMetrics:
    """Test system-wide performance metrics"""

    def test_end_to_end_prp_latency(self):
        """Measure end-to-end PRP processing latency"""
        redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        bench = PerformanceBenchmark("End-to-End PRP Latency")

        # Simulate complete PRP lifecycle
        for i in range(20):
            prp_id = f"PERF-E2E-{i}"
            prp_key = f"prp:{prp_id}"

            def process_prp():
                # 1. Add to dev queue
                redis_client.lpush("dev_queue", prp_id)

                # 2. Dev picks up
                redis_client.brpoplpush("dev_queue", "dev_queue:inflight", timeout=1)

                # 3. Dev completes with evidence
                redis_client.hset(
                    prp_key,
                    mapping={"tests_passed": "true", "coverage_pct": "85", "timestamp": datetime.utcnow().isoformat()},
                )
                redis_client.lrem("dev_queue:inflight", 0, prp_id)

                # 4. Add to validation queue
                redis_client.lpush("validation_queue", prp_id)

                # 5. Validator picks up
                redis_client.brpoplpush("validation_queue", "validation_queue:inflight", timeout=1)

                # 6. Validator completes
                redis_client.hset(prp_key, "validation_passed", "true")
                redis_client.lrem("validation_queue:inflight", 0, prp_id)

                # 7. Add to integration queue
                redis_client.lpush("integration_queue", prp_id)

                # 8. Integration completes
                redis_client.brpoplpush("integration_queue", "integration_queue:inflight", timeout=1)
                redis_client.hset(prp_key, "status", "complete")
                redis_client.lrem("integration_queue:inflight", 0, prp_id)

            bench.measure(process_prp)

            # Clean up
            redis_client.delete(prp_key)

        stats = bench.get_stats()
        bench.report()

        # End-to-end performance targets
        assert stats["median_ms"] < 100, "E2E processing should complete in <100ms median"
        assert stats["p99_ms"] < 500, "E2E processing should complete in <500ms for 99th percentile"

    def test_concurrent_agent_performance(self):
        """Test performance with concurrent agent operations"""
        redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        bench = PerformanceBenchmark("Concurrent Agent Operations")

        from threading import Thread

        def agent_operation(agent_id: str, prp_id: str):
            """Simulate agent doing work"""
            # Update status
            redis_client.hset(
                f"agent:{agent_id}",
                mapping={"status": "working", "current_prp": prp_id, "last_activity": datetime.utcnow().isoformat()},
            )

            # Write evidence
            redis_client.hset(f"prp:{prp_id}", mapping={"assigned_to": agent_id, "progress": "50%"})

            # Complete work
            redis_client.hset(f"agent:{agent_id}", "status", "idle")
            redis_client.hdel(f"agent:{agent_id}", "current_prp")

        # Test concurrent operations
        for batch in range(10):

            def run_concurrent_batch():
                threads = []
                for i in range(5):  # 5 concurrent agents
                    agent_id = f"perf-concurrent-{i}"
                    prp_id = f"PERF-CONCURRENT-{batch}-{i}"
                    t = Thread(target=agent_operation, args=(agent_id, prp_id))
                    threads.append(t)
                    t.start()

                for t in threads:
                    t.join()

            bench.measure(run_concurrent_batch)

        stats = bench.get_stats()
        bench.report()

        # Concurrent operation targets
        assert stats["median_ms"] < 50, "Concurrent ops should complete in <50ms median"
        assert stats["p99_ms"] < 200, "Concurrent ops should complete in <200ms for 99th percentile"


def main():
    """Run all performance benchmarks"""
    print("=== Running Performance Benchmarks ===")
    print("Note: These test performance at current volume, NOT load capacity")

    # Queue operations
    queue_test = TestQueueOperationPerformance()
    queue_test.setup_method()
    queue_test.test_queue_push_performance()
    queue_test.test_queue_pop_performance()
    queue_test.test_queue_scan_performance()
    queue_test.teardown_method()

    # Evidence operations
    evidence_test = TestEvidenceOperationPerformance()
    evidence_test.setup_method()
    evidence_test.test_evidence_write_performance()
    evidence_test.test_evidence_read_performance()
    evidence_test.teardown_method()

    # Lua scripts
    lua_test = TestLuaScriptPerformance()
    lua_test.setup_method()
    lua_test.test_promotion_script_performance()
    lua_test.teardown_method()

    # Agent coordination
    agent_test = TestAgentCoordinationPerformance()
    agent_test.setup_method()
    agent_test.test_heartbeat_update_performance()
    agent_test.test_agent_status_check_performance()
    agent_test.teardown_method()

    # System metrics
    system_test = TestSystemMetrics()
    system_test.test_end_to_end_prp_latency()
    system_test.test_concurrent_agent_performance()

    print("\n✅ All performance benchmarks completed")


if __name__ == "__main__":
    main()
