"""
Comprehensive tests for prerequisites validation system.

Tests critical infrastructure validation including:
- Python version validation
- Docker and Docker Compose version checking
- Database connectivity testing
- Environment variables validation
- Dependencies installation verification
- CI toolchain functionality
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from packaging.version import InvalidVersion

from core.prerequisites import (
    PrerequisiteCheck,
    PrerequisiteResult,
    PrerequisiteValidator,
    print_results,
    validate_all_prerequisites,
)


class TestPrerequisiteCheck:
    """Test PrerequisiteCheck model."""

    def test_prerequisite_check_creation(self):
        """Test basic PrerequisiteCheck creation."""
        check = PrerequisiteCheck(
            name="Test Check",
            required=True,
            passed=True,
            version_found="1.0.0",
            version_required=">=1.0.0",
            message="Test passed",
            details={"test": True},
        )

        assert check.name == "Test Check"
        assert check.required is True
        assert check.passed is True
        assert check.version_found == "1.0.0"
        assert check.version_required == ">=1.0.0"
        assert check.message == "Test passed"
        assert check.details == {"test": True}

    def test_prerequisite_check_defaults(self):
        """Test PrerequisiteCheck default values."""
        check = PrerequisiteCheck(name="Test Check")

        assert check.name == "Test Check"
        assert check.required is True
        assert check.passed is False
        assert check.version_found is None
        assert check.version_required is None
        assert check.message == ""
        assert check.details == {}


class TestPrerequisiteResult:
    """Test PrerequisiteResult model."""

    def test_prerequisite_result_empty(self):
        """Test empty PrerequisiteResult."""
        result = PrerequisiteResult()

        assert result.passed is False
        assert result.total_checks == 0
        assert result.passed_checks == 0
        assert result.failed_checks == 0
        assert result.warning_checks == 0
        assert result.checks == []
        assert result.environment_info == {}

    def test_prerequisite_result_with_passing_checks(self):
        """Test PrerequisiteResult with all passing checks."""
        checks = [
            PrerequisiteCheck(name="Check 1", required=True, passed=True),
            PrerequisiteCheck(name="Check 2", required=True, passed=True),
            PrerequisiteCheck(name="Check 3", required=False, passed=True),
        ]

        result = PrerequisiteResult(checks=checks)

        assert result.passed is True
        assert result.total_checks == 3
        assert result.passed_checks == 3
        assert result.failed_checks == 0
        assert result.warning_checks == 0

    def test_prerequisite_result_with_failing_required_check(self):
        """Test PrerequisiteResult with failing required check."""
        checks = [
            PrerequisiteCheck(name="Check 1", required=True, passed=True),
            PrerequisiteCheck(name="Check 2", required=True, passed=False),
            PrerequisiteCheck(name="Check 3", required=False, passed=False),
        ]

        result = PrerequisiteResult(checks=checks)

        assert result.passed is False
        assert result.total_checks == 3
        assert result.passed_checks == 1
        assert result.failed_checks == 1
        assert result.warning_checks == 1

    def test_prerequisite_result_with_failing_optional_check(self):
        """Test PrerequisiteResult with failing optional check only."""
        checks = [
            PrerequisiteCheck(name="Check 1", required=True, passed=True),
            PrerequisiteCheck(name="Check 2", required=True, passed=True),
            PrerequisiteCheck(name="Check 3", required=False, passed=False),
        ]

        result = PrerequisiteResult(checks=checks)

        assert result.passed is True  # Optional failure doesn't fail overall
        assert result.total_checks == 3
        assert result.passed_checks == 2
        assert result.failed_checks == 0
        assert result.warning_checks == 1


class TestPrerequisiteValidator:
    """Test PrerequisiteValidator class."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        with patch("core.prerequisites.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            validator = PrerequisiteValidator()

            assert validator.settings is not None
            assert validator.checks == []

    def test_validator_initialization_with_settings(self):
        """Test validator initialization with custom settings."""
        settings = Mock()
        validator = PrerequisiteValidator(settings=settings)

        assert validator.settings is settings
        assert validator.checks == []

    def test_run_command_success(self):
        """Test successful command execution."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "test output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            exit_code, stdout, stderr = validator._run_command(["echo", "test"])

            assert exit_code == 0
            assert stdout == "test output"
            assert stderr == ""

    def test_run_command_failure(self):
        """Test failed command execution."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "error output"
            mock_run.return_value = mock_result

            exit_code, stdout, stderr = validator._run_command(["false"])

            assert exit_code == 1
            assert stdout == ""
            assert stderr == "error output"

    def test_run_command_timeout(self):
        """Test command timeout handling."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 1)

            exit_code, stdout, stderr = validator._run_command(["sleep", "10"], timeout=1)

            assert exit_code == -1
            assert stdout == ""
            assert "timed out" in stderr

    def test_run_command_file_not_found(self):
        """Test command not found handling."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            exit_code, stdout, stderr = validator._run_command(["nonexistent_command"])

            assert exit_code == -1
            assert stdout == ""
            assert "Command not found" in stderr

    def test_check_python_version_valid(self):
        """Test Python version check with valid version."""
        validator = PrerequisiteValidator(settings=Mock())

        # Create a mock version_info with proper attributes
        mock_version_info = Mock()
        mock_version_info.major = 3
        mock_version_info.minor = 11
        mock_version_info.micro = 5

        with patch.object(sys, "version_info", mock_version_info):
            check = validator.check_python_version()

            assert check.name == "Python Version"
            assert check.required is True
            assert check.passed is True
            assert check.version_found == "3.11.5"
            assert check.version_required == "3.11.x"
            assert "✅" in check.message
            assert "3.11.5" in check.message

    def test_check_python_version_invalid(self):
        """Test Python version check with invalid version."""
        validator = PrerequisiteValidator(settings=Mock())

        # Create a mock version_info with proper attributes
        mock_version_info = Mock()
        mock_version_info.major = 3
        mock_version_info.minor = 10
        mock_version_info.micro = 0

        with patch.object(sys, "version_info", mock_version_info):
            check = validator.check_python_version()

            assert check.name == "Python Version"
            assert check.required is True
            assert check.passed is False
            assert check.version_found == "3.10.0"
            assert "❌" in check.message
            assert "3.10.0" in check.message

    def test_check_python_version_exception(self):
        """Test Python version check with exception."""
        validator = PrerequisiteValidator(settings=Mock())

        # Test with actual exception in the version access by patching the specific access
        with patch("core.prerequisites.sys") as mock_sys:
            # Make accessing major attribute raise an exception
            mock_version_info = Mock()
            type(mock_version_info).major = PropertyMock(side_effect=Exception("Test error"))
            mock_sys.version_info = mock_version_info

            check = validator.check_python_version()

            assert check.passed is False
            assert "Error checking Python version" in check.message
            assert check.details["error"] == "Test error"

    def test_check_docker_version_valid(self):
        """Test Docker version check with valid version."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "Docker version 20.10.17, build 100c701", "")

            check = validator.check_docker_version()

            assert check.name == "Docker Version"
            assert check.required is True
            assert check.passed is True
            assert check.version_found == "20.10.17"
            assert "✅" in check.message

    def test_check_docker_version_invalid(self):
        """Test Docker version check with invalid version."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "Docker version 19.03.12, build 48a66213fe", "")

            check = validator.check_docker_version()

            assert check.passed is False
            assert check.version_found == "19.03.12"
            assert "❌" in check.message

    def test_check_docker_version_not_found(self):
        """Test Docker version check when Docker not found."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (1, "", "docker: command not found")

            check = validator.check_docker_version()

            assert check.passed is False
            assert "Docker not found" in check.message

    def test_check_docker_compose_version_valid(self):
        """Test Docker Compose version check with valid version."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "Docker Compose version v2.17.2", "")

            check = validator.check_docker_compose_version()

            assert check.passed is True
            assert check.version_found == "2.17.2"
            assert "✅" in check.message

    def test_check_docker_compose_version_with_suffix(self):
        """Test Docker Compose version check with version suffix."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "Docker Compose version v2.37.1-desktop.1", "")

            check = validator.check_docker_compose_version()

            assert check.passed is True
            assert check.version_found == "2.37.1-desktop.1"
            assert "✅" in check.message

    def test_check_docker_compose_version_invalid(self):
        """Test Docker Compose version check with invalid version."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "Docker Compose version v1.29.2", "")

            check = validator.check_docker_compose_version()

            assert check.passed is False
            assert check.version_found == "1.29.2"
            assert "❌" in check.message

    def test_check_database_connectivity_success(self):
        """Test successful database connectivity check."""
        mock_settings = Mock()
        mock_settings.database_url = "postgresql://user:pass@localhost:5432/test"
        validator = PrerequisiteValidator(settings=mock_settings)

        with patch("core.prerequisites.create_engine") as mock_create_engine:
            mock_engine = Mock()
            mock_connection = Mock()
            mock_connection.execute.return_value.scalar.return_value = 1

            # Properly mock the context manager using MagicMock
            from unittest.mock import MagicMock

            mock_context_manager = MagicMock()
            mock_context_manager.__enter__.return_value = mock_connection
            mock_context_manager.__exit__.return_value = None
            mock_engine.connect.return_value = mock_context_manager
            mock_engine.dialect.name = "postgresql"
            mock_create_engine.return_value = mock_engine

            check = validator.check_database_connectivity()

            assert check.passed is True
            assert "✅" in check.message
            assert "Database connection successful" in check.message
            assert "postgresql" in check.details["driver"]

    def test_check_database_connectivity_failure(self):
        """Test failed database connectivity check."""
        mock_settings = Mock()
        mock_settings.database_url = "postgresql://user:pass@localhost:5432/test"
        validator = PrerequisiteValidator(settings=mock_settings)

        with patch("core.prerequisites.create_engine") as mock_create_engine:
            mock_create_engine.side_effect = Exception("Connection failed")

            check = validator.check_database_connectivity()

            assert check.passed is False
            assert "❌" in check.message
            assert "Connection failed" in check.message

    def test_check_environment_variables_success(self):
        """Test environment variables check with all required vars."""
        validator = PrerequisiteValidator(settings=Mock())

        env_vars = {
            "DATABASE_URL": "postgresql://localhost/test",
            "SECRET_KEY": "test-secret-key",
            "ENVIRONMENT": "test",
            "USE_STUBS": "true",
            "LOG_LEVEL": "INFO",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            check = validator.check_environment_variables()

            assert check.passed is True
            assert "✅" in check.message
            assert "All required environment variables found" in check.message

    def test_check_environment_variables_missing_required(self):
        """Test environment variables check with missing required vars."""
        validator = PrerequisiteValidator(settings=Mock())

        env_vars = {
            "SECRET_KEY": "test-secret-key",
            # Missing DATABASE_URL and ENVIRONMENT
        }

        with patch.dict(os.environ, env_vars, clear=True):
            check = validator.check_environment_variables()

            assert check.passed is False
            assert "❌" in check.message
            assert "Missing required environment variables" in check.message
            assert "DATABASE_URL" in check.message

    def test_check_dependencies_installed_success(self):
        """Test dependencies check with successful pip check."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.side_effect = [
                (0, "No broken requirements found.", ""),  # pip check
                (0, "package1==1.0.0\npackage2==2.0.0", ""),  # pip list
            ]

            check = validator.check_dependencies_installed()

            assert check.passed is True
            assert "✅" in check.message
            assert "correctly installed" in check.message

    def test_check_dependencies_installed_failure(self):
        """Test dependencies check with pip check failure."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.side_effect = [
                (1, "", "package1 has requirement package2>=2.0.0, but you have package2 1.0.0"),
                (0, "package1==1.0.0\npackage2==1.0.0", ""),
            ]

            check = validator.check_dependencies_installed()

            assert check.passed is False
            assert "❌" in check.message
            assert "Dependency conflicts detected" in check.message

    def test_check_pytest_collection_success(self):
        """Test pytest collection check with successful collection."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (0, "2191 items collected in 5.23s", "")

            check = validator.check_pytest_collection()

            assert check.passed is True
            assert "✅" in check.message
            assert "2191 tests found" in check.message

    def test_check_pytest_collection_failure(self):
        """Test pytest collection check with collection failure."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.return_value = (1, "", "SyntaxError: invalid syntax")

            check = validator.check_pytest_collection()

            assert check.passed is False
            assert "❌" in check.message
            assert "Pytest collection failed" in check.message

    def test_check_ci_toolchain_success(self):
        """Test CI toolchain check with all tools available."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.side_effect = [
                (0, "ruff 0.1.6", ""),  # ruff --version
                (0, "mypy 1.7.1", ""),  # mypy --version
                (0, "pytest 7.4.3", ""),  # pytest --version
            ]

            check = validator.check_ci_toolchain()

            assert check.passed is True
            assert "✅" in check.message
            assert "CI toolchain" in check.message
            assert check.details["tools"]["ruff"]["available"] is True
            assert check.details["tools"]["mypy"]["available"] is True
            assert check.details["tools"]["pytest"]["available"] is True

    def test_check_ci_toolchain_missing_tools(self):
        """Test CI toolchain check with missing tools."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch.object(validator, "_run_command") as mock_run:
            mock_run.side_effect = [
                (1, "", "ruff: command not found"),  # ruff --version
                (0, "mypy 1.7.1", ""),  # mypy --version
                (0, "pytest 7.4.3", ""),  # pytest --version
            ]

            check = validator.check_ci_toolchain()

            assert check.passed is False
            assert "❌" in check.message
            assert "ruff not available" in check.message

    def test_check_docker_build_success(self):
        """Test Docker build check with successful build."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            with patch.object(validator, "_run_command") as mock_run:
                mock_run.return_value = (0, "Successfully built abc123", "")

                check = validator.check_docker_build()

                assert check.passed is True
                assert "✅" in check.message
                assert "builds successfully" in check.message

    def test_check_docker_build_no_dockerfile(self):
        """Test Docker build check with missing Dockerfile."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            check = validator.check_docker_build()

            assert check.passed is False
            assert "❌" in check.message
            assert "Dockerfile.test not found" in check.message

    def test_check_docker_build_failure(self):
        """Test Docker build check with build failure."""
        validator = PrerequisiteValidator(settings=Mock())

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            with patch.object(validator, "_run_command") as mock_run:
                mock_run.return_value = (1, "", "Build failed: syntax error")

                check = validator.check_docker_build()

                assert check.passed is False
                assert "❌" in check.message
                assert "Docker build failed" in check.message

    def test_validate_all_prerequisites(self):
        """Test complete prerequisite validation."""
        mock_settings = Mock()
        validator = PrerequisiteValidator(settings=mock_settings)

        # Mock all individual check methods
        with (
            patch.object(validator, "check_python_version") as mock_python,
            patch.object(validator, "check_docker_version") as mock_docker,
            patch.object(validator, "check_docker_compose_version") as mock_compose,
            patch.object(validator, "check_database_connectivity") as mock_db,
            patch.object(validator, "check_environment_variables") as mock_env,
            patch.object(validator, "check_dependencies_installed") as mock_deps,
            patch.object(validator, "check_pytest_collection") as mock_pytest,
            patch.object(validator, "check_ci_toolchain") as mock_ci,
            patch.object(validator, "check_docker_build") as mock_build,
        ):
            # Configure mocks to return passing checks
            mock_python.return_value = PrerequisiteCheck(name="Python", passed=True, required=True)
            mock_docker.return_value = PrerequisiteCheck(name="Docker", passed=True, required=True)
            mock_compose.return_value = PrerequisiteCheck(name="Compose", passed=True, required=True)
            mock_db.return_value = PrerequisiteCheck(name="Database", passed=True, required=True)
            mock_env.return_value = PrerequisiteCheck(name="Environment", passed=True, required=True)
            mock_deps.return_value = PrerequisiteCheck(name="Dependencies", passed=True, required=True)
            mock_pytest.return_value = PrerequisiteCheck(name="Pytest", passed=True, required=True)
            mock_ci.return_value = PrerequisiteCheck(name="CI", passed=True, required=True)
            mock_build.return_value = PrerequisiteCheck(name="Build", passed=True, required=False)

            result = validator.validate_all_prerequisites()

            assert result.passed is True
            assert result.total_checks == 9
            assert result.passed_checks == 9
            assert result.failed_checks == 0

            # Verify all check methods were called
            mock_python.assert_called_once()
            mock_docker.assert_called_once()
            mock_compose.assert_called_once()
            mock_db.assert_called_once()
            mock_env.assert_called_once()
            mock_deps.assert_called_once()
            mock_pytest.assert_called_once()
            mock_ci.assert_called_once()
            mock_build.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_validate_all_prerequisites_function(self):
        """Test validate_all_prerequisites convenience function."""
        with patch("core.prerequisites.PrerequisiteValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_result = Mock()
            mock_validator.validate_all_prerequisites.return_value = mock_result
            mock_validator_class.return_value = mock_validator

            result = validate_all_prerequisites()

            assert result is mock_result
            mock_validator_class.assert_called_once()
            mock_validator.validate_all_prerequisites.assert_called_once()

    def test_print_results_passing(self):
        """Test print_results with passing result."""
        result = PrerequisiteResult(
            checks=[
                PrerequisiteCheck(name="Test", passed=True, required=True),
            ],
            environment_info={
                "python_version": "3.11.5",
                "platform": "linux",
                "environment": "test",
                "use_stubs": True,
            },
        )

        with patch("builtins.print") as mock_print:
            print_results(result)

            # Verify expected output elements
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            output = "\n".join(print_calls)

            assert "LEADFACTORY PREREQUISITES VALIDATION" in output
            assert "✅ Overall Status: PASSED" in output
            assert "1/1 checks passed" in output
            assert "Python: 3.11.5" in output
            assert "All prerequisites validated successfully!" in output

    def test_print_results_failing(self):
        """Test print_results with failing result."""
        result = PrerequisiteResult(
            checks=[
                PrerequisiteCheck(name="Test1", passed=True, required=True),
                PrerequisiteCheck(name="Test2", passed=False, required=True, message="❌ Test failed"),
                PrerequisiteCheck(name="Test3", passed=False, required=False),
            ],
            environment_info={
                "python_version": "3.10.0",
                "platform": "linux",
                "environment": "test",
                "use_stubs": True,
            },
        )

        with patch("builtins.print") as mock_print:
            print_results(result)

            # Verify expected output elements
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            output = "\n".join(print_calls)

            assert "❌ Overall Status: FAILED" in output
            assert "1/3 checks passed" in output
            assert "❌ Failed: 1" in output
            assert "⚠️  Warnings: 1" in output
            assert "Prerequisites validation failed" in output
            assert "🔧 Recommendations:" in output


# Integration tests
class TestPrerequisitesIntegration:
    """Integration tests for prerequisites system."""

    def test_full_validation_cycle(self):
        """Test complete validation cycle with realistic data."""
        # Create a validator with actual settings
        with patch("core.prerequisites.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
            mock_get_settings.return_value = mock_settings

            validator = PrerequisiteValidator()

            # Mock system commands to simulate real environment
            def mock_run_command(cmd, timeout=30):
                if cmd[0] == "docker" and cmd[1] == "--version":
                    return (0, "Docker version 20.10.17, build 100c701", "")
                if cmd[0] == "docker-compose" and cmd[1] == "--version":
                    return (0, "Docker Compose version v2.17.2", "")
                if cmd[1:3] == ["-m", "pip"] and cmd[3] == "check":
                    return (0, "No broken requirements found.", "")
                if cmd[1:3] == ["-m", "pip"] and cmd[3] == "list":
                    return (0, "pytest==7.4.3\nruff==0.1.6", "")
                if cmd[1:3] == ["-m", "pytest"] and cmd[3] == "--collect-only":
                    return (0, "2191 items collected in 5.23s", "")
                if cmd[1:3] == ["-m", "ruff"]:
                    return (0, "ruff 0.1.6", "")
                if cmd[1:3] == ["-m", "mypy"]:
                    return (0, "mypy 1.7.1", "")
                if cmd[1:3] == ["-m", "pytest"] and cmd[3] == "--version":
                    return (0, "pytest 7.4.3", "")
                return (1, "", "Command not found")

            # Create mock version_info with proper attributes
            mock_version_info = Mock()
            mock_version_info.major = 3
            mock_version_info.minor = 11
            mock_version_info.micro = 5

            with (
                patch.object(validator, "_run_command", side_effect=mock_run_command),
                patch.object(sys, "version_info", mock_version_info),
                patch("core.prerequisites.create_engine") as mock_engine,
                patch.dict(
                    os.environ,
                    {
                        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
                        "SECRET_KEY": "test-secret",
                        "ENVIRONMENT": "test",
                    },
                ),
            ):
                # Mock database connection
                mock_conn = Mock()
                mock_conn.execute.return_value.scalar.return_value = 1

                # Properly mock the context manager using MagicMock
                from unittest.mock import MagicMock

                mock_context_manager = MagicMock()
                mock_context_manager.__enter__.return_value = mock_conn
                mock_context_manager.__exit__.return_value = None
                mock_engine.return_value.connect.return_value = mock_context_manager
                mock_engine.return_value.dialect.name = "postgresql"

                result = validator.validate_all_prerequisites()

                # Should have successful validation
                assert result.passed is True
                assert result.total_checks == 9
                assert result.failed_checks == 0

                # Verify environment info is populated
                assert result.environment_info["python_version"] == "3.11.5"
                assert result.environment_info["environment"] == "test"

    def test_command_line_interface_json_output(self):
        """Test command line interface with JSON output."""
        test_result = PrerequisiteResult(
            checks=[PrerequisiteCheck(name="Test", passed=True, required=True)],
            environment_info={"python_version": "3.11.5"},
        )

        with patch("core.prerequisites.PrerequisiteValidator") as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_all_prerequisites.return_value = test_result
            mock_validator_class.return_value = mock_validator

            with (
                patch("sys.argv", ["prerequisites.py", "--json"]),
                patch("builtins.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                # Import and run main
                from core.prerequisites import main

                # Call main function
                main()

                # Verify JSON output
                mock_print.assert_called_once()
                output = mock_print.call_args[0][0]
                parsed = json.loads(output)

                assert parsed["passed"] is True
                assert parsed["total_checks"] == 1
                assert len(parsed["checks"]) == 1
                assert parsed["checks"][0]["name"] == "Test"
                mock_exit.assert_called_once_with(0)
