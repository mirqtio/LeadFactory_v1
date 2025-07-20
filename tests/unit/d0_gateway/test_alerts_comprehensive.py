"""
Comprehensive unit tests for alerts.py - Alert system and notifications
Tests for AlertManager, alert channels, throttling, and template system
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d0_gateway.alerts import (
    AlertChannel,
    AlertContext,
    AlertHistory,
    AlertLevel,
    AlertManager,
    AlertTemplate,
    AlertThrottle,
    alert_manager,
    get_alert_manager,
    send_cost_alert,
)
from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope


class TestAlertModels:
    """Test Pydantic models for alerts"""

    def test_alert_template_creation(self):
        """Test AlertTemplate model creation"""
        template = AlertTemplate(
            subject="Test Alert: {provider}",
            body="Alert body with {current_spend}",
            html_body="<h1>Alert</h1>",
            slack_blocks=[{"type": "section", "text": "test"}],
        )

        assert template.subject == "Test Alert: {provider}"
        assert template.body == "Alert body with {current_spend}"
        assert template.html_body == "<h1>Alert</h1>"
        assert len(template.slack_blocks) == 1

    def test_alert_context_creation(self):
        """Test AlertContext model creation"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("750.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.75,
            provider="dataaxle",
            operation="search",
            action_taken=[GuardrailAction.ALERT],
        )

        context = AlertContext(
            violation=violation,
            current_spend=Decimal("750.0"),
            limit=Decimal("1000.0"),
            percentage=0.75,
            provider="dataaxle",
            operation="search",
            campaign_id=123,
            spend_rate_per_hour=50.0,
            time_to_limit="5 hours",
            recommended_action="Monitor closely",
        )

        assert context.violation == violation
        assert context.current_spend == Decimal("750.0")
        assert context.limit == Decimal("1000.0")
        assert context.percentage == 0.75
        assert context.provider == "dataaxle"
        assert context.operation == "search"
        assert context.campaign_id == 123
        assert context.spend_rate_per_hour == 50.0
        assert context.time_to_limit == "5 hours"
        assert context.recommended_action == "Monitor closely"
        assert isinstance(context.timestamp, datetime)

    def test_alert_history_creation(self):
        """Test AlertHistory model creation"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("750.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.75,
            action_taken=[GuardrailAction.ALERT],
        )

        history = AlertHistory(
            channel="email",
            limit_name="test_limit",
            last_sent=datetime.utcnow(),
            count_this_hour=3,
            aggregated_violations=[violation],
        )

        assert history.channel == "email"
        assert history.limit_name == "test_limit"
        assert history.count_this_hour == 3
        assert len(history.aggregated_violations) == 1

    def test_alert_throttle_defaults(self):
        """Test AlertThrottle default values"""
        throttle = AlertThrottle()

        assert throttle.max_alerts_per_hour == 10
        assert throttle.cooldown_minutes == 5
        assert throttle.aggregation_window_minutes == 15
        assert throttle.critical_cooldown_minutes == 2
        assert throttle.halt_cooldown_minutes == 0


class TestAlertManager:
    """Test AlertManager class"""

    def test_alert_manager_initialization(self):
        """Test AlertManager initialization"""
        manager = AlertManager()

        assert manager.logger is not None
        assert manager.settings is not None
        assert isinstance(manager._history, dict)
        assert isinstance(manager._templates, dict)
        assert manager._sendgrid is None

        # Test templates are loaded
        assert "warning" in manager._templates
        assert "critical" in manager._templates
        assert "halt" in manager._templates

    def test_load_templates(self):
        """Test template loading"""
        manager = AlertManager()
        templates = manager._load_templates()

        assert "warning" in templates
        assert "critical" in templates
        assert "halt" in templates

        # Test template structure
        warning_template = templates["warning"]
        assert "Cost Warning" in warning_template.subject
        assert "{provider}" in warning_template.subject
        assert "{percentage:.0%}" in warning_template.subject
        assert "WARNING" in warning_template.body
        assert warning_template.html_body is not None

    def test_get_email_html_template(self):
        """Test HTML email template generation"""
        manager = AlertManager()

        # Test warning template
        html = manager._get_email_html_template("warning")
        assert "<!DOCTYPE html>" in html
        assert "#ff9900" in html  # Warning color
        assert "font-family" in html
        assert "{subject}" in html
        assert "{provider}" in html

        # Test critical template
        html = manager._get_email_html_template("critical")
        assert "#ff0000" in html  # Critical color

        # Test halt template
        html = manager._get_email_html_template("halt")
        assert "#990000" in html  # Halt color

        # Test unknown severity defaults
        html = manager._get_email_html_template("unknown")
        assert "#000" in html  # Default color

    def test_get_alert_level_mapping(self):
        """Test violation to alert level mapping"""
        manager = AlertManager()

        # Test halt level (over 100%)
        violation = GuardrailViolation(
            limit_name="test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            action_taken=[GuardrailAction.ALERT],
        )
        assert manager._get_alert_level(violation) == AlertLevel.HALT

        # Test critical level (emergency severity)
        violation.percentage_used = 0.9
        violation.severity = AlertSeverity.EMERGENCY
        assert manager._get_alert_level(violation) == AlertLevel.CRITICAL

        # Test critical level (critical severity)
        violation.severity = AlertSeverity.CRITICAL
        assert manager._get_alert_level(violation) == AlertLevel.CRITICAL

        # Test warning level
        violation.severity = AlertSeverity.WARNING
        assert manager._get_alert_level(violation) == AlertLevel.WARNING

        # Test info level (default)
        violation.severity = AlertSeverity.INFO
        assert manager._get_alert_level(violation) == AlertLevel.INFO

    def test_build_context(self):
        """Test alert context building"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="daily_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider="dataaxle",
            operation="search",
            campaign_id=123,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(manager, "_calculate_spend_rate", return_value=50.0):
            context = manager._build_context(violation)

        assert context.violation == violation
        assert context.current_spend == Decimal("800.0")
        assert context.limit == Decimal("1000.0")
        assert context.percentage == 0.8
        assert context.provider == "dataaxle"
        assert context.operation == "search"
        assert context.campaign_id == 123
        assert context.spend_rate_per_hour == 50.0
        assert "hours" in context.time_to_limit or "minutes" in context.time_to_limit
        assert "Monitor closely" in context.recommended_action

    def test_build_context_time_calculations(self):
        """Test time calculation logic in context building"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("900.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.9,
            action_taken=[GuardrailAction.ALERT],
        )

        # Test minutes calculation (< 1 hour)
        with patch.object(manager, "_calculate_spend_rate", return_value=200.0):  # High rate
            context = manager._build_context(violation)
            assert "minutes" in context.time_to_limit

        # Test hours calculation (< 24 hours)
        with patch.object(manager, "_calculate_spend_rate", return_value=10.0):  # Medium rate
            context = manager._build_context(violation)
            assert "hours" in context.time_to_limit

        # Test days calculation (> 24 hours)
        with patch.object(manager, "_calculate_spend_rate", return_value=1.0):  # Low rate
            context = manager._build_context(violation)
            assert "days" in context.time_to_limit

        # Test no spending rate
        with patch.object(manager, "_calculate_spend_rate", return_value=0.0):
            context = manager._build_context(violation)
            assert "N/A" in context.time_to_limit

    def test_recommended_actions(self):
        """Test recommended action logic"""
        manager = AlertManager()

        # Test over limit action
        violation = GuardrailViolation(
            limit_name="test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            action_taken=[GuardrailAction.ALERT],
        )
        context = manager._build_context(violation)
        assert "stop all operations" in context.recommended_action.lower()

        # Test 95% action
        violation.current_spend = Decimal("950.0")
        violation.percentage_used = 0.95
        context = manager._build_context(violation)
        assert "reduce usage immediately" in context.recommended_action.lower()

        # Test 80% action
        violation.current_spend = Decimal("800.0")
        violation.percentage_used = 0.8
        context = manager._build_context(violation)
        assert "monitor closely" in context.recommended_action.lower()

        # Test under 80% action
        violation.current_spend = Decimal("600.0")
        violation.percentage_used = 0.6
        context = manager._build_context(violation)
        assert "monitor spending patterns" in context.recommended_action.lower()

    def test_get_configured_channels(self):
        """Test configured channels detection"""
        manager = AlertManager()

        # Test default (log only)
        with patch.object(manager.settings, "guardrail_alert_email", None), patch.object(
            manager.settings, "guardrail_alert_slack_webhook", None
        ):
            channels = manager._get_configured_channels()
            assert channels == [AlertChannel.LOG]

        # Test with email
        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch.object(
            manager.settings, "guardrail_alert_slack_webhook", None
        ):
            channels = manager._get_configured_channels()
            assert AlertChannel.LOG in channels
            assert AlertChannel.EMAIL in channels
            assert len(channels) == 2

        # Test with slack
        with patch.object(manager.settings, "guardrail_alert_email", None), patch.object(
            manager.settings, "guardrail_alert_slack_webhook", "https://hooks.slack.com/test"
        ):
            channels = manager._get_configured_channels()
            assert AlertChannel.LOG in channels
            assert AlertChannel.SLACK in channels
            assert len(channels) == 2

        # Test with both
        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch.object(
            manager.settings, "guardrail_alert_slack_webhook", "https://hooks.slack.com/test"
        ):
            channels = manager._get_configured_channels()
            assert AlertChannel.LOG in channels
            assert AlertChannel.EMAIL in channels
            assert AlertChannel.SLACK in channels
            assert len(channels) == 3

    def test_should_send_throttling(self):
        """Test alert throttling logic"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        # Test halt alerts are never throttled
        assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.HALT) is True

        # Test no history - should send
        assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is True

        # Add history
        key = f"{AlertChannel.EMAIL.value}:test_limit"
        now = datetime.utcnow()
        manager._history[key] = AlertHistory(
            channel=AlertChannel.EMAIL.value,
            limit_name="test_limit",
            last_sent=now - timedelta(minutes=1),  # 1 minute ago
            count_this_hour=1,
        )

        # Test cooldown for warning (5 min cooldown)
        assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is False

        # Test cooldown for critical (2 min cooldown) - should still be blocked
        assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.CRITICAL) is False

        # Test after cooldown expires
        manager._history[key].last_sent = now - timedelta(minutes=6)
        assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is True

        # Test hourly limit
        manager._history[key].count_this_hour = 10
        assert manager._should_send(AlertChannel.EMAIL, violation, AlertLevel.WARNING) is False

    def test_record_sent(self):
        """Test recording sent alerts"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        # Test first record
        manager._record_sent(AlertChannel.EMAIL, violation)
        key = f"{AlertChannel.EMAIL.value}:test_limit"
        assert key in manager._history
        assert manager._history[key].count_this_hour == 1

        # Test increment
        manager._record_sent(AlertChannel.EMAIL, violation)
        assert manager._history[key].count_this_hour == 2

        # Test reset after hour
        manager._history[key].last_sent = datetime.utcnow() - timedelta(hours=2)
        manager._record_sent(AlertChannel.EMAIL, violation)
        assert manager._history[key].count_this_hour == 1

    def test_send_log_alert(self):
        """Test log alert sending"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
            provider="dataaxle",
            recommended_action="Monitor closely",
        )

        # Test different log levels
        with patch.object(manager.logger, "info") as mock_info:
            result = manager._send_log_alert(context, AlertLevel.INFO)
            assert result is True
            mock_info.assert_called_once()

        with patch.object(manager.logger, "warning") as mock_warning:
            result = manager._send_log_alert(context, AlertLevel.WARNING)
            assert result is True
            mock_warning.assert_called_once()

        with patch.object(manager.logger, "error") as mock_error:
            result = manager._send_log_alert(context, AlertLevel.CRITICAL)
            assert result is True
            mock_error.assert_called_once()

        with patch.object(manager.logger, "error") as mock_error:
            result = manager._send_log_alert(context, AlertLevel.HALT)
            assert result is True
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_alert_success(self):
        """Test successful email alert sending"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test_limit",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
            provider="dataaxle",
            recommended_action="Monitor closely",
            spend_rate_per_hour=50.0,
            time_to_limit="4 hours",
        )

        mock_sendgrid = AsyncMock()
        mock_sendgrid.send_email.return_value = {"success": True}

        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch.object(
            manager.settings, "base_url", "https://app.example.com"
        ), patch.object(manager.settings, "from_email", "noreply@example.com"), patch.object(
            manager.settings, "from_name", "LeadFactory"
        ), patch(
            "d0_gateway.alerts.SendGridClient", return_value=mock_sendgrid
        ):
            result = await manager._send_email_alert(context, AlertLevel.WARNING)
            assert result is True
            mock_sendgrid.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_alert_no_config(self):
        """Test email alert when no email configured"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
        )

        with patch.object(manager.settings, "guardrail_alert_email", None):
            result = await manager._send_email_alert(context, AlertLevel.WARNING)
            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_alert_exception(self):
        """Test email alert exception handling"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
        )

        mock_sendgrid = AsyncMock()
        mock_sendgrid.send_email.side_effect = Exception("SendGrid error")

        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch(
            "d0_gateway.alerts.SendGridClient", return_value=mock_sendgrid
        ), patch.object(manager.logger, "error") as mock_error:
            result = await manager._send_email_alert(context, AlertLevel.WARNING)
            assert result is False
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_alert_success(self):
        """Test successful Slack alert sending"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test_limit",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
            provider="dataaxle",
            recommended_action="Monitor closely",
            time_to_limit="4 hours",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(manager.settings, "guardrail_alert_slack_webhook", "https://hooks.slack.com/test"), patch(
            "httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await manager._send_slack_alert(context, AlertLevel.WARNING)
            assert result is True

    @pytest.mark.asyncio
    async def test_send_slack_alert_no_config(self):
        """Test Slack alert when no webhook configured"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
        )

        with patch.object(manager.settings, "guardrail_alert_slack_webhook", None):
            result = await manager._send_slack_alert(context, AlertLevel.WARNING)
            assert result is False

    @pytest.mark.asyncio
    async def test_send_slack_alert_exception(self):
        """Test Slack alert exception handling"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
        )

        with patch.object(manager.settings, "guardrail_alert_slack_webhook", "https://hooks.slack.com/test"), patch(
            "httpx.AsyncClient"
        ) as mock_client, patch.object(manager.logger, "error") as mock_error:
            mock_client.return_value.__aenter__.side_effect = Exception("HTTP error")

            result = await manager._send_slack_alert(context, AlertLevel.WARNING)
            assert result is False
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_alert(self):
        """Test webhook alert (not implemented)"""
        manager = AlertManager()

        context = AlertContext(
            violation=GuardrailViolation(
                limit_name="test",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("800.0"),
                limit_amount=Decimal("1000.0"),
                percentage_used=0.8,
                action_taken=[GuardrailAction.ALERT],
            ),
            current_spend=Decimal("800.0"),
            limit=Decimal("1000.0"),
            percentage=0.8,
        )

        result = await manager._send_webhook_alert(context, AlertLevel.WARNING)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_integration(self):
        """Test complete send_alert workflow"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider="dataaxle",
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(
            manager, "_get_configured_channels", return_value=[AlertChannel.LOG, AlertChannel.EMAIL]
        ), patch.object(manager, "_should_send", return_value=True), patch.object(
            manager, "_send_to_channel", return_value=True
        ) as mock_send, patch.object(
            manager, "_record_sent"
        ) as mock_record:
            results = await manager.send_alert(violation)

            assert results[AlertChannel.LOG] is True
            assert results[AlertChannel.EMAIL] is True
            assert mock_send.call_count == 2
            assert mock_record.call_count == 2

    @pytest.mark.asyncio
    async def test_send_alert_with_throttling(self):
        """Test send_alert with throttling"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(manager, "_get_configured_channels", return_value=[AlertChannel.EMAIL]), patch.object(
            manager, "_should_send", return_value=False
        ):  # Throttled
            results = await manager.send_alert(violation)

            assert results[AlertChannel.EMAIL] is False

    @pytest.mark.asyncio
    async def test_send_alert_exception_handling(self):
        """Test send_alert exception handling"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(manager, "_get_configured_channels", return_value=[AlertChannel.EMAIL]), patch.object(
            manager, "_should_send", return_value=True
        ), patch.object(manager, "_send_to_channel", side_effect=Exception("Channel error")), patch.object(
            manager.logger, "error"
        ) as mock_error:
            results = await manager.send_alert(violation)

            assert results[AlertChannel.EMAIL] is False
            mock_error.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions"""

    @pytest.mark.asyncio
    async def test_send_cost_alert(self):
        """Test send_cost_alert convenience function"""
        violation = GuardrailViolation(
            limit_name="test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(alert_manager, "send_alert", return_value={AlertChannel.LOG: True}) as mock_send:
            result = await send_cost_alert(violation)
            mock_send.assert_called_once_with(violation, None)
            assert result[AlertChannel.LOG] is True

        # Test with specific channels
        with patch.object(alert_manager, "send_alert", return_value={AlertChannel.EMAIL: True}) as mock_send:
            result = await send_cost_alert(violation, channels=["email"])
            mock_send.assert_called_once()
            # Check that AlertChannel enum was passed
            call_args = mock_send.call_args[0]
            assert call_args[0] == violation
            assert call_args[1] == [AlertChannel.EMAIL]

    def test_get_alert_manager(self):
        """Test get_alert_manager function"""
        manager = get_alert_manager()
        assert isinstance(manager, AlertManager)
        assert manager is alert_manager


class TestAlertsIntegration:
    """Integration tests for alert system"""

    @pytest.mark.asyncio
    async def test_complete_alert_workflow(self):
        """Test complete alert workflow from violation to delivery"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="integration_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("950.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.95,
            provider="dataaxle",
            operation="search",
            campaign_id=123,
            action_taken=[GuardrailAction.ALERT],
        )

        # Mock all external dependencies
        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch.object(
            manager.settings, "guardrail_alert_slack_webhook", "https://hooks.slack.com/test"
        ), patch.object(manager, "_send_log_alert", return_value=True) as mock_log, patch.object(
            manager, "_send_email_alert", return_value=True
        ) as mock_email, patch.object(
            manager, "_send_slack_alert", return_value=True
        ) as mock_slack:
            results = await manager.send_alert(violation)

            # All channels should succeed
            assert results[AlertChannel.LOG] is True
            assert results[AlertChannel.EMAIL] is True
            assert results[AlertChannel.SLACK] is True

            # Verify all channels were called
            mock_log.assert_called_once()
            mock_email.assert_called_once()
            mock_slack.assert_called_once()

            # Verify history was recorded
            assert len(manager._history) == 3

    @pytest.mark.asyncio
    async def test_mixed_success_failure_scenario(self):
        """Test scenario with mixed success/failure across channels"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="mixed_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch.object(
            manager.settings, "guardrail_alert_slack_webhook", "https://hooks.slack.com/test"
        ), patch.object(manager, "_send_log_alert", return_value=True), patch.object(
            manager, "_send_email_alert", return_value=False
        ), patch.object(
            manager, "_send_slack_alert", return_value=True
        ):
            results = await manager.send_alert(violation)

            assert results[AlertChannel.LOG] is True
            assert results[AlertChannel.EMAIL] is False  # Failed
            assert results[AlertChannel.SLACK] is True

    @pytest.mark.asyncio
    async def test_halt_alert_bypasses_throttling(self):
        """Test that HALT alerts bypass throttling"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="halt_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,  # Over limit triggers HALT
            action_taken=[GuardrailAction.BLOCK],
        )

        # Set up existing history that would normally throttle
        key = f"{AlertChannel.EMAIL.value}:halt_test"
        manager._history[key] = AlertHistory(
            channel=AlertChannel.EMAIL.value,
            limit_name="halt_test",
            last_sent=datetime.utcnow() - timedelta(minutes=1),  # Recent
            count_this_hour=15,  # Over limit
        )

        with patch.object(manager.settings, "guardrail_alert_email", "admin@example.com"), patch.object(
            manager, "_send_log_alert", return_value=True
        ), patch.object(manager, "_send_email_alert", return_value=True) as mock_email:
            results = await manager.send_alert(violation)

            # HALT alert should succeed despite throttling conditions
            assert results[AlertChannel.EMAIL] is True
            mock_email.assert_called_once()
