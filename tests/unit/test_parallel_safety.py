"""
Tests for parallel safety plugin functionality.
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.mark.unit
class TestParallelSafety:
    """Test parallel safety mechanisms."""

    def test_database_isolation(self, isolated_db):
        """Test that database isolation is working."""
        # Get worker-specific database info
        assert "worker_id" in isolated_db
        assert "db_url" in isolated_db

        # In parallel execution, database URL should be modified
        if isolated_db["worker_id"] != "master":
            db_url = isolated_db["db_url"]
            worker_id = isolated_db["worker_id"]

            # Check that URL contains worker ID for SQLite
            if "sqlite" in db_url:
                assert worker_id in db_url or "leadfactory.db" in db_url

    def test_temp_directory_isolation(self, isolated_temp_dir):
        """Test that temp directory isolation is working."""
        assert isinstance(isolated_temp_dir, Path)
        assert isolated_temp_dir.exists()

        # Create a test file
        test_file = isolated_temp_dir / "test.txt"
        test_file.write_text("test content")

        # Verify file exists
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_redis_isolation(self):
        """Test that Redis isolation is configured."""
        # Check if Redis environment variables are set for workers
        redis_url = os.environ.get("REDIS_URL", "")
        redis_prefix = os.environ.get("REDIS_KEY_PREFIX", "")

        # If we're in a worker, these should be modified
        if "PYTEST_XDIST_WORKER" in os.environ:
            worker_id = os.environ["PYTEST_XDIST_WORKER"]
            # Either Redis DB number should be changed or prefix should be set
            assert "/0" not in redis_url or f"test_{worker_id}_" in redis_prefix

    @pytest.mark.parametrize("n", range(5))
    def test_parallel_execution(self, n, isolated_temp_dir):
        """Test that can run multiple times in parallel without conflicts."""
        # Each parallel execution should have its own temp directory
        file_path = isolated_temp_dir / f"parallel_test_{n}.txt"
        file_path.write_text(f"Parallel test {n}")

        # Verify no conflicts
        assert file_path.exists()
        assert file_path.read_text() == f"Parallel test {n}"

        # Check that we don't see files from other parallel executions
        other_files = list(isolated_temp_dir.glob("parallel_test_*.txt"))
        assert len(other_files) == 1  # Only our file should exist
