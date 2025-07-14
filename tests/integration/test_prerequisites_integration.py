"""
Integration tests for prerequisites validation in Docker environment.

These tests verify that the prerequisites validation system works correctly
in the actual Docker environment where CI runs.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from core.prerequisites import PrerequisiteValidator, validate_all_prerequisites


class TestPrerequisitesIntegration:
    """Integration tests for prerequisites validation."""

    def test_validate_all_prerequisites_real_environment(self):
        """Test full validation in real environment."""
        result = validate_all_prerequisites()

        # Check that all critical checks are present
        check_names = [check.name for check in result.checks]
        expected_checks = [
            "Python Version",
            "Docker Version",
            "Docker Compose Version",
            "Database Connectivity",
            "Environment Variables",
            "Python Dependencies",
            "Pytest Collection",
            "CI Toolchain",
        ]

        for expected_check in expected_checks:
            assert expected_check in check_names, f"Missing check: {expected_check}"

        # Verify result structure
        assert isinstance(result.total_checks, int)
        assert result.total_checks > 0
        assert isinstance(result.passed_checks, int)
        assert isinstance(result.failed_checks, int)
        assert isinstance(result.warning_checks, int)
        assert result.passed_checks + result.failed_checks + result.warning_checks == result.total_checks

        # Check environment info is populated
        assert result.environment_info
        assert "python_version" in result.environment_info
        assert "platform" in result.environment_info
        assert "working_directory" in result.environment_info

    def test_python_version_check_real(self):
        """Test Python version check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_python_version()

        assert check.name == "Python Version"
        assert check.version_found is not None
        assert check.version_required == "3.11.x"
        assert check.message
        assert check.details

        # Check that version info is populated
        assert "version_info" in check.details
        assert "executable" in check.details
        assert "platform" in check.details

        # In CI environment, we should have the correct Python version
        if os.getenv("CI"):
            assert check.passed is True
            assert check.version_found.startswith("3.11.")

    def test_docker_version_check_real(self):
        """Test Docker version check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_docker_version()

        assert check.name == "Docker Version"
        assert check.version_required == "≥ 20.10"
        assert check.message

        # If Docker is available, check version info
        if check.passed:
            assert check.version_found is not None
            assert check.details
            assert "version_output" in check.details

    def test_docker_compose_version_check_real(self):
        """Test Docker Compose version check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_docker_compose_version()

        assert check.name == "Docker Compose Version"
        assert check.version_required == "≥ 2.0"
        assert check.message

        # If Docker Compose is available, check version info
        if check.passed:
            assert check.version_found is not None
            assert check.details
            assert "version_output" in check.details

    def test_database_connectivity_check_real(self):
        """Test database connectivity check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_database_connectivity()

        assert check.name == "Database Connectivity"
        assert check.message
        assert check.details

        # Check that database URL is masked in details
        if "database_url" in check.details:
            assert "****" in check.details["database_url"] or "test" in check.details["database_url"]

    def test_environment_variables_check_real(self):
        """Test environment variables check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_environment_variables()

        assert check.name == "Environment Variables"
        assert check.message
        assert check.details

        # Check that details contain expected keys
        assert "found_variables" in check.details
        assert "missing_required" in check.details
        assert "missing_optional" in check.details
        assert "env_file_exists" in check.details

        # Check that sensitive data is masked
        found_vars = check.details["found_variables"]
        for var_name, var_value in found_vars.items():
            if "KEY" in var_name or "SECRET" in var_name or "PASSWORD" in var_name:
                assert "****" in var_value or var_value == "not_set"

    def test_dependencies_check_real(self):
        """Test dependencies check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_dependencies_installed()

        assert check.name == "Python Dependencies"
        assert check.message
        assert check.details

        # Check that details contain expected keys
        assert "pip_check_output" in check.details
        assert "pip_check_errors" in check.details
        assert "installed_packages_count" in check.details
        assert "requirements_files" in check.details

        # Check that requirements files info is populated
        req_files = check.details["requirements_files"]
        assert "requirements.txt" in req_files
        assert "requirements-dev.txt" in req_files
        assert isinstance(req_files["requirements.txt"], bool)
        assert isinstance(req_files["requirements-dev.txt"], bool)

    def test_pytest_collection_check_real(self):
        """Test pytest collection check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_pytest_collection()

        assert check.name == "Pytest Collection"
        assert check.message
        assert check.details

        # Check that details contain expected keys
        assert "exit_code" in check.details
        assert "stdout" in check.details
        assert "stderr" in check.details
        assert "test_directory_exists" in check.details

        # In our environment, tests directory should exist
        assert check.details["test_directory_exists"] is True

        # If collection succeeds, we should have test count info
        if check.passed:
            assert "tests found" in check.message or "items collected" in check.details["stdout"]

    def test_ci_toolchain_check_real(self):
        """Test CI toolchain check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_ci_toolchain()

        assert check.name == "CI Toolchain"
        assert check.message
        assert check.details

        # Check that details contain tools info
        assert "tools" in check.details
        tools = check.details["tools"]

        # Check that all expected tools are tested
        expected_tools = ["ruff", "mypy", "pytest"]
        for tool in expected_tools:
            assert tool in tools
            assert "available" in tools[tool]
            assert isinstance(tools[tool]["available"], bool)

            # If tool is available, check version info
            if tools[tool]["available"]:
                assert "version" in tools[tool]
                assert tools[tool]["version"] is not None

    def test_docker_build_check_real(self):
        """Test Docker build check in real environment."""
        validator = PrerequisiteValidator()
        check = validator.check_docker_build()

        assert check.name == "Docker Build"
        assert check.message
        assert check.details

        # Check that details contain expected keys
        assert "dockerfile_exists" in check.details

        # In our environment, Dockerfile.test should exist
        assert check.details["dockerfile_exists"] is True

        # If build succeeds or fails, we should have build info
        if "build_exit_code" in check.details:
            assert isinstance(check.details["build_exit_code"], int)
            assert "build_output" in check.details
            assert "build_errors" in check.details

    def test_get_environment_info_real(self):
        """Test environment info collection in real environment."""
        validator = PrerequisiteValidator()
        info = validator._get_environment_info()

        # Check that all expected keys are present
        expected_keys = [
            "python_version",
            "python_executable",
            "platform",
            "working_directory",
            "virtual_environment",
            "environment",
            "use_stubs",
        ]

        for key in expected_keys:
            assert key in info

        # Check that values are reasonable
        assert info["python_version"]  # Should not be empty
        assert info["python_executable"]  # Should not be empty
        assert info["platform"]  # Should not be empty
        assert info["working_directory"]  # Should not be empty
        assert isinstance(info["use_stubs"], bool)

        # Check that paths are absolute
        assert os.path.isabs(info["python_executable"])
        assert os.path.isabs(info["working_directory"])

    def test_get_docker_info_real(self):
        """Test Docker info collection in real environment."""
        validator = PrerequisiteValidator()
        info = validator._get_docker_info()

        # Docker info should be a dict (empty if Docker not available)
        assert isinstance(info, dict)

        # If Docker is available, check for common fields
        if info:
            # Docker info usually contains these fields
            possible_fields = ["ServerVersion", "Platform", "Architecture", "KernelVersion", "OperatingSystem"]

            # At least one of these should be present
            assert any(field in info for field in possible_fields)

    def test_command_execution_real(self):
        """Test command execution in real environment."""
        validator = PrerequisiteValidator()

        # Test successful command
        exit_code, stdout, stderr = validator._run_command(["echo", "test"])
        assert exit_code == 0
        assert "test" in stdout
        assert stderr == ""

        # Test failed command
        exit_code, stdout, stderr = validator._run_command(["false"])
        assert exit_code != 0

        # Test command with timeout
        exit_code, stdout, stderr = validator._run_command(["sleep", "0.1"], timeout=1)
        assert exit_code == 0

        # Test non-existent command
        exit_code, stdout, stderr = validator._run_command(["nonexistent-command-12345"])
        assert exit_code == -1
        assert "Command not found" in stderr

    def test_cli_interface_real(self):
        """Test CLI interface in real environment."""
        # Test full validation via CLI
        result = subprocess.run([sys.executable, "-m", "core.prerequisites"], capture_output=True, text=True)

        # Should exit with 0 or 1 (success or failure)
        assert result.returncode in [0, 1]

        # Should produce output
        assert result.stdout

        # Should contain expected sections
        assert "PREREQUISITES VALIDATION" in result.stdout
        assert "Overall Status:" in result.stdout
        assert "Summary:" in result.stdout

        # Test JSON output
        result_json = subprocess.run(
            [sys.executable, "-m", "core.prerequisites", "--json"], capture_output=True, text=True
        )

        assert result_json.returncode in [0, 1]

        # Should be valid JSON
        try:
            data = json.loads(result_json.stdout)
            assert "passed" in data
            assert "total_checks" in data
            assert "checks" in data
            assert isinstance(data["checks"], list)
        except json.JSONDecodeError:
            pytest.fail("CLI JSON output is not valid JSON")

        # Test specific check
        result_specific = subprocess.run(
            [sys.executable, "-m", "core.prerequisites", "--check", "python"], capture_output=True, text=True
        )

        assert result_specific.returncode in [0, 1]
        assert result_specific.stdout

        # Test quiet mode
        result_quiet = subprocess.run(
            [sys.executable, "-m", "core.prerequisites", "--quiet"], capture_output=True, text=True
        )

        assert result_quiet.returncode in [0, 1]
        # Quiet mode should produce minimal output
        assert len(result_quiet.stdout) < len(result.stdout)

    def test_performance_integration(self):
        """Test performance of prerequisites validation."""
        import time

        # Full validation should complete in reasonable time
        start_time = time.time()
        result = validate_all_prerequisites()
        end_time = time.time()

        duration = end_time - start_time

        # Should complete within 60 seconds (reasonable for CI)
        assert duration < 60, f"Validation took {duration:.2f} seconds, which is too long"

        # Should complete basic checks quickly
        assert result.total_checks > 0
        assert result.checks

        # Each check should have reasonable execution time info
        for check in result.checks:
            assert check.name
            assert check.message
            assert isinstance(check.passed, bool)
            assert isinstance(check.required, bool)

    def test_error_handling_integration(self):
        """Test error handling in real environment."""
        validator = PrerequisiteValidator()

        # Test with invalid database URL
        original_url = validator.settings.database_url
        validator.settings.database_url = "invalid://url"

        check = validator.check_database_connectivity()
        assert check.passed is False
        assert "Database connection failed" in check.message

        # Restore original URL
        validator.settings.database_url = original_url

        # Test with command that times out
        exit_code, stdout, stderr = validator._run_command(["sleep", "10"], timeout=1)
        assert exit_code == -1
        assert "timed out" in stderr

    def test_concurrent_validation(self):
        """Test concurrent validation execution."""
        import threading
        import time

        results = []
        errors = []

        def run_validation():
            try:
                result = validate_all_prerequisites()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run multiple validations concurrently
        threads = []
        for i in range(3):
            thread = threading.Thread(target=run_validation)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=120)  # 2 minutes timeout

        # Check results
        assert len(errors) == 0, f"Concurrent validation errors: {errors}"
        assert len(results) == 3

        # All results should be consistent
        for result in results:
            assert isinstance(result.total_checks, int)
            assert result.total_checks > 0
            assert len(result.checks) == result.total_checks

    def test_integration_with_settings(self):
        """Test integration with actual settings."""
        from core.config import get_settings

        settings = get_settings()
        validator = PrerequisiteValidator(settings=settings)

        # Test that validator uses actual settings
        assert validator.settings == settings

        # Test database connectivity with real settings
        check = validator.check_database_connectivity()
        assert check.name == "Database Connectivity"
        assert check.details

        # Check that database URL is from settings
        if hasattr(settings, "database_url"):
            # URL should be masked in details
            if "database_url" in check.details:
                assert "****" in check.details["database_url"] or "test" in check.details["database_url"]

    def test_integration_with_existing_setup(self):
        """Test integration with existing setup.sh script."""
        setup_script = Path("setup.sh")

        if setup_script.exists():
            # Test that our validation complements the setup script
            result = validate_all_prerequisites()

            # If setup.sh exists, basic requirements should be checked
            check_names = [check.name for check in result.checks]

            # These checks should align with setup.sh requirements
            expected_checks = [
                "Python Version",
                "Docker Version",
                "Docker Compose Version",
                "Environment Variables",
                "Python Dependencies",
            ]

            for expected_check in expected_checks:
                assert expected_check in check_names

    def test_docker_environment_specific_checks(self):
        """Test checks specific to Docker environment."""
        validator = PrerequisiteValidator()

        # Test that Docker-specific checks work
        docker_check = validator.check_docker_version()
        compose_check = validator.check_docker_compose_version()
        build_check = validator.check_docker_build()

        # These checks should provide useful information
        assert docker_check.message
        assert compose_check.message
        assert build_check.message

        # If we're in a Docker environment, these should pass
        if os.getenv("DOCKER_CONTAINER"):
            # Inside Docker container, docker command might not be available
            # but the checks should handle this gracefully
            assert docker_check.details
            assert compose_check.details
            assert build_check.details

    def test_ci_environment_specific_checks(self):
        """Test checks specific to CI environment."""
        validator = PrerequisiteValidator()

        # Test CI toolchain
        ci_check = validator.check_ci_toolchain()
        assert ci_check.message
        assert ci_check.details

        # In CI environment, these tools should be available
        if os.getenv("CI"):
            tools = ci_check.details.get("tools", {})

            # pytest should always be available in CI
            assert "pytest" in tools
            assert tools["pytest"]["available"] is True

            # Other tools might be available
            for tool_name in ["ruff", "mypy"]:
                if tool_name in tools:
                    tool_info = tools[tool_name]
                    assert "available" in tool_info
                    if tool_info["available"]:
                        assert "version" in tool_info

    def test_memory_usage_integration(self):
        """Test memory usage during validation."""
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Run validation
        result = validate_all_prerequisites()

        # Get final memory usage
        final_memory = process.memory_info().rss

        # Memory usage should not increase dramatically
        memory_increase = final_memory - initial_memory

        # Should not use more than 100MB of additional memory
        assert memory_increase < 100 * 1024 * 1024, f"Memory usage increased by {memory_increase / 1024 / 1024:.2f} MB"

        # Validation should complete successfully
        assert result.total_checks > 0

    def test_file_system_integration(self):
        """Test file system integration."""
        validator = PrerequisiteValidator()

        # Test that validator can access expected files
        info = validator._get_environment_info()

        # Working directory should be accessible
        assert os.path.exists(info["working_directory"])
        assert os.access(info["working_directory"], os.R_OK)

        # Python executable should be accessible
        assert os.path.exists(info["python_executable"])
        assert os.access(info["python_executable"], os.X_OK)

        # Test that validation can create temporary files if needed
        with tempfile.TemporaryDirectory() as temp_dir:
            # This should work without issues
            assert os.path.exists(temp_dir)
            assert os.access(temp_dir, os.W_OK)

    def test_network_isolation_integration(self):
        """Test that validation works without network access."""
        validator = PrerequisiteValidator()

        # Most validation should work without network
        # (except database connectivity which depends on local setup)
        checks_that_should_work = [
            validator.check_python_version,
            validator.check_dependencies_installed,
            validator.check_pytest_collection,
            validator.check_ci_toolchain,
            validator.check_environment_variables,
        ]

        for check_func in checks_that_should_work:
            try:
                check = check_func()
                assert check.name
                assert check.message
                assert isinstance(check.passed, bool)
            except Exception as e:
                pytest.fail(f"Check {check_func.__name__} failed without network: {e}")

    def test_result_serialization_integration(self):
        """Test that results can be serialized and deserialized."""
        result = validate_all_prerequisites()

        # Test JSON serialization
        json_str = json.dumps(result.dict())
        assert json_str

        # Test deserialization
        data = json.loads(json_str)
        assert data["passed"] == result.passed
        assert data["total_checks"] == result.total_checks
        assert data["passed_checks"] == result.passed_checks
        assert data["failed_checks"] == result.failed_checks
        assert data["warning_checks"] == result.warning_checks
        assert len(data["checks"]) == len(result.checks)

        # Test that check data is complete
        for i, check_data in enumerate(data["checks"]):
            original_check = result.checks[i]
            assert check_data["name"] == original_check.name
            assert check_data["passed"] == original_check.passed
            assert check_data["required"] == original_check.required
            assert check_data["message"] == original_check.message
