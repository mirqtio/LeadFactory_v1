"""
Pytest Plugin for Parallel Test Safety

This plugin ensures test isolation when running with pytest-xdist:
- Database tests use separate test databases per worker
- Redis test isolation
- Temporary file conflict management
"""

import os
import tempfile
from pathlib import Path

import pytest


class ParallelSafetyPlugin:
    """Plugin to ensure test safety in parallel execution."""

    def __init__(self):
        self.worker_id = None
        self.original_db_url = None
        self.temp_dirs = {}

    def pytest_configure_node(self, node):
        """Configure node for parallel execution."""
        # Store worker ID
        self.worker_id = node.workerinput.get("workerid", "master")

        # Configure database isolation
        self._configure_database_isolation()

        # Configure temp directory isolation
        self._configure_temp_isolation()

        # Configure Redis isolation
        self._configure_redis_isolation()

    def _configure_database_isolation(self):
        """Ensure each worker uses a separate test database."""
        # Check if we're in a worker process
        if not self.worker_id or self.worker_id == "master":
            return

        # Get original database URL
        self.original_db_url = os.environ.get("DATABASE_URL", "sqlite:///tmp/leadfactory.db")

        if self.original_db_url.startswith("sqlite://"):
            # For SQLite, create separate database files
            base_path = self.original_db_url.replace("sqlite:///", "")
            path = Path(base_path)
            new_path = path.parent / f"{path.stem}_{self.worker_id}{path.suffix}"
            os.environ["DATABASE_URL"] = f"sqlite:///{new_path}"

        elif "postgresql://" in self.original_db_url or "postgres://" in self.original_db_url:
            # For PostgreSQL, use separate schemas or databases
            # This assumes the test database allows dynamic database creation
            if "/" in self.original_db_url:
                base_url, db_name = self.original_db_url.rsplit("/", 1)
                # Remove any query parameters
                if "?" in db_name:
                    db_name, params = db_name.split("?", 1)
                    new_db_name = f"{db_name}_{self.worker_id}"
                    os.environ["DATABASE_URL"] = f"{base_url}/{new_db_name}?{params}"
                else:
                    new_db_name = f"{db_name}_{self.worker_id}"
                    os.environ["DATABASE_URL"] = f"{base_url}/{new_db_name}"

    def _configure_temp_isolation(self):
        """Ensure each worker uses separate temp directories."""
        if not self.worker_id or self.worker_id == "master":
            return

        # Create worker-specific temp directory
        base_temp = tempfile.gettempdir()
        worker_temp = Path(base_temp) / f"leadfactory_test_{self.worker_id}"
        worker_temp.mkdir(exist_ok=True)

        # Store for cleanup
        self.temp_dirs[self.worker_id] = worker_temp

        # Update temp directory for this worker
        os.environ["TMPDIR"] = str(worker_temp)
        os.environ["TEMP"] = str(worker_temp)
        os.environ["TMP"] = str(worker_temp)

    def _configure_redis_isolation(self):
        """Ensure Redis test isolation using separate databases or key prefixes."""
        if not self.worker_id or self.worker_id == "master":
            return

        # Get Redis configuration
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

        # Use different Redis databases for different workers
        # Redis typically has 16 databases (0-15)
        if redis_url and "/0" in redis_url:
            # Extract worker number from worker_id (e.g., 'gw0' -> 0)
            import re

            match = re.search(r"gw(\d+)", self.worker_id)
            if match:
                worker_num = int(match.group(1))
                # Use databases 1-15 for workers, keep 0 for master
                db_num = (worker_num % 15) + 1
                new_redis_url = redis_url.replace("/0", f"/{db_num}")
                os.environ["REDIS_URL"] = new_redis_url

        # Also set a key prefix for additional safety
        os.environ["REDIS_KEY_PREFIX"] = f"test_{self.worker_id}_"

    def pytest_unconfigure(self, config):
        """Clean up after test run."""
        # Restore original database URL
        if self.original_db_url:
            os.environ["DATABASE_URL"] = self.original_db_url

        # Clean up temp directories
        for temp_dir in self.temp_dirs.values():
            if temp_dir.exists():
                import shutil

                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass  # Best effort cleanup


def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", None)
    if worker_id:
        # Print worker configuration for debugging
        print(f"\nWorker {worker_id} configuration:")
        print(f"  DATABASE_URL: {os.environ.get('DATABASE_URL', 'not set')}")
        print(f"  REDIS_URL: {os.environ.get('REDIS_URL', 'not set')}")
        print(f"  TMPDIR: {os.environ.get('TMPDIR', 'not set')}")


def pytest_runtest_setup(item):
    """Called before running each test."""
    # Mark tests that must run serially
    serial_markers = ["serial", "no_parallel", "shared_resource"]

    for marker in serial_markers:
        if item.get_closest_marker(marker):
            # These tests should not run in parallel
            if os.environ.get("PYTEST_XDIST_WORKER"):
                pytest.skip(f"Test marked as '{marker}' - skipping in parallel execution")


# Fixtures for test isolation


@pytest.fixture
def isolated_db(request):
    """
    Provide an isolated database connection for tests that need it.

    This fixture ensures that even in parallel execution, each test
    gets its own database isolation.
    """
    worker_id = getattr(request.config, "workerinput", {}).get("workerid", "master")
    return {
        "worker_id": worker_id,
        "db_url": os.environ.get("DATABASE_URL"),
    }


@pytest.fixture
def isolated_temp_dir(request):
    """
    Provide an isolated temporary directory for each test.

    This ensures no conflicts between parallel test runs.
    """
    worker_id = getattr(request.config, "workerinput", {}).get("workerid", "master")
    base_dir = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))

    # Create test-specific temp directory
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    temp_dir = base_dir / f"test_{test_name}_{worker_id}"
    temp_dir.mkdir(exist_ok=True, parents=True)

    yield temp_dir

    # Cleanup
    if temp_dir.exists():
        import shutil

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Best effort cleanup


# Register the plugin
def pytest_configure(config):
    """Register the parallel safety plugin."""
    if config.pluginmanager.has_plugin("xdist"):
        config.pluginmanager.register(ParallelSafetyPlugin(), "parallel_safety")


# Export plugin and fixtures
__all__ = ["ParallelSafetyPlugin", "isolated_db", "isolated_temp_dir"]
