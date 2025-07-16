#!/usr/bin/env python3
"""
Test Parallelization Configuration

This module determines optimal worker count for pytest-xdist based on:
- CPU cores available
- Test types (unit tests can be highly parallel, integration tests less so)
- Memory constraints
"""

import multiprocessing
import os
import sys
from pathlib import Path


def get_system_info():
    """Get system information for test parallelization."""
    cpu_count = multiprocessing.cpu_count()
    # Get available memory in GB (rough estimate)
    try:
        import psutil

        mem_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        # Fallback if psutil not available
        mem_gb = 16  # Assume reasonable default

    return {
        "cpu_count": cpu_count,
        "memory_gb": mem_gb,
        "is_ci": os.environ.get("CI", "").lower() == "true",
        "is_docker": os.path.exists("/.dockerenv"),
    }


def calculate_workers(test_type="auto", system_info=None):
    """
    Calculate optimal number of workers for different test types.

    Args:
        test_type: Type of tests being run ('unit', 'integration', 'e2e', 'auto')
        system_info: Optional system info dict, will be auto-detected if None

    Returns:
        Number of workers to use
    """
    if system_info is None:
        system_info = get_system_info()

    cpu_count = system_info["cpu_count"]
    memory_gb = system_info["memory_gb"]
    is_ci = system_info["is_ci"]
    is_docker = system_info["is_docker"]

    # CI environment constraints
    if is_ci:
        # GitHub Actions typically has 2 CPUs and 7GB RAM
        cpu_count = min(cpu_count, 2)
        memory_gb = min(memory_gb, 7)

    # Docker environment constraints
    if is_docker:
        # Be conservative in Docker to avoid resource exhaustion
        cpu_count = min(cpu_count, 4)

    # Calculate workers based on test type
    if test_type == "unit":
        # Unit tests: can use most CPUs, lightweight
        workers = min(cpu_count, int(memory_gb / 0.5))  # 0.5GB per worker
    elif test_type == "integration":
        # Integration tests: need database/service isolation
        workers = min(max(2, cpu_count // 2), 4)  # Max 4 workers
    elif test_type == "e2e":
        # E2E tests: should run serially
        workers = 1
    else:  # 'auto' or unknown
        # Default: conservative approach
        workers = min(cpu_count, max(2, int(memory_gb / 1.0)))  # 1GB per worker

    # Never use more workers than CPUs
    workers = min(workers, cpu_count)

    # Ensure at least 1 worker
    workers = max(1, workers)

    return workers


def get_pytest_args(test_type="auto", additional_args=None):
    """
    Get pytest arguments optimized for parallel execution.

    Args:
        test_type: Type of tests being run
        additional_args: Additional pytest arguments

    Returns:
        List of pytest arguments
    """
    workers = calculate_workers(test_type)

    args = []

    if workers > 1:
        args.extend(["-n", str(workers)])

        # Use worksteal for better load balancing
        args.extend(["--dist", "worksteal"])

        # Increase timeout for parallel tests
        args.extend(["--timeout", "300"])

    # Add test type specific args
    if test_type == "unit":
        args.extend(["-m", "unit"])
    elif test_type == "integration":
        args.extend(["-m", "integration"])
        # For integration tests, ensure proper DB isolation
        args.extend(["--tb=short"])
    elif test_type == "e2e":
        args.extend(["-m", "e2e"])
        # E2E tests need more verbose output
        args.extend(["-v", "--tb=short"])

    # Add any additional args
    if additional_args:
        args.extend(additional_args)

    return args


def print_config(test_type="auto"):
    """Print the parallelization configuration."""
    system_info = get_system_info()
    workers = calculate_workers(test_type, system_info)

    print(f"Test Parallelization Configuration")
    print(f"==================================")
    print(f"System Info:")
    print(f"  CPUs: {system_info['cpu_count']}")
    print(f"  Memory: {system_info['memory_gb']:.1f} GB")
    print(f"  CI Environment: {system_info['is_ci']}")
    print(f"  Docker Environment: {system_info['is_docker']}")
    print(f"")
    print(f"Test Type: {test_type}")
    print(f"Workers: {workers}")
    print(f"")
    print(f"Pytest Command:")
    args = get_pytest_args(test_type)
    print(f"  pytest {' '.join(args)}")


def main():
    """Main entry point for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Test parallelization configuration")
    parser.add_argument(
        "--type", choices=["unit", "integration", "e2e", "auto"], default="auto", help="Type of tests to configure for"
    )
    parser.add_argument("--print-args", action="store_true", help="Print only the pytest arguments")
    parser.add_argument("--print-workers", action="store_true", help="Print only the number of workers")

    args = parser.parse_args()

    if args.print_workers:
        print(calculate_workers(args.type))
    elif args.print_args:
        print(" ".join(get_pytest_args(args.type)))
    else:
        print_config(args.type)


if __name__ == "__main__":
    main()
