"""
SSH deployment automation module for PRP-1060.

Provides secure SSH-based deployment to VPS with comprehensive
error handling, retry logic, and rollback capabilities.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import paramiko
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DeploymentConfig(BaseModel):
    """Configuration for SSH deployment."""

    host: str = Field(..., description="Target VPS hostname or IP")
    user: str = Field(..., description="SSH username")
    key_path: str = Field(..., description="Path to SSH private key")
    port: int = Field(default=22, description="SSH port")
    timeout: int = Field(default=300, description="Deployment timeout in seconds")
    max_retries: int = Field(default=2, description="Maximum deployment retries")

    # Deployment scripts
    deploy_script: str = Field(default="~/bin/deploy.sh", description="Path to deployment script on VPS")
    health_script: str = Field(default="~/bin/health_check.sh", description="Path to health check script")
    rollback_script: str = Field(default="~/bin/rollback.sh", description="Path to rollback script")

    # Additional environment variables to pass
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables for deployment")


class DeploymentResult(BaseModel):
    """Result of a deployment operation."""

    status: str = Field(..., description="Deployment status: success, failed, timeout, error")
    start_time: datetime = Field(..., description="Deployment start timestamp")
    end_time: Optional[datetime] = Field(None, description="Deployment end timestamp")
    duration_seconds: float = Field(default=0.0, description="Total deployment duration")

    # Script execution results
    deploy_exit_code: Optional[int] = Field(None, description="Deploy script exit code")
    deploy_output: str = Field(default="", description="Deploy script stdout")
    deploy_error: str = Field(default="", description="Deploy script stderr")

    # Health check results
    health_checks: List[Dict[str, Any]] = Field(default_factory=list, description="Health check results")

    # Error information
    error: str = Field(default="", description="Error message if deployment failed")
    retry_count: int = Field(default=0, description="Number of retries attempted")


class SSHConnection:
    """Manages SSH connection with automatic reconnection."""

    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.client: Optional[paramiko.SSHClient] = None
        self.connected = False

    async def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logger.info(f"Connecting to {self.config.user}@{self.config.host}:{self.config.port}")

            # Connect with timeout
            self.client.connect(
                hostname=self.config.host,
                port=self.config.port,
                username=self.config.user,
                key_filename=self.config.key_path,
                timeout=30,
                compress=True,
            )

            self.connected = True
            logger.info("SSH connection established successfully")
            return True

        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            self.connected = False
            if self.client:
                self.client.close()
                self.client = None
            return False

    async def execute_command(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        """Execute command over SSH."""
        if not self.connected or not self.client:
            raise RuntimeError("SSH connection not established")

        try:
            logger.info(f"Executing command: {command}")

            # Execute command
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)

            # Read output
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            error = stderr.read().decode("utf-8", errors="replace")

            result = {
                "command": command,
                "exit_code": exit_code,
                "output": output,
                "error": error,
                "success": exit_code == 0,
            }

            if exit_code == 0:
                logger.info(f"Command completed successfully: {command}")
            else:
                logger.error(f"Command failed with exit code {exit_code}: {command}")
                logger.error(f"Error output: {error}")

            return result

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {"command": command, "exit_code": -1, "output": "", "error": str(e), "success": False}

    def close(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("SSH connection closed")


class SSHDeployer:
    """SSH-based deployment automation."""

    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.connection = SSHConnection(config)

    async def deploy(self) -> DeploymentResult:
        """Execute deployment to VPS."""
        logger.info(f"Starting deployment to {self.config.host}")

        result = DeploymentResult(status="failed", start_time=datetime.now(timezone.utc))

        start_time = time.time()

        try:
            # Attempt deployment with retries
            for attempt in range(self.config.max_retries + 1):
                result.retry_count = attempt

                if attempt > 0:
                    logger.info(f"Deployment attempt {attempt + 1}/{self.config.max_retries + 1}")
                    await asyncio.sleep(min(attempt * 2, 10))  # Exponential backoff

                # Try to deploy
                deploy_success = await self._execute_deployment()

                if deploy_success:
                    result.status = "success"
                    break

                if attempt < self.config.max_retries:
                    logger.warning(f"Deployment attempt {attempt + 1} failed, retrying...")
                else:
                    logger.error("All deployment attempts failed")
                    result.status = "failed"

        except asyncio.TimeoutError:
            result.status = "timeout"
            result.error = f"Deployment timed out after {self.config.timeout} seconds"
            logger.error("Deployment timed out")

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error(f"Deployment error: {e}")

        finally:
            end_time = time.time()
            result.end_time = datetime.now(timezone.utc)
            result.duration_seconds = round(end_time - start_time, 2)

            # Close connection
            self.connection.close()

        logger.info(f"Deployment completed with status: {result.status}")
        return result

    async def _execute_deployment(self) -> bool:
        """Execute single deployment attempt."""
        try:
            # Connect to VPS
            if not await self.connection.connect():
                return False

            # Prepare environment
            await self._prepare_deployment_environment()

            # Execute deployment script
            deploy_result = await self.connection.execute_command(
                self.config.deploy_script, timeout=self.config.timeout
            )

            if not deploy_result["success"]:
                logger.error(f"Deployment script failed: {deploy_result['error']}")
                return False

            # Run health checks
            health_passed = await self._run_health_checks()

            if not health_passed:
                logger.error("Health checks failed after deployment")
                return False

            logger.info("Deployment completed successfully")
            return True

        except Exception as e:
            logger.error(f"Deployment execution failed: {e}")
            return False

    async def _prepare_deployment_environment(self):
        """Prepare deployment environment variables."""
        if not self.config.environment:
            return

        logger.info("Setting deployment environment variables")

        # Export environment variables
        for key, value in self.config.environment.items():
            command = f"export {key}='{value}'"
            await self.connection.execute_command(command, timeout=10)

    async def _run_health_checks(self) -> bool:
        """Run post-deployment health checks."""
        logger.info("Running post-deployment health checks")

        try:
            # Check if health script exists
            check_script = await self.connection.execute_command(f"test -f {self.config.health_script}", timeout=10)

            if not check_script["success"]:
                logger.warning(f"Health check script not found: {self.config.health_script}")
                return await self._run_default_health_checks()

            # Execute health check script
            health_result = await self.connection.execute_command(self.config.health_script, timeout=60)

            if health_result["success"]:
                logger.info("Health checks passed")
                return True
            else:
                logger.error(f"Health checks failed: {health_result['error']}")
                return False

        except Exception as e:
            logger.error(f"Health check execution failed: {e}")
            return False

    async def _run_default_health_checks(self) -> bool:
        """Run default health checks if custom script not available."""
        logger.info("Running default health checks")

        # Check 1: Docker services
        docker_check = await self.connection.execute_command("docker compose ps --format json", timeout=30)

        if not docker_check["success"]:
            logger.error("Docker services check failed")
            return False

        # Check 2: System resources
        resource_check = await self.connection.execute_command("df -h / && free -h", timeout=10)

        if not resource_check["success"]:
            logger.warning("System resource check failed")

        # Check 3: Process check
        process_check = await self.connection.execute_command(
            "pgrep -f python || pgrep -f node || pgrep -f gunicorn", timeout=10
        )

        if not process_check["success"]:
            logger.warning("No application processes detected")

        logger.info("Default health checks completed")
        return True

    async def rollback(self) -> bool:
        """Execute rollback to previous deployment."""
        logger.info("Starting deployment rollback")

        try:
            # Connect to VPS
            if not await self.connection.connect():
                logger.error("Failed to connect for rollback")
                return False

            # Execute rollback script
            rollback_result = await self.connection.execute_command(
                self.config.rollback_script, timeout=self.config.timeout
            )

            if rollback_result["success"]:
                logger.info("Rollback completed successfully")

                # Run health checks after rollback
                health_passed = await self._run_health_checks()

                if health_passed:
                    logger.info("Health checks passed after rollback")
                    return True
                else:
                    logger.error("Health checks failed after rollback")
                    return False
            else:
                logger.error(f"Rollback script failed: {rollback_result['error']}")
                return False

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

        finally:
            self.connection.close()

    async def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status from VPS."""
        logger.info("Checking deployment status")

        status = {"connected": False, "services": {}, "health": {}, "timestamp": datetime.now(timezone.utc).isoformat()}

        try:
            # Connect to VPS
            if not await self.connection.connect():
                return status

            status["connected"] = True

            # Get service status
            service_result = await self.connection.execute_command("docker compose ps --format json", timeout=30)

            if service_result["success"]:
                status["services"] = {"docker_compose": "running", "output": service_result["output"][:500]}
            else:
                status["services"] = {"docker_compose": "failed", "error": service_result["error"][:500]}

            # Get system health
            health_result = await self.connection.execute_command("uptime && df -h / | tail -1", timeout=10)

            if health_result["success"]:
                status["health"] = {"system": "healthy", "details": health_result["output"]}

        except Exception as e:
            logger.error(f"Status check failed: {e}")
            status["error"] = str(e)

        finally:
            self.connection.close()

        return status
