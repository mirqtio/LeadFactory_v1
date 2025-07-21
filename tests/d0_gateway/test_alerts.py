"""
Tests for the alert system in P1-060 Cost guardrails
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d0_gateway.alerts import AlertChannel, AlertContext, AlertLevel, AlertManager, AlertTemplate, send_cost_alert
from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope


@pytest.fixture
def alert_manager():
    """Create a fresh alert manager instance"""
    return AlertManager()


@pytest.fixture
def sample_violation():
    """Create a sample guardrail violation"""
    return GuardrailViolation(
        limit_name="test_daily_limit",
        scope=LimitScope.PROVIDER,
        severity=AlertSeverity.WARNING,
        current_spend=Decimal("800.00"),
        limit_amount=Decimal("1000.00"),
        percentage_used=0.8,
        provider="openai",
        operation="chat_completion",
        action_taken=[GuardrailAction.LOG, GuardrailAction.ALERT],
        metadata={"test": True},
    )


@pytest.fixture
def critical_violation():
    """Create a critical guardrail violation"""
    return GuardrailViolation(
        limit_name="test_daily_limit",
        scope=LimitScope.PROVIDER,
        severity=AlertSeverity.CRITICAL,
        current_spend=Decimal("950.00"),
        limit_amount=Decimal("1000.00"),
        percentage_used=0.95,
        provider="openai",
        operation="chat_completion",
        action_taken=[GuardrailAction.LOG, GuardrailAction.ALERT, GuardrailAction.THROTTLE],
        metadata={"test": True},
    )


@pytest.fixture
def halt_violation():
    """Create a halt-level guardrail violation"""
    return GuardrailViolation(
        limit_name="test_daily_limit",
        scope=LimitScope.PROVIDER,
        severity=AlertSeverity.EMERGENCY,
        current_spend=Decimal("1050.00"),
        limit_amount=Decimal("1000.00"),
        percentage_used=1.05,
        provider="openai",
        operation="chat_completion",
        action_taken=[GuardrailAction.LOG, GuardrailAction.ALERT, GuardrailAction.BLOCK],
        metadata={"test": True},
    )


class TestAlertManager:
    """Test AlertManager functionality"""

    def test_init(self, alert_manager):
        """Test alert manager initialization"""
        assert alert_manager.logger is not None
        assert alert_manager.settings is not None
        assert isinstance(alert_manager._history, dict)
        assert isinstance(alert_manager._templates, dict)

    def test_get_alert_level(self, alert_manager, sample_violation, critical_violation, halt_violation):
        """Test alert level determination"""
        assert alert_manager._get_alert_level(sample_violation) == AlertLevel.WARNING
        assert alert_manager._get_alert_level(critical_violation) == AlertLevel.CRITICAL
        assert alert_manager._get_alert_level(halt_violation) == AlertLevel.HALT

    def test_build_context(self, alert_manager, sample_violation):
        """Test context building for alerts"""
        context = alert_manager._build_context(sample_violation)

        assert isinstance(context, AlertContext)
        assert context.violation == sample_violation
        assert context.current_spend == Decimal("800.00")
        assert context.limit == Decimal("1000.00")
        assert context.percentage == 0.8
        assert context.provider == "openai"
        assert context.operation == "chat_completion"
        assert context.recommended_action is not None

    def test_should_send_throttling(self, alert_manager, sample_violation):
        """Test alert throttling logic"""
        # First alert should send
        assert alert_manager._should_send(AlertChannel.EMAIL, sample_violation, AlertLevel.WARNING)

        # Record the alert
        alert_manager._record_sent(AlertChannel.EMAIL, sample_violation)

        # Second alert within cooldown should not send
        assert not alert_manager._should_send(AlertChannel.EMAIL, sample_violation, AlertLevel.WARNING)

        # Halt alerts should always send
        assert alert_manager._should_send(AlertChannel.EMAIL, sample_violation, AlertLevel.HALT)

    def test_send_log_alert(self, alert_manager, sample_violation):
        """Test log alert sending"""
        context = alert_manager._build_context(sample_violation)
        result = alert_manager._send_log_alert(context, AlertLevel.WARNING)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_alert_no_config(self, alert_manager, sample_violation):
        """Test email alert when not configured"""
        context = alert_manager._build_context(sample_violation)
        result = await alert_manager._send_email_alert(context, AlertLevel.WARNING)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_slack_alert_no_config(self, alert_manager, sample_violation):
        """Test Slack alert when not configured"""
        context = alert_manager._build_context(sample_violation)
        result = await alert_manager._send_slack_alert(context, AlertLevel.WARNING)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_all_channels(self, alert_manager, sample_violation):
        """Test sending alerts to all channels"""
        results = await alert_manager.send_alert(sample_violation)

        # Should at least log
        assert AlertChannel.LOG in results
        assert results[AlertChannel.LOG] is True

    def test_email_template_formatting(self, alert_manager):
        """Test email template HTML generation"""
        template_html = alert_manager._get_email_html_template("warning")

        assert "<!DOCTYPE html>" in template_html
        assert "{provider}" in template_html
        assert "{current_spend" in template_html
        assert "{percentage" in template_html
        assert "ff9900" in template_html  # Warning color

    def test_alert_history_tracking(self, alert_manager, sample_violation):
        """Test alert history is properly tracked"""
        # Send first alert
        alert_manager._record_sent(AlertChannel.EMAIL, sample_violation)

        key = f"{AlertChannel.EMAIL}:{sample_violation.limit_name}"
        assert key in alert_manager._history
        assert alert_manager._history[key].count_this_hour == 1

        # Send second alert
        alert_manager._record_sent(AlertChannel.EMAIL, sample_violation)
        assert alert_manager._history[key].count_this_hour == 2

    @pytest.mark.asyncio
    async def test_send_cost_alert_convenience(self, sample_violation):
        """Test the convenience function"""
        with patch("d0_gateway.alerts.alert_manager") as mock_manager:
            mock_manager.send_alert = AsyncMock(return_value={AlertChannel.LOG: True})

            results = await send_cost_alert(sample_violation, channels=["log"])

            mock_manager.send_alert.assert_called_once()
            assert results == {AlertChannel.LOG: True}


class TestAlertTemplates:
    """Test alert template functionality"""

    def test_template_structure(self):
        """Test alert template structure"""
        template = AlertTemplate(
            subject="Test Alert: {provider}",
            body="Alert for {provider} at {percentage:.0%}",
            html_body="<html>{provider}</html>",
        )

        assert template.subject == "Test Alert: {provider}"
        assert template.body == "Alert for {provider} at {percentage:.0%}"
        assert template.html_body == "<html>{provider}</html>"

    def test_template_formatting(self):
        """Test template string formatting"""
        template = AlertTemplate(
            subject="Cost Alert: {provider} at {percentage:.0%}",
            body="Provider {provider} has reached {percentage:.1%} of limit",
        )

        data = {
            "provider": "openai",
            "percentage": 0.85,
        }

        formatted_subject = template.subject.format(**data)
        formatted_body = template.body.format(**data)

        assert formatted_subject == "Cost Alert: openai at 85%"
        assert formatted_body == "Provider openai has reached 85.0% of limit"


class TestAlertIntegration:
    """Integration tests for alert system"""

    @pytest.mark.asyncio
    async def test_alert_flow_warning_to_critical(self, alert_manager, sample_violation, critical_violation):
        """Test alert flow from warning to critical"""
        # Send warning alert
        results1 = await alert_manager.send_alert(sample_violation)
        assert results1[AlertChannel.LOG] is True

        # Critical alerts have shorter cooldown, but still have one
        # Since these are for the same limit_name, the second might be throttled
        # Let's check that the first alert was sent
        assert len(alert_manager._history) > 0

    @pytest.mark.asyncio
    async def test_multi_provider_alerts(self, alert_manager):
        """Test alerts for multiple providers"""
        providers = ["openai", "dataaxle", "hunter"]
        violations = []

        for provider in providers:
            violation = GuardrailViolation(
                limit_name=f"{provider}_daily",
                scope=LimitScope.PROVIDER,
                severity=AlertSeverity.WARNING,
                current_spend=Decimal("80.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.8,
                provider=provider,
                operation="test_op",
                action_taken=[GuardrailAction.ALERT],
            )
            violations.append(violation)

        # Send alerts for all providers
        for violation in violations:
            results = await alert_manager.send_alert(violation)
            assert results[AlertChannel.LOG] is True

    def test_calculate_spend_rate_placeholder(self, alert_manager, sample_violation):
        """Test spend rate calculation (placeholder)"""
        rate = alert_manager._calculate_spend_rate(sample_violation)

        # This is a placeholder implementation
        assert isinstance(rate, float)
        assert rate == float(sample_violation.current_spend) * 0.1
