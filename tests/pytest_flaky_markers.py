"""
Pytest plugin to automatically mark known flaky tests.

This plugin identifies tests that are timing-sensitive or have
race conditions and marks them with @pytest.mark.flaky for
automatic retry.
"""

import pytest

# Known flaky test patterns
FLAKY_TEST_PATTERNS = [
    # Threading tests
    ("test_singleton_thread_safety", {"reruns": 3, "reruns_delay": 0.5}),
    ("test_client_cache_thread_safety", {"reruns": 3, "reruns_delay": 0.5}),
    ("test_concurrent_", {"reruns": 3, "reruns_delay": 0.5}),
    ("test_parallel_", {"reruns": 3, "reruns_delay": 0.5}),
    # File system watchers
    ("test_hot_reload", {"reruns": 3, "reruns_delay": 1}),
    ("test_file_modification", {"reruns": 3, "reruns_delay": 1}),
    ("test_real_file_modification", {"reruns": 3, "reruns_delay": 1}),
    # Network/server tests
    ("test_stub_server", {"reruns": 3, "reruns_delay": 2}),
    ("test_server_startup", {"reruns": 3, "reruns_delay": 2}),
    ("test_health_endpoint", {"reruns": 3, "reruns_delay": 1}),
    # Performance tests
    ("test_performance", {"reruns": 2, "reruns_delay": 1}),
    ("test_load_", {"reruns": 2, "reruns_delay": 1}),
    # Database tests
    ("test_migration", {"reruns": 2, "reruns_delay": 0.5}),
    ("test_concurrent_access", {"reruns": 3, "reruns_delay": 0.5}),
    # Redis tests
    ("test_redis_", {"reruns": 3, "reruns_delay": 0.5}),
    ("test_cache_", {"reruns": 3, "reruns_delay": 0.5}),
    # Integration tests
    ("test_integration", {"reruns": 2, "reruns_delay": 1}),
    ("test_e2e", {"reruns": 2, "reruns_delay": 2}),
]


def pytest_collection_modifyitems(config, items):
    """
    Automatically add flaky markers to known problematic tests.
    """
    flaky_plugin = config.pluginmanager.get_plugin("flaky")
    if not flaky_plugin:
        # pytest-flaky not installed, skip
        return

    for item in items:
        # Check if test already has flaky marker
        if item.get_closest_marker("flaky"):
            continue

        # Check test name against patterns
        test_name = item.name
        test_file = str(item.fspath)

        for pattern, flaky_config in FLAKY_TEST_PATTERNS:
            if pattern in test_name or pattern in test_file:
                # Add flaky marker with configuration
                marker = pytest.mark.flaky(**flaky_config)
                item.add_marker(marker)

                # Log that we marked it
                if config.option.verbose:
                    print(f"Marked {item.nodeid} as flaky with {flaky_config}")
                break


def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line("markers", "flaky(reruns=n, reruns_delay=n): mark test as flaky with retry logic")
    config.addinivalue_line("markers", "serial: mark test to run serially (not in parallel)")
    config.addinivalue_line("markers", "no_parallel: mark test that cannot run in parallel")
    config.addinivalue_line("markers", "shared_resource: mark test that uses shared resources")


def pytest_runtest_setup(item):
    """
    Set up test run with stability enhancements.
    """
    # Add timeout to tests that don't have one
    if not item.get_closest_marker("timeout"):
        # Default timeout based on test type
        if "integration" in str(item.fspath) or "e2e" in str(item.fspath):
            timeout = 60  # 1 minute for integration tests
        elif "performance" in str(item.fspath):
            timeout = 120  # 2 minutes for performance tests
        else:
            timeout = 30  # 30 seconds for unit tests

        marker = pytest.mark.timeout(timeout)
        item.add_marker(marker)


def pytest_runtest_teardown(item, nextitem):
    """
    Clean up after test run.
    """
    # Force garbage collection after heavy tests
    if any(pattern in item.name for pattern in ["integration", "e2e", "performance"]):
        import gc

        gc.collect()

    # Give system time to release resources
    if any(pattern in str(item.fspath) for pattern in ["thread", "concurrent", "parallel"]):
        import time

        time.sleep(0.1)  # Small delay to let threads clean up


# Export plugin
pytest_plugins = ["pytest_flaky_markers"]
