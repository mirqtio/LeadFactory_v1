"""
Integration tests for PRP-1060 Acceptance + Deploy Runner pipeline.

Comprehensive end-to-end testing of the containerized acceptance testing
workflow including evidence collection and deployment validation.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis
import yaml

from core.acceptance_integration import AcceptanceConfig, AcceptanceIntegrator
from deployment.evidence_validator import EvidenceConfig, EvidenceValidator
from deployment.health_checker import HealthCheckConfig, HealthChecker
from deployment.ssh_deployer import DeploymentConfig, SSHDeployer
from profiles import ProfileLoader


class TestAcceptanceProfileIntegration:
    """Test acceptance profile system integration."""

    @pytest.fixture
    def profile_loader(self):
        """Create ProfileLoader for testing."""
        return ProfileLoader()

    @pytest.fixture
    def mock_acceptance_profile(self):
        """Mock acceptance profile configuration."""
        return {
            "name": "acceptance",
            "description": "Containerized acceptance testing profile",
            "command": "/acceptance",
            "workflow": {
                "type": "containerized",
                "steps": [
                    {"name": "setup", "actions": ["clone_repository", "setup_environment"]},
                    {"name": "test_execution", "actions": ["run_tests", "collect_results"]},
                    {"name": "evidence_validation", "actions": ["store_evidence", "validate_promotion"]},
                    {"name": "deployment", "actions": ["deploy_to_vps", "health_check"]},
                ],
            },
            "environment": {
                "variables": ["REDIS_URL", "PRP_ID", "VPS_SSH_HOST", "VPS_SSH_USER"],
                "required_secrets": ["VPS_SSH_KEY", "GITHUB_TOKEN"],
            },
            "container": {"registry": "ghcr.io/leadfactory", "image": "acceptance-runner", "tag": "latest"},
            "evidence": {
                "redis_keys": {
                    "acceptance_passed": "boolean evidence for test success",
                    "deploy_ok": "boolean evidence for deployment success",
                }
            },
            "deployment": {
                "target_host": "production.leadfactory.io",
                "user": "deploy",
                "key_path": "/tmp/vps_ssh_key",
            },
        }

    @patch("builtins.open")
    @patch("yaml.safe_load")
    @patch("pathlib.Path.exists")
    def test_profile_loading_integration(
        self, mock_exists, mock_yaml_load, mock_open, profile_loader, mock_acceptance_profile
    ):
        """Test profile loading integrates correctly."""
        mock_exists.return_value = True
        mock_yaml_load.return_value = mock_acceptance_profile

        profile = profile_loader.load_profile("acceptance")

        assert profile["name"] == "acceptance"
        assert profile["workflow"]["type"] == "containerized"
        assert "acceptance_passed" in profile["evidence"]["redis_keys"]
        assert "deploy_ok" in profile["evidence"]["redis_keys"]

    def test_profile_validation_requirements(self, profile_loader, mock_acceptance_profile):
        """Test profile validation enforces requirements."""
        # Test valid profile
        result = profile_loader._validate_profile(mock_acceptance_profile, "acceptance")
        assert result == mock_acceptance_profile

        # Test missing workflow
        invalid_profile = {k: v for k, v in mock_acceptance_profile.items() if k != "workflow"}

        with pytest.raises(ValueError, match="Missing required field 'workflow'"):
            profile_loader._validate_profile(invalid_profile, "acceptance")


class TestContainerIntegration:
    """Test container execution and Docker integration."""

    @pytest.fixture
    def acceptance_config(self):
        """Mock acceptance configuration."""
        return AcceptanceConfig(
            redis_url="redis://localhost:6379",
            prp_id="test-prp-1060",
            vps_ssh_host="test.leadfactory.io",
            vps_ssh_user="deploy",
            vps_ssh_key_path="/tmp/test_ssh_key",
            github_repo="leadfactory/test-repo",
            github_token="ghp_test_token",
        )

    @pytest.fixture
    def acceptance_integrator(self, acceptance_config):
        """Create AcceptanceIntegrator for testing."""
        with patch("docker.from_env"):
            integrator = AcceptanceIntegrator(acceptance_config)
            integrator.docker_client = MagicMock()
            return integrator

    def test_container_environment_preparation(self, acceptance_integrator):
        """Test container environment variable preparation."""
        env_vars = acceptance_integrator._prepare_container_environment()

        assert env_vars["REDIS_URL"] == "redis://localhost:6379"
        assert env_vars["PRP_ID"] == "test-prp-1060"
        assert env_vars["VPS_SSH_HOST"] == "test.leadfactory.io"
        assert env_vars["VPS_SSH_USER"] == "deploy"
        assert env_vars["VPS_SSH_KEY"] == "/home/acceptance/.ssh/id_rsa"
        assert env_vars["GITHUB_REPO"] == "leadfactory/test-repo"
        assert env_vars["GITHUB_TOKEN"] == "ghp_test_token"

    @patch("os.path.exists")
    @patch("os.chmod")
    def test_ssh_key_preparation(self, mock_chmod, mock_exists, acceptance_integrator):
        """Test SSH key preparation for container mounting."""
        mock_exists.return_value = True

        acceptance_integrator._prepare_ssh_key()

        mock_chmod.assert_called_once_with("/tmp/test_ssh_key", 0o600)

    @pytest.mark.asyncio
    async def test_container_image_pull(self, acceptance_integrator):
        """Test container image pulling."""
        mock_images = MagicMock()
        acceptance_integrator.docker_client.images = mock_images

        await acceptance_integrator._pull_container_image()

        mock_images.pull.assert_called_once_with("ghcr.io/leadfactory/acceptance-runner:latest")

    @pytest.mark.asyncio
    async def test_container_execution_success(self, acceptance_integrator):
        """Test successful container execution."""
        # Mock container execution
        mock_container = MagicMock()
        mock_container.id = "test_container_123"
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"Tests passed successfully"

        acceptance_integrator.docker_client.containers.run.return_value = mock_container

        env_vars = {"TEST_ENV": "value"}
        result = await acceptance_integrator._run_acceptance_container(env_vars)

        assert result["exit_code"] == 0
        assert result["container_id"] == "test_container_123"
        assert "Tests passed successfully" in result["output"]
        assert result["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_container_execution_timeout(self, acceptance_integrator):
        """Test container execution timeout handling."""
        # Mock container timeout
        mock_container = MagicMock()
        mock_container.id = "test_container_timeout"
        mock_container.wait.side_effect = Exception("timeout")
        mock_container.logs.return_value = b"Partial output before timeout"

        acceptance_integrator.docker_client.containers.run.return_value = mock_container

        env_vars = {"TEST_ENV": "value"}
        result = await acceptance_integrator._run_acceptance_container(env_vars)

        assert result["exit_code"] == 1
        assert "timeout" in result["error"]
        assert "Partial output before timeout" in result["output"]


class TestEvidenceValidationIntegration:
    """Test evidence collection and validation integration."""

    @pytest.fixture
    def evidence_config(self):
        """Mock evidence configuration."""
        return EvidenceConfig(
            redis_url="redis://localhost:6379",
            prp_id="test-prp-1060",
        )

    @pytest.fixture
    def evidence_validator(self, evidence_config):
        """Create EvidenceValidator for testing."""
        with patch("redis.from_url"):
            validator = EvidenceValidator(evidence_config)
            validator.redis_client = MagicMock()
            return validator

    @pytest.mark.asyncio
    async def test_evidence_collection_success(self, evidence_validator):
        """Test successful evidence collection."""
        # Mock Redis operations
        evidence_validator.redis_client.hset.return_value = True
        evidence_validator.redis_client.set.return_value = True

        success = await evidence_validator.collect_evidence(
            "acceptance_passed", "true", {"test_results": {"status": "passed", "tests_run": 5, "tests_passed": 5}}
        )

        assert success is True
        evidence_validator.redis_client.hset.assert_called()
        evidence_validator.redis_client.set.assert_called()

    @pytest.mark.asyncio
    async def test_acceptance_evidence_validation(self, evidence_validator):
        """Test acceptance test evidence validation."""
        test_results = {
            "status": "passed",
            "exit_code": 0,
            "tests_failed": 0,
            "tests_run": 10,
            "tests_passed": 10,
        }

        with patch.object(evidence_validator, "collect_evidence", return_value=True):
            result = await evidence_validator.validate_acceptance_evidence(test_results)

            assert result is True

    @pytest.mark.asyncio
    async def test_deployment_evidence_validation(self, evidence_validator):
        """Test deployment evidence validation."""
        deploy_results = {
            "status": "success",
            "health_check_results": [
                {"healthy": True, "name": "http_health"},
                {"healthy": True, "name": "docker_services"},
            ],
        }

        with patch.object(evidence_validator, "collect_evidence", return_value=True):
            result = await evidence_validator.validate_deployment_evidence(deploy_results)

            assert result is True

    @pytest.mark.asyncio
    async def test_evidence_completeness_check(self, evidence_validator):
        """Test evidence completeness validation."""
        # Mock Redis responses
        evidence_validator.redis_client.hget.side_effect = lambda key, field: {
            ("prp:test-prp-1060", "acceptance_passed"): "true",
            ("prp:test-prp-1060", "deploy_ok"): "true",
        }.get((key, field))

        result = await evidence_validator.check_evidence_completeness()

        assert result["complete"] is True
        assert result["valid"] is True
        assert result["ready_for_promotion"] is True


class TestDeploymentIntegration:
    """Test SSH deployment and health checking integration."""

    @pytest.fixture
    def deployment_config(self):
        """Mock deployment configuration."""
        return DeploymentConfig(
            host="test.leadfactory.io",
            user="deploy",
            key_path="/tmp/test_ssh_key",
            timeout=30,
        )

    @pytest.fixture
    def ssh_deployer(self, deployment_config):
        """Create SSHDeployer for testing."""
        return SSHDeployer(deployment_config)

    @pytest.fixture
    def health_check_config(self):
        """Mock health check configuration."""
        return HealthCheckConfig(
            base_url="https://test.leadfactory.io",
            timeout_seconds=30,
        )

    @pytest.fixture
    def health_checker(self, health_check_config):
        """Create HealthChecker for testing."""
        return HealthChecker(health_check_config)

    @pytest.mark.asyncio
    @patch("paramiko.SSHClient")
    async def test_ssh_deployment_success(self, mock_ssh_client, ssh_deployer):
        """Test successful SSH deployment."""
        # Mock SSH connection and command execution
        mock_ssh = MagicMock()
        mock_ssh_client.return_value = mock_ssh

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"Deployment successful"
        mock_stdout.channel.recv_exit_status.return_value = 0

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)

        result = await ssh_deployer.deploy()

        assert result.success is True
        assert "Deployment successful" in result.output
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_health_check_success(self, health_checker):
        """Test successful health check execution."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "healthy"}'
            mock_response.headers = {}

            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            result = await health_checker.check_health_endpoint()

            assert result.status == "healthy"
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_comprehensive_health_checks(self, health_checker):
        """Test comprehensive health check execution."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock successful responses for all endpoints
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "ok"}'
            mock_response.headers = {"Content-Type": "application/json"}

            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            results = await health_checker.run_all_checks()

            assert results["overall_status"] in ["healthy", "degraded"]
            assert results["total_checks"] > 0
            assert len(results["checks"]) > 0


class TestEndToEndIntegration:
    """Test complete end-to-end acceptance pipeline."""

    @pytest.fixture
    def acceptance_integrator(self):
        """Create AcceptanceIntegrator for end-to-end testing."""
        config = AcceptanceConfig(
            redis_url="redis://localhost:6379",
            prp_id="test-e2e-1060",
            vps_ssh_host="test.leadfactory.io",
            vps_ssh_user="deploy",
            vps_ssh_key_path="/tmp/test_ssh_key",
        )

        with patch("docker.from_env"):
            integrator = AcceptanceIntegrator(config)
            integrator.docker_client = MagicMock()
            return integrator

    @pytest.mark.asyncio
    async def test_acceptance_readiness_validation(self, acceptance_integrator):
        """Test complete acceptance readiness validation."""
        with (
            patch("redis.from_url") as mock_redis,
            patch("os.path.exists", return_value=True),
            patch("os.getenv") as mock_getenv,
        ):
            # Mock Redis connection
            mock_redis.return_value.ping.return_value = True

            # Mock Docker client
            acceptance_integrator.docker_client.ping.return_value = True
            acceptance_integrator.docker_client.images.get.return_value = MagicMock()

            # Mock environment variables
            mock_getenv.side_effect = lambda var, default=None: {
                "PRP_ID": "test-e2e-1060",
                "VPS_SSH_HOST": "test.leadfactory.io",
                "VPS_SSH_USER": "deploy",
            }.get(var, default)

            readiness = await acceptance_integrator.validate_acceptance_readiness()

            assert readiness["ready"] is True
            assert readiness["requirements_met"]["redis"] is True
            assert readiness["requirements_met"]["docker"] is True
            assert readiness["requirements_met"]["container_image"] is True
            assert readiness["requirements_met"]["ssh_key"] is True
            assert readiness["requirements_met"]["environment"] is True

    @pytest.mark.asyncio
    async def test_full_acceptance_workflow(self, acceptance_integrator):
        """Test complete acceptance workflow integration."""
        # Mock container execution
        mock_container = MagicMock()
        mock_container.id = "test_e2e_container"
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"All tests passed, deployment successful"

        acceptance_integrator.docker_client.containers.run.return_value = mock_container
        acceptance_integrator.docker_client.images.pull.return_value = None

        # Mock evidence validation
        with (
            patch.object(acceptance_integrator.evidence_validator, "check_evidence_completeness") as mock_evidence,
            patch.object(acceptance_integrator.evidence_validator, "get_evidence_summary") as mock_summary,
        ):
            mock_evidence.return_value = {
                "complete": True,
                "valid": True,
                "ready_for_promotion": True,
                "evidence": {"acceptance_passed": {"valid": True}, "deploy_ok": {"valid": True}},
            }

            mock_summary.return_value = {
                "prp_id": "test-e2e-1060",
                "evidence_details": {},
            }

            # Mock SSH key preparation
            with patch("os.path.exists", return_value=True), patch("os.chmod"):
                result = await acceptance_integrator.run_acceptance_tests()

                assert result.passed is True
                assert result.service_name == "acceptance_runner"
                assert result.test_name == "containerized_acceptance_tests"
                assert result.status_code == 0
                assert result.response_time_ms > 0


class TestPerformanceValidation:
    """Test performance requirements for PRP-1060."""

    @pytest.mark.asyncio
    async def test_acceptance_workflow_performance(self):
        """Test that acceptance workflow meets performance requirements."""
        # Mock fast execution
        config = AcceptanceConfig(
            redis_url="redis://localhost:6379",
            prp_id="test-perf-1060",
            vps_ssh_host="test.leadfactory.io",
            vps_ssh_user="deploy",
        )

        with patch("docker.from_env"), patch("time.time", side_effect=[0, 120]):  # 2 minute execution
            integrator = AcceptanceIntegrator(config)
            integrator.docker_client = MagicMock()

            # Mock fast container execution
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = b"Fast execution"
            integrator.docker_client.containers.run.return_value = mock_container

            # Mock evidence validation
            with patch.object(integrator.evidence_validator, "check_evidence_completeness") as mock_evidence:
                mock_evidence.return_value = {
                    "complete": True,
                    "valid": True,
                    "ready_for_promotion": True,
                    "evidence": {"acceptance_passed": {"valid": True}, "deploy_ok": {"valid": True}},
                }

                result = await integrator.run_acceptance_tests()

                # Verify performance requirement: <3min p95 PRP completion
                assert result.response_time_ms < 180000  # 3 minutes in milliseconds
                assert result.passed is True


class TestErrorHandlingIntegration:
    """Test comprehensive error handling and recovery."""

    @pytest.fixture
    def acceptance_integrator(self):
        """Create AcceptanceIntegrator for error testing."""
        config = AcceptanceConfig(
            redis_url="redis://localhost:6379",
            prp_id="test-error-1060",
            vps_ssh_host="test.leadfactory.io",
            vps_ssh_user="deploy",
        )

        with patch("docker.from_env"):
            integrator = AcceptanceIntegrator(config)
            integrator.docker_client = MagicMock()
            return integrator

    @pytest.mark.asyncio
    async def test_container_failure_handling(self, acceptance_integrator):
        """Test handling of container execution failures."""
        # Mock container failure
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.return_value = b"Test failures detected"

        acceptance_integrator.docker_client.containers.run.return_value = mock_container

        # Mock evidence showing failure
        with patch.object(acceptance_integrator.evidence_validator, "check_evidence_completeness") as mock_evidence:
            mock_evidence.return_value = {
                "complete": True,
                "valid": False,
                "ready_for_promotion": False,
                "evidence": {"acceptance_passed": {"valid": False}, "deploy_ok": {"valid": False}},
            }

            result = await acceptance_integrator.run_acceptance_tests()

            assert result.passed is False
            assert result.status_code == 1
            assert "Test failures detected" in result.details["container_result"]["output"]

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, acceptance_integrator):
        """Test handling of Redis connection failures."""
        # Mock Redis connection failure
        with patch.object(acceptance_integrator.evidence_validator, "check_evidence_completeness") as mock_evidence:
            mock_evidence.side_effect = Exception("Redis connection failed")

            # Mock successful container execution
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = b"Tests passed"
            acceptance_integrator.docker_client.containers.run.return_value = mock_container

            result = await acceptance_integrator.run_acceptance_tests()

            assert result.passed is False
            assert "Redis connection failed" in result.error_message

    @pytest.mark.asyncio
    async def test_docker_unavailable_handling(self, acceptance_integrator):
        """Test handling when Docker is unavailable."""
        # Mock Docker unavailable
        acceptance_integrator.docker_client.containers.run.side_effect = Exception("Docker daemon not running")

        result = await acceptance_integrator.run_acceptance_tests()

        assert result.passed is False
        assert "Docker daemon not running" in result.error_message
