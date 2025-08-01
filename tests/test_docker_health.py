"""
Simple health check test to verify Docker test environment
This test should always pass if the environment is set up correctly
"""

import os
import sys

import pytest

# Mark entire module as smoke test - critical environment validation
pytestmark = pytest.mark.smoke


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
        import importlib.util

        # Check if modules are available
        modules_to_check = ["fastapi", "psycopg2", "pytest", "sqlalchemy", "alembic", "coverage"]

        for module_name in modules_to_check:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                pytest.fail(f"Module {module_name} is not available")

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
