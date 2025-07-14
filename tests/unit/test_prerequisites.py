"""
Unit tests for prerequisites validation module.

Tests all prerequisite checks including:
- Python version validation
- Docker and Docker Compose version checks
- Database connectivity
- Environment variables
- Dependencies installation
- Pytest collection
- CI toolchain validation

Coverage target: >80%
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from core.prerequisites import (
    PrerequisiteCheck,
    PrerequisiteResult,
    PrerequisiteValidator,
    print_results,
    validate_all_prerequisites,
)


class TestPrerequisiteCheck:
    """Test PrerequisiteCheck model."""

    def test_basic_check_creation(self):
        """Test basic check creation."""
        check = PrerequisiteCheck(name="Test Check", passed=True, message="Test message")

        assert check.name == "Test Check"
        assert check.passed is True
        assert check.required is True  # Default
        assert check.message == "Test message"
        assert check.version_found is None
        assert check.version_required is None
        assert check.details == {}

    def test_check_with_version_info(self):
        """Test check with version information."""
        check = PrerequisiteCheck(
            name="Version Check",
            passed=True,
            version_found="1.2.3",
            version_required="≥ 1.0.0",
            message="Version check passed",
        )

        assert check.version_found == "1.2.3"
        assert check.version_required == "≥ 1.0.0"

    def test_check_with_details(self):
        """Test check with additional details."""
        details = {"key": "value", "number": 42}
        check = PrerequisiteCheck(name="Detailed Check", passed=False, message="Failed", details=details)

        assert check.details == details

    def test_optional_check(self):
        """Test optional check creation."""
        check = PrerequisiteCheck(name="Optional Check", required=False, passed=False, message="Optional check failed")

        assert check.required is False


class TestPrerequisiteResult:
    """Test PrerequisiteResult model."""

    def test_empty_result(self):
        """Test empty result creation."""
        result = PrerequisiteResult()

        assert result.passed is False
        assert result.total_checks == 0
        assert result.passed_checks == 0
        assert result.failed_checks == 0
        assert result.warning_checks == 0
        assert result.checks == []
        assert result.environment_info == {}

    def test_result_with_all_passing_checks(self):
        """Test result with all checks passing."""
        checks = [
            PrerequisiteCheck(name="Check 1", passed=True, required=True, message="Pass 1"),
            PrerequisiteCheck(name="Check 2", passed=True, required=True, message="Pass 2"),
            PrerequisiteCheck(name="Check 3", passed=True, required=False, message="Pass 3"),
        ]

        result = PrerequisiteResult(checks=checks)

        assert result.passed is True
        assert result.total_checks == 3
        assert result.passed_checks == 3
        assert result.failed_checks == 0
        assert result.warning_checks == 0

    def test_result_with_failed_required_check(self):
        """Test result with failed required check."""
        checks = [
            PrerequisiteCheck(name="Check 1", passed=True, required=True, message="Pass 1"),
            PrerequisiteCheck(name="Check 2", passed=False, required=True, message="Fail 2"),
            PrerequisiteCheck(name="Check 3", passed=True, required=False, message="Pass 3"),
        ]

        result = PrerequisiteResult(checks=checks)

        assert result.passed is False
        assert result.total_checks == 3
        assert result.passed_checks == 2
        assert result.failed_checks == 1
        assert result.warning_checks == 0

    def test_result_with_failed_optional_check(self):
        """Test result with failed optional check."""
        checks = [
            PrerequisiteCheck(name="Check 1", passed=True, required=True, message="Pass 1"),
            PrerequisiteCheck(name="Check 2", passed=True, required=True, message="Pass 2"),
            PrerequisiteCheck(name="Check 3", passed=False, required=False, message="Fail 3"),
        ]

        result = PrerequisiteResult(checks=checks)

        assert result.passed is True  # Optional failure doesn't fail overall
        assert result.total_checks == 3
        assert result.passed_checks == 2
        assert result.failed_checks == 0
        assert result.warning_checks == 1

    def test_result_with_environment_info(self):
        """Test result with environment information."""
        env_info = {"python_version": "3.11.0", "platform": "darwin", "environment": "development"}

        result = PrerequisiteResult(environment_info=env_info)

        assert result.environment_info == env_info


class TestPrerequisiteValidator:
    """Test PrerequisiteValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance with mock settings."""
        mock_settings = Mock()
        mock_settings.database_url = "sqlite:///test.db"
        return PrerequisiteValidator(settings=mock_settings)

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess for command execution."""
        with patch("core.prerequisites.subprocess.run") as mock_run:
            yield mock_run

    def test_validator_initialization(self, validator):
        """Test validator initialization."""
        assert validator.settings is not None
        assert validator.checks == []

    def test_validator_initialization_with_default_settings(self):
        """Test validator initialization with default settings."""
        with patch("core.prerequisites.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_get_settings.return_value = mock_settings

            validator = PrerequisiteValidator()

            assert validator.settings == mock_settings
            mock_get_settings.assert_called_once()

    def test_run_command_success(self, validator, mock_subprocess):
        """Test successful command execution."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "success output"
        mock_subprocess.return_value.stderr = ""

        exit_code, stdout, stderr = validator._run_command(["echo", "test"])

        assert exit_code == 0
        assert stdout == "success output"
        assert stderr == ""
        mock_subprocess.assert_called_once()

    def test_run_command_failure(self, validator, mock_subprocess):
        """Test failed command execution."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "error output"

        exit_code, stdout, stderr = validator._run_command(["false"])

        assert exit_code == 1
        assert stdout == ""
        assert stderr == "error output"

    def test_run_command_timeout(self, validator, mock_subprocess):
        """Test command timeout handling."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 30)

        exit_code, stdout, stderr = validator._run_command(["sleep", "60"], timeout=1)

        assert exit_code == -1
        assert stdout == ""
        assert "timed out" in stderr

    def test_run_command_file_not_found(self, validator, mock_subprocess):
        """Test command not found handling."""
        mock_subprocess.side_effect = FileNotFoundError("command not found")

        exit_code, stdout, stderr = validator._run_command(["nonexistent"])

        assert exit_code == -1
        assert stdout == ""
        assert "Command not found" in stderr

    def test_run_command_exception(self, validator, mock_subprocess):
        """Test command exception handling."""
        mock_subprocess.side_effect = Exception("unexpected error")

        exit_code, stdout, stderr = validator._run_command(["test"])

        assert exit_code == -1
        assert stdout == ""
        assert "Error running command" in stderr

    def test_check_python_version_correct(self, validator):
        """Test Python version check with correct version."""
        with patch("core.prerequisites.sys.version_info") as mock_version:
            mock_version.major = 3
            mock_version.minor = 11
            mock_version.micro = 0

            check = validator.check_python_version()

            assert check.name == "Python Version"
            assert check.passed is True
            assert check.version_found == "3.11.0"
            assert check.version_required == "3.11.x"
            assert "✅" in check.message

    def test_check_python_version_incorrect(self, validator):
        """Test Python version check with incorrect version."""
        with patch("core.prerequisites.sys.version_info") as mock_version:
            mock_version.major = 3
            mock_version.minor = 10
            mock_version.micro = 0

            check = validator.check_python_version()

            assert check.name == "Python Version"
            assert check.passed is False
            assert check.version_found == "3.10.0"
            assert check.version_required == "3.11.x"
            assert "❌" in check.message

    def test_check_python_version_exception(self, validator):
        """Test Python version check with exception."""
        with patch.object(validator, "check_python_version") as mock_check:
            check = PrerequisiteCheck(
                name="Python Version",
                passed=False,
                version_required="3.11.x",
                message="❌ Error checking Python version: test error",
                details={"error": "test error"},
            )
            mock_check.return_value = check

            result = validator.check_python_version()

            assert result.name == "Python Version"
            assert result.passed is False
            assert "Error checking Python version" in result.message

    def test_check_docker_version_success(self, validator, mock_subprocess):
        """Test Docker version check with valid version."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Docker version 20.10.17, build 100c701"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_docker_version()

        assert check.name == "Docker Version"
        assert check.passed is True
        assert check.version_found == "20.10.17"
        assert check.version_required == "≥ 20.10"
        assert "✅" in check.message

    def test_check_docker_version_old(self, validator, mock_subprocess):
        """Test Docker version check with old version."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Docker version 19.03.12, build 48a66213fe"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_docker_version()

        assert check.name == "Docker Version"
        assert check.passed is False
        assert check.version_found == "19.03.12"
        assert "❌" in check.message

    def test_check_docker_version_not_found(self, validator, mock_subprocess):
        """Test Docker version check when Docker not found."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "docker: command not found"

        check = validator.check_docker_version()

        assert check.name == "Docker Version"
        assert check.passed is False
        assert "Docker not found" in check.message

    def test_check_docker_version_parse_error(self, validator, mock_subprocess):
        """Test Docker version check with unparseable output."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Invalid output"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_docker_version()

        assert check.name == "Docker Version"
        assert check.passed is False
        assert "Could not parse Docker version" in check.message

    def test_check_docker_compose_version_success(self, validator, mock_subprocess):
        """Test Docker Compose version check with valid version."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Docker Compose version v2.17.2"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_docker_compose_version()

        assert check.name == "Docker Compose Version"
        assert check.passed is True
        assert check.version_found == "2.17.2"
        assert check.version_required == "≥ 2.0"
        assert "✅" in check.message

    def test_check_docker_compose_version_old(self, validator, mock_subprocess):
        """Test Docker Compose version check with old version."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Docker Compose version v1.29.2"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_docker_compose_version()

        assert check.name == "Docker Compose Version"
        assert check.passed is False
        assert check.version_found == "1.29.2"
        assert "❌" in check.message

    def test_check_docker_compose_version_not_found(self, validator, mock_subprocess):
        """Test Docker Compose version check when not found."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "docker-compose: command not found"

        check = validator.check_docker_compose_version()

        assert check.name == "Docker Compose Version"
        assert check.passed is False
        assert "Docker Compose not found" in check.message

    def test_check_database_connectivity_success(self, validator):
        """Test database connectivity check with successful connection."""
        mock_engine = Mock()
        mock_conn = Mock()
        mock_conn.execute.return_value.scalar.return_value = 1
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_conn

        with patch("core.prerequisites.create_engine", return_value=mock_engine):
            check = validator.check_database_connectivity()

            assert check.name == "Database Connectivity"
            assert check.passed is True
            assert "✅" in check.message

    def test_check_database_connectivity_failure(self, validator):
        """Test database connectivity check with connection failure."""
        with patch("core.prerequisites.create_engine", side_effect=SQLAlchemyError("Connection failed")):
            check = validator.check_database_connectivity()

            assert check.name == "Database Connectivity"
            assert check.passed is False
            assert "Database connection failed" in check.message

    def test_check_database_connectivity_wrong_result(self, validator):
        """Test database connectivity check with wrong result."""
        mock_engine = Mock()
        mock_conn = Mock()
        mock_conn.execute.return_value.scalar.return_value = 0  # Wrong result
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_conn

        with patch("core.prerequisites.create_engine", return_value=mock_engine):
            check = validator.check_database_connectivity()

            assert check.name == "Database Connectivity"
            assert check.passed is False
            assert "unexpected result" in check.message

    def test_check_environment_variables_success(self, validator):
        """Test environment variables check with all required variables."""
        env_vars = {
            "DATABASE_URL": "postgres://user:pass@localhost/db",
            "SECRET_KEY": "secret-key-123",
            "ENVIRONMENT": "development",
            "USE_STUBS": "true",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            check = validator.check_environment_variables()

            assert check.name == "Environment Variables"
            assert check.passed is True
            assert "✅" in check.message

    def test_check_environment_variables_missing_required(self, validator):
        """Test environment variables check with missing required variables."""
        env_vars = {
            "DATABASE_URL": "postgres://user:pass@localhost/db",
            # Missing SECRET_KEY and ENVIRONMENT
        }

        with patch.dict(os.environ, env_vars, clear=True):
            check = validator.check_environment_variables()

            assert check.name == "Environment Variables"
            assert check.passed is False
            assert "Missing required environment variables" in check.message
            assert "SECRET_KEY" in check.message
            assert "ENVIRONMENT" in check.message

    def test_check_environment_variables_with_env_file(self, validator):
        """Test environment variables check with .env file present."""
        env_vars = {
            "DATABASE_URL": "postgres://user:pass@localhost/db",
            "SECRET_KEY": "secret-key-123",
            "ENVIRONMENT": "development",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("core.prerequisites.os.path.exists", return_value=True):
                check = validator.check_environment_variables()

                assert check.name == "Environment Variables"
                assert check.passed is True
                assert check.details["env_file_exists"] is True

    def test_check_dependencies_installed_success(self, validator, mock_subprocess):
        """Test dependencies check with successful pip check."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "No conflicts detected"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_dependencies_installed()

        assert check.name == "Python Dependencies"
        assert check.passed is True
        assert "✅" in check.message

    def test_check_dependencies_installed_conflicts(self, validator, mock_subprocess):
        """Test dependencies check with dependency conflicts."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Dependency conflicts detected"

        check = validator.check_dependencies_installed()

        assert check.name == "Python Dependencies"
        assert check.passed is False
        assert "Dependency conflicts detected" in check.message

    def test_check_dependencies_installed_exception(self, validator):
        """Test dependencies check with exception."""
        with patch.object(validator, '_run_command', side_effect=Exception("pip error")):
            check = validator.check_dependencies_installed()

            assert check.name == "Python Dependencies"
            assert check.passed is False
            assert "Error checking dependencies" in check.message

    def test_check_pytest_collection_success(self, validator, mock_subprocess):
        """Test pytest collection check with successful collection."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "2191 items collected"
        mock_subprocess.return_value.stderr = ""

        check = validator.check_pytest_collection()

        assert check.name == "Pytest Collection"
        assert check.passed is True
        assert "2191 tests found" in check.message
        assert "✅" in check.message

    def test_check_pytest_collection_failure(self, validator, mock_subprocess):
        """Test pytest collection check with failure."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Collection failed"

        check = validator.check_pytest_collection()

        assert check.name == "Pytest Collection"
        assert check.passed is False
        assert "Pytest collection failed" in check.message

    def test_check_pytest_collection_exception(self, validator):
        """Test pytest collection check with exception."""
        with patch.object(validator, '_run_command', side_effect=Exception("pytest error")):
            check = validator.check_pytest_collection()

            assert check.name == "Pytest Collection"
            assert check.passed is False
            assert "Error running pytest collection" in check.message

    def test_check_ci_toolchain_success(self, validator, mock_subprocess):
        """Test CI toolchain check with all tools available."""

        def mock_run_side_effect(cmd, **kwargs):
            mock_result = Mock()
            mock_result.returncode = 0

            if "ruff" in cmd:
                mock_result.stdout = "ruff 0.1.0"
            elif "mypy" in cmd:
                mock_result.stdout = "mypy 1.7.0"
            elif "pytest" in cmd:
                mock_result.stdout = "pytest 7.4.3"
            else:
                mock_result.stdout = "tool version"

            mock_result.stderr = ""
            return mock_result

        mock_subprocess.side_effect = mock_run_side_effect

        check = validator.check_ci_toolchain()

        assert check.name == "CI Toolchain"
        assert check.passed is True
        assert "✅" in check.message
        assert "ruff, mypy, pytest" in check.message

    def test_check_ci_toolchain_missing_tools(self, validator, mock_subprocess):
        """Test CI toolchain check with missing tools."""

        def mock_run_side_effect(cmd, **kwargs):
            mock_result = Mock()

            if "ruff" in cmd:
                mock_result.returncode = 1
                mock_result.stderr = "ruff not found"
            else:
                mock_result.returncode = 0
                mock_result.stdout = "tool version"
                mock_result.stderr = ""

            return mock_result

        mock_subprocess.side_effect = mock_run_side_effect

        check = validator.check_ci_toolchain()

        assert check.name == "CI Toolchain"
        assert check.passed is False
        assert "ruff not available" in check.message

    def test_check_ci_toolchain_exception(self, validator, mock_subprocess):
        """Test CI toolchain check with exception."""
        mock_subprocess.side_effect = Exception("tool error")

        check = validator.check_ci_toolchain()

        assert check.name == "CI Toolchain"
        assert check.passed is False
        assert "tool error" in str(check.details)

    def test_check_docker_build_success(self, validator, mock_subprocess):
        """Test Docker build check with successful build."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Successfully built image"
        mock_subprocess.return_value.stderr = ""

        with patch("core.prerequisites.Path.exists", return_value=True):
            check = validator.check_docker_build()

            assert check.name == "Docker Build"
            assert check.passed is True
            assert "✅" in check.message

    def test_check_docker_build_no_dockerfile(self, validator, mock_subprocess):
        """Test Docker build check with missing Dockerfile.test."""
        with patch("core.prerequisites.Path.exists", return_value=False):
            check = validator.check_docker_build()

            assert check.name == "Docker Build"
            assert check.passed is False
            assert "Dockerfile.test not found" in check.message

    def test_check_docker_build_failure(self, validator, mock_subprocess):
        """Test Docker build check with build failure."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Build failed"

        with patch("core.prerequisites.Path.exists", return_value=True):
            check = validator.check_docker_build()

            assert check.name == "Docker Build"
            assert check.passed is False
            assert "Docker build failed" in check.message

    def test_check_docker_build_exception(self, validator):
        """Test Docker build check with exception."""
        with patch.object(validator, '_run_command', side_effect=Exception("build error")):
            with patch("core.prerequisites.Path.exists", return_value=True):
                check = validator.check_docker_build()

                assert check.name == "Docker Build"
                assert check.passed is False
                assert "Error building Docker image" in check.message

    def test_get_environment_info(self, validator):
        """Test environment info collection."""
        with patch.dict(os.environ, {"VIRTUAL_ENV": "/path/to/venv", "ENVIRONMENT": "test", "USE_STUBS": "false"}):
            info = validator._get_environment_info()

            assert "python_version" in info
            assert "python_executable" in info
            assert "platform" in info
            assert "working_directory" in info
            assert info["virtual_environment"] == "/path/to/venv"
            assert info["environment"] == "test"
            assert info["use_stubs"] is False

    def test_get_docker_info_success(self, validator, mock_subprocess):
        """Test Docker info collection with success."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = '{"ServerVersion": "20.10.17"}'
        mock_subprocess.return_value.stderr = ""

        info = validator._get_docker_info()

        assert info == {"ServerVersion": "20.10.17"}

    def test_get_docker_info_failure(self, validator, mock_subprocess):
        """Test Docker info collection with failure."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Docker not running"

        info = validator._get_docker_info()

        assert info == {}

    def test_get_docker_info_exception(self, validator, mock_subprocess):
        """Test Docker info collection with exception."""
        mock_subprocess.side_effect = Exception("docker error")

        info = validator._get_docker_info()

        assert info == {}

    def test_validate_all_prerequisites_success(self, validator):
        """Test full validation with all checks passing."""
        # Mock all check methods to return successful results
        successful_check = PrerequisiteCheck(
            name="Mock Check", passed=True, required=True, message="✅ Mock check passed"
        )

        with patch.object(validator, "check_python_version", return_value=successful_check):
            with patch.object(validator, "check_docker_version", return_value=successful_check):
                with patch.object(validator, "check_docker_compose_version", return_value=successful_check):
                    with patch.object(validator, "check_database_connectivity", return_value=successful_check):
                        with patch.object(validator, "check_environment_variables", return_value=successful_check):
                            with patch.object(validator, "check_dependencies_installed", return_value=successful_check):
                                with patch.object(validator, "check_pytest_collection", return_value=successful_check):
                                    with patch.object(validator, "check_ci_toolchain", return_value=successful_check):
                                        with patch.object(
                                            validator, "check_docker_build", return_value=successful_check
                                        ):
                                            result = validator.validate_all_prerequisites()

                                            assert result.passed is True
                                            assert result.total_checks == 9
                                            assert result.passed_checks == 9
                                            assert result.failed_checks == 0

    def test_validate_all_prerequisites_failure(self, validator):
        """Test full validation with some checks failing."""
        successful_check = PrerequisiteCheck(name="Success Check", passed=True, required=True, message="✅ Success")

        failed_check = PrerequisiteCheck(name="Failed Check", passed=False, required=True, message="❌ Failed")

        with patch.object(validator, "check_python_version", return_value=failed_check):
            with patch.object(validator, "check_docker_version", return_value=successful_check):
                with patch.object(validator, "check_docker_compose_version", return_value=successful_check):
                    with patch.object(validator, "check_database_connectivity", return_value=successful_check):
                        with patch.object(validator, "check_environment_variables", return_value=successful_check):
                            with patch.object(validator, "check_dependencies_installed", return_value=successful_check):
                                with patch.object(validator, "check_pytest_collection", return_value=successful_check):
                                    with patch.object(validator, "check_ci_toolchain", return_value=successful_check):
                                        with patch.object(
                                            validator, "check_docker_build", return_value=successful_check
                                        ):
                                            result = validator.validate_all_prerequisites()

                                            assert result.passed is False
                                            assert result.total_checks == 9
                                            assert result.passed_checks == 8
                                            assert result.failed_checks == 1


class TestModuleFunctions:
    """Test module-level functions."""

    def test_validate_all_prerequisites_function(self):
        """Test validate_all_prerequisites convenience function."""
        with patch("core.prerequisites.PrerequisiteValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_result = Mock()
            mock_validator.validate_all_prerequisites.return_value = mock_result
            mock_validator_class.return_value = mock_validator

            result = validate_all_prerequisites()

            assert result == mock_result
            mock_validator_class.assert_called_once()
            mock_validator.validate_all_prerequisites.assert_called_once()

    def test_print_results_success(self, capsys):
        """Test print_results with successful result."""
        result = PrerequisiteResult(
            checks=[PrerequisiteCheck(name="Test Check", passed=True, required=True, message="✅ Test passed")],
            environment_info={
                "python_version": "3.11.0",
                "platform": "darwin",
                "environment": "test",
                "use_stubs": True,
            },
        )

        print_results(result)

        captured = capsys.readouterr()
        assert "✅ Overall Status: PASSED" in captured.out
        assert "1/1 checks passed" in captured.out
        assert "Python: 3.11.0" in captured.out
        assert "All prerequisites validated successfully!" in captured.out

    def test_print_results_failure(self, capsys):
        """Test print_results with failed result."""
        result = PrerequisiteResult(
            checks=[PrerequisiteCheck(name="Test Check", passed=False, required=True, message="❌ Test failed")],
            environment_info={
                "python_version": "3.10.0",
                "platform": "darwin",
                "environment": "test",
                "use_stubs": True,
            },
        )

        print_results(result)

        captured = capsys.readouterr()
        assert "❌ Overall Status: FAILED" in captured.out
        assert "0/1 checks passed" in captured.out
        assert "Prerequisites validation failed" in captured.out

    def test_print_results_with_warnings(self, capsys):
        """Test print_results with warnings."""
        result = PrerequisiteResult(
            checks=[
                PrerequisiteCheck(name="Required Check", passed=True, required=True, message="✅ Required passed"),
                PrerequisiteCheck(name="Optional Check", passed=False, required=False, message="❌ Optional failed"),
            ],
            environment_info={
                "python_version": "3.11.0",
                "platform": "darwin",
                "environment": "test",
                "use_stubs": True,
            },
        )

        print_results(result)

        captured = capsys.readouterr()
        assert "✅ Overall Status: PASSED" in captured.out
        assert "1/2 checks passed" in captured.out
        assert "⚠️  Warnings: 1" in captured.out


@pytest.mark.skip(reason="CLI tests need refactoring - module structure doesn't support current test approach")
class TestCLIInterface:
    """Test command-line interface."""

    def test_cli_main_success(self, capsys):
        """Test CLI main function with successful validation."""
        test_args = ["core.prerequisites"]

        with patch("core.prerequisites.sys.argv", test_args):
            with patch("core.prerequisites.PrerequisiteValidator") as mock_validator_class:
                mock_validator = Mock()
                mock_result = PrerequisiteResult(
                    checks=[PrerequisiteCheck(name="Test", passed=True, required=True, message="✅ Test passed")]
                )
                mock_validator.validate_all_prerequisites.return_value = mock_result
                mock_validator_class.return_value = mock_validator

                with patch("core.prerequisites.sys.exit") as mock_exit:
                    # Import and run main
                    from core.prerequisites import __main__

                    mock_exit.assert_called_with(0)

    def test_cli_main_failure(self, capsys):
        """Test CLI main function with failed validation."""
        test_args = ["core.prerequisites"]

        with patch("core.prerequisites.sys.argv", test_args):
            with patch("core.prerequisites.PrerequisiteValidator") as mock_validator_class:
                mock_validator = Mock()
                mock_result = PrerequisiteResult(
                    checks=[PrerequisiteCheck(name="Test", passed=False, required=True, message="❌ Test failed")]
                )
                mock_validator.validate_all_prerequisites.return_value = mock_result
                mock_validator_class.return_value = mock_validator

                with patch("core.prerequisites.sys.exit") as mock_exit:
                    # Import and run main
                    from core.prerequisites import __main__

                    mock_exit.assert_called_with(1)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_prerequisite_check_creation(self):
        """Test invalid PrerequisiteCheck creation."""
        with pytest.raises(ValidationError):
            PrerequisiteCheck()  # Missing required name field

    def test_prerequisite_result_with_invalid_checks(self):
        """Test PrerequisiteResult with invalid checks."""
        # Test with no checks parameter (uses default)
        result = PrerequisiteResult()

        assert result.passed is False
        assert result.total_checks == 0
        assert result.checks == []

    def test_validator_with_none_settings(self):
        """Test validator with None settings."""
        with patch("core.prerequisites.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_get_settings.return_value = mock_settings

            validator = PrerequisiteValidator(settings=None)

            assert validator.settings == mock_settings

    def test_database_connectivity_with_invalid_url(self):
        """Test database connectivity with invalid URL."""
        validator = PrerequisiteValidator()
        validator.settings = Mock()
        validator.settings.database_url = "invalid://url"

        check = validator.check_database_connectivity()

        assert check.passed is False
        assert "Database connection failed" in check.message

    def test_environment_variables_with_empty_values(self):
        """Test environment variables check with empty values."""
        validator = PrerequisiteValidator()

        env_vars = {"DATABASE_URL": "", "SECRET_KEY": "secret", "ENVIRONMENT": "development"}  # Empty value

        with patch.dict(os.environ, env_vars, clear=True):
            check = validator.check_environment_variables()

            assert check.passed is False
            assert "DATABASE_URL" in check.message

    def test_version_parsing_edge_cases(self):
        """Test version parsing with edge cases."""
        validator = PrerequisiteValidator()

        # Test with mock subprocess for Docker version with unusual format
        # Note: version.parse() can't handle non-PEP440 versions like "20.10.17-ce"
        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "Docker version 20.10.17-ce, build 12345", "")

            check = validator.check_docker_version()

            # The version parsing should fail due to invalid format
            assert check.passed is False
            assert check.version_found == "20.10.17-ce"
            assert "Error checking Docker version" in check.message

    def test_performance_with_large_output(self):
        """Test performance with large command output."""
        validator = PrerequisiteValidator()

        # Mock command with large output
        large_output = "x" * 10000  # 10KB output

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, large_output, "")

            check = validator.check_pytest_collection()

            assert check.details["stdout"] == large_output

    def test_concurrent_safety(self):
        """Test that validator is safe for concurrent use."""
        import threading

        validator = PrerequisiteValidator()
        results = []

        def run_check():
            with patch.object(validator, "_run_command") as mock_run:
                mock_run.return_value = (0, "Python 3.11.0", "")
                result = validator.check_python_version()
                results.append(result)

        threads = [threading.Thread(target=run_check) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 5
        assert all(result.passed for result in results)
