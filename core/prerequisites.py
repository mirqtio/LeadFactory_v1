"""
Prerequisites validation system for LeadFactory development environment.

This module provides comprehensive validation of system requirements including:
- Python version (3.11.0)
- Docker and Docker Compose versions
- Database connectivity
- Environment variables
- Dependencies installation
- CI toolchain functionality

Usage:
    From Python:
        from core.prerequisites import validate_all_prerequisites
        result = validate_all_prerequisites()
        
    From command line:
        python -m core.prerequisites
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from packaging import version
from packaging.version import InvalidVersion
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from core.config import get_settings
from core.logging import get_logger
from core.utils import mask_sensitive_data

logger = get_logger(__name__)


class PrerequisiteCheck(BaseModel):
    """Model for individual prerequisite check result."""

    name: str
    required: bool = True
    passed: bool = False
    version_found: Optional[str] = None
    version_required: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class PrerequisiteResult(BaseModel):
    """Model for overall prerequisite validation result."""

    passed: bool = False
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    checks: List[PrerequisiteCheck] = Field(default_factory=list)
    environment_info: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        """Initialize and compute derived fields."""
        super().__init__(**data)
        self._compute_derived_fields()

    def _compute_derived_fields(self):
        """Compute derived fields from checks."""
        if not self.checks:
            self.passed = False
            self.total_checks = 0
            self.passed_checks = 0
            self.failed_checks = 0
            self.warning_checks = 0
            return

        # Count checks
        self.total_checks = len(self.checks)
        self.passed_checks = sum(1 for check in self.checks if check.passed)
        self.failed_checks = sum(1 for check in self.checks if not check.passed and check.required)
        self.warning_checks = sum(1 for check in self.checks if not check.passed and not check.required)

        # Determine overall pass/fail
        required_checks = [c for c in self.checks if c.required]
        self.passed = all(check.passed for check in required_checks)


class PrerequisiteValidator:
    """Main prerequisites validation class."""

    def __init__(self, settings: Optional[Any] = None):
        """Initialize validator with settings."""
        self.settings = settings or get_settings()
        self.checks: List[PrerequisiteCheck] = []

    def _run_command(self, cmd: List[str], timeout: int = 30) -> Tuple[int, str, str]:
        """
        Run a command and return exit code, stdout, stderr.

        Args:
            cmd: Command to run as list of strings
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", f"Error running command: {str(e)}"

    def check_python_version(self) -> PrerequisiteCheck:
        """Check if Python version is 3.11.x (major.minor must match CI environment)."""
        check = PrerequisiteCheck(name="Python Version", version_required="3.11.x", required=True)

        try:
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            check.version_found = current_version

            # Check major.minor version (3.11.x is acceptable)
            if sys.version_info.major == 3 and sys.version_info.minor == 11:
                check.passed = True
                check.message = f"✅ Python {current_version} (required: 3.11.x - matches CI environment)"
            else:
                check.passed = False
                check.message = f"❌ Python {current_version} found, but 3.11.x required (match CI environment)"

            check.details = {
                "version_info": sys.version_info,
                "executable": sys.executable,
                "platform": sys.platform,
                "major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
            }

        except Exception as e:
            check.passed = False
            check.message = f"❌ Error checking Python version: {str(e)}"
            check.details = {"error": str(e)}

        return check

    def check_docker_version(self) -> PrerequisiteCheck:
        """Check if Docker version is >= 20.10."""
        check = PrerequisiteCheck(name="Docker Version", version_required="≥ 20.10", required=True)

        try:
            exit_code, stdout, stderr = self._run_command(["docker", "--version"])

            if exit_code != 0:
                check.passed = False
                check.message = f"❌ Docker not found or not running: {stderr}"
                check.details = {"error": stderr}
                return check

            # Extract version from output like "Docker version 20.10.17, build 100c701"
            version_line = stdout.strip()
            version_parts = version_line.split()

            if len(version_parts) >= 3:
                docker_version = version_parts[2].rstrip(",")
                check.version_found = docker_version

                if version.parse(docker_version) >= version.parse("20.10.0"):
                    check.passed = True
                    check.message = f"✅ Docker {docker_version} (required: ≥ 20.10)"
                else:
                    check.passed = False
                    check.message = f"❌ Docker {docker_version} found, but ≥ 20.10 required"
            else:
                check.passed = False
                check.message = f"❌ Could not parse Docker version from: {version_line}"

            check.details = {"version_output": version_line, "docker_info": self._get_docker_info()}

        except Exception as e:
            check.passed = False
            check.message = f"❌ Error checking Docker version: {str(e)}"
            check.details = {"error": str(e)}

        return check

    def check_docker_compose_version(self) -> PrerequisiteCheck:
        """Check if Docker Compose version is >= 2.0."""
        check = PrerequisiteCheck(name="Docker Compose Version", version_required="≥ 2.0", required=True)

        try:
            exit_code, stdout, stderr = self._run_command(["docker-compose", "--version"])

            if exit_code != 0:
                check.passed = False
                check.message = f"❌ Docker Compose not found: {stderr}"
                check.details = {"error": stderr}
                return check

            # Extract version from output like "Docker Compose version v2.17.2" or "Docker Compose version v2.37.1-desktop.1"
            version_line = stdout.strip()
            version_parts = version_line.split()

            if len(version_parts) >= 4:
                compose_version = version_parts[3].lstrip("v")
                check.version_found = compose_version

                # Extract major.minor version for comparison (ignore build suffixes)
                try:
                    # Split by '-' to remove desktop or other suffixes
                    base_version = compose_version.split("-")[0]
                    parsed_version = version.parse(base_version)

                    if parsed_version >= version.parse("2.0.0"):
                        check.passed = True
                        check.message = f"✅ Docker Compose {compose_version} (required: ≥ 2.0)"
                    else:
                        check.passed = False
                        check.message = f"❌ Docker Compose {compose_version} found, but ≥ 2.0 required"
                except InvalidVersion:
                    check.passed = False
                    check.message = f"❌ Invalid Docker Compose version format: {compose_version}"
            else:
                check.passed = False
                check.message = f"❌ Could not parse Docker Compose version from: {version_line}"

            check.details = {"version_output": version_line}

        except Exception as e:
            check.passed = False
            check.message = f"❌ Error checking Docker Compose version: {str(e)}"
            check.details = {"error": str(e)}

        return check

    def check_database_connectivity(self) -> PrerequisiteCheck:
        """Check database connectivity."""
        check = PrerequisiteCheck(name="Database Connectivity", required=True)

        try:
            # Use settings database URL
            database_url = self.settings.database_url

            # Mask sensitive data for logging
            masked_url = mask_sensitive_data(database_url)
            logger.info(f"Testing database connection to: {masked_url}")

            # Test connection using SQLAlchemy
            engine = create_engine(database_url, echo=False)

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar()

                if result == 1:
                    check.passed = True
                    check.message = "✅ Database connection successful"
                else:
                    check.passed = False
                    check.message = "❌ Database connection failed: unexpected result"

            check.details = {"database_url": masked_url, "driver": str(engine.dialect.name), "connection_tested": True}

        except Exception as e:
            check.passed = False
            check.message = f"❌ Database connection failed: {str(e)}"
            check.details = {
                "error": str(e),
                "database_url": mask_sensitive_data(getattr(self.settings, "database_url", "not_set")),
            }

        return check

    def check_environment_variables(self) -> PrerequisiteCheck:
        """Check required environment variables."""
        check = PrerequisiteCheck(name="Environment Variables", required=True)

        # Required environment variables
        required_vars = {
            "DATABASE_URL": "Database connection string",
            "SECRET_KEY": "Application secret key",
            "ENVIRONMENT": "Application environment (development/staging/production)",
        }

        # Optional but recommended variables
        optional_vars = {
            "USE_STUBS": "Use stub services for testing",
            "LOG_LEVEL": "Logging level",
            "REDIS_URL": "Redis connection string",
        }

        missing_required = []
        missing_optional = []
        found_vars = {}

        # Check required variables
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if value:
                found_vars[var_name] = mask_sensitive_data(value)
            else:
                missing_required.append(f"{var_name} ({description})")

        # Check optional variables
        for var_name, description in optional_vars.items():
            value = os.getenv(var_name)
            if value:
                found_vars[var_name] = mask_sensitive_data(value)
            else:
                missing_optional.append(f"{var_name} ({description})")

        if not missing_required:
            check.passed = True
            check.message = "✅ All required environment variables found"
            if missing_optional:
                check.message += f" (optional missing: {len(missing_optional)})"
        else:
            check.passed = False
            check.message = f"❌ Missing required environment variables: {', '.join(missing_required)}"

        check.details = {
            "found_variables": found_vars,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "env_file_exists": os.path.exists(".env"),
        }

        return check

    def check_dependencies_installed(self) -> PrerequisiteCheck:
        """Check if all Python dependencies are installed."""
        check = PrerequisiteCheck(name="Python Dependencies", required=True)

        try:
            # Check if pip check passes
            exit_code, stdout, stderr = self._run_command([sys.executable, "-m", "pip", "check"])

            if exit_code == 0:
                check.passed = True
                check.message = "✅ All Python dependencies are correctly installed"
            else:
                check.passed = False
                check.message = f"❌ Dependency conflicts detected: {stderr}"

            # Get installed packages list
            exit_code2, packages_output, _ = self._run_command([sys.executable, "-m", "pip", "list", "--format=freeze"])

            installed_packages = packages_output.strip().split("\n") if exit_code2 == 0 else []

            check.details = {
                "pip_check_output": stdout,
                "pip_check_errors": stderr,
                "installed_packages_count": len(installed_packages),
                "requirements_files": {
                    "requirements.txt": os.path.exists("requirements.txt"),
                    "requirements-dev.txt": os.path.exists("requirements-dev.txt"),
                },
            }

        except Exception as e:
            check.passed = False
            check.message = f"❌ Error checking dependencies: {str(e)}"
            check.details = {"error": str(e)}

        return check

    def check_pytest_collection(self) -> PrerequisiteCheck:
        """Check if pytest can collect tests without errors."""
        check = PrerequisiteCheck(name="Pytest Collection", required=True)

        try:
            # Run pytest --collect-only
            exit_code, stdout, stderr = self._run_command(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"], timeout=60
            )

            if exit_code == 0:
                check.passed = True
                # Count collected tests
                lines = stdout.strip().split("\n")
                test_count = 0
                for line in lines:
                    if "items" in line and "collected" in line:
                        # Extract number from line like "2191 items collected"
                        words = line.split()
                        if words and words[0].isdigit():
                            test_count = int(words[0])
                            break

                check.message = f"✅ Pytest collection successful ({test_count} tests found)"
            else:
                check.passed = False
                check.message = f"❌ Pytest collection failed: {stderr}"

            check.details = {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "test_directory_exists": os.path.exists("tests"),
            }

        except Exception as e:
            check.passed = False
            check.message = f"❌ Error running pytest collection: {str(e)}"
            check.details = {"error": str(e)}

        return check

    def check_ci_toolchain(self) -> PrerequisiteCheck:
        """Check if CI toolchain (ruff, mypy) is working."""
        check = PrerequisiteCheck(name="CI Toolchain", required=True)

        tools_status = {}
        all_passed = True

        # Check ruff
        try:
            exit_code, stdout, stderr = self._run_command([sys.executable, "-m", "ruff", "--version"])
            tools_status["ruff"] = {
                "available": exit_code == 0,
                "version": stdout.strip() if exit_code == 0 else None,
                "error": stderr if exit_code != 0 else None,
            }
            if exit_code != 0:
                all_passed = False
        except Exception as e:
            tools_status["ruff"] = {"available": False, "error": str(e)}
            all_passed = False

        # Check mypy
        try:
            exit_code, stdout, stderr = self._run_command([sys.executable, "-m", "mypy", "--version"])
            tools_status["mypy"] = {
                "available": exit_code == 0,
                "version": stdout.strip() if exit_code == 0 else None,
                "error": stderr if exit_code != 0 else None,
            }
            if exit_code != 0:
                all_passed = False
        except Exception as e:
            tools_status["mypy"] = {"available": False, "error": str(e)}
            all_passed = False

        # Check pytest
        try:
            exit_code, stdout, stderr = self._run_command([sys.executable, "-m", "pytest", "--version"])
            tools_status["pytest"] = {
                "available": exit_code == 0,
                "version": stdout.strip() if exit_code == 0 else None,
                "error": stderr if exit_code != 0 else None,
            }
            if exit_code != 0:
                all_passed = False
        except Exception as e:
            tools_status["pytest"] = {"available": False, "error": str(e)}
            all_passed = False

        if all_passed:
            check.passed = True
            check.message = "✅ CI toolchain (ruff, mypy, pytest) is working"
        else:
            check.passed = False
            failed_tools = [name for name, info in tools_status.items() if not info["available"]]
            check.message = f"❌ CI toolchain issues: {', '.join(failed_tools)} not available"

        check.details = {"tools": tools_status}

        return check

    def check_docker_build(self) -> PrerequisiteCheck:
        """Check if Docker test image can be built."""
        check = PrerequisiteCheck(name="Docker Build", required=False)  # Optional check

        try:
            # Check if Dockerfile.test exists
            dockerfile_test = Path("Dockerfile.test")
            if not dockerfile_test.exists():
                check.passed = False
                check.message = "❌ Dockerfile.test not found"
                check.details = {"dockerfile_exists": False}
                return check

            # Try to build the test image
            exit_code, stdout, stderr = self._run_command(
                ["docker", "build", "-f", "Dockerfile.test", "-t", "leadfactory-test", "."], timeout=300
            )  # 5 minutes timeout

            if exit_code == 0:
                check.passed = True
                check.message = "✅ Docker test image builds successfully"
            else:
                check.passed = False
                check.message = f"❌ Docker build failed: {stderr}"

            check.details = {
                "dockerfile_exists": True,
                "build_exit_code": exit_code,
                "build_output": stdout,
                "build_errors": stderr,
            }

        except Exception as e:
            check.passed = False
            check.message = f"❌ Error building Docker image: {str(e)}"
            check.details = {"error": str(e)}

        return check

    def _get_docker_info(self) -> Dict[str, Any]:
        """Get Docker system information."""
        try:
            exit_code, stdout, stderr = self._run_command(["docker", "info", "--format", "json"])
            if exit_code == 0:
                import json

                return json.loads(stdout)
        except Exception:
            pass
        return {}

    def _get_environment_info(self) -> Dict[str, Any]:
        """Get environment information."""
        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "python_executable": sys.executable,
            "platform": sys.platform,
            "working_directory": os.getcwd(),
            "virtual_environment": os.getenv("VIRTUAL_ENV"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "use_stubs": os.getenv("USE_STUBS", "true").lower() == "true",
        }

    def validate_all_prerequisites(self) -> PrerequisiteResult:
        """
        Run all prerequisite checks and return comprehensive result.

        Returns:
            PrerequisiteResult with all check results
        """
        logger.info("Starting comprehensive prerequisites validation...")

        # Run all checks
        checks = [
            self.check_python_version(),
            self.check_docker_version(),
            self.check_docker_compose_version(),
            self.check_database_connectivity(),
            self.check_environment_variables(),
            self.check_dependencies_installed(),
            self.check_pytest_collection(),
            self.check_ci_toolchain(),
            self.check_docker_build(),  # Optional check
        ]

        # Create result
        result = PrerequisiteResult(checks=checks, environment_info=self._get_environment_info())

        # Log results
        logger.info(f"Prerequisites validation completed: {result.passed_checks}/{result.total_checks} checks passed")

        if not result.passed:
            failed_checks = [c.name for c in result.checks if not c.passed and c.required]
            logger.error(f"Prerequisites validation failed. Failed checks: {', '.join(failed_checks)}")

        return result


