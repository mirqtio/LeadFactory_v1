"""
Performance tests for Redis Lua promotion script
Tests performance targets of ≤50μs per call @ 1K RPS
"""

import asyncio
import json
import statistics
import time
from typing import List

import pytest
import redis.asyncio as aioredis

from core.config import get_settings
from lua_scripts.script_loader import ScriptLoader


@pytest.fixture
async def performance_redis_client():
    """Dedicated Redis client for performance testing"""
    settings = get_settings()
    client = await aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        encoding="utf-8",
        connection_pool_max_connections=20,  # Higher connection pool for performance
    )

    # Clean up performance test keys
    test_pattern = "perf:*"
    keys = await client.keys(test_pattern)
    if keys:
        await client.delete(*keys)

    yield client

    # Cleanup
    keys = await client.keys(test_pattern)
    if keys:
        await client.delete(*keys)
    await client.close()


@pytest.fixture
async def performance_script_loader(performance_redis_client):
    """Script loader optimized for performance testing"""
    loader = ScriptLoader(performance_redis_client)

    # Pre-load promotion script
    await loader.load_script("promote")

    # Verify script is cached in Redis to avoid NOSCRIPT
    assert await loader.script_exists("promote")

    return loader


@pytest.fixture
def performance_evidence():
    """Minimal valid evidence for performance testing"""
    return {
        "timestamp": "2025-07-21T10:00:00Z",
        "agent_id": "pm-perf",
        "transition_type": "pending_to_development",
        "requirements_analysis": "Performance test requirements",
        "acceptance_criteria": ["Performance target ≤50μs @ 1K RPS"],
    }


class TestSinglePromotionPerformance:
    """Test single promotion operation performance"""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_single_promotion_latency(
        self, performance_redis_client, performance_script_loader, performance_evidence
    ):
        """Test single promotion latency meets <50μs target"""
        prp_id = "PRP-PERF-SINGLE"
        metadata_key = f"perf:prp:{prp_id}:metadata"

        # Pre-setup to reduce measurement noise
        await performance_redis_client.lpush("perf:queue:pending", prp_id)
        await performance_redis_client.hset(metadata_key, "status", "pending")

        keys = ["perf:queue:pending", "perf:queue:development", metadata_key]
        args = ["promote", prp_id, json.dumps(performance_evidence), "pending_to_development", str(int(time.time()))]

        # Warm up Redis connection and script cache
        await performance_script_loader.execute_script("promote", keys, args)

        # Reset for actual measurement
        await performance_redis_client.lpush("perf:queue:pending", prp_id)

        # Measure execution time
        start_time = time.perf_counter_ns()
        result = await performance_script_loader.execute_script("promote", keys, args)
        end_time = time.perf_counter_ns()

        execution_time_us = (end_time - start_time) / 1000  # Convert to microseconds

        # Verify success
        assert result[0] == 1

        # Performance assertion
        assert execution_time_us <= 50.0, f"Execution time {execution_time_us:.2f}μs exceeds 50μs target"

        print(f"\nSingle promotion latency: {execution_time_us:.2f}μs")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_batch_promotion_performance(
        self, performance_redis_client, performance_script_loader, performance_evidence
    ):
        """Test batch promotion performance scaling"""
        batch_sizes = [1, 5, 10, 20, 50]

        for batch_size in batch_sizes:
            # Setup batch of PRPs
            prp_ids = [f"PRP-BATCH-{i}" for i in range(batch_size)]
            for prp_id in prp_ids:
                await performance_redis_client.lpush("perf:queue:pending", prp_id)

            batch_evidence = [performance_evidence] * batch_size

            keys = ["perf:queue:pending", "perf:queue:development"]
            args = [
                "batch_promote",
                "pending_to_development",
                str(int(time.time())),
                json.dumps(batch_evidence),
            ] + prp_ids

            # Measure batch promotion
            start_time = time.perf_counter_ns()
            result = await performance_script_loader.execute_script("promote", keys, args)
            end_time = time.perf_counter_ns()

            total_time_us = (end_time - start_time) / 1000
            per_prp_time_us = total_time_us / batch_size

            assert result[0] == batch_size  # All promoted successfully
            assert (
                per_prp_time_us <= 50.0
            ), f"Per-PRP time {per_prp_time_us:.2f}μs exceeds target for batch size {batch_size}"

            print(f"Batch size {batch_size}: {total_time_us:.2f}μs total, {per_prp_time_us:.2f}μs per PRP")


