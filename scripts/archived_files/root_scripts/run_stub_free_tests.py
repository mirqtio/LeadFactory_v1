#!/usr/bin/env python3
"""
Run tests without stub server setup for ultra-fast CI.
Bypasses expensive infrastructure setup.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def create_minimal_conftest():
    """Create a minimal conftest.py that bypasses stub setup."""
    minimal_conftest = '''"""
Minimal conftest for ultra-fast testing.
Bypasses all expensive setup.
"""
import os
import pytest


# Override environment for minimal setup
os.environ["USE_STUBS"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["SKIP_INFRASTRUCTURE"] = "true"


@pytest.fixture(scope="session", autouse=True)
def minimal_setup():
    """Minimal setup - no stub server, no database."""
    # Disable all providers
    os.environ["ENABLE_GBP"] = "false"
    os.environ["ENABLE_PAGESPEED"] = "false"
    os.environ["ENABLE_SENDGRID"] = "false"
    os.environ["ENABLE_OPENAI"] = "false"
    os.environ["ENABLE_DATAAXLE"] = "false"
    os.environ["ENABLE_HUNTER"] = "false"
    os.environ["ENABLE_SEMRUSH"] = "false"
    os.environ["ENABLE_SCREENSHOTONE"] = "false"
    
    # Mock database
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    
    yield


@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress all logging for speed."""
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


# Override the main conftest fixtures to prevent stub server startup
@pytest.fixture(scope="session")
def stub_server_session():
    """Override to prevent stub server startup."""
    yield


@pytest.fixture
def provider_stub():
    """Override provider stub fixture."""
    yield
'''
    return minimal_conftest


def run_stub_free_tests(test_paths):
    """Run tests with minimal setup, bypassing stub server."""

    # Create temporary minimal conftest
    with tempfile.NamedTemporaryFile(mode="w", suffix="_conftest.py", delete=False) as f:
        f.write(create_minimal_conftest())
        temp_conftest = f.name

    try:
        # Set environment for minimal setup
        env = os.environ.copy()
        env.update(
            {
                "USE_STUBS": "false",
                "ENVIRONMENT": "test",
                "SKIP_INFRASTRUCTURE": "true",
                "PYTEST_DISABLE_PLUGIN_MANAGER": "1",
            }
        )

        # Build pytest command
        cmd = [
            "python",
            "-m",
            "pytest",
            "--tb=no",
            "-q",
            "--disable-warnings",
            "-p",
            "no:warnings",
            "--override-ini",
            f"python_files=test_*.py {temp_conftest}",
            "--maxfail=1",
            "-x",
            "--timeout=15",  # 15 second timeout per test
            "--timeout-method=signal",
        ] + test_paths

        print(f"Running command: {' '.join(cmd)}")

        # Run tests
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return code:", result.returncode)

        return result.returncode == 0

    finally:
        # Clean up temp file
        if os.path.exists(temp_conftest):
            os.unlink(temp_conftest)


def main():
    """Main execution."""
    # Ultra-fast test targets
    fast_tests = [
        "tests/unit/d5_scoring/test_omega.py",
        "tests/unit/d5_scoring/test_impact_calculator.py",
        "tests/unit/d8_personalization/test_templates.py",
        "tests/unit/design/test_token_extraction.py",
        "tests/unit/design/test_validation_module.py",
    ]

    # Filter existing tests
    existing_tests = [t for t in fast_tests if Path(t).exists()]

    if not existing_tests:
        print("No test files found!")
        return 1

    print(f"Running {len(existing_tests)} ultra-fast tests without stub setup...")
    print("Tests:", existing_tests)

    success = run_stub_free_tests(existing_tests)

    if success:
        print("✅ All ultra-fast tests passed!")
        return 0
    print("❌ Some tests failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
