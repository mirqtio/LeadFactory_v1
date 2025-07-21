"""
Acceptance Integration Module for PRP-1060

Integrates containerized acceptance testing into the core validation workflow,
providing seamless integration with existing integration_validator system.
"""

import os
import time
from typing import Any

import redis
from pydantic import BaseModel

import docker
from core.config import get_settings
from core.integration_validator import ValidationResult, integration_validator
from core.logging import get_logger
from deployment.evidence_validator import EvidenceConfig, EvidenceValidator

logger = get_logger(__name__)


class AcceptanceConfig(BaseModel):
    """Configuration for acceptance testing integration."""

    container_image: str = "ghcr.io/leadfactory/acceptance-runner:latest"
    redis_url: str
    prp_id: str
    vps_ssh_host: str
    vps_ssh_user: str
    vps_ssh_key_path: str = "/tmp/vps_ssh_key"
    github_repo: str | None = None
    github_token: str | None = None
    timeout_seconds: int = 1800  # 30 minutes
    evidence_timeout: int = 600  # 10 minutes


class AcceptanceIntegrator:
    """
    Integrates acceptance testing with core validation system.

    Provides seamless integration between container-based acceptance testing
    and the existing integration validation framework.
    """

    def __init__(self, config: AcceptanceConfig | None = None):
        self.config = config or self._load_config()
        self.docker_client = docker.from_env()
        self.evidence_validator = EvidenceValidator(
            EvidenceConfig(redis_url=self.config.redis_url, prp_id=self.config.prp_id)
        )

    def _load_config(self) -> AcceptanceConfig:
        """Load acceptance configuration from environment."""
        settings = get_settings()

        return AcceptanceConfig(
            redis_url=settings.redis_url,
            prp_id=os.getenv("PRP_ID", "unknown"),
            vps_ssh_host=os.getenv("VPS_SSH_HOST", ""),
            vps_ssh_user=os.getenv("VPS_SSH_USER", ""),
            vps_ssh_key_path=os.getenv("VPS_SSH_KEY", "/tmp/vps_ssh_key"),
            github_repo=os.getenv("GITHUB_REPO"),
            github_token=os.getenv("GITHUB_TOKEN"),
        )

    async def run_acceptance_tests(self) -> ValidationResult:
        """
        Execute containerized acceptance tests and return validation result.

        Returns:
            ValidationResult indicating overall acceptance test success
        """
        logger.info(f"Starting acceptance tests for PRP {self.config.prp_id}")
        start_time = time.time()

        try:
            # Prepare container environment
            container_env = self._prepare_container_environment()

            # Prepare SSH key
            self._prepare_ssh_key()

            # Pull latest container image
            await self._pull_container_image()

            # Run acceptance container
            container_result = await self._run_acceptance_container(container_env)

            # Validate evidence was written to Redis
            evidence_status = await self._validate_evidence_collection()

            response_time = int((time.time() - start_time) * 1000)

            # Determine overall success
            success = (
                container_result.get("exit_code") == 0
                and evidence_status.get("acceptance_passed")
                and evidence_status.get("deploy_ok")
            )

            return ValidationResult(
                service_name="acceptance_runner",
                test_name="containerized_acceptance_tests",
                passed=success,
                response_time_ms=response_time,
                status_code=container_result.get("exit_code"),
                error_message=None if success else self._format_error_message(container_result, evidence_status),
                details={
                    "container_result": container_result,
                    "evidence_status": evidence_status,
                    "prp_id": self.config.prp_id,
                    "container_image": self.config.container_image,
                },
            )

        except Exception as e:
            logger.error(f"Acceptance test execution failed: {e}")
            response_time = int((time.time() - start_time) * 1000)

            return ValidationResult(
                service_name="acceptance_runner",
                test_name="containerized_acceptance_tests",
                passed=False,
                response_time_ms=response_time,
                error_message=f"Acceptance test execution failed: {str(e)}",
                details={"error_type": type(e).__name__, "prp_id": self.config.prp_id},
            )

    def _prepare_container_environment(self) -> dict[str, str]:
        """Prepare environment variables for acceptance container."""
        return {
            "REDIS_URL": self.config.redis_url,
            "PRP_ID": self.config.prp_id,
            "VPS_SSH_HOST": self.config.vps_ssh_host,
            "VPS_SSH_USER": self.config.vps_ssh_user,
            "VPS_SSH_KEY": "/home/acceptance/.ssh/id_rsa",
            "GITHUB_REPO": self.config.github_repo or "",
            "GITHUB_TOKEN": self.config.github_token or "",
            "ACCEPTANCE_TIMEOUT": "600",
            "DEPLOYMENT_TIMEOUT": "300",
            "MAX_RETRIES": "2",
        }

    def _prepare_ssh_key(self):
        """Prepare SSH key for container mounting."""
        if os.path.exists(self.config.vps_ssh_key_path):
            # Ensure SSH key has correct permissions
            os.chmod(self.config.vps_ssh_key_path, 0o600)
            logger.info("SSH key prepared for container mounting")
        else:
            logger.warning(f"SSH key not found at {self.config.vps_ssh_key_path}")

    async def _pull_container_image(self):
        """Pull the latest acceptance runner container image."""
        try:
            logger.info(f"Pulling container image: {self.config.container_image}")
            self.docker_client.images.pull(self.config.container_image)
            logger.info("Container image pulled successfully")
        except Exception as e:
            logger.warning(f"Failed to pull container image: {e}")
            # Continue with existing image if pull fails

    async def _run_acceptance_container(self, env_vars: dict[str, str]) -> dict[str, Any]:
        """
        Run the acceptance container with proper configuration.

        Args:
            env_vars: Environment variables for the container

        Returns:
            Dictionary with container execution results
        """
        logger.info("Starting acceptance container execution")

        # Prepare volume mounts
        volumes = {}
        if os.path.exists(self.config.vps_ssh_key_path):
            volumes[self.config.vps_ssh_key_path] = {"bind": "/home/acceptance/.ssh/id_rsa", "mode": "ro"}

        # If we have a local codebase, mount it for testing
        workspace_path = os.getcwd()
        volumes[workspace_path] = {"bind": "/workspace", "mode": "ro"}

        container_result = {
            "exit_code": 1,
            "output": "",
            "error": "",
            "duration_seconds": 0,
            "container_id": None,
        }

        start_time = time.time()

        try:
            # Run container
            container = self.docker_client.containers.run(
                image=self.config.container_image,
                environment=env_vars,
                volumes=volumes,
                network_mode="host",  # Allow access to Redis and VPS
                detach=True,
                remove=False,  # Keep container for log inspection
                stdout=True,
                stderr=True,
            )

            container_result["container_id"] = container.id
            logger.info(f"Container started: {container.id}")

            # Wait for container completion with timeout
            try:
                exit_code = container.wait(timeout=self.config.timeout_seconds)
                container_result["exit_code"] = exit_code["StatusCode"]

                # Get container logs
                logs = container.logs(stdout=True, stderr=True).decode("utf-8")
                container_result["output"] = logs

                logger.info(f"Container completed with exit code: {exit_code['StatusCode']}")

            except Exception as wait_error:
                logger.error(f"Container execution timeout or error: {wait_error}")
                container_result["error"] = f"Container timeout: {str(wait_error)}"

                # Try to get partial logs
                try:
                    logs = container.logs(stdout=True, stderr=True).decode("utf-8")
                    container_result["output"] = logs
                except:
                    pass

                # Kill container if still running
                try:
                    container.kill()
                except:
                    pass

            finally:
                # Clean up container
                try:
                    container.remove()
                except:
                    pass

        except Exception as e:
            logger.error(f"Failed to run acceptance container: {e}")
            container_result["error"] = str(e)

        container_result["duration_seconds"] = round(time.time() - start_time, 2)
        return container_result

    async def _validate_evidence_collection(self) -> dict[str, Any]:
        """
        Validate that evidence was properly collected in Redis.

        Returns:
            Dictionary with evidence validation status
        """
        logger.info("Validating evidence collection")

        try:
            # Check evidence completeness
            evidence_check = await self.evidence_validator.check_evidence_completeness()

            # Get evidence summary
            evidence_summary = await self.evidence_validator.get_evidence_summary()

            return {
                "evidence_complete": evidence_check.get("complete", False),
                "evidence_valid": evidence_check.get("valid", False),
                "ready_for_promotion": evidence_check.get("ready_for_promotion", False),
                "acceptance_passed": evidence_check.get("evidence", {})
                .get("acceptance_passed", {})
                .get("valid", False),
                "deploy_ok": evidence_check.get("evidence", {}).get("deploy_ok", {}).get("valid", False),
                "evidence_details": evidence_check.get("evidence", {}),
                "evidence_summary": evidence_summary,
            }

        except Exception as e:
            logger.error(f"Evidence validation failed: {e}")
            return {
                "evidence_complete": False,
                "evidence_valid": False,
                "ready_for_promotion": False,
                "acceptance_passed": False,
                "deploy_ok": False,
                "error": str(e),
            }

    def _format_error_message(self, container_result: dict, evidence_status: dict) -> str:
        """Format a comprehensive error message for failed acceptance tests."""
        errors = []

        if container_result.get("exit_code") != 0:
            errors.append(f"Container exit code: {container_result.get('exit_code')}")

        if container_result.get("error"):
            errors.append(f"Container error: {container_result.get('error')}")

        if not evidence_status.get("acceptance_passed"):
            errors.append("Acceptance tests did not pass")

        if not evidence_status.get("deploy_ok"):
            errors.append("Deployment validation failed")

        if evidence_status.get("error"):
            errors.append(f"Evidence error: {evidence_status.get('error')}")

        return "; ".join(errors) if errors else "Unknown error"

    async def validate_acceptance_readiness(self) -> dict[str, Any]:
        """
        Validate that the system is ready for acceptance testing.

        Returns:
            Dictionary with readiness assessment
        """
        logger.info("Validating acceptance testing readiness")

        readiness = {
            "ready": False,
            "issues": [],
            "requirements_met": {},
        }

        # Check Redis connectivity
        try:
            redis_client = redis.from_url(self.config.redis_url)
            redis_client.ping()
            readiness["requirements_met"]["redis"] = True
        except Exception as e:
            readiness["requirements_met"]["redis"] = False
            readiness["issues"].append(f"Redis connection failed: {e}")

        # Check Docker availability
        try:
            self.docker_client.ping()
            readiness["requirements_met"]["docker"] = True
        except Exception as e:
            readiness["requirements_met"]["docker"] = False
            readiness["issues"].append(f"Docker not available: {e}")

        # Check container image availability
        try:
            self.docker_client.images.get(self.config.container_image)
            readiness["requirements_met"]["container_image"] = True
        except Exception:
            # Try to pull the image
            try:
                await self._pull_container_image()
                readiness["requirements_met"]["container_image"] = True
            except Exception as e:
                readiness["requirements_met"]["container_image"] = False
                readiness["issues"].append(f"Container image not available: {e}")

        # Check SSH key
        if os.path.exists(self.config.vps_ssh_key_path):
            readiness["requirements_met"]["ssh_key"] = True
        else:
            readiness["requirements_met"]["ssh_key"] = False
            readiness["issues"].append(f"SSH key not found: {self.config.vps_ssh_key_path}")

        # Check environment configuration
        required_env = ["PRP_ID", "VPS_SSH_HOST", "VPS_SSH_USER"]
        missing_env = [var for var in required_env if not os.getenv(var)]

        if not missing_env:
            readiness["requirements_met"]["environment"] = True
        else:
            readiness["requirements_met"]["environment"] = False
            readiness["issues"].append(f"Missing environment variables: {missing_env}")

        # Overall readiness
        readiness["ready"] = all(readiness["requirements_met"].values())

        return readiness