class TestThroughputPerformance:
    """Test throughput performance at scale"""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_sustained_throughput_1k_rps(
        self, performance_redis_client, performance_script_loader, performance_evidence
    ):
        """Test sustained 1K RPS performance target"""
        target_rps = 1000
        test_duration_seconds = 5
        total_operations = target_rps * test_duration_seconds

        # Pre-setup PRPs
        prp_ids = [f"PRP-RPS-{i}" for i in range(total_operations)]
        for prp_id in prp_ids:
            await performance_redis_client.lpush("perf:queue:pending", prp_id)

        evidence_json = json.dumps(performance_evidence)
        latencies = []

        async def single_promotion(prp_id: str) -> float:
            """Execute single promotion and return latency"""
            metadata_key = f"perf:prp:{prp_id}:metadata"

            keys = ["perf:queue:pending", "perf:queue:development", metadata_key]
            args = ["promote", prp_id, evidence_json, "pending_to_development", str(int(time.time()))]

            start_time = time.perf_counter_ns()
            result = await performance_script_loader.execute_script("promote", keys, args)
            end_time = time.perf_counter_ns()

            assert result[0] == 1  # Verify success

            return (end_time - start_time) / 1000  # Return microseconds

        # Execute sustained load test
        start_test = time.time()

        # Use semaphore to control concurrency for 1K RPS
        semaphore = asyncio.Semaphore(50)  # Limit concurrent operations

        async def rate_limited_promotion(prp_id: str):
            async with semaphore:
                return await single_promotion(prp_id)

        # Run all promotions
        tasks = [rate_limited_promotion(prp_id) for prp_id in prp_ids]
        latencies = await asyncio.gather(*tasks)

        end_test = time.time()
        actual_duration = end_test - start_test
        actual_rps = total_operations / actual_duration

        # Analyze latencies
        mean_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
        p99_latency = sorted(latencies)[int(0.99 * len(latencies))]
        max_latency = max(latencies)

        # Performance assertions
        assert actual_rps >= target_rps * 0.95, f"Achieved RPS {actual_rps:.0f} below target {target_rps}"
        assert mean_latency <= 50.0, f"Mean latency {mean_latency:.2f}μs exceeds 50μs target"
        assert p95_latency <= 100.0, f"P95 latency {p95_latency:.2f}μs too high"

        print(
            f"""
Throughput Test Results:
- Target RPS: {target_rps}
- Actual RPS: {actual_rps:.0f}
- Test Duration: {actual_duration:.2f}s
- Total Operations: {total_operations}
- Mean Latency: {mean_latency:.2f}μs
- P95 Latency: {p95_latency:.2f}μs  
- P99 Latency: {p99_latency:.2f}μs
- Max Latency: {max_latency:.2f}μs
        """
        )

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_promotion_scaling(
        self, performance_redis_client, performance_script_loader, performance_evidence
    ):
        """Test concurrent promotion scaling characteristics"""
        concurrency_levels = [1, 5, 10, 25, 50, 100]
        operations_per_level = 100

        for concurrency in concurrency_levels:
            # Setup PRPs for this concurrency level
            prp_ids = [f"PRP-CONC-{concurrency}-{i}" for i in range(operations_per_level)]
            for prp_id in prp_ids:
                await performance_redis_client.lpush("perf:queue:pending", prp_id)

            evidence_json = json.dumps(performance_evidence)

            async def concurrent_promotion(prp_id: str):
                metadata_key = f"perf:prp:{prp_id}:metadata"

                keys = ["perf:queue:pending", "perf:queue:development", metadata_key]
                args = ["promote", prp_id, evidence_json, "pending_to_development", str(int(time.time()))]

                start = time.perf_counter_ns()
                result = await performance_script_loader.execute_script("promote", keys, args)
                end = time.perf_counter_ns()

                return (end - start) / 1000, result[0]  # latency_us, success

            # Execute with limited concurrency
            semaphore = asyncio.Semaphore(concurrency)

            async def limited_promotion(prp_id: str):
                async with semaphore:
                    return await concurrent_promotion(prp_id)

            start_time = time.time()
            results = await asyncio.gather(*[limited_promotion(prp_id) for prp_id in prp_ids])
            end_time = time.time()

            # Analyze results
            latencies = [r[0] for r in results]
            successes = [r[1] for r in results]

            total_duration = end_time - start_time
            actual_rps = operations_per_level / total_duration
            mean_latency = statistics.mean(latencies)
            success_rate = sum(successes) / len(successes) * 100

            # Performance validation
            assert success_rate >= 99.0, f"Success rate {success_rate}% too low at concurrency {concurrency}"
            assert mean_latency <= 100.0, f"Mean latency {mean_latency:.2f}μs too high at concurrency {concurrency}"

            print(
                f"Concurrency {concurrency}: {actual_rps:.0f} RPS, {mean_latency:.2f}μs mean latency, {success_rate:.1f}% success"
            )


