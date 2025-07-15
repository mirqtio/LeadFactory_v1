"""
Simple health check test to verify Docker test environment
This test should always pass if the environment is set up correctly
"""
import os
import sys


def test_python_version():
    """Test that we're running the correct Python version"""
    assert sys.version_info >= (3, 11), f"Expected Python 3.11+, got {sys.version}"


def test_environment_variables():
    """Test that critical environment variables are set"""
    assert os.getenv("CI") == "true", "CI environment variable not set"
    assert os.getenv("ENVIRONMENT") == "test", "ENVIRONMENT not set to 'test'"
    assert os.getenv("USE_STUBS") == "true", "USE_STUBS not set to 'true'"
    assert os.getenv("DATABASE_URL"), "DATABASE_URL not set"
    assert os.getenv("STUB_BASE_URL"), "STUB_BASE_URL not set"
    assert os.getenv("PYTHONPATH") == "/app", "PYTHONPATH not set correctly"


def test_import_core_modules():
    """Test that core modules can be imported"""
    try:
        import pytest
        import coverage
        import psycopg2
        import fastapi
        import sqlalchemy
        import alembic
    except ImportError as e:
        pytest.fail(f"Failed to import required module: {e}")


def test_simple_assertion():
    """Basic test to ensure pytest is working"""
    assert 1 + 1 == 2
    assert True is True
    assert "test" in "testing"


if __name__ == "__main__":
    # Run tests if executed directly
    import pytest
    pytest.main([__file__, "-v"])