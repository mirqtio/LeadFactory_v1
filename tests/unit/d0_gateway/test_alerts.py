"""
Comprehensive tests for alert system and notifications.

Tests critical alert infrastructure including:
- Multi-channel alert delivery (email, Slack, webhook, log)
- Alert throttling and rate limiting mechanisms
- Template-based message formatting
- Severity level mapping and escalation
- Context building and metrics calculation
- Error handling and failure scenarios
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from d0_gateway.alerts import (
    AlertChannel,
    AlertContext,
    AlertHistory,
    AlertLevel,
    AlertManager,
    AlertTemplate,
    AlertThrottle,
    get_alert_manager,
    send_cost_alert,
)
from d0_gateway.guardrails import AlertSeverity, GuardrailViolation


class TestAlertModels:
    """Test alert data models."""

    def test_alert_context_creation(self, test_db):
        """Test AlertContext model creation."""
        violation = GuardrailViolation(
            limit_name="daily_spend",
            provider="openai",
            operation="chat_completion",
            current_spend=Decimal("85.50"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.855,
            severity=AlertSeverity.WARNING,
            campaign_id=123,
            scope="campaign",
            action_taken=["block"],
        )

        context = AlertContext(
            violation=violation,
            current_spend=violation.current_spend,
            limit=violation.limit_amount,
            percentage=violation.percentage_used,
            provider="openai",
            operation="chat_completion",
            campaign_id=123,
            spend_rate_per_hour=8.5,
            time_to_limit="1.7 hours",
            recommended_action="Monitor closely",
        )

        assert context.violation == violation
        assert context.current_spend == Decimal("85.50")
        assert context.limit == Decimal("100.00")
        assert context.percentage == 0.855
        assert context.provider == "openai"
        assert context.operation == "chat_completion"
        assert context.campaign_id == 123
        assert context.spend_rate_per_hour == 8.5
        assert context.time_to_limit == "1.7 hours"
        assert context.recommended_action == "Monitor closely"
        assert isinstance(context.timestamp, datetime)

    def test_alert_template_creation(self):
        """Test AlertTemplate model creation."""
        template = AlertTemplate(
            subject="Test Alert: {provider}",
            body="Provider {provider} has an issue",
            html_body="<p>Provider {provider} has an issue</p>",
            slack_blocks=[{"type": "section", "text": "Test"}],
        )

        assert template.subject == "Test Alert: {provider}"
        assert template.body == "Provider {provider} has an issue"
        assert template.html_body == "<p>Provider {provider} has an issue</p>"
        assert template.slack_blocks == [{"type": "section", "text": "Test"}]

    def test_alert_history_creation(self, test_db):
        """Test AlertHistory model creation."""
        now = datetime.utcnow()
        violation = GuardrailViolation(
            limit_name="daily_spend",
            provider="openai",
            operation="test",
            current_spend=Decimal("50.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.5,
            severity=AlertSeverity.WARNING,
            scope="campaign",
            action_taken=["alert"],
        )

        history = AlertHistory(
            channel="email",
            limit_name="daily_spend",
            last_sent=now,
            count_this_hour=3,
            aggregated_violations=[violation],
        )

        assert history.channel == "email"
        assert history.limit_name == "daily_spend"
        assert history.last_sent == now
        assert history.count_this_hour == 3
        assert len(history.aggregated_violations) == 1

    def test_alert_throttle_defaults(self):
        """Test AlertThrottle default values."""
        throttle = AlertThrottle()

        assert throttle.max_alerts_per_hour == 10
        assert throttle.cooldown_minutes == 5
        assert throttle.aggregation_window_minutes == 15
        assert throttle.critical_cooldown_minutes == 2
        assert throttle.halt_cooldown_minutes == 0


class TestAlertManager:
    """Test AlertManager class."""

    def test_alert_manager_initialization(self, test_db):
        """Test AlertManager initialization."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            assert manager._history == {}
            assert isinstance(manager._templates, dict)
            assert "warning" in manager._templates
            assert "critical" in manager._templates
            assert "halt" in manager._templates
            assert manager._sendgrid is None

    def test_load_templates(self, test_db):
        """Test template loading."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            templates = manager._templates

            # Check warning template
            warning = templates["warning"]
            assert "{provider}" in warning.subject
            assert "{percentage" in warning.subject
            assert "{current_spend}" in warning.body
            assert warning.html_body is not None

            # Check critical template
            critical = templates["critical"]
            assert "CRITICAL" in critical.subject
            assert "IMMEDIATE ACTION REQUIRED" in critical.body

            # Check halt template
            halt = templates["halt"]
            assert "EMERGENCY" in halt.subject
            assert "HALTED" in halt.subject
            assert "BLOCKED" in halt.body

    def test_get_alert_level_mapping(self, test_db):
        """Test alert level mapping from violation severity."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            # Test HALT level (100% usage)
            violation = GuardrailViolation(
                limit_name="test",
                provider="test",
                operation="test",
                current_spend=Decimal("100.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=1.0,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["block"],
            )
            assert manager._get_alert_level(violation) == AlertLevel.HALT

            # Test CRITICAL level (emergency severity)
            violation.percentage_used = 0.9
            violation.severity = AlertSeverity.EMERGENCY
            assert manager._get_alert_level(violation) == AlertLevel.CRITICAL

            # Test CRITICAL level (critical severity)
            violation.severity = AlertSeverity.CRITICAL
            assert manager._get_alert_level(violation) == AlertLevel.CRITICAL

            # Test WARNING level
            violation.severity = AlertSeverity.WARNING
            assert manager._get_alert_level(violation) == AlertLevel.WARNING

            # Test INFO level (unknown severity)
            violation.severity = AlertSeverity.INFO
            assert manager._get_alert_level(violation) == AlertLevel.INFO

    def test_build_context(self, test_db):
        """Test building alert context from violation."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="chat_completion",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                campaign_id=456,
                scope="campaign",
                action_taken=["alert"],
            )

            with patch.object(manager, "_calculate_spend_rate", return_value=5.0):
                context = manager._build_context(violation)

                assert context.violation == violation
                assert context.current_spend == Decimal("80.00")
                assert context.limit == Decimal("100.00")
                assert context.percentage == 0.8
                assert context.provider == "openai"
                assert context.operation == "chat_completion"
                assert context.campaign_id == 456
                assert context.spend_rate_per_hour == 5.0
                assert context.time_to_limit == "4.0 hours"  # (100-80)/5 = 4 hours
                assert "Monitor closely" in context.recommended_action

    def test_build_context_time_calculations(self, test_db):
        """Test time to limit calculations in different scenarios."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="test",
                provider="test",
                operation="test",
                current_spend=Decimal("90.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.9,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            # Test minutes calculation (< 1 hour)
            with patch.object(manager, "_calculate_spend_rate", return_value=20.0):
                context = manager._build_context(violation)
                assert "30 minutes" in context.time_to_limit

            # Test days calculation (> 24 hours)
            with patch.object(manager, "_calculate_spend_rate", return_value=0.2):
                context = manager._build_context(violation)
                assert "days" in context.time_to_limit

            # Test no spending scenario
            with patch.object(manager, "_calculate_spend_rate", return_value=0.0):
                context = manager._build_context(violation)
                assert "N/A" in context.time_to_limit

    def test_recommended_actions(self, test_db):
        """Test recommended action logic based on usage percentage."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            with patch.object(manager, "_calculate_spend_rate", return_value=1.0):
                # Test 100% usage
                violation = GuardrailViolation(
                    limit_name="test",
                    provider="test",
                    operation="test",
                    current_spend=Decimal("100.00"),
                    limit_amount=Decimal("100.00"),
                    percentage_used=1.0,
                    severity=AlertSeverity.EMERGENCY,
                    scope="campaign",
                    action_taken=["block"],
                )
                context = manager._build_context(violation)
                assert "Increase limit or stop all operations" in context.recommended_action

                # Test 95% usage
                violation.percentage_used = 0.95
                violation.current_spend = Decimal("95.00")
                context = manager._build_context(violation)
                assert "Review and reduce usage immediately" in context.recommended_action

                # Test 80% usage
                violation.percentage_used = 0.8
                violation.current_spend = Decimal("80.00")
                context = manager._build_context(violation)
                assert "Monitor closely" in context.recommended_action

                # Test 50% usage
                violation.percentage_used = 0.5
                violation.current_spend = Decimal("50.00")
                context = manager._build_context(violation)
                assert "Monitor spending patterns" in context.recommended_action

    def test_get_configured_channels(self):
        """Test getting configured alert channels."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            channels = manager._get_configured_channels()

            assert AlertChannel.LOG in channels  # Always included
            assert AlertChannel.EMAIL in channels
            assert AlertChannel.SLACK in channels

    def test_get_configured_channels_minimal(self, test_db):
        """Test getting configured channels with minimal config."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = None
        mock_settings.guardrail_alert_slack_webhook = None

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            channels = manager._get_configured_channels()

            assert channels == [AlertChannel.LOG]  # Only log when nothing configured

    def test_should_send_throttling(self, test_db):
        """Test alert throttling logic."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="test",
                operation="test",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            # Test HALT alerts are never throttled
            assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.HALT) is True

            # Test first alert should be sent
            assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is True

            # Add history to simulate previous alert
            now = datetime.utcnow()
            manager._history["email:daily_spend"] = AlertHistory(
                channel="email",
                limit_name="daily_spend",
                last_sent=now - timedelta(minutes=2),  # 2 minutes ago
                count_this_hour=1,
            )

            # Test cooldown period (should not send)
            assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is False

            # Test after cooldown period (should send)
            manager._history["email:daily_spend"].last_sent = now - timedelta(minutes=10)
            assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is True

            # Test hourly limit
            manager._history["email:daily_spend"].count_this_hour = 10
            assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is False

    def test_record_sent(self, test_db):
        """Test recording sent alerts."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="test",
                operation="test",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            # Test first record
            manager._record_sent(AlertChannel.EMAIL, violation)

            key = "email:daily_spend"
            assert key in manager._history
            history = manager._history[key]
            assert history.channel == "email"
            assert history.limit_name == "daily_spend"
            assert history.count_this_hour == 1

            # Test subsequent record
            manager._record_sent(AlertChannel.EMAIL, violation)
            assert manager._history[key].count_this_hour == 2

            # Test hourly reset
            manager._history[key].last_sent = datetime.utcnow() - timedelta(hours=2)
            manager._record_sent(AlertChannel.EMAIL, violation)
            assert manager._history[key].count_this_hour == 1  # Reset

    def test_send_log_alert(self, test_db):
        """Test sending log alerts."""
        with patch("d0_gateway.alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="test",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            context = AlertContext(
                violation=violation,
                current_spend=Decimal("80.00"),
                limit=Decimal("100.00"),
                percentage=0.8,
                provider="openai",
                recommended_action="Monitor closely",
            )

            with patch.object(manager.logger, "warning") as mock_warning:
                result = manager._send_log_alert(context, AlertLevel.WARNING)

                assert result is True
                mock_warning.assert_called_once()
                call_args = mock_warning.call_args[0][0]
                assert "COST ALERT [WARNING]" in call_args
                assert "openai at 80.0%" in call_args
                assert "$80.00/$100.00" in call_args

    @pytest.mark.asyncio
    async def test_send_email_alert_success(self, test_db):
        """Test successful email alert sending."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.from_email = "noreply@test.com"
        mock_settings.from_name = "Test System"
        mock_settings.base_url = "https://test.com"

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            # Mock SendGrid client
            mock_sendgrid = Mock()
            mock_sendgrid.send_email = AsyncMock(return_value={"success": True})

            with patch("d0_gateway.alerts.SendGridClient", return_value=mock_sendgrid):
                violation = GuardrailViolation(
                    limit_name="daily_spend",
                    provider="openai",
                    operation="test",
                    current_spend=Decimal("80.00"),
                    limit_amount=Decimal("100.00"),
                    percentage_used=0.8,
                    severity=AlertSeverity.WARNING,
                    scope="campaign",
                    action_taken=["alert"],
                )

                context = AlertContext(
                    violation=violation,
                    current_spend=Decimal("80.00"),
                    limit=Decimal("100.00"),
                    percentage=0.8,
                    provider="openai",
                    spend_rate_per_hour=5.0,
                    time_to_limit="4.0 hours",
                    recommended_action="Monitor closely",
                )

                result = await manager._send_email_alert(context, AlertLevel.WARNING)

                assert result is True
                mock_sendgrid.send_email.assert_called_once()
                call_kwargs = mock_sendgrid.send_email.call_args[1]
                assert call_kwargs["to_email"] == "admin@test.com"
                assert "openai" in call_kwargs["subject"]
                assert "80%" in call_kwargs["subject"]

    @pytest.mark.asyncio
    async def test_send_email_alert_no_config(self, test_db):
        """Test email alert when not configured."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = None

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            context = Mock()
            result = await manager._send_email_alert(context, AlertLevel.WARNING)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_slack_alert_success(self, test_db):
        """Test successful Slack alert sending."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="test",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            context = AlertContext(
                violation=violation,
                current_spend=Decimal("80.00"),
                limit=Decimal("100.00"),
                percentage=0.8,
                provider="openai",
                time_to_limit="4.0 hours",
                recommended_action="Monitor closely",
            )

            mock_response = Mock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await manager._send_slack_alert(context, AlertLevel.WARNING)

                assert result is True
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "https://hooks.slack.com/test"

                # Check message structure
                message = call_args[1]["json"]
                assert "attachments" in message
                assert len(message["attachments"]) == 1
                attachment = message["attachments"][0]
                assert attachment["color"] == "#ff9900"  # Warning color
                assert "openai at 80%" in attachment["title"]

    @pytest.mark.asyncio
    async def test_send_slack_alert_failure(self, test_db):
        """Test Slack alert sending failure."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            context = Mock()
            context.provider = "test"
            context.percentage = 0.8
            context.violation = Mock()
            context.violation.limit_name = "daily_spend"
            context.current_spend = Decimal("80.00")
            context.limit = Decimal("100.00")
            context.time_to_limit = "4.0 hours"
            context.recommended_action = "Monitor"
            context.timestamp = datetime.utcnow()

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.side_effect = Exception("Network error")
                mock_client_class.return_value.__aenter__.return_value = mock_client

                with patch.object(manager.logger, "error") as mock_error:
                    result = await manager._send_slack_alert(context, AlertLevel.WARNING)

                    assert result is False
                    mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_integration(self, test_db):
        """Test complete send_alert workflow."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.guardrail_alert_slack_webhook = None

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="test",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            with patch.object(manager, "_send_log_alert", return_value=True) as mock_log, patch.object(
                manager, "_send_email_alert", return_value=True
            ) as mock_email:
                results = await manager.send_alert(violation)

                assert results[AlertChannel.LOG] is True
                assert results[AlertChannel.EMAIL] is True
                mock_log.assert_called_once()
                mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_with_throttling(self, test_db):
        """Test send_alert with throttling applied."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.guardrail_alert_slack_webhook = None

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="test",
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                severity=AlertSeverity.WARNING,
                scope="campaign",
                action_taken=["alert"],
            )

            # Set up throttling
            now = datetime.utcnow()
            manager._history["email:daily_spend"] = AlertHistory(
                channel="email",
                limit_name="daily_spend",
                last_sent=now - timedelta(minutes=2),  # Recent alert
                count_this_hour=1,
            )

            with patch.object(manager, "_send_log_alert", return_value=True) as mock_log:
                results = await manager.send_alert(violation)

                # Log should work, email should be throttled
                assert results[AlertChannel.LOG] is True
                assert results[AlertChannel.EMAIL] is False
                mock_log.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_send_cost_alert(self, test_db):
        """Test send_cost_alert convenience function."""
        violation = GuardrailViolation(
            limit_name="test",
            provider="test",
            operation="test",
            current_spend=Decimal("50.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.5,
            severity=AlertSeverity.WARNING,
            scope="campaign",
            action_taken=["alert"],
        )

        with patch("d0_gateway.alerts.alert_manager") as mock_manager:
            mock_manager.send_alert = AsyncMock(return_value={"log": True})

            result = await send_cost_alert(violation, ["log"])

            mock_manager.send_alert.assert_called_once()
            call_args = mock_manager.send_alert.call_args
            assert call_args[0][0] == violation
            assert call_args[0][1] == [AlertChannel.LOG]

    def test_get_alert_manager(self, test_db):
        """Test get_alert_manager function."""
        manager = get_alert_manager()
        assert isinstance(manager, AlertManager)


# Integration tests
class TestAlertsIntegration:
    """Integration tests for alert system."""

    @pytest.mark.asyncio
    async def test_complete_alert_workflow(self, test_db):
        """Test complete alert workflow from violation to delivery."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"
        mock_settings.from_email = "noreply@test.com"
        mock_settings.from_name = "Test System"
        mock_settings.base_url = "https://test.com"

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="chat_completion",
                current_spend=Decimal("95.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.95,
                severity=AlertSeverity.CRITICAL,
                campaign_id=789,
                scope="campaign",
                action_taken=["alert"],
            )

            # Mock all channel implementations
            mock_sendgrid = Mock()
            mock_sendgrid.send_email = AsyncMock(return_value={"success": True})

            mock_response = Mock()
            mock_response.status_code = 200

            with patch("d0_gateway.alerts.SendGridClient", return_value=mock_sendgrid), patch(
                "httpx.AsyncClient"
            ) as mock_client_class, patch.object(manager.logger, "error") as mock_log_error:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                results = await manager.send_alert(violation)

                # All channels should succeed
                assert results[AlertChannel.LOG] is True
                assert results[AlertChannel.EMAIL] is True
                assert results[AlertChannel.SLACK] is True

                # Verify email was sent with correct template
                mock_sendgrid.send_email.assert_called_once()
                email_kwargs = mock_sendgrid.send_email.call_args[1]
                assert "CRITICAL" in email_kwargs["subject"]
                assert "openai" in email_kwargs["subject"]

                # Verify Slack was called
                mock_client.post.assert_called_once()
                slack_args = mock_client.post.call_args
                slack_message = slack_args[1]["json"]
                assert slack_message["attachments"][0]["color"] == "#ff0000"  # Critical color

                # No errors should be logged
                mock_log_error.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_success_failure_scenario(self, test_db):
        """Test scenario with mixed success and failure across channels."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="test",
                current_spend=Decimal("100.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=1.0,
                severity=AlertSeverity.EMERGENCY,
                scope="campaign",
                action_taken=["block"],
            )

            # Mock email success but Slack failure
            mock_sendgrid = Mock()
            mock_sendgrid.send_email = AsyncMock(return_value={"success": True})

            with patch("d0_gateway.alerts.SendGridClient", return_value=mock_sendgrid), patch(
                "httpx.AsyncClient"
            ) as mock_client_class, patch.object(manager.logger, "error") as mock_log_error:
                mock_client = AsyncMock()
                mock_client.post.side_effect = Exception("Slack API error")
                mock_client_class.return_value.__aenter__.return_value = mock_client

                results = await manager.send_alert(violation)

                # Log and email should succeed, Slack should fail
                assert results[AlertChannel.LOG] is True
                assert results[AlertChannel.EMAIL] is True
                assert results[AlertChannel.SLACK] is False

                # Error should be logged for Slack failure
                mock_log_error.assert_called_once()
                error_call = mock_log_error.call_args[0][0]
                assert "Failed to send alert via slack" in error_call

    @pytest.mark.asyncio
    async def test_halt_alert_bypasses_throttling(self, test_db):
        """Test that HALT alerts bypass all throttling mechanisms."""
        mock_settings = Mock()
        mock_settings.guardrail_alert_email = "admin@test.com"
        mock_settings.guardrail_alert_slack_webhook = None

        with patch("d0_gateway.alerts.get_settings", return_value=mock_settings):
            manager = AlertManager()

            # Create HALT violation
            violation = GuardrailViolation(
                limit_name="daily_spend",
                provider="openai",
                operation="test",
                current_spend=Decimal("105.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=1.05,
                severity=AlertSeverity.EMERGENCY,
                scope="campaign",
                action_taken=["block"],
            )

            # Set up aggressive throttling
            now = datetime.utcnow()
            manager._history["email:daily_spend"] = AlertHistory(
                channel="email",
                limit_name="daily_spend",
                last_sent=now,  # Just sent
                count_this_hour=15,  # Over limit
            )

            with patch.object(manager, "_send_log_alert", return_value=True), patch.object(
                manager, "_send_email_alert", return_value=True
            ) as mock_email:
                results = await manager.send_alert(violation)

                # Both should succeed despite throttling
                assert results[AlertChannel.LOG] is True
                assert results[AlertChannel.EMAIL] is True
                mock_email.assert_called_once()

                # Verify HALT level was detected
                email_call = mock_email.call_args[0]
                assert email_call[1] == AlertLevel.HALT
