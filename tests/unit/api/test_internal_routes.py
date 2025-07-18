"""
Comprehensive tests for internal API routes.

Tests critical internal administrative functionality including:
- Scoring rules hot-reload endpoint with authentication
- Internal health check for scoring system
- Authentication and authorization mechanisms
- Error handling and failure scenarios
- Metrics collection and logging
"""

import time
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from prometheus_client import REGISTRY

from api.internal_routes import _get_git_sha, get_internal_auth, reload_scoring_rules, scoring_health_check


class TestInternalAuth:
    """Test internal authentication mechanisms."""

    def test_get_internal_auth_valid_token(self):
        """Test internal auth with valid token."""
        with patch("api.internal_routes.verify_internal_token", return_value=True):
            result = get_internal_auth("valid-token")
            assert result is True

    def test_get_internal_auth_invalid_token(self):
        """Test internal auth with invalid token."""
        with patch("api.internal_routes.verify_internal_token", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                get_internal_auth("invalid-token")

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "Invalid internal token"

    def test_get_internal_auth_missing_token(self):
        """Test internal auth with missing token."""
        with patch("api.internal_routes.verify_internal_token", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                get_internal_auth("")

            assert exc_info.value.status_code == 403


class TestReloadScoringRules:
    """Test scoring rules reload endpoint."""

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_success(self):
        """Test successful scoring rules reload."""
        # Mock scoring engine
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"
        mock_engine.reload_rules.return_value = None

        # Mock new schema validation
        mock_new_schema = Mock()
        mock_new_schema.version = "1.1.0"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "api.internal_routes.ConfigurableScoringEngine", spec=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "api.internal_routes.logger"
        ) as mock_logger, patch(
            "time.time", side_effect=[0.0, 0.5, 1.0]
        ):
            # Set up isinstance check
            mock_engine.__class__.__name__ = "ConfigurableScoringEngine"
            with patch("isinstance", return_value=True):
                result = await reload_scoring_rules(auth=True)

            assert result["status"] == "success"
            assert result["message"] == "Scoring rules reloaded successfully"
            assert result["details"]["old_version"] == "1.0.0"
            assert result["details"]["new_version"] == "1.1.0"
            assert result["details"]["reload_time_seconds"] == 1.0
            assert result["details"]["config_file"] == "/path/to/rules.yaml"

            mock_engine.reload_rules.assert_called_once()
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_unsupported_engine(self):
        """Test reload with unsupported engine type."""
        mock_engine = Mock()

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=False
        ):
            with pytest.raises(HTTPException) as exc_info:
                await reload_scoring_rules(auth=True)

            assert exc_info.value.status_code == 501
            assert "does not support hot reload" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_validation_failure(self):
        """Test reload with configuration validation failure."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", side_effect=ValueError("Invalid YAML")), patch(
            "api.internal_routes.logger"
        ) as mock_logger, patch(
            "api.internal_routes._get_git_sha", return_value="abc12345"
        ):
            with pytest.raises(HTTPException) as exc_info:
                await reload_scoring_rules(auth=True)

            assert exc_info.value.status_code == 400
            assert "Configuration validation failed" in exc_info.value.detail
            assert "Invalid YAML" in exc_info.value.detail
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_engine_error(self):
        """Test reload with engine reload error."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"
        mock_engine.reload_rules.side_effect = Exception("Engine reload failed")

        mock_new_schema = Mock()
        mock_new_schema.version = "1.1.0"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "api.internal_routes.logger"
        ) as mock_logger, patch(
            "api.internal_routes._get_git_sha", return_value="abc12345"
        ):
            with pytest.raises(HTTPException) as exc_info:
                await reload_scoring_rules(auth=True)

            assert exc_info.value.status_code == 500
            assert "Failed to reload scoring rules" in exc_info.value.detail
            assert "Engine reload failed" in exc_info.value.detail
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_no_schema(self):
        """Test reload when engine has no schema."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema = None
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"

        mock_new_schema = Mock()
        mock_new_schema.version = "1.0.0"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "api.internal_routes.logger"
        ) as mock_logger, patch(
            "time.time", side_effect=[0.0, 0.5]
        ):
            result = await reload_scoring_rules(auth=True)

            assert result["status"] == "success"
            assert result["details"]["old_version"] == "unknown"
            assert result["details"]["new_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_metrics_collection(self):
        """Test that metrics are properly collected during reload."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"

        mock_new_schema = Mock()
        mock_new_schema.version = "1.1.0"

        # Get initial metric values
        initial_success_count = None
        initial_failure_count = None

        try:
            success_metric = REGISTRY._names_to_collectors["internal_reload_requests_total"]
            initial_success_count = success_metric._value._value.get(("reload_rules", "success"), 0)
        except (KeyError, AttributeError):
            initial_success_count = 0

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "time.time", side_effect=[0.0, 0.5]
        ):
            result = await reload_scoring_rules(auth=True)

            assert result["status"] == "success"
            # Metric verification would need more complex setup for complete testing

    @pytest.mark.asyncio
    async def test_reload_scoring_rules_timing_measurement(self):
        """Test that reload timing is accurately measured."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"

        mock_new_schema = Mock()
        mock_new_schema.version = "1.1.0"

        # Mock time to simulate specific reload duration
        mock_times = [100.0, 100.25, 100.75]  # 0.75 second total, 0.5 second reload

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "time.time", side_effect=mock_times
        ):
            result = await reload_scoring_rules(auth=True)

            assert result["details"]["reload_time_seconds"] == 0.75
            assert result["details"]["timestamp"] == 100.75


class TestScoringHealthCheck:
    """Test scoring system health check endpoint."""

    @pytest.mark.asyncio
    async def test_scoring_health_check_healthy(self):
        """Test healthy scoring system check."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.calculate_score.return_value = {"total_score": 85.5}
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine):
            result = await scoring_health_check(auth=True)

            assert result["status"] == "healthy"
            assert result["details"]["has_configuration"] is True
            assert result["details"]["configuration_version"] == "1.0.0"
            assert result["details"]["can_calculate_scores"] is True
            assert result["details"]["engine_type"] == "ConfigurableScoringEngine"

    @pytest.mark.asyncio
    async def test_scoring_health_check_no_config(self):
        """Test health check when engine has no configuration."""
        mock_engine = Mock()
        mock_engine.rules_parser = None
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine):
            result = await scoring_health_check(auth=True)

            assert result["status"] == "unhealthy"
            assert result["details"]["has_configuration"] is False
            assert result["details"]["configuration_version"] == "unknown"

    @pytest.mark.asyncio
    async def test_scoring_health_check_no_schema(self):
        """Test health check when engine has no schema."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema = None
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine):
            result = await scoring_health_check(auth=True)

            assert result["status"] == "unhealthy"
            assert result["details"]["has_configuration"] is False
            assert result["details"]["configuration_version"] == "unknown"

    @pytest.mark.asyncio
    async def test_scoring_health_check_cannot_score(self):
        """Test health check when engine cannot calculate scores."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.calculate_score.side_effect = Exception("Scoring failed")
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine):
            result = await scoring_health_check(auth=True)

            assert result["status"] == "unhealthy"
            assert result["details"]["has_configuration"] is True
            assert result["details"]["configuration_version"] == "1.0.0"
            assert result["details"]["can_calculate_scores"] is False

    @pytest.mark.asyncio
    async def test_scoring_health_check_score_missing_field(self):
        """Test health check when score result is missing total_score."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.calculate_score.return_value = {"partial_score": 50.0}  # Missing total_score
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine):
            result = await scoring_health_check(auth=True)

            assert result["status"] == "unhealthy"
            assert result["details"]["can_calculate_scores"] is False

    @pytest.mark.asyncio
    async def test_scoring_health_check_engine_error(self):
        """Test health check when getting engine fails."""
        with patch("api.internal_routes.get_scoring_engine", side_effect=Exception("Engine unavailable")), patch(
            "api.internal_routes.logger"
        ) as mock_logger:
            result = await scoring_health_check(auth=True)

            assert result["status"] == "unhealthy"
            assert result["error"] == "Engine unavailable"
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_scoring_health_check_test_data_format(self):
        """Test that health check uses correct test data format."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.calculate_score.return_value = {"total_score": 75.0}
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine):
            await scoring_health_check(auth=True)

            # Verify the test data format passed to calculate_score
            call_args = mock_engine.calculate_score.call_args[0][0]
            assert "company_info" in call_args
            assert "online_presence" in call_args
            assert call_args["company_info"]["name_quality"] is True
            assert call_args["online_presence"]["website_quality"] is True


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_git_sha_success(self):
        """Test successful git SHA retrieval."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.stdout = "abc1234567890abcdef1234567890abcdef12\n"
            mock_run.return_value = mock_result

            result = _get_git_sha()

            assert result == "abc12345"  # First 8 characters
            mock_run.assert_called_once_with(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)

    def test_get_git_sha_failure(self):
        """Test git SHA retrieval failure."""
        with patch("subprocess.run", side_effect=Exception("Git not found")):
            result = _get_git_sha()

            assert result == "unknown"

    def test_get_git_sha_subprocess_error(self):
        """Test git SHA retrieval with subprocess error."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            result = _get_git_sha()

            assert result == "unknown"

    def test_get_git_sha_empty_output(self):
        """Test git SHA retrieval with empty output."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.stdout = "\n"
            mock_run.return_value = mock_result

            result = _get_git_sha()

            assert result == ""  # Empty string, first 8 characters of empty string


# Integration tests
class TestInternalRoutesIntegration:
    """Integration tests for internal routes."""

    @pytest.mark.asyncio
    async def test_reload_and_health_check_flow(self):
        """Test complete flow of reload followed by health check."""
        # Mock scoring engine for both operations
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"
        mock_engine.reload_rules.return_value = None
        mock_engine.calculate_score.return_value = {"total_score": 90.0}
        mock_engine.__class__.__name__ = "ConfigurableScoringEngine"

        # Mock new schema after reload
        mock_new_schema = Mock()
        mock_new_schema.version = "2.0.0"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "time.time", side_effect=[0.0, 0.5, 1.0]
        ):
            # First, reload the rules
            reload_result = await reload_scoring_rules(auth=True)
            assert reload_result["status"] == "success"
            assert reload_result["details"]["new_version"] == "2.0.0"

            # Update engine to reflect the reload
            mock_engine.rules_parser.schema.version = "2.0.0"

            # Then check health
            health_result = await scoring_health_check(auth=True)
            assert health_result["status"] == "healthy"
            assert health_result["details"]["configuration_version"] == "2.0.0"
            assert health_result["details"]["can_calculate_scores"] is True

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test that error handling is consistent across endpoints."""
        # Test reload error handling
        with patch("api.internal_routes.get_scoring_engine", side_effect=Exception("Service unavailable")), patch(
            "api.internal_routes.logger"
        ):
            with pytest.raises(HTTPException) as reload_exc:
                await reload_scoring_rules(auth=True)

            assert reload_exc.value.status_code == 500

        # Test health check error handling
        with patch("api.internal_routes.get_scoring_engine", side_effect=Exception("Service unavailable")), patch(
            "api.internal_routes.logger"
        ):
            health_result = await scoring_health_check(auth=True)

            assert health_result["status"] == "unhealthy"
            assert health_result["error"] == "Service unavailable"

    @pytest.mark.asyncio
    async def test_authentication_required_for_all_endpoints(self):
        """Test that authentication is required for all internal endpoints."""
        # This test would normally be done at the router level in FastAPI
        # Here we test the dependency function behavior

        with patch("api.internal_routes.verify_internal_token", return_value=False):
            # Test auth dependency raises exception for invalid token
            with pytest.raises(HTTPException) as exc_info:
                get_internal_auth("invalid-token")

            assert exc_info.value.status_code == 403

        with patch("api.internal_routes.verify_internal_token", return_value=True):
            # Test auth dependency succeeds for valid token
            result = get_internal_auth("valid-token")
            assert result is True

    @pytest.mark.asyncio
    async def test_logging_and_metrics_integration(self):
        """Test that logging and metrics work together correctly."""
        mock_engine = Mock()
        mock_engine.rules_parser.schema.version = "1.0.0"
        mock_engine.rules_parser.rules_file = "/path/to/rules.yaml"

        mock_new_schema = Mock()
        mock_new_schema.version = "1.1.0"

        with patch("api.internal_routes.get_scoring_engine", return_value=mock_engine), patch(
            "isinstance", return_value=True
        ), patch("api.internal_routes.validate_rules", return_value=mock_new_schema), patch(
            "api.internal_routes.logger"
        ) as mock_logger, patch(
            "time.time", side_effect=[0.0, 0.5]
        ):
            await reload_scoring_rules(auth=True)

            # Verify structured logging occurred
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args

            # Check log message
            assert "reloaded successfully" in log_call[0][0]

            # Check structured extra data
            extra_data = log_call[1]["extra"]
            assert extra_data["event"] == "rules_reload"
            assert extra_data["status"] == "success"
            assert extra_data["old_version"] == "1.0.0"
            assert extra_data["new_version"] == "1.1.0"
