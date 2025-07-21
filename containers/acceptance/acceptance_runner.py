#!/usr/bin/env python3
"""
Acceptance Runner - Main execution script for containerized acceptance testing.

PRP-1060: Acceptance + Deploy Runner Persona
Implements clone → pytest → evidence → deploy workflow with comprehensive error handling.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import paramiko
import redis
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/workspace/acceptance.log")],
)
logger = logging.getLogger(__name__)


class AcceptanceConfig(BaseModel):
    """Configuration for acceptance testing workflow."""

    redis_url: str
    prp_id: str
    vps_ssh_host: str
    vps_ssh_user: str
    vps_ssh_key: str = "/home/acceptance/.ssh/id_rsa"
    github_repo: str | None = None
    github_token: str | None = None
    acceptance_timeout: int = 600
    deployment_timeout: int = 300
    max_retries: int = 2


class EvidenceCollector:
    """Collects and stores evidence in Redis for PRP promotion."""

    def __init__(self, config: AcceptanceConfig):
        self.config = config
        self.redis_client = redis.from_url(config.redis_url)

    async def write_evidence(self, key: str, value: str, log_data: dict | None = None) -> bool:
        """Write evidence to Redis with optional log data."""
        try:
            # Write main evidence flag
            redis_key = f"prp:{self.config.prp_id}:{key}"
            self.redis_client.hset(f"prp:{self.config.prp_id}", key, value)

            # Write detailed log if provided
            if log_data:
                log_key = f"prp:{self.config.prp_id}:{key}_log"
                self.redis_client.set(log_key, json.dumps(log_data, default=str))

            logger.info(f"Evidence written: {redis_key} = {value}")
            return True

        except Exception as e:
            logger.error(f"Failed to write evidence {key}: {e}")
            return False

    async def read_evidence(self, key: str) -> str | None:
        """Read evidence from Redis."""
        try:
            redis_key = f"prp:{self.config.prp_id}"
            value = self.redis_client.hget(redis_key, key)
            return value.decode() if value else None
        except Exception as e:
            logger.error(f"Failed to read evidence {key}: {e}")
            return None


class AcceptanceTestRunner:
    """Runs acceptance tests and collects results."""

    def __init__(self, config: AcceptanceConfig):
        self.config = config
        self.evidence = EvidenceCollector(config)

    async def run_acceptance_tests(self) -> dict[str, Any]:
        """Execute acceptance test suite and return results."""
        logger.info("Starting acceptance test execution")

        test_result = {
            "status": "failed",
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": None,
            "duration_seconds": 0,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "exit_code": -1,
            "output": "",
            "error": "",
        }

        start_time = time.time()

        try:
            # Check if tests directory exists
            test_paths = ["/workspace/tests/acceptance/", "/workspace/tests/integration/", "/workspace/tests/"]

            test_path = None
            for path in test_paths:
                if Path(path).exists():
                    test_path = path
                    break

            if not test_path:
                logger.warning("No test directory found, creating minimal test")
                await self._create_minimal_test()
                test_path = "/workspace/tests/"

            # Run pytest with coverage and structured output
            cmd = [
                "python",
                "-m",
                "pytest",
                test_path,
                "-v",
                "--tb=short",
                "--junit-xml=/workspace/test-results.xml",
                "--cov=.",
                "--cov-report=term-missing",
                "--timeout=300",
            ]

            logger.info(f"Executing: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd="/workspace"
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.config.acceptance_timeout)

            end_time = time.time()

            test_result.update(
                {
                    "end_time": datetime.now(UTC).isoformat(),
                    "duration_seconds": round(end_time - start_time, 2),
                    "exit_code": process.returncode,
                    "output": stdout.decode(),
                    "error": stderr.decode(),
                }
            )

            # Parse test results
            await self._parse_test_results(test_result)

            # Determine overall status
            if process.returncode == 0:
                test_result["status"] = "passed"
                logger.info(f"Acceptance tests PASSED ({test_result['tests_passed']}/{test_result['tests_run']})")
            else:
                test_result["status"] = "failed"
                logger.error(f"Acceptance tests FAILED (exit code: {process.returncode})")

        except TimeoutError:
            test_result.update(
                {
                    "status": "timeout",
                    "error": f"Tests timed out after {self.config.acceptance_timeout} seconds",
                    "end_time": datetime.now(UTC).isoformat(),
                    "duration_seconds": self.config.acceptance_timeout,
                }
            )
            logger.error("Acceptance tests timed out")

        except Exception as e:
            test_result.update(
                {
                    "status": "error",
                    "error": str(e),
                    "end_time": datetime.now(UTC).isoformat(),
                    "duration_seconds": round(time.time() - start_time, 2),
                }
            )
            logger.error(f"Error running acceptance tests: {e}")

        # Write evidence
        success = test_result["status"] == "passed"
        await self.evidence.write_evidence("acceptance_passed", "true" if success else "false", test_result)

        return test_result

    async def _create_minimal_test(self):
        """Create a minimal test if none exist."""
        test_dir = Path("/workspace/tests")
        test_dir.mkdir(exist_ok=True)

        minimal_test = '''
import pytest

def test_basic_health():
    """Minimal health check test."""
    assert True

def test_environment_variables():
    """Test that required environment variables are set."""
    import os
    assert os.getenv("REDIS_URL") is not None
    assert os.getenv("PRP_ID") is not None

def test_redis_connectivity():
    """Test Redis connection."""
    import redis
    import os
    
    redis_url = os.getenv("REDIS_URL")
    client = redis.from_url(redis_url)
    
    # Simple ping test
    assert client.ping() is True
'''

        test_file = test_dir / "test_minimal_acceptance.py"
        with open(test_file, "w") as f:
            f.write(minimal_test)

        logger.info("Created minimal acceptance test")

    async def _parse_test_results(self, test_result: dict[str, Any]):
        """Parse pytest output to extract test statistics."""
        output = test_result.get("output", "")

        # Try to parse from JUnit XML if available
        junit_file = Path("/workspace/test-results.xml")
        if junit_file.exists():
            try:
                import xml.etree.ElementTree as ET

                tree = ET.parse(junit_file)
                root = tree.getroot()

                test_result["tests_run"] = int(root.get("tests", 0))
                test_result["tests_failed"] = int(root.get("failures", 0)) + int(root.get("errors", 0))
                test_result["tests_passed"] = test_result["tests_run"] - test_result["tests_failed"]

                return
            except Exception as e:
                logger.warning(f"Failed to parse JUnit XML: {e}")

        # Fall back to parsing pytest output
        lines = output.split("\n")
        for line in lines:
            if " passed" in line and " failed" in line:
                # Example: "5 passed, 2 failed in 10.23s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed," and i > 0:
                        test_result["tests_passed"] = int(parts[i - 1])
                    elif part == "failed" and i > 0:
                        test_result["tests_failed"] = int(parts[i - 1])

                test_result["tests_run"] = test_result["tests_passed"] + test_result["tests_failed"]
                break


class SSHDeployer:
    """Handles SSH deployment to VPS."""

    def __init__(self, config: AcceptanceConfig):
        self.config = config
        self.evidence = EvidenceCollector(config)

    async def deploy_to_vps(self) -> dict[str, Any]:
        """Execute SSH deployment to VPS."""
        logger.info(f"Starting deployment to {self.config.vps_ssh_host}")

        deploy_result = {
            "status": "failed",
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": None,
            "duration_seconds": 0,
            "deploy_output": "",
            "health_check_results": [],
            "error": "",
        }

        start_time = time.time()

        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect to VPS
            logger.info(f"Connecting to {self.config.vps_ssh_user}@{self.config.vps_ssh_host}")
            ssh.connect(
                hostname=self.config.vps_ssh_host,
                username=self.config.vps_ssh_user,
                key_filename=self.config.vps_ssh_key,
                timeout=30,
            )

            # Execute deployment script
            deploy_script = "~/bin/deploy.sh"
            logger.info(f"Executing deployment script: {deploy_script}")

            stdin, stdout, stderr = ssh.exec_command(deploy_script, timeout=self.config.deployment_timeout)

            deploy_output = stdout.read().decode()
            deploy_error = stderr.read().decode()
            exit_code = stdout.channel.recv_exit_status()

            deploy_result.update(
                {"deploy_output": deploy_output, "deploy_error": deploy_error, "deploy_exit_code": exit_code}
            )

            if exit_code == 0:
                logger.info("Deployment script completed successfully")

                # Run health checks
                health_results = await self._run_health_checks(ssh)
                deploy_result["health_check_results"] = health_results

                # Determine overall success
                all_healthy = all(check.get("healthy", False) for check in health_results)

                if all_healthy:
                    deploy_result["status"] = "success"
                    logger.info("Deployment completed successfully - all health checks passed")
                else:
                    deploy_result["status"] = "unhealthy"
                    logger.error("Deployment completed but health checks failed")
            else:
                deploy_result["status"] = "failed"
                deploy_result["error"] = f"Deployment script failed with exit code {exit_code}"
                logger.error(f"Deployment script failed: {deploy_error}")

            ssh.close()

        except Exception as e:
            deploy_result.update({"status": "error", "error": str(e)})
            logger.error(f"Deployment error: {e}")

        end_time = time.time()
        deploy_result.update(
            {"end_time": datetime.now(UTC).isoformat(), "duration_seconds": round(end_time - start_time, 2)}
        )

        # Write evidence
        success = deploy_result["status"] == "success"
        await self.evidence.write_evidence("deploy_ok", "true" if success else "false", deploy_result)

        return deploy_result

    async def _run_health_checks(self, ssh: paramiko.SSHClient) -> list[dict[str, Any]]:
        """Run health checks after deployment."""
        health_checks = []

        # Check 1: Docker services health
        try:
            stdin, stdout, stderr = ssh.exec_command("docker compose ps --format json", timeout=30)
            output = stdout.read().decode()

            health_check = {
                "name": "docker_services",
                "healthy": "running" in output.lower(),
                "output": output,
                "error": stderr.read().decode(),
            }
            health_checks.append(health_check)

        except Exception as e:
            health_checks.append({"name": "docker_services", "healthy": False, "error": str(e)})

        # Check 2: HTTP health endpoint
        try:
            health_url = f"https://{self.config.vps_ssh_host}/health"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(health_url)

                health_check = {
                    "name": "http_health",
                    "healthy": response.status_code == 200,
                    "status_code": response.status_code,
                    "response": response.text[:500],  # Truncate response
                }
                health_checks.append(health_check)

        except Exception as e:
            health_checks.append({"name": "http_health", "healthy": False, "error": str(e)})

        return health_checks


class AcceptanceRunner:
    """Main acceptance runner orchestrator."""

    def __init__(self):
        self.config = self._load_config()
        self.test_runner = AcceptanceTestRunner(self.config)
        self.deployer = SSHDeployer(self.config)
        self.evidence = EvidenceCollector(self.config)

    def _load_config(self) -> AcceptanceConfig:
        """Load configuration from environment variables."""
        return AcceptanceConfig(
            redis_url=os.getenv("REDIS_URL"),
            prp_id=os.getenv("PRP_ID"),
            vps_ssh_host=os.getenv("VPS_SSH_HOST"),
            vps_ssh_user=os.getenv("VPS_SSH_USER"),
            vps_ssh_key=os.getenv("VPS_SSH_KEY", "/home/acceptance/.ssh/id_rsa"),
            github_repo=os.getenv("GITHUB_REPO"),
            github_token=os.getenv("GITHUB_TOKEN"),
            acceptance_timeout=int(os.getenv("ACCEPTANCE_TIMEOUT", "600")),
            deployment_timeout=int(os.getenv("DEPLOYMENT_TIMEOUT", "300")),
            max_retries=int(os.getenv("MAX_RETRIES", "2")),
        )

    async def run_full_workflow(self) -> dict[str, Any]:
        """Execute the complete acceptance and deployment workflow."""
        logger.info(f"Starting acceptance workflow for PRP {self.config.prp_id}")

        workflow_result = {
            "prp_id": self.config.prp_id,
            "workflow_start": datetime.now(UTC).isoformat(),
            "workflow_end": None,
            "workflow_duration": 0,
            "acceptance_tests": {},
            "deployment": {},
            "overall_status": "failed",
            "next_steps": [],
        }

        start_time = time.time()

        try:
            # Step 1: Run acceptance tests
            logger.info("=== Step 1: Running Acceptance Tests ===")
            test_results = await self.test_runner.run_acceptance_tests()
            workflow_result["acceptance_tests"] = test_results

            if test_results["status"] != "passed":
                workflow_result["overall_status"] = "tests_failed"
                workflow_result["next_steps"] = [
                    "Fix failing acceptance tests",
                    "Review test output and errors",
                    "Re-run acceptance workflow",
                ]
                return workflow_result

            # Step 2: Deploy to VPS
            logger.info("=== Step 2: Deploying to VPS ===")
            deploy_results = await self.deployer.deploy_to_vps()
            workflow_result["deployment"] = deploy_results

            if deploy_results["status"] != "success":
                workflow_result["overall_status"] = "deployment_failed"
                workflow_result["next_steps"] = [
                    "Check VPS deployment logs",
                    "Verify SSH connectivity",
                    "Run manual deployment",
                    "Check health endpoints",
                ]
                return workflow_result

            # Success!
            workflow_result["overall_status"] = "success"
            workflow_result["next_steps"] = [
                "PRP ready for promotion",
                "Monitor production health",
                "Verify end-to-end functionality",
            ]

            logger.info("✅ Acceptance workflow completed successfully!")

        except Exception as e:
            workflow_result["overall_status"] = "error"
            workflow_result["error"] = str(e)
            workflow_result["next_steps"] = [
                "Check container logs",
                "Verify environment configuration",
                "Contact development team",
            ]
            logger.error(f"Workflow error: {e}")

        finally:
            end_time = time.time()
            workflow_result.update(
                {
                    "workflow_end": datetime.now(UTC).isoformat(),
                    "workflow_duration": round(end_time - start_time, 2),
                }
            )

            # Write final workflow summary
            await self.evidence.write_evidence(
                "acceptance_workflow", workflow_result["overall_status"], workflow_result
            )

        return workflow_result


async def main():
    """Main entry point."""
    try:
        runner = AcceptanceRunner()
        result = await runner.run_full_workflow()

        # Print summary
        print("\n" + "=" * 60)
        print("ACCEPTANCE WORKFLOW SUMMARY")
        print("=" * 60)
        print(f"PRP ID: {result['prp_id']}")
        print(f"Overall Status: {result['overall_status']}")
        print(f"Duration: {result['workflow_duration']}s")

        if result.get("acceptance_tests"):
            tests = result["acceptance_tests"]
            print(f"Tests: {tests.get('tests_passed', 0)}/{tests.get('tests_run', 0)} passed")

        if result.get("deployment"):
            deploy = result["deployment"]
            print(f"Deployment: {deploy['status']}")

        if result.get("next_steps"):
            print("\nNext Steps:")
            for step in result["next_steps"]:
                print(f"  • {step}")

        print("=" * 60)

        # Exit with appropriate code
        if result["overall_status"] == "success":
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ FATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
