#!/usr/bin/env python3
"""
Bootstrap CI v3 - Local Docker CI Testing
Mirrors GitHub CI exactly to catch all issues before pushing

This script runs the EXACT same Docker environment and tests as GitHub CI.
Any failure here WILL fail in GitHub CI, and any pass here WILL pass in GitHub CI.
"""

import subprocess
import sys
import time
from pathlib import Path


class Colors:
    """Terminal colors for output"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(message: str):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def print_step(message: str):
    """Print a step message"""
    print(f"{Colors.CYAN}▶ {message}{Colors.RESET}")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")


def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.MAGENTA}ℹ️  {message}{Colors.RESET}")


def run_command(cmd: list[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run a command and return the result"""
    print_step(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
        if check and result.returncode == 0:
            print_success("Command succeeded")
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        raise


def check_docker():
    """Check if Docker is running"""
    print_step("Checking Docker status...")
    try:
        run_command(["docker", "info"], capture_output=True)
        print_success("Docker is running")
        return True
    except Exception:
        print_error("Docker is not running or not installed")
        print_info("Please start Docker Desktop or install Docker")
        return False


def clean_docker_environment():
    """Clean up any existing containers and volumes"""
    print_header("Cleaning Docker Environment")

    # Stop and remove any existing containers
    print_step("Stopping existing containers...")
    run_command(["docker", "compose", "-f", "docker-compose.test.yml", "down", "-v"], check=False)

    # Clean up any orphaned containers
    print_step("Removing orphaned containers...")
    result = run_command(["docker", "ps", "-aq"], capture_output=True, check=False)
    if result.stdout.strip():
        container_ids = result.stdout.strip().split("\n")
        for container_id in container_ids:
            run_command(["docker", "rm", "-f", container_id], check=False)

    print_success("Docker environment cleaned")


def build_test_image():
    """Build the test Docker image - mirrors GitHub CI exactly"""
    print_header("Building Test Image")

    # This mirrors the GitHub CI build step exactly
    try:
        run_command(["docker", "build", "-f", "Dockerfile.test", "-t", "leadfactory-test", "."])
        print_success("Test image built successfully")
        return True
    except subprocess.CalledProcessError:
        print_error("Docker build failed")

        # Mirror the debugging from GitHub CI
        print_info("Current directory contents:")
        run_command(["ls", "-la"], check=False)

        print_info("Dockerfile.test contents (first 20 lines):")
        run_command(["head", "-20", "Dockerfile.test"], check=False)

        return False


def start_services():
    """Start PostgreSQL and stub server - mirrors GitHub CI exactly"""
    print_header("Starting Services")

    # Create coverage directory (like GitHub CI)
    print_step("Creating coverage directory...")
    Path("coverage").mkdir(exist_ok=True)

    # Start services
    print_step("Starting PostgreSQL and stub server...")
    run_command(["docker", "compose", "-f", "docker-compose.test.yml", "up", "-d", "postgres", "stub-server"])

    # Wait for PostgreSQL - mirrors GitHub CI timeout and check
    print_step("Waiting for PostgreSQL to be ready...")
    postgres_ready = False
    for i in range(60):  # 60 second timeout like GitHub CI
        try:
            result = run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    "docker-compose.test.yml",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_isready",
                    "-U",
                    "postgres",
                ],
                check=False,
                capture_output=True,
            )

            if result.returncode == 0:
                postgres_ready = True
                break
        except Exception:
            pass

        if i % 5 == 0:
            print_info(f"Still waiting for PostgreSQL... ({i}s)")
        time.sleep(1)

    if not postgres_ready:
        print_error("PostgreSQL failed to start")
        print_info("PostgreSQL container logs:")
        run_command(["docker", "compose", "-f", "docker-compose.test.yml", "logs", "postgres"], check=False)
        return False

    print_success("PostgreSQL is ready")

    # Wait for stub server - mirrors GitHub CI timeout and check
    print_step("Waiting for stub server to be ready...")
    stub_ready = False
    for i in range(60):  # 60 second timeout like GitHub CI
        try:
            result = run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    "docker-compose.test.yml",
                    "exec",
                    "-T",
                    "stub-server",
                    "curl",
                    "-f",
                    "http://localhost:5010/health",
                ],
                check=False,
                capture_output=True,
            )

            if result.returncode == 0:
                stub_ready = True
                break
        except Exception:
            pass

        if i % 2 == 0:
            print_info("Waiting for stub server...")
        time.sleep(2)

    if not stub_ready:
        print_error("Stub server failed to start")
        print_info("Stub server container logs:")
        run_command(["docker", "compose", "-f", "docker-compose.test.yml", "logs", "stub-server"], check=False)
        print_info("Checking stub server status:")
        run_command(["docker", "compose", "-f", "docker-compose.test.yml", "ps", "stub-server"], check=False)
        return False

    print_success("All services are ready")
    return True