def validate_all_prerequisites() -> PrerequisiteResult:
    """
    Convenience function to validate all prerequisites.

    Returns:
        PrerequisiteResult with all check results
    """
    validator = PrerequisiteValidator()
    return validator.validate_all_prerequisites()


def print_results(result: PrerequisiteResult) -> None:
    """
    Print formatted results to console.

    Args:
        result: PrerequisiteResult to print
    """
    print("\n" + "=" * 80)
    print("🚀 LEADFACTORY PREREQUISITES VALIDATION")
    print("=" * 80)

    # Overall status
    status_emoji = "✅" if result.passed else "❌"
    print(f"\n{status_emoji} Overall Status: {'PASSED' if result.passed else 'FAILED'}")
    print(f"📊 Summary: {result.passed_checks}/{result.total_checks} checks passed")

    if result.failed_checks > 0:
        print(f"❌ Failed: {result.failed_checks}")
    if result.warning_checks > 0:
        print(f"⚠️  Warnings: {result.warning_checks}")

    # Environment info
    print("\n📋 Environment Information:")
    env_info = result.environment_info
    print(f"  • Python: {env_info.get('python_version', 'unknown')}")
    print(f"  • Platform: {env_info.get('platform', 'unknown')}")
    print(f"  • Environment: {env_info.get('environment', 'unknown')}")
    print(f"  • Use Stubs: {env_info.get('use_stubs', 'unknown')}")

    # Individual checks
    print("\n🔍 Detailed Check Results:")
    for check in result.checks:
        print(f"  {check.message}")
        if check.version_found and check.version_required:
            print(f"    Found: {check.version_found} | Required: {check.version_required}")

    # Recommendations
    if not result.passed:
        print("\n🔧 Recommendations:")
        failed_checks = [c for c in result.checks if not c.passed and c.required]

        for check in failed_checks:
            print(f"  • {check.name}: {check.message}")
            if check.name == "Python Version":
                print("    → Install Python 3.11.0 using pyenv: pyenv install 3.11.0")
            elif check.name == "Docker Version":
                print("    → Update Docker to version 20.10 or higher")
            elif check.name == "Docker Compose Version":
                print("    → Update Docker Compose to version 2.0 or higher")
            elif check.name == "Database Connectivity":
                print("    → Check database connection string in .env file")
                print("    → Ensure database server is running")
            elif check.name == "Environment Variables":
                print("    → Copy .env.example to .env and update values")
            elif check.name == "Python Dependencies":
                print("    → Run: pip install -r requirements-dev.txt")
            elif check.name == "Pytest Collection":
                print("    → Check for syntax errors in test files")
            elif check.name == "CI Toolchain":
                print("    → Install missing tools: pip install ruff mypy pytest")

    print("\n" + "=" * 80)
    if result.passed:
        print("🎉 All prerequisites validated successfully!")
        print("You can now run: pytest --collect-only")
    else:
        print("❌ Prerequisites validation failed. Please fix the issues above.")
    print("=" * 80)