# Global acceptance integrator instance
acceptance_integrator = AcceptanceIntegrator()


async def run_acceptance_validation(prp_id: str) -> ValidationResult:
    """
    Convenience function to run acceptance validation for a specific PRP.

    Args:
        prp_id: PRP identifier for acceptance testing

    Returns:
        ValidationResult indicating acceptance test success
    """
    # Update PRP ID in config
    acceptance_integrator.config.prp_id = prp_id
    acceptance_integrator.evidence_validator.config.prp_id = prp_id

    return await acceptance_integrator.run_acceptance_tests()


async def validate_acceptance_readiness() -> dict[str, Any]:
    """
    Convenience function to validate acceptance testing readiness.

    Returns:
        Dictionary with readiness assessment
    """
    return await acceptance_integrator.validate_acceptance_readiness()


# Integration with existing validation framework
async def extended_integration_validation() -> dict[str, Any]:
    """
    Extended integration validation that includes acceptance testing.

    Integrates with the existing integration_validator to provide
    comprehensive validation including acceptance tests.

    Returns:
        Enhanced integration report with acceptance testing results
    """
    logger.info("Running extended integration validation with acceptance tests")

    # Run standard integration validation
    standard_report = await integration_validator.validate_all_services()

    # Check if acceptance testing is configured
    acceptance_readiness = await validate_acceptance_readiness()

    results = {
        "standard_integration": standard_report.model_dump(),
        "acceptance_readiness": acceptance_readiness,
        "acceptance_result": None,
        "overall_ready": False,
    }

    # Run acceptance tests if system is ready
    if acceptance_readiness["ready"]:
        try:
            acceptance_result = await acceptance_integrator.run_acceptance_tests()
            results["acceptance_result"] = acceptance_result.model_dump()

            # Update overall readiness
            results["overall_ready"] = standard_report.overall_score >= 80.0 and acceptance_result.passed

        except Exception as e:
            logger.error(f"Acceptance testing failed: {e}")
            results["acceptance_result"] = {
                "passed": False,
                "error": str(e),
                "service_name": "acceptance_runner",
                "test_name": "containerized_acceptance_tests",
            }
    else:
        logger.warning("Acceptance testing not ready, skipping acceptance validation")
        results["overall_ready"] = standard_report.overall_score >= 80.0

    return results