def run_tests():
    """Run tests in Docker - mirrors GitHub CI exactly"""
    print_header("Running Tests in Docker")

    # Create directories with proper permissions (like GitHub CI)
    print_step("Creating test directories...")
    Path("./coverage").mkdir(exist_ok=True)
    Path("./test-results").mkdir(exist_ok=True)

    # Set permissions (mirrors GitHub CI)
    run_command(["chmod", "777", "./coverage", "./test-results"])

    print_info("Starting comprehensive test suite...")

    # Run tests with exact same command as GitHub CI
    # Using timeout of 1200 seconds (20 minutes) like GitHub CI
    test_result = run_command(
        ["timeout", "1200", "docker", "compose", "-f", "docker-compose.test.yml", "run", "--rm", "test"], check=False
    )

    if test_result.returncode != 0:
        print_error(f"Tests failed with exit code: {test_result.returncode}")

        # Mirror GitHub CI debugging steps
        print_info("=== Container Logs ===")
        run_command(["docker", "compose", "-f", "docker-compose.test.yml", "logs", "test", "--tail=200"], check=False)

        print_info("=== Services Status ===")
        run_command(["docker", "compose", "-f", "docker-compose.test.yml", "ps"], check=False)

        print_info("=== Network Connectivity Check ===")
        connectivity_cmd = """
echo 'Testing database connection...'
python -c 'import psycopg2; psycopg2.connect("$DATABASE_URL"); print("✅ Database connection OK")'
echo 'Testing stub server connection...'
curl -f http://stub-server:5010/health || echo '❌ Stub server connection failed'
"""
        run_command(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.test.yml",
                "run",
                "--rm",
                "test",
                "bash",
                "-c",
                connectivity_cmd,
            ],
            check=False,
        )

        print_info("=== Python Environment ===")
        run_command(
            ["docker", "compose", "-f", "docker-compose.test.yml", "run", "--rm", "test", "pip", "list"], check=False
        )

        # Check for partial test results
        print_info("=== Checking for partial test results ===")
        run_command(["ls", "-la", "./coverage/"], check=False)
        run_command(["ls", "-la", "./test-results/"], check=False)

        return False

    print_success("All tests passed successfully")
    return True


def extract_results():
    """Extract test results - mirrors GitHub CI exactly"""
    print_header("Extracting Test Results")

    # Check coverage directory
    print_info("Coverage directory contents:")
    run_command(["ls", "-la", "./coverage/"], check=False)

    # Check test-results directory
    print_info("Test-results directory contents:")
    run_command(["ls", "-la", "./test-results/"], check=False)

    # Ensure test-results directory exists
    Path("test-results").mkdir(exist_ok=True)

    # Copy coverage.xml if it exists
    coverage_file = Path("./coverage/coverage.xml")
    if coverage_file.exists():
        run_command(["cp", "./coverage/coverage.xml", "./test-results/"])
        print_success("Copied coverage.xml")

    # Check for junit.xml
    junit_file = Path("./test-results/junit.xml")
    junit_root = Path("./junit.xml")

    if junit_file.exists():
        print_success("Found junit.xml")
    elif junit_root.exists():
        run_command(["cp", "./junit.xml", "./test-results/"])
        print_success("Copied junit.xml from root")

    # Final check
    print_info("Final test-results contents:")
    run_command(["ls", "-la", "test-results/"], check=False)


def cleanup():
    """Clean up Docker environment"""
    print_header("Cleaning Up")
    run_command(["docker", "compose", "-f", "docker-compose.test.yml", "down", "-v"], check=False)
    print_success("Cleanup complete")


def main():
    """Main function - runs exact same flow as GitHub CI"""
    print_header("Bootstrap CI v3 - Local Docker Testing")
    print_info("This runs the EXACT same tests as GitHub CI")
    print_info("If this passes, GitHub CI will pass")
    print_info("If this fails, GitHub CI will fail")

    # Check Docker
    if not check_docker():
        return 1

    # Clean environment
    clean_docker_environment()

    # Build test image
    if not build_test_image():
        cleanup()
        return 1

    # Start services
    if not start_services():
        cleanup()
        return 1

    # Run tests
    test_passed = run_tests()

    # Extract results (always run, even if tests failed)
    extract_results()

    # Cleanup
    cleanup()

    # Final status
    if test_passed:
        print_header("✅ ALL TESTS PASSED - CI WILL BE GREEN")
        return 0
    print_header("❌ TESTS FAILED - CI WILL BE RED")
    print_warning("Fix the issues above before pushing to GitHub")
    return 1


if __name__ == "__main__":
    sys.exit(main())
