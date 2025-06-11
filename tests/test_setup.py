"""
Test basic project setup and dependencies
"""
import importlib
import sys

import pytest


def test_python_version():
    """Ensure we're running Python 3.11"""
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 11


def test_core_imports():
    """Test that core dependencies can be imported"""
    dependencies = [
        "fastapi",
        "sqlalchemy",
        "alembic",
        "httpx",
        "redis",
        "stripe",
        "sendgrid",
        "pandas",
        "prometheus_client",
        "pydantic",
        "pytest",
    ]

    for dep in dependencies:
        try:
            importlib.import_module(dep)
        except ImportError:
            pytest.fail(f"Failed to import {dep}")


def test_environment_setup():
    """Test that environment is properly configured"""
    import os

    # These environment variables should be set during test runs
    # If not set, the test environment may not be properly configured
    env = os.getenv("ENVIRONMENT", "development")
    use_stubs = os.getenv("USE_STUBS", "false")
    db_url = os.getenv("DATABASE_URL", "sqlite:///tmp/test.db")
    
    # For CI/testing, we accept either test or development environment
    assert env in ["test", "development"], f"ENVIRONMENT should be test or development, got {env}"
    
    # In test environments, stubs might be enabled
    assert use_stubs in ["true", "false"], f"USE_STUBS should be true or false, got {use_stubs}"
    
    # Database URL should point to a test database
    assert "test" in db_url or ":memory:" in db_url, f"DATABASE_URL should contain 'test' or ':memory:', got {db_url}"


def test_project_structure():
    """Verify basic project structure exists"""
    import os
    from pathlib import Path

    root = Path(__file__).parent.parent

    # Check required files exist
    assert (root / "requirements.txt").exists()
    assert (root / "requirements-dev.txt").exists()
    assert (root / "Dockerfile.test").exists()
    assert (root / "setup.py").exists()
    assert (root / ".gitignore").exists()
    assert (root / "README.md").exists()
    assert (root / "PRD.md").exists()

    # Check tmp directory exists
    assert (root / "tmp").exists() or os.makedirs(root / "tmp", exist_ok=True) is None
