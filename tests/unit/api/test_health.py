"""
Comprehensive tests for health check endpoints.

Tests critical health monitoring infrastructure including:
- Basic health check endpoint with database and Redis validation
- Performance timing and timeout handling
- Detailed health check with system information
- Error handling and failure scenarios
- Response format and status code validation
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.health import check_database_health, check_redis_health, detailed_health_check, health_check


class TestDatabaseHealth:
    """Test database health check function."""

    def test_check_database_health_success(self):
        """Test successful database health check."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        with patch("time.time", side_effect=[0.0, 0.005]):  # 5ms latency
            result = check_database_health(mock_db)

            assert result["status"] == "connected"
            assert result["latency_ms"] == 5.0
            mock_db.execute.assert_called_once()

    def test_check_database_health_with_text_query(self):
        """Test database health check uses correct SQL query."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        check_database_health(mock_db)

        # Verify SELECT 1 query is used
        call_args = mock_db.execute.call_args[0][0]
        assert str(call_args) == "SELECT 1"

    def test_check_database_health_connection_error(self):
        """Test database health check with connection error."""
        mock_db = Mock()
        mock_db.execute.side_effect = SQLAlchemyError("Connection lost")

        with patch("api.health.logger") as mock_logger:
            result = check_database_health(mock_db)

            assert result["status"] == "error"
            assert "Connection lost" in result["error"]
            mock_logger.error.assert_called_once()

    def test_check_database_health_timeout_simulation(self):
        """Test database health check with slow response."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        # Simulate 100ms latency
        with patch("time.time", side_effect=[0.0, 0.1]):
            result = check_database_health(mock_db)

            assert result["status"] == "connected"
            assert result["latency_ms"] == 100.0

    def test_check_database_health_exception_handling(self):
        """Test database health check with unexpected exception."""
        mock_db = Mock()
        mock_db.execute.side_effect = Exception("Unexpected error")

        result = check_database_health(mock_db)

        assert result["status"] == "error"
        assert result["error"] == "Unexpected error"


class TestRedisHealth:
    """Test Redis health check function."""

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self):
        """Test successful Redis health check."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.close.return_value = None

        with (
            patch("redis.asyncio.from_url", return_value=mock_client) as mock_from_url,
            patch("time.time", side_effect=[0.0, 0.002]),
        ):  # 2ms latency
            result = await check_redis_health("redis://localhost:6379/0")

            assert result["status"] == "connected"
            assert result["latency_ms"] == 2.0
            mock_from_url.assert_called_once_with("redis://localhost:6379/0", decode_responses=True)
            mock_client.ping.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_ping_false(self):
        """Test Redis health check when PING returns False."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = False
        mock_client.close.return_value = None

        with patch("redis.asyncio.from_url", return_value=mock_client):
            result = await check_redis_health("redis://localhost:6379/0")

            assert result["status"] == "error"
            assert result["error"] == "PING returned False"

    @pytest.mark.asyncio
    async def test_check_redis_health_connection_error(self):
        """Test Redis health check with connection error."""
        with (
            patch("redis.asyncio.from_url", side_effect=redis.ConnectionError("Connection refused")),
            patch("api.health.logger") as mock_logger,
        ):
            result = await check_redis_health("redis://localhost:6379/0")

            assert result["status"] == "error"
            assert "Connection refused" in result["error"]
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_timeout_simulation(self):
        """Test Redis health check with slow response."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.close.return_value = None

        with (
            patch("redis.asyncio.from_url", return_value=mock_client),
            patch("time.time", side_effect=[0.0, 0.025]),
        ):  # 25ms latency
            result = await check_redis_health("redis://localhost:6379/0")

            assert result["status"] == "connected"
            assert result["latency_ms"] == 25.0

    @pytest.mark.asyncio
    async def test_check_redis_health_exception_during_close(self):
        """Test Redis health check when client close fails."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.close.side_effect = Exception("Close failed")

        with patch("redis.asyncio.from_url", return_value=mock_client), patch("time.time", side_effect=[0.0, 0.001]):
            # Should not raise exception even if close fails
            result = await check_redis_health("redis://localhost:6379/0")

            assert result["status"] == "connected"
            assert result["latency_ms"] == 1.0