if __name__ == "__main__":
    """Command line interface for prerequisites validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate LeadFactory prerequisites")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", action="store_true", help="Only output essential information")
    parser.add_argument(
        "--check", choices=["python", "docker", "database", "deps", "pytest", "ci"], help="Run only specific check"
    )

    args = parser.parse_args()

    # Disable logging if JSON output is requested
    if args.json:
        import logging

        logging.disable(logging.CRITICAL)
        # Also suppress any root logger output
        logging.getLogger().handlers = []
        # Suppress structured logging as well
        for logger_name in logging.Logger.manager.loggerDict:
            logging.getLogger(logger_name).handlers = []
            logging.getLogger(logger_name).propagate = False

    # Run validation
    validator = PrerequisiteValidator()

    if args.check:
        # Run specific check
        check_methods = {
            "python": validator.check_python_version,
            "docker": validator.check_docker_version,
            "database": validator.check_database_connectivity,
            "deps": validator.check_dependencies_installed,
            "pytest": validator.check_pytest_collection,
            "ci": validator.check_ci_toolchain,
        }

        if args.check in check_methods:
            check_result = check_methods[args.check]()
            result = PrerequisiteResult(checks=[check_result])
        else:
            print(f"Unknown check: {args.check}")
            sys.exit(1)
    else:
        # Run all checks
        result = validator.validate_all_prerequisites()

    # Output results
    if args.json:
        import json

        print(json.dumps(result.model_dump(), indent=2))
    elif not args.quiet:
        print_results(result)

    # Exit with appropriate code
    sys.exit(0 if result.passed else 1)
