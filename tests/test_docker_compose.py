"""
Test Docker Compose configuration
"""
import subprocess
import time

import httpx
import psycopg2
import pytest
import redis


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def docker_compose_available() -> bool:
    """Check if docker-compose is available"""
    try:
        result = subprocess.run(["docker-compose", "--version"], capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


class TestDockerCompose:
    """Test Docker Compose setup for local development"""

    @pytest.fixture(scope="class")
    def docker_compose_up(self):
        """Start Docker Compose services"""
        # Stop any existing services
        run_command("docker-compose down -v")

        # Start services
        code, stdout, stderr = run_command("docker-compose up -d")
        assert code == 0, f"Failed to start services: {stderr}"

        # Wait for services to be ready
        time.sleep(10)

        yield

        # Cleanup
        run_command("docker-compose down -v")

    @pytest.mark.skipif(
        not docker_compose_available(), reason="docker-compose not available"
    )
    def test_docker_compose_file_valid(self):
        """Test that docker-compose.yml is valid"""
        code, stdout, stderr = run_command("docker-compose config")
        assert code == 0, f"Invalid docker-compose.yml: {stderr}"

    @pytest.mark.skipif(
        not docker_compose_available(), reason="docker-compose not available"
    )
    def test_docker_compose_test_file_valid(self):
        """Test that docker-compose.test.yml is valid"""
        code, stdout, stderr = run_command(
            "docker-compose -f docker-compose.test.yml config"
        )
        assert code == 0, f"Invalid docker-compose.test.yml: {stderr}"

    @pytest.mark.integration
    @pytest.mark.skipif(
        not docker_compose_available(), reason="docker-compose not available"
    )
    def test_all_services_start(self, docker_compose_up):
        """Test that all services start properly"""
        code, stdout, stderr = run_command("docker-compose ps")
        assert code == 0

        # Check that all services are running
        services = [
            "db",
            "redis",
            "stub-server",
            "app",
            "prometheus",
            "grafana",
            "mailhog",
        ]
        for service in services:
            assert service in stdout, f"Service {service} not found in running services"

    @pytest.mark.integration
    def test_database_connection(self, docker_compose_up):
        """Test PostgreSQL database connection"""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="leadfactory_dev",
                user="leadfactory",
                password="leadfactory_dev",
            )
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            assert version is not None
            assert "PostgreSQL" in version[0]
            cursor.close()
            conn.close()
        except Exception as e:
            pytest.fail(f"Failed to connect to PostgreSQL: {e}")

    @pytest.mark.integration
    def test_redis_connection(self, docker_compose_up):
        """Test Redis connection"""
        try:
            r = redis.Redis(host="localhost", port=6379, decode_responses=True)
            r.ping()

            # Test basic operations
            r.set("test_key", "test_value")
            assert r.get("test_key") == "test_value"
            r.delete("test_key")
        except Exception as e:
            pytest.fail(f"Failed to connect to Redis: {e}")

    @pytest.mark.integration
    def test_stub_server_health(self, docker_compose_up):
        """Test stub server health endpoint"""
        try:
            response = httpx.get("http://localhost:5010/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["use_stubs"] is True
        except Exception as e:
            pytest.fail(f"Failed to connect to stub server: {e}")

    @pytest.mark.integration
    def test_app_health(self, docker_compose_up):
        """Test main application health endpoint"""
        # Wait a bit more for app to start
        time.sleep(5)

        try:
            response = httpx.get("http://localhost:8000/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
        except Exception as e:
            pytest.fail(f"Failed to connect to app: {e}")

    @pytest.mark.integration
    def test_prometheus_health(self, docker_compose_up):
        """Test Prometheus is running"""
        try:
            response = httpx.get("http://localhost:9090/-/ready")
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"Failed to connect to Prometheus: {e}")

    @pytest.mark.integration
    def test_grafana_health(self, docker_compose_up):
        """Test Grafana is running"""
        try:
            response = httpx.get("http://localhost:3000/api/health")
            assert response.status_code == 200
            data = response.json()
            assert data["database"] == "ok"
        except Exception as e:
            pytest.fail(f"Failed to connect to Grafana: {e}")

    @pytest.mark.integration
    def test_mailhog_health(self, docker_compose_up):
        """Test Mailhog is running"""
        try:
            # Check SMTP port
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", 1025))
            sock.close()
            assert result == 0, "Mailhog SMTP port not accessible"

            # Check Web UI
            response = httpx.get("http://localhost:8025/api/v2/messages")
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(f"Failed to connect to Mailhog: {e}")

    def test_volumes_created(self):
        """Test that Docker volumes are created"""
        code, stdout, stderr = run_command("docker volume ls --format '{{.Name}}'")
        assert code == 0

        expected_volumes = [
            "postgres-data",
            "redis-data",
            "prometheus-data",
            "grafana-data",
        ]

        for volume in expected_volumes:
            assert any(
                volume in line for line in stdout.splitlines()
            ), f"Volume {volume} not found"