class TestHealthCheckEndpoint:
    """Test main health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check endpoint."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None

        with (
            patch("api.health.settings", mock_settings),
            patch("time.time", side_effect=[0.0, 0.001, 0.01]),
        ):  # Start, DB check, End
            response = await health_check(mock_db)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 200

            content = json.loads(response.body)
            assert content["status"] == "ok"
            assert content["version"] == "1.0.0"
            assert content["environment"] == "test"
            assert content["checks"]["database"]["status"] == "connected"
            assert content["response_time_ms"] == 10.0

    @pytest.mark.asyncio
    async def test_health_check_database_failure(self):
        """Test health check with database failure."""
        mock_db = Mock()
        mock_db.execute.side_effect = SQLAlchemyError("Database error")

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None

        with patch("api.health.settings", mock_settings):
            response = await health_check(mock_db)

            assert response.status_code == 503
            content = json.loads(response.body)
            assert content["status"] == "unhealthy"
            assert content["checks"]["database"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_database_timeout(self):
        """Test health check with slow database response."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None

        # Simulate database check taking 60ms (exceeds 50ms limit)
        with (
            patch("api.health.settings", mock_settings),
            patch("time.time", side_effect=[0.0, 0.0, 0.06, 0.07]),
        ):  # Start, DB start, DB end, End
            response = await health_check(mock_db)

            assert response.status_code == 503
            content = json.loads(response.body)
            assert content["status"] == "unhealthy"
            assert content["checks"]["database"]["status"] == "timeout"
            assert "exceeds 50ms limit" in content["checks"]["database"]["error"]

    @pytest.mark.asyncio
    async def test_health_check_with_redis_success(self):
        """Test health check with Redis configured and working."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = "redis://redis-server:6379/0"

        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.close.return_value = None

        with (
            patch("api.health.settings", mock_settings),
            patch("redis.asyncio.from_url", return_value=mock_client),
            patch("time.time", side_effect=[0.0, 0.001, 0.002, 0.01]),
        ):
            response = await health_check(mock_db)

            assert response.status_code == 200
            content = json.loads(response.body)
            assert content["status"] == "ok"
            assert content["checks"]["database"]["status"] == "connected"
            assert content["checks"]["redis"]["status"] == "connected"

    @pytest.mark.asyncio
    async def test_health_check_with_redis_failure(self):
        """Test health check with Redis failure (non-critical)."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = "redis://redis-server:6379/0"

        with (
            patch("api.health.settings", mock_settings),
            patch("redis.asyncio.from_url", side_effect=redis.ConnectionError("Redis down")),
            patch("api.health.logger") as mock_logger,
            patch("time.time", side_effect=[0.0, 0.001, 0.01]),
        ):
            response = await health_check(mock_db)

            # Redis failure should not make health check fail (it's non-critical)
            assert response.status_code == 200
            content = json.loads(response.body)
            assert content["status"] == "ok"
            assert content["checks"]["database"]["status"] == "connected"
            assert content["checks"]["redis"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_with_redis_timeout(self):
        """Test health check with Redis timeout."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = "redis://redis-server:6379/0"

        async def slow_redis_check(redis_url):
            await asyncio.sleep(0.1)  # Simulate slow Redis
            return {"status": "connected"}

        with (
            patch("api.health.settings", mock_settings),
            patch("api.health.check_redis_health", slow_redis_check),
            patch("time.time", side_effect=[0.0, 0.001, 0.01]),
        ):
            response = await health_check(mock_db)

            assert response.status_code == 200
            content = json.loads(response.body)
            assert content["checks"]["redis"]["status"] == "timeout"
            assert "timed out after 30ms" in content["checks"]["redis"]["error"]

    @pytest.mark.asyncio
    async def test_health_check_performance_warning(self):
        """Test health check with performance warning."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None

        with (
            patch("api.health.settings", mock_settings),
            patch("api.health.logger") as mock_logger,
            patch("time.time", side_effect=[0.0, 0.001, 0.15]),
        ):  # 150ms total time
            response = await health_check(mock_db)

            assert response.status_code == 200
            content = json.loads(response.body)
            assert content["response_time_ms"] == 150.0
            assert "performance_warning" in content
            assert "exceeded 100ms threshold" in content["performance_warning"]
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_ignores_default_redis_url(self):
        """Test health check ignores default localhost Redis URL."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = "redis://localhost:6379/0"  # Default URL

        with patch("api.health.settings", mock_settings), patch("time.time", side_effect=[0.0, 0.001, 0.01]):
            response = await health_check(mock_db)

            assert response.status_code == 200
            content = json.loads(response.body)
            assert "redis" not in content["checks"]  # Should not check default Redis

    @pytest.mark.asyncio
    async def test_health_check_timestamp_format(self):
        """Test health check timestamp is in correct ISO format."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None

        with patch("api.health.settings", mock_settings), patch("api.health.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2023-12-01T12:00:00.000000"

            response = await health_check(mock_db)

            content = json.loads(response.body)
            assert content["timestamp"] == "2023-12-01T12:00:00.000000"


class TestDetailedHealthCheck:
    """Test detailed health check endpoint."""

    @pytest.mark.asyncio
    async def test_detailed_health_check_success(self):
        """Test successful detailed health check."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None
        mock_settings.use_stubs = True
        mock_settings.enable_emails = True
        mock_settings.enable_enrichment = True
        mock_settings.enable_llm_insights = False
        mock_settings.enable_email_tracking = True
        mock_settings.enable_template_studio = True
        mock_settings.enable_scoring_playground = False
        mock_settings.enable_governance = True
        mock_settings.max_daily_emails = 1000
        mock_settings.max_businesses_per_batch = 50
        mock_settings.request_timeout = 30

        with patch("api.health.settings", mock_settings), patch("time.time", side_effect=[0.0, 0.001, 0.01]):
            response = await detailed_health_check(mock_db)

            assert response.status_code == 200
            content = json.loads(response.body)

            # Basic health check data
            assert content["status"] == "ok"
            assert content["version"] == "1.0.0"

            # System information
            assert content["system"]["use_stubs"] is True
            assert content["system"]["features"]["emails"] is True
            assert content["system"]["features"]["llm_insights"] is False
            assert content["system"]["limits"]["max_daily_emails"] == 1000
            assert content["system"]["limits"]["max_businesses_per_batch"] == 50

    @pytest.mark.asyncio
    async def test_detailed_health_check_with_unhealthy_basic(self):
        """Test detailed health check when basic check is unhealthy."""
        mock_db = Mock()
        mock_db.execute.side_effect = SQLAlchemyError("Database error")

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = None
        mock_settings.use_stubs = False
        mock_settings.enable_emails = False
        mock_settings.enable_enrichment = False
        mock_settings.enable_llm_insights = False
        mock_settings.enable_email_tracking = False
        mock_settings.enable_template_studio = False
        mock_settings.enable_scoring_playground = False
        mock_settings.enable_governance = False
        mock_settings.max_daily_emails = 500
        mock_settings.max_businesses_per_batch = 25
        mock_settings.request_timeout = 60

        with patch("api.health.settings", mock_settings):
            response = await detailed_health_check(mock_db)

            assert response.status_code == 503
            content = json.loads(response.body)

            # Should still include system information even when unhealthy
            assert content["status"] == "unhealthy"
            assert content["system"]["use_stubs"] is False
            assert content["system"]["features"]["emails"] is False
            assert content["system"]["limits"]["max_daily_emails"] == 500

    @pytest.mark.asyncio
    async def test_detailed_health_check_feature_flags(self):
        """Test detailed health check includes all feature flags."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "production"
        mock_settings.redis_url = None
        mock_settings.use_stubs = False

        # Set all feature flags to different values
        mock_settings.enable_emails = True
        mock_settings.enable_enrichment = False
        mock_settings.enable_llm_insights = True
        mock_settings.enable_email_tracking = False
        mock_settings.enable_template_studio = True
        mock_settings.enable_scoring_playground = True
        mock_settings.enable_governance = False

        # Set limits
        mock_settings.max_daily_emails = 2000
        mock_settings.max_businesses_per_batch = 100
        mock_settings.request_timeout = 45

        with patch("api.health.settings", mock_settings), patch("time.time", side_effect=[0.0, 0.001, 0.01]):
            response = await detailed_health_check(mock_db)

            content = json.loads(response.body)
            features = content["system"]["features"]
            limits = content["system"]["limits"]

            # Verify all feature flags are included
            assert features["emails"] is True
            assert features["enrichment"] is False
            assert features["llm_insights"] is True
            assert features["email_tracking"] is False
            assert features["template_studio"] is True
            assert features["scoring_playground"] is True
            assert features["governance"] is False

            # Verify all limits are included
            assert limits["max_daily_emails"] == 2000
            assert limits["max_businesses_per_batch"] == 100
            assert limits["request_timeout"] == 45


# Integration tests
class TestHealthEndpointsIntegration:
    """Integration tests for health endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoints_realistic_scenario(self):
        """Test health endpoints with realistic timing and responses."""
        mock_db = Mock()
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        mock_settings = Mock()
        mock_settings.app_version = "2.1.0"
        mock_settings.environment = "production"
        mock_settings.redis_url = "redis://prod-redis:6379/0"
        mock_settings.use_stubs = False
        mock_settings.enable_emails = True
        mock_settings.enable_enrichment = True
        mock_settings.enable_llm_insights = True
        mock_settings.enable_email_tracking = True
        mock_settings.enable_template_studio = True
        mock_settings.enable_scoring_playground = True
        mock_settings.enable_governance = True
        mock_settings.max_daily_emails = 5000
        mock_settings.max_businesses_per_batch = 200
        mock_settings.request_timeout = 30

        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.close.return_value = None

        with (
            patch("api.health.settings", mock_settings),
            patch("redis.asyncio.from_url", return_value=mock_client),
            patch("time.time", side_effect=[0.0, 0.001, 0.003, 0.02]),
        ):  # Realistic timings
            # Test basic health check
            basic_response = await health_check(mock_db)
            assert basic_response.status_code == 200

            basic_content = json.loads(basic_response.body)
            assert basic_content["status"] == "ok"
            assert basic_content["environment"] == "production"
            assert basic_content["checks"]["database"]["status"] == "connected"
            assert basic_content["checks"]["redis"]["status"] == "connected"
            assert basic_content["response_time_ms"] == 20.0

            # Test detailed health check
            detailed_response = await detailed_health_check(mock_db)
            assert detailed_response.status_code == 200

            detailed_content = json.loads(detailed_response.body)

            # Should include all basic health data
            assert detailed_content["status"] == "ok"
            assert detailed_content["checks"]["database"]["status"] == "connected"

            # Should include additional system data
            assert detailed_content["system"]["use_stubs"] is False
            assert detailed_content["system"]["features"]["emails"] is True
            assert detailed_content["system"]["limits"]["max_daily_emails"] == 5000

    @pytest.mark.asyncio
    async def test_health_check_edge_cases(self):
        """Test health check with various edge cases."""
        mock_db = Mock()

        # Test with missing settings attributes
        mock_settings = Mock()
        mock_settings.app_version = "1.0.0"
        mock_settings.environment = "test"
        mock_settings.redis_url = ""  # Empty Redis URL

        # Configure database to respond normally
        mock_result = Mock()
        mock_db.execute.return_value = mock_result
        mock_result.fetchone.return_value = (1,)

        with patch("api.health.settings", mock_settings), patch("time.time", side_effect=[0.0, 0.001, 0.005]):
            response = await health_check(mock_db)

            assert response.status_code == 200
            content = json.loads(response.body)

            # Should not check Redis with empty URL
            assert "redis" not in content["checks"]
            assert content["checks"]["database"]["status"] == "connected"
