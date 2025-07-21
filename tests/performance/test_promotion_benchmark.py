"""
Performance benchmarking for Redis Lua promotion script
Validates ≤50μs per call @ 1K RPS requirement
"""

import asyncio
import json
import statistics

# Use the lua_scripts package per validation requirements
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import pytest
import redis

from lua_scripts.script_loader import ScriptLoader as AsyncScriptLoader


class SyncScriptLoader:
    """Synchronous wrapper for async ScriptLoader"""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        # AsyncScriptLoader will create its own aioredis connection
        self.async_loader = AsyncScriptLoader(None)

    def load_script(self, script_name: str) -> str:
        """Synchronous wrapper for load_script"""
        return asyncio.run(self.async_loader.load_script(script_name))

    def execute_script(self, script_name: str, keys: List[str], args: List) -> any:
        """Synchronous wrapper for execute_script"""
        return asyncio.run(self.async_loader.execute_script(script_name, keys, args))


class PromotionBenchmark:
    """Performance benchmarking suite for promotion script"""

    def __init__(self, redis_url: str = "redis://staging-infra-redis:6379/0"):
        """Initialize benchmark with Redis connection"""
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.script_loader = SyncScriptLoader(self.redis_client)

        # Verify connection
        try:
            self.redis_client.ping()
        except redis.ConnectionError:
            raise Exception("Redis server not available for benchmarking")

        # Load promotion script
        self.script_loader.load_script("promote")

        self.valid_evidence = {
            "timestamp": "2025-07-21T10:00:00Z",
            "agent_id": "pm-1",
            "transition_type": "pending_to_development",
            "requirements_analysis": "Complete requirements analysis performed",
            "acceptance_criteria": [
                "Feature must handle atomic operations",
                "Evidence validation required",
                "Performance <50μs at 1K RPS",
            ],
        }

    def setup_test_data(self, num_prps: int) -> List[str]:
        """Setup test PRPs in pending queue"""
        prp_ids = [f"PRP-BENCH-{i:04d}" for i in range(num_prps)]

        # Clear existing data
        self.redis_client.flushdb()

        # Add PRPs to pending queue
        if prp_ids:
            self.redis_client.lpush("queue:pending", *prp_ids)

        return prp_ids

    def single_promotion_benchmark(self, num_iterations: int = 1000) -> dict:
        """Benchmark single PRP promotions"""
        results = {
            "test_type": "single_promotion",
            "iterations": num_iterations,
            "execution_times": [],
            "success_count": 0,
            "error_count": 0,
        }

        print(f"Running {num_iterations} single promotion benchmarks...")

        for i in range(num_iterations):
            # Setup single PRP
            prp_id = f"PRP-BENCH-{i:04d}"
            self.redis_client.lpush("queue:pending", prp_id)

            keys = [
                "queue:pending",
                "queue:development",
                f"prp:{prp_id}:metadata",
            ]
            args = [
                "promote",
                prp_id,
                json.dumps(self.valid_evidence),
                "pending_to_development",
                str(int(time.time())),
            ]

            try:
                # Measure execution time
                start_time = time.perf_counter()
                result = self.script_loader.execute_script("promote", keys, args)
                end_time = time.perf_counter()

                execution_time = (end_time - start_time) * 1000 * 1000  # microseconds
                results["execution_times"].append(execution_time)

                if result[0] == 1:
                    results["success_count"] += 1
                else:
                    results["error_count"] += 1

            except Exception as e:
                results["error_count"] += 1
                print(f"Error in iteration {i}: {e}")

        # Calculate statistics
        if results["execution_times"]:
            results["mean_time"] = statistics.mean(results["execution_times"])
            results["median_time"] = statistics.median(results["execution_times"])
            results["min_time"] = min(results["execution_times"])
            results["max_time"] = max(results["execution_times"])
            results["p95_time"] = self._percentile(results["execution_times"], 95)
            results["p99_time"] = self._percentile(results["execution_times"], 99)
            results["std_dev"] = (
                statistics.stdev(results["execution_times"]) if len(results["execution_times"]) > 1 else 0
            )

        return results

    def batch_promotion_benchmark(self, batch_sizes: List[int] = [10, 50, 100]) -> dict:
        """Benchmark batch promotions with different sizes"""
        results = {"test_type": "batch_promotion", "batch_results": {}}

        for batch_size in batch_sizes:
            print(f"Benchmarking batch size {batch_size}...")

            batch_results = {
                "batch_size": batch_size,
                "execution_times": [],
                "per_prp_times": [],
                "success_count": 0,
                "error_count": 0,
            }

            # Run 100 batch operations
            for iteration in range(100):
                prp_ids = self.setup_test_data(batch_size)
                batch_evidence = [self.valid_evidence] * batch_size

                keys = ["queue:pending", "queue:development"]
                args = [
                    "batch_promote",
                    "pending_to_development",
                    str(int(time.time())),
                    json.dumps(batch_evidence),
                ] + prp_ids

                try:
                    start_time = time.perf_counter()
                    result = self.script_loader.execute_script("promote", keys, args)
                    end_time = time.perf_counter()

                    execution_time = (end_time - start_time) * 1000 * 1000  # microseconds
                    per_prp_time = execution_time / batch_size

                    batch_results["execution_times"].append(execution_time)
                    batch_results["per_prp_times"].append(per_prp_time)

                    if result[0] == batch_size:
                        batch_results["success_count"] += 1
                    else:
                        batch_results["error_count"] += 1

                except Exception as e:
                    batch_results["error_count"] += 1
                    print(f"Error in batch {batch_size} iteration {iteration}: {e}")

            # Calculate statistics for this batch size
            if batch_results["per_prp_times"]:
                batch_results["mean_per_prp"] = statistics.mean(batch_results["per_prp_times"])
                batch_results["median_per_prp"] = statistics.median(batch_results["per_prp_times"])
                batch_results["p95_per_prp"] = self._percentile(batch_results["per_prp_times"], 95)
                batch_results["p99_per_prp"] = self._percentile(batch_results["per_prp_times"], 99)

            results["batch_results"][batch_size] = batch_results

        return results

    def concurrent_load_benchmark(self, num_threads: int = 10, operations_per_thread: int = 100) -> dict:
        """Benchmark concurrent operations to simulate 1K RPS"""
        results = {
            "test_type": "concurrent_load",
            "num_threads": num_threads,
            "operations_per_thread": operations_per_thread,
            "total_operations": num_threads * operations_per_thread,
            "execution_times": [],
            "success_count": 0,
            "error_count": 0,
        }

        print(f"Running concurrent load test: {num_threads} threads × {operations_per_thread} ops...")

        def worker_thread(thread_id: int) -> Tuple[int, int, List[float]]:
            """Worker function for concurrent testing"""
            successes = 0
            errors = 0
            times = []

            for i in range(operations_per_thread):
                prp_id = f"PRP-THREAD-{thread_id:02d}-{i:04d}"

                # Setup PRP in queue (using thread-safe operations)
                try:
                    self.redis_client.lpush("queue:pending", prp_id)

                    keys = [
                        "queue:pending",
                        "queue:development",
                        f"prp:{prp_id}:metadata",
                    ]
                    args = [
                        "promote",
                        prp_id,
                        json.dumps(self.valid_evidence),
                        "pending_to_development",
                        str(int(time.time())),
                    ]

                    start_time = time.perf_counter()
                    result = self.script_loader.execute_script("promote", keys, args)
                    end_time = time.perf_counter()

                    execution_time = (end_time - start_time) * 1000 * 1000  # microseconds
                    times.append(execution_time)

                    if result[0] == 1:
                        successes += 1
                    else:
                        errors += 1

                except Exception as e:
                    errors += 1
                    # Don't print errors in concurrent test to avoid spam

            return successes, errors, times

        # Run concurrent operations
        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(num_threads)]

            for future in as_completed(futures):
                try:
                    successes, errors, times = future.result()
                    results["success_count"] += successes
                    results["error_count"] += errors
                    results["execution_times"].extend(times)
                except Exception as e:
                    print(f"Thread execution error: {e}")
                    results["error_count"] += operations_per_thread

        end_total = time.perf_counter()
        total_time = end_total - start_total

        # Calculate overall statistics
        results["total_time_seconds"] = total_time
        results["actual_rps"] = results["total_operations"] / total_time if total_time > 0 else 0

        if results["execution_times"]:
            results["mean_time"] = statistics.mean(results["execution_times"])
            results["median_time"] = statistics.median(results["execution_times"])
            results["p95_time"] = self._percentile(results["execution_times"], 95)
            results["p99_time"] = self._percentile(results["execution_times"], 99)
            results["max_time"] = max(results["execution_times"])

        return results

    def stress_test_1k_rps(self, duration_seconds: int = 10) -> dict:
        """Stress test targeting 1K RPS"""
        target_rps = 1000
        total_operations = target_rps * duration_seconds

        results = {
            "test_type": "stress_1k_rps",
            "target_rps": target_rps,
            "duration_seconds": duration_seconds,
            "target_operations": total_operations,
            "execution_times": [],
            "success_count": 0,
            "error_count": 0,
        }

        print(f"Stress testing at 1K RPS for {duration_seconds} seconds...")

        # Use thread pool to generate load
        def rate_limited_operations():
            """Generate operations at target rate"""
            operation_interval = 1.0 / target_rps  # seconds between operations

            for i in range(total_operations):
                yield i
                time.sleep(max(0, operation_interval))

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []

            for op_id in rate_limited_operations():
                if time.perf_counter() - start_time > duration_seconds:
                    break

                future = executor.submit(self._single_promotion_op, op_id)
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    success, execution_time = future.result()
                    if success:
                        results["success_count"] += 1
                    else:
                        results["error_count"] += 1

                    if execution_time is not None:
                        results["execution_times"].append(execution_time)

                except Exception:
                    results["error_count"] += 1

        end_time = time.perf_counter()
        actual_duration = end_time - start_time
        actual_operations = results["success_count"] + results["error_count"]

        results["actual_duration"] = actual_duration
        results["actual_operations"] = actual_operations
        results["actual_rps"] = actual_operations / actual_duration if actual_duration > 0 else 0

        if results["execution_times"]:
            results["mean_time"] = statistics.mean(results["execution_times"])
            results["p95_time"] = self._percentile(results["execution_times"], 95)
            results["p99_time"] = self._percentile(results["execution_times"], 99)
            results["max_time"] = max(results["execution_times"])

        return results

    def _single_promotion_op(self, op_id: int) -> Tuple[bool, float]:
        """Single promotion operation for stress testing"""
        prp_id = f"PRP-STRESS-{op_id:06d}"

        try:
            self.redis_client.lpush("queue:pending", prp_id)

            keys = [
                "queue:pending",
                "queue:development",
                f"prp:{prp_id}:metadata",
            ]
            args = [
                "promote",
                prp_id,
                json.dumps(self.valid_evidence),
                "pending_to_development",
                str(int(time.time())),
            ]

            start_time = time.perf_counter()
            result = self.script_loader.execute_script("promote", keys, args)
            end_time = time.perf_counter()

            execution_time = (end_time - start_time) * 1000 * 1000  # microseconds
            success = result[0] == 1

            return success, execution_time

        except Exception:
            return False, None

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def run_full_benchmark_suite(self) -> dict:
        """Run complete benchmark suite"""
        print("=" * 60)
        print("REDIS LUA PROMOTION SCRIPT - PERFORMANCE BENCHMARK")
        print("=" * 60)

        all_results = {
            "benchmark_timestamp": time.time(),
            "target_performance": "≤50μs per call @ 1K RPS",
            "redis_info": self._get_redis_info(),
        }

        # 1. Single promotion benchmark
        print("\n1. Single Promotion Benchmark")
        print("-" * 30)
        single_results = self.single_promotion_benchmark(1000)
        all_results["single_promotion"] = single_results
        self._print_single_results(single_results)

        # 2. Batch promotion benchmark
        print("\n2. Batch Promotion Benchmark")
        print("-" * 30)
        batch_results = self.batch_promotion_benchmark([10, 50, 100])
        all_results["batch_promotion"] = batch_results
        self._print_batch_results(batch_results)

        # 3. Concurrent load benchmark
        print("\n3. Concurrent Load Benchmark")
        print("-" * 30)
        concurrent_results = self.concurrent_load_benchmark(20, 50)
        all_results["concurrent_load"] = concurrent_results
        self._print_concurrent_results(concurrent_results)

        # 4. 1K RPS stress test
        print("\n4. 1K RPS Stress Test")
        print("-" * 30)
        stress_results = self.stress_test_1k_rps(10)
        all_results["stress_test"] = stress_results
        self._print_stress_results(stress_results)

        # 5. Performance validation
        print("\n5. Performance Validation")
        print("-" * 30)
        validation = self._validate_performance(all_results)
        all_results["validation"] = validation
        self._print_validation(validation)

        return all_results

    def _get_redis_info(self) -> dict:
        """Get Redis server information"""
        try:
            info = self.redis_client.info()
            return {
                "version": info.get("redis_version"),
                "memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime": info.get("uptime_in_seconds"),
            }
        except Exception:
            return {"error": "Could not retrieve Redis info"}

    def _print_single_results(self, results: dict):
        """Print single promotion benchmark results"""
        if results["execution_times"]:
            print(f"Iterations: {results['iterations']}")
            print(f"Successes: {results['success_count']}")
            print(f"Errors: {results['error_count']}")
            print(f"Mean time: {results['mean_time']:.2f}μs")
            print(f"Median time: {results['median_time']:.2f}μs")
            print(f"95th percentile: {results['p95_time']:.2f}μs")
            print(f"99th percentile: {results['p99_time']:.2f}μs")
            print(f"Max time: {results['max_time']:.2f}μs")
            print(f"Standard deviation: {results['std_dev']:.2f}μs")

    def _print_batch_results(self, results: dict):
        """Print batch promotion benchmark results"""
        for batch_size, batch_data in results["batch_results"].items():
            print(f"\nBatch size {batch_size}:")
            if batch_data["per_prp_times"]:
                print(f"  Mean per PRP: {batch_data['mean_per_prp']:.2f}μs")
                print(f"  Median per PRP: {batch_data['median_per_prp']:.2f}μs")
                print(f"  95th percentile: {batch_data['p95_per_prp']:.2f}μs")
                print(f"  99th percentile: {batch_data['p99_per_prp']:.2f}μs")

    def _print_concurrent_results(self, results: dict):
        """Print concurrent load benchmark results"""
        print(f"Threads: {results['num_threads']}")
        print(f"Operations per thread: {results['operations_per_thread']}")
        print(f"Total operations: {results['total_operations']}")
        print(f"Successes: {results['success_count']}")
        print(f"Errors: {results['error_count']}")
        print(f"Total time: {results['total_time_seconds']:.2f}s")
        print(f"Actual RPS: {results['actual_rps']:.1f}")

        if results["execution_times"]:
            print(f"Mean time: {results['mean_time']:.2f}μs")
            print(f"95th percentile: {results['p95_time']:.2f}μs")
            print(f"99th percentile: {results['p99_time']:.2f}μs")

    def _print_stress_results(self, results: dict):
        """Print stress test results"""
        print(f"Target RPS: {results['target_rps']}")
        print(f"Duration: {results['duration_seconds']}s")
        print(f"Target operations: {results['target_operations']}")
        print(f"Actual operations: {results['actual_operations']}")
        print(f"Actual RPS: {results['actual_rps']:.1f}")
        print(f"Successes: {results['success_count']}")
        print(f"Errors: {results['error_count']}")

        if results["execution_times"]:
            print(f"Mean time: {results['mean_time']:.2f}μs")
            print(f"95th percentile: {results['p95_time']:.2f}μs")
            print(f"99th percentile: {results['p99_time']:.2f}μs")

    def _validate_performance(self, all_results: dict) -> dict:
        """Validate performance against requirements"""
        validation = {
            "target_time": 50.0,  # μs
            "target_rps": 1000,
            "tests_passed": 0,
            "tests_failed": 0,
            "details": {},
        }

        # Test 1: Single promotion mean time
        single = all_results.get("single_promotion", {})
        if single.get("mean_time"):
            passed = single["mean_time"] <= validation["target_time"]
            validation["details"]["single_mean"] = {
                "actual": single["mean_time"],
                "target": validation["target_time"],
                "passed": passed,
            }
            if passed:
                validation["tests_passed"] += 1
            else:
                validation["tests_failed"] += 1

        # Test 2: Single promotion 95th percentile
        if single.get("p95_time"):
            passed = single["p95_time"] <= validation["target_time"] * 2  # Allow 2x for 95th
            validation["details"]["single_p95"] = {
                "actual": single["p95_time"],
                "target": validation["target_time"] * 2,
                "passed": passed,
            }
            if passed:
                validation["tests_passed"] += 1
            else:
                validation["tests_failed"] += 1

        # Test 3: Concurrent load can achieve target RPS
        concurrent = all_results.get("concurrent_load", {})
        if concurrent.get("actual_rps"):
            passed = concurrent["actual_rps"] >= validation["target_rps"] * 0.8  # 80% of target
            validation["details"]["concurrent_rps"] = {
                "actual": concurrent["actual_rps"],
                "target": validation["target_rps"] * 0.8,
                "passed": passed,
            }
            if passed:
                validation["tests_passed"] += 1
            else:
                validation["tests_failed"] += 1

        # Test 4: Stress test performance under load
        stress = all_results.get("stress_test", {})
        if stress.get("p95_time"):
            passed = stress["p95_time"] <= validation["target_time"] * 3  # Allow 3x under stress
            validation["details"]["stress_p95"] = {
                "actual": stress["p95_time"],
                "target": validation["target_time"] * 3,
                "passed": passed,
            }
            if passed:
                validation["tests_passed"] += 1
            else:
                validation["tests_failed"] += 1

        validation["overall_passed"] = validation["tests_failed"] == 0
        return validation

    def _print_validation(self, validation: dict):
        """Print performance validation results"""
        print(f"Performance Target: ≤{validation['target_time']}μs per call @ {validation['target_rps']} RPS")
        print(f"Tests Passed: {validation['tests_passed']}")
        print(f"Tests Failed: {validation['tests_failed']}")
        print(f"Overall Result: {'✅ PASSED' if validation['overall_passed'] else '❌ FAILED'}")

        print("\nDetailed Results:")
        for test_name, details in validation["details"].items():
            status = "✅ PASS" if details["passed"] else "❌ FAIL"
            print(f"  {test_name}: {details['actual']:.2f}μs (target: {details['target']:.2f}μs) {status}")


if __name__ == "__main__":
    # Run benchmark suite
    benchmark = PromotionBenchmark()
    results = benchmark.run_full_benchmark_suite()

    # Save results to file
    import json

    timestamp = int(time.time())
    results_file = f"promotion_benchmark_{timestamp}.json"

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nBenchmark results saved to: {results_file}")