class TestStatusCheckPerformance:
    """Test performance of status and evidence operations"""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_status_check_performance(self, performance_redis_client, performance_script_loader):
        """Test PRP status check performance"""
        num_checks = 1000
        prp_ids = [f"PRP-STATUS-{i}" for i in range(num_checks)]

        # Setup PRP metadata
        for prp_id in prp_ids:
            metadata_key = f"perf:prp:{prp_id}:metadata"
            await performance_redis_client.hset(
                metadata_key,
                "status",
                "development",
                "last_transition",
                str(int(time.time())),
                "last_transition_type",
                "pending_to_development",
            )
            await performance_redis_client.lpush("perf:queue:development", prp_id)

        latencies = []

        async def check_status(prp_id: str):
            metadata_key = f"perf:prp:{prp_id}:metadata"

            start = time.perf_counter_ns()
            result = await performance_script_loader.execute_script("promote", [metadata_key], ["status", prp_id])
            end = time.perf_counter_ns()

            assert result[0] == "development"  # Verify result
            return (end - start) / 1000  # Return microseconds

        # Execute all status checks
        latencies = await asyncio.gather(*[check_status(prp_id) for prp_id in prp_ids])

        mean_latency = statistics.mean(latencies)
        max_latency = max(latencies)

        assert mean_latency <= 25.0, f"Status check mean latency {mean_latency:.2f}μs exceeds 25μs target"

        print(f"Status check performance: {mean_latency:.2f}μs mean, {max_latency:.2f}μs max")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_evidence_retrieval_performance(
        self, performance_redis_client, performance_script_loader, performance_evidence
    ):
        """Test evidence history retrieval performance"""
        prp_id = "PRP-EVIDENCE-PERF"
        num_evidence_entries = 50

        # Create evidence history
        base_timestamp = int(time.time())
        for i in range(num_evidence_entries):
            evidence_key = f"perf:evidence:{prp_id}:{base_timestamp + i}"
            await performance_redis_client.hset(
                evidence_key,
                "prp_id",
                prp_id,
                "transition_type",
                "pending_to_development",
                "evidence_data",
                json.dumps(performance_evidence),
                "created_at",
                str(base_timestamp + i),
            )

        # Test evidence retrieval performance
        start = time.perf_counter_ns()
        result = await performance_script_loader.execute_script("promote", [], ["evidence", prp_id, "10"])
        end = time.perf_counter_ns()

        latency_us = (end - start) / 1000

        assert len(result) == 10  # Verify limit works
        assert latency_us <= 100.0, f"Evidence retrieval latency {latency_us:.2f}μs too high"

        print(f"Evidence retrieval performance: {latency_us:.2f}μs for {len(result)} entries")


class TestMemoryEfficiency:
    """Test memory efficiency and resource usage"""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_script_memory_footprint(self, performance_redis_client, performance_script_loader):
        """Test script memory usage doesn't grow excessively"""
        # Get initial Redis memory usage
        initial_memory = await performance_redis_client.memory_usage("promote")

        # Execute many operations to test memory growth
        num_operations = 1000
        for i in range(num_operations):
            prp_id = f"PRP-MEM-{i}"
            await performance_redis_client.lpush("perf:queue:pending", prp_id)

        # Execute batch promotion
        batch_evidence = [
            {
                "timestamp": "2025-07-21T10:00:00Z",
                "agent_id": "pm-mem",
                "transition_type": "pending_to_development",
                "requirements_analysis": f"Memory test {i}",
                "acceptance_criteria": ["Memory efficiency"],
            }
            for i in range(num_operations)
        ]

        prp_ids = [f"PRP-MEM-{i}" for i in range(num_operations)]

        keys = ["perf:queue:pending", "perf:queue:development"]
        args = ["batch_promote", "pending_to_development", str(int(time.time())), json.dumps(batch_evidence)] + prp_ids

        result = await performance_script_loader.execute_script("promote", keys, args)

        assert result[0] == num_operations  # All successful

        # Memory usage should be reasonable
        info = await performance_redis_client.info("memory")
        used_memory_mb = info["used_memory"] / 1024 / 1024

        assert (
            used_memory_mb < 100
        ), f"Redis memory usage {used_memory_mb:.1f}MB too high after {num_operations} operations"

        print(f"Memory usage after {num_operations} operations: {used_memory_mb:.1f}MB")
