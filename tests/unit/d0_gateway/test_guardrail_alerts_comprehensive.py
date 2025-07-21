"""
Comprehensive unit tests for guardrail_alerts.py - Alert system for cost guardrail violations
Tests for AlertChannel, AlertConfig, AlertMessage, AlertManager and utility functions
"""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from d0_gateway.guardrail_alerts import (
    AlertChannel,
    AlertConfig,
    AlertManager,
    AlertMessage,
    alert_manager,
    configure_alerts,
    send_cost_alert,
)
from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope


class TestAlertChannel:
    """Test AlertChannel enum"""

    def test_alert_channel_values(self):
        """Test AlertChannel enum values"""
        assert AlertChannel.EMAIL == "email"
        assert AlertChannel.SLACK == "slack"
        assert AlertChannel.WEBHOOK == "webhook"
        assert AlertChannel.LOG == "log"

    def test_alert_channel_string_enum(self):
        """Test AlertChannel string enum behavior"""
        assert isinstance(AlertChannel.EMAIL, str)
        assert str(AlertChannel.EMAIL) == "email"


class TestAlertConfig:
    """Test AlertConfig Pydantic model"""

    def test_alert_config_creation_minimal(self):
        """Test AlertConfig creation with minimal parameters"""
        config = AlertConfig(channel=AlertChannel.EMAIL)

        assert config.channel == AlertChannel.EMAIL
        assert config.enabled is True
        assert config.email_addresses is None
        assert config.slack_webhook_url is None
        assert config.webhook_url is None
        assert config.webhook_headers is None
        assert config.min_severity == AlertSeverity.WARNING
        assert config.providers is None
        assert config.max_alerts_per_hour == 10
        assert config.cooldown_minutes == 5

    def test_alert_config_creation_complete(self):
        """Test AlertConfig creation with all parameters"""
        config = AlertConfig(
            channel=AlertChannel.SLACK,
            enabled=False,
            email_addresses=["admin@example.com", "alerts@example.com"],
            slack_webhook_url="https://hooks.slack.com/test",
            webhook_url="https://api.example.com/webhook",
            webhook_headers={"Authorization": "Bearer token123"},
            min_severity=AlertSeverity.CRITICAL,
            providers=["dataaxle", "openai"],
            max_alerts_per_hour=20,
            cooldown_minutes=10,
        )

        assert config.channel == AlertChannel.SLACK
        assert config.enabled is False
        assert config.email_addresses == ["admin@example.com", "alerts@example.com"]
        assert str(config.slack_webhook_url) == "https://hooks.slack.com/test"
        assert str(config.webhook_url) == "https://api.example.com/webhook"
        assert config.webhook_headers == {"Authorization": "Bearer token123"}
        assert config.min_severity == AlertSeverity.CRITICAL
        assert config.providers == ["dataaxle", "openai"]
        assert config.max_alerts_per_hour == 20
        assert config.cooldown_minutes == 10

    def test_alert_config_url_validation(self):
        """Test AlertConfig URL validation"""
        # Valid URLs should work
        config = AlertConfig(
            channel=AlertChannel.SLACK,
            slack_webhook_url="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
        )
        assert config.slack_webhook_url is not None

        # Invalid URLs should raise validation error
        with pytest.raises(ValueError):
            AlertConfig(channel=AlertChannel.SLACK, slack_webhook_url="not-a-url")


class TestAlertMessage:
    """Test AlertMessage Pydantic model"""

    def setup_method(self):
        """Setup test fixtures"""
        self.violation = GuardrailViolation(
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

    def test_alert_message_creation(self):
        """Test AlertMessage creation"""
        message = AlertMessage(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            violation=self.violation,
            metadata={"key": "value"},
        )

        assert message.title == "Test Alert"
        assert message.message == "Test message"
        assert message.severity == AlertSeverity.WARNING
        assert message.violation == self.violation
        assert message.metadata == {"key": "value"}
        assert isinstance(message.timestamp, datetime)

    def test_alert_message_default_timestamp(self):
        """Test AlertMessage default timestamp generation"""
        before = datetime.utcnow()
        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=self.violation
        )
        after = datetime.utcnow()

        assert before <= message.timestamp <= after

    def test_alert_message_to_slack_blocks_warning(self):
        """Test AlertMessage Slack blocks formatting for warning"""
        message = AlertMessage(
            title="Cost Warning",
            message="Provider dataaxle approaching limit",
            severity=AlertSeverity.WARNING,
            violation=self.violation,
        )

        blocks = message.to_slack_blocks()

        assert len(blocks) == 1
        assert "attachments" in blocks[0]
        assert "color" in blocks[0]["attachments"][0]
        assert blocks[0]["attachments"][0]["color"] == "#ff9900"  # Warning color

        attachment_blocks = blocks[0]["attachments"][0]["blocks"]
        assert len(attachment_blocks) == 4  # header, section, section with fields, context

        # Check header
        assert attachment_blocks[0]["type"] == "header"
        assert "🚨 Cost Warning" in attachment_blocks[0]["text"]["text"]

        # Check section with message
        assert attachment_blocks[1]["type"] == "section"
        assert attachment_blocks[1]["text"]["text"] == "Provider dataaxle approaching limit"

        # Check fields section
        assert attachment_blocks[2]["type"] == "section"
        assert len(attachment_blocks[2]["fields"]) == 6
        assert "*Severity:* WARNING" in [field["text"] for field in attachment_blocks[2]["fields"]]
        assert "*Current Spend:* $800.00" in [field["text"] for field in attachment_blocks[2]["fields"]]

    def test_alert_message_to_slack_blocks_critical(self):
        """Test AlertMessage Slack blocks formatting for critical severity"""
        critical_violation = GuardrailViolation(
            limit_name="critical_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("950.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.95,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Critical Alert",
            message="Critical threshold reached",
            severity=AlertSeverity.CRITICAL,
            violation=critical_violation,
        )

        blocks = message.to_slack_blocks()
        assert blocks[0]["attachments"][0]["color"] == "#ff0000"  # Critical color

    def test_alert_message_to_slack_blocks_emergency(self):
        """Test AlertMessage Slack blocks formatting for emergency severity"""
        emergency_violation = GuardrailViolation(
            limit_name="emergency_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            action_taken=[GuardrailAction.BLOCK],
        )

        message = AlertMessage(
            title="Emergency Alert",
            message="Limit exceeded",
            severity=AlertSeverity.EMERGENCY,
            violation=emergency_violation,
        )

        blocks = message.to_slack_blocks()
        assert blocks[0]["attachments"][0]["color"] == "#990000"  # Emergency color

    def test_alert_message_to_slack_blocks_unknown_severity(self):
        """Test AlertMessage Slack blocks formatting for unknown severity"""
        # Create a violation with a mock severity not in the color map
        # Test INFO severity color handling
        message = AlertMessage(
            title="Unknown Alert", message="Info severity test", severity=AlertSeverity.INFO, violation=self.violation
        )

        blocks = message.to_slack_blocks()
        assert blocks[0]["attachments"][0]["color"] == "#36a64f"  # INFO color as defined in implementation

    def test_alert_message_to_email_html_warning(self):
        """Test AlertMessage HTML email formatting for warning"""
        message = AlertMessage(
            title="Cost Warning",
            message="Provider dataaxle approaching limit",
            severity=AlertSeverity.WARNING,
            violation=self.violation,
        )

        html = message.to_email_html()

        assert "<!DOCTYPE html>" not in html  # Should be HTML fragment
        assert "<html>" in html
        assert "#ffc107" in html  # Warning color
        assert "🚨 Cost Warning" in html
        assert "Provider dataaxle approaching limit" in html
        assert "$800.00" in html  # Current spend
        assert "$1000.00" in html  # Limit amount
        assert "80.0%" in html  # Percentage used
        assert "dataaxle" in html  # Provider
        assert "daily_limit" in html  # Limit name

    def test_alert_message_to_email_html_info(self):
        """Test AlertMessage HTML email formatting for info severity"""
        info_violation = GuardrailViolation(
            limit_name="info_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.INFO,
            current_spend=Decimal("500.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.5,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Info Alert", message="Info message", severity=AlertSeverity.INFO, violation=info_violation
        )

        html = message.to_email_html()
        assert "#28a745" in html  # Info color

    def test_alert_message_to_email_html_critical(self):
        """Test AlertMessage HTML email formatting for critical severity"""
        critical_violation = GuardrailViolation(
            limit_name="critical_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("950.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.95,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Critical Alert",
            message="Critical message",
            severity=AlertSeverity.CRITICAL,
            violation=critical_violation,
        )

        html = message.to_email_html()
        assert "#dc3545" in html  # Critical color

    def test_alert_message_to_email_html_emergency(self):
        """Test AlertMessage HTML email formatting for emergency severity"""
        emergency_violation = GuardrailViolation(
            limit_name="emergency_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            action_taken=[GuardrailAction.BLOCK],
        )

        message = AlertMessage(
            title="Emergency Alert",
            message="Emergency message",
            severity=AlertSeverity.EMERGENCY,
            violation=emergency_violation,
        )

        html = message.to_email_html()
        assert "#721c24" in html  # Emergency color

    def test_alert_message_to_email_html_no_provider(self):
        """Test AlertMessage HTML email formatting with no provider"""
        no_provider_violation = GuardrailViolation(
            limit_name="global_limit",
            scope=LimitScope.GLOBAL,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider=None,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Global Alert",
            message="Global limit",
            severity=AlertSeverity.WARNING,
            violation=no_provider_violation,
        )

        html = message.to_email_html()
        assert "All Providers" in html

    def test_alert_message_to_email_html_unknown_severity(self):
        """Test AlertMessage HTML email formatting for unknown severity"""
        # Test INFO severity color handling
        message = AlertMessage(
            title="Unknown Alert", message="Info severity test", severity=AlertSeverity.INFO, violation=self.violation
        )

        html = message.to_email_html()
        assert "#6c757d" in html  # Default color


class TestAlertManager:
    """Test AlertManager class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.manager = AlertManager()
        # Clear any existing configs to start fresh
        self.manager._configs = []
        self.manager._alert_history = {}

    def test_alert_manager_initialization(self):
        """Test AlertManager initialization"""
        assert self.manager.logger is not None
        assert isinstance(self.manager._configs, list)
        assert isinstance(self.manager._alert_history, dict)

    @patch("d0_gateway.guardrail_alerts.get_settings")
    def test_load_default_configs_log_only(self, mock_settings):
        """Test loading default configs with log only"""
        mock_settings.return_value.guardrail_alert_slack_webhook = None
        mock_settings.return_value.guardrail_alert_email = None

        manager = AlertManager()

        assert len(manager._configs) == 1
        assert manager._configs[0].channel == AlertChannel.LOG
        assert manager._configs[0].enabled is True
        assert manager._configs[0].min_severity == AlertSeverity.INFO

    @patch("d0_gateway.guardrail_alerts.get_settings")
    def test_load_default_configs_with_slack(self, mock_settings):
        """Test loading default configs with Slack configured"""
        mock_settings.return_value.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"
        mock_settings.return_value.guardrail_alert_email = None

        manager = AlertManager()

        assert len(manager._configs) == 2
        # Check log config
        log_config = next(c for c in manager._configs if c.channel == AlertChannel.LOG)
        assert log_config.enabled is True

        # Check Slack config
        slack_config = next(c for c in manager._configs if c.channel == AlertChannel.SLACK)
        assert slack_config.enabled is True
        assert str(slack_config.slack_webhook_url) == "https://hooks.slack.com/test"
        assert slack_config.min_severity == AlertSeverity.WARNING

    @patch("d0_gateway.guardrail_alerts.get_settings")
    def test_load_default_configs_with_email(self, mock_settings):
        """Test loading default configs with email configured"""
        mock_settings.return_value.guardrail_alert_slack_webhook = None
        mock_settings.return_value.guardrail_alert_email = "admin@example.com,alerts@example.com"

        manager = AlertManager()

        assert len(manager._configs) == 2
        # Check email config
        email_config = next(c for c in manager._configs if c.channel == AlertChannel.EMAIL)
        assert email_config.enabled is True
        assert email_config.email_addresses == ["admin@example.com", "alerts@example.com"]
        assert email_config.min_severity == AlertSeverity.CRITICAL

    @patch("d0_gateway.guardrail_alerts.get_settings")
    def test_load_default_configs_all_channels(self, mock_settings):
        """Test loading default configs with all channels configured"""
        mock_settings.return_value.guardrail_alert_slack_webhook = "https://hooks.slack.com/test"
        mock_settings.return_value.guardrail_alert_email = "admin@example.com"

        manager = AlertManager()

        assert len(manager._configs) == 3
        channels = {c.channel for c in manager._configs}
        assert channels == {AlertChannel.LOG, AlertChannel.SLACK, AlertChannel.EMAIL}

    def test_add_config(self):
        """Test adding alert configuration"""
        config = AlertConfig(channel=AlertChannel.WEBHOOK, webhook_url="https://api.example.com/webhook")

        with patch.object(self.manager.logger, "info") as mock_info:
            self.manager.add_config(config)

        assert config in self.manager._configs
        mock_info.assert_called_once()
        assert "webhook" in mock_info.call_args[0][0]

    def test_create_alert_message_warning(self):
        """Test creating alert message for warning violation"""
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

        message = self.manager._create_alert_message(violation)

        assert message.title == "Cost Warning - Approaching Limit"
        assert "Provider dataaxle (search)" in message.message
        assert "80.0%" in message.message
        assert "$800.00 / $1000.00" in message.message
        assert message.severity == AlertSeverity.WARNING
        assert message.violation == violation
        assert message.metadata["campaign_id"] == 123
        assert message.metadata["actions_taken"] == ["alert"]

    def test_create_alert_message_critical(self):
        """Test creating alert message for critical violation"""
        violation = GuardrailViolation(
            limit_name="critical_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("950.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.95,
            provider="openai",
            action_taken=[GuardrailAction.ALERT],
        )

        message = self.manager._create_alert_message(violation)

        assert message.title == "Cost Alert - Critical Threshold"
        assert "Provider openai" in message.message
        assert "Immediate attention required." in message.message

    def test_create_alert_message_emergency(self):
        """Test creating alert message for emergency violation"""
        violation = GuardrailViolation(
            limit_name="emergency_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            provider="dataaxle",
            action_taken=[GuardrailAction.BLOCK],
        )

        message = self.manager._create_alert_message(violation)

        assert message.title == "URGENT - Cost Limit Exceeded"
        assert "Further requests may be blocked!" in message.message

    def test_create_alert_message_no_provider(self):
        """Test creating alert message for violation without provider"""
        violation = GuardrailViolation(
            limit_name="global_limit",
            scope=LimitScope.GLOBAL,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider=None,
            action_taken=[GuardrailAction.ALERT],
        )

        message = self.manager._create_alert_message(violation)
        assert "All providers" in message.message

    def test_create_alert_message_provider_no_operation(self):
        """Test creating alert message for provider without operation"""
        violation = GuardrailViolation(
            limit_name="provider_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider="dataaxle",
            operation=None,
            action_taken=[GuardrailAction.ALERT],
        )

        message = self.manager._create_alert_message(violation)
        assert "Provider dataaxle" in message.message
        assert "Provider dataaxle (" not in message.message  # No operation parentheses

    def test_should_send_alert_disabled_config(self):
        """Test should_send_alert with disabled config"""
        config = AlertConfig(channel=AlertChannel.EMAIL, enabled=False)
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        result = self.manager._should_send_alert(config, violation)
        assert result is False

    def test_should_send_alert_severity_threshold(self):
        """Test should_send_alert with severity threshold"""
        config = AlertConfig(channel=AlertChannel.EMAIL, min_severity=AlertSeverity.CRITICAL)

        # WARNING violation should not pass CRITICAL threshold
        warning_violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        result = self.manager._should_send_alert(config, warning_violation)
        assert result is False

        # CRITICAL violation should pass CRITICAL threshold
        critical_violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("950.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.95,
            action_taken=[GuardrailAction.ALERT],
        )

        result = self.manager._should_send_alert(config, critical_violation)
        assert result is True

    def test_should_send_alert_provider_filter(self):
        """Test should_send_alert with provider filter"""
        config = AlertConfig(channel=AlertChannel.EMAIL, providers=["dataaxle", "openai"])

        # Allowed provider should pass
        allowed_violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider="dataaxle",
            action_taken=[GuardrailAction.ALERT],
        )

        result = self.manager._should_send_alert(config, allowed_violation)
        assert result is True

        # Disallowed provider should not pass
        disallowed_violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            provider="hunter",
            action_taken=[GuardrailAction.ALERT],
        )

        result = self.manager._should_send_alert(config, disallowed_violation)
        assert result is False

    def test_should_send_alert_rate_limiting(self):
        """Test should_send_alert with rate limiting"""
        config = AlertConfig(channel=AlertChannel.EMAIL, max_alerts_per_hour=2, cooldown_minutes=0)  # No cooldown

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        # First alert should pass
        result = self.manager._should_send_alert(config, violation)
        assert result is True

        # Second alert should pass (within hourly limit)
        result = self.manager._should_send_alert(config, violation)
        assert result is True

        # Third alert should fail (exceeds hourly limit)
        result = self.manager._should_send_alert(config, violation)
        assert result is False

    def test_should_send_alert_cooldown(self):
        """Test should_send_alert with cooldown period"""
        config = AlertConfig(channel=AlertChannel.EMAIL, cooldown_minutes=5)

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        # First alert should pass
        result = self.manager._should_send_alert(config, violation)
        assert result is True

        # Second alert immediately should fail (within cooldown)
        result = self.manager._should_send_alert(config, violation)
        assert result is False

        # Mock time passing beyond cooldown
        key = f"{config.channel.value}:{violation.limit_name}"
        old_time = datetime.utcnow() - timedelta(minutes=6)
        self.manager._alert_history[key] = [old_time]

        # Alert after cooldown should pass
        result = self.manager._should_send_alert(config, violation)
        assert result is True

    def test_should_send_alert_history_cleanup(self):
        """Test should_send_alert cleans up old history entries"""
        config = AlertConfig(channel=AlertChannel.EMAIL)

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        # Add old entries to history
        key = f"{config.channel.value}:{violation.limit_name}"
        old_time = datetime.utcnow() - timedelta(hours=2)
        self.manager._alert_history[key] = [old_time, old_time, old_time]

        # Should clean up old entries
        result = self.manager._should_send_alert(config, violation)
        assert result is True
        assert len(self.manager._alert_history[key]) == 1  # Only the new entry

    def test_send_log_alert(self):
        """Test sending alert to logs"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        with patch.object(self.manager.logger, "warning") as mock_warning:
            self.manager._send_log_alert(message)

        mock_warning.assert_called_once()
        log_message = mock_warning.call_args[0][0]
        assert "GUARDRAIL ALERT" in log_message
        assert "Test Alert" in log_message
        assert "$800.00/$1000.00" in log_message

    def test_send_log_alert_different_severities(self):
        """Test sending log alerts with different severities"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.INFO,
            current_spend=Decimal("500.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.5,
            action_taken=[GuardrailAction.ALERT],
        )

        # Test INFO severity
        info_message = AlertMessage(title="Info", message="Info", severity=AlertSeverity.INFO, violation=violation)
        with patch.object(self.manager.logger, "info") as mock_info:
            self.manager._send_log_alert(info_message)
        mock_info.assert_called_once()

        # Test CRITICAL severity
        critical_message = AlertMessage(
            title="Critical", message="Critical", severity=AlertSeverity.CRITICAL, violation=violation
        )
        with patch.object(self.manager.logger, "error") as mock_error:
            self.manager._send_log_alert(critical_message)
        mock_error.assert_called_once()

        # Test EMERGENCY severity
        emergency_message = AlertMessage(
            title="Emergency", message="Emergency", severity=AlertSeverity.EMERGENCY, violation=violation
        )
        with patch.object(self.manager.logger, "error") as mock_error:
            self.manager._send_log_alert(emergency_message)
        mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_alert_success(self):
        """Test successful Slack alert sending"""
        config = AlertConfig(channel=AlertChannel.SLACK, slack_webhook_url="https://hooks.slack.com/test")

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            await self.manager._send_slack_alert(config, message)

            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert call_args[0][0] == "https://hooks.slack.com/test"
            assert "json" in call_args[1]

    @pytest.mark.asyncio
    async def test_send_slack_alert_no_webhook(self):
        """Test Slack alert when no webhook URL configured"""
        config = AlertConfig(channel=AlertChannel.SLACK, slack_webhook_url=None)

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        with patch("httpx.AsyncClient") as mock_client:
            await self.manager._send_slack_alert(config, message)

            # Should not attempt HTTP request
            mock_client.return_value.__aenter__.return_value.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_email_alert_success(self):
        """Test successful email alert sending"""
        config = AlertConfig(channel=AlertChannel.EMAIL, email_addresses=["admin@example.com", "alerts@example.com"])

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        mock_sendgrid = AsyncMock()
        mock_sendgrid.send_email.return_value = {"success": True}

        with (
            patch("d0_gateway.providers.sendgrid.SendGridClient", return_value=mock_sendgrid),
            patch("d0_gateway.guardrail_alerts.get_settings") as mock_settings,
            patch.object(self.manager.logger, "info") as mock_info,
        ):
            mock_settings.return_value.from_email = "noreply@example.com"
            mock_settings.return_value.from_name = "LeadFactory"

            await self.manager._send_email_alert(config, message)

            # Should send to both email addresses
            assert mock_sendgrid.send_email.call_count == 2
            mock_info.assert_called()

    @pytest.mark.asyncio
    async def test_send_email_alert_no_addresses(self):
        """Test email alert when no addresses configured"""
        config = AlertConfig(channel=AlertChannel.EMAIL, email_addresses=None)

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        mock_sendgrid = AsyncMock()

        with patch("d0_gateway.providers.sendgrid.SendGridClient", return_value=mock_sendgrid):
            await self.manager._send_email_alert(config, message)

            # Should not attempt to send emails
            mock_sendgrid.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_email_alert_failure(self):
        """Test email alert failure handling"""
        config = AlertConfig(channel=AlertChannel.EMAIL, email_addresses=["admin@example.com"])

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        mock_sendgrid = AsyncMock()
        mock_sendgrid.send_email.return_value = {"success": False, "error": "SendGrid error"}

        with (
            patch("d0_gateway.providers.sendgrid.SendGridClient", return_value=mock_sendgrid),
            patch("d0_gateway.guardrail_alerts.get_settings") as mock_settings,
            patch.object(self.manager.logger, "error") as mock_error,
        ):
            mock_settings.return_value.from_email = "noreply@example.com"
            mock_settings.return_value.from_name = "LeadFactory"

            await self.manager._send_email_alert(config, message)

            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_send_email_alert_exception(self):
        """Test email alert exception handling"""
        config = AlertConfig(channel=AlertChannel.EMAIL, email_addresses=["admin@example.com"])

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        with (
            patch("d0_gateway.providers.sendgrid.SendGridClient", side_effect=Exception("Import error")),
            patch.object(self.manager.logger, "error") as mock_error,
        ):
            await self.manager._send_email_alert(config, message)

            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_send_webhook_alert_success(self):
        """Test successful webhook alert sending"""
        config = AlertConfig(
            channel=AlertChannel.WEBHOOK,
            webhook_url="https://api.example.com/webhook",
            webhook_headers={"Authorization": "Bearer token123"},
        )

        violation = GuardrailViolation(
            limit_name="test_limit",
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

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            await self.manager._send_webhook_alert(config, message)

            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert call_args[0][0] == "https://api.example.com/webhook"

            # Check payload structure
            payload = call_args[1]["json"]
            assert payload["title"] == "Test Alert"
            assert payload["message"] == "Test message"
            assert payload["severity"] == "warning"
            assert payload["violation"]["limit_name"] == "test_limit"
            assert payload["violation"]["current_spend"] == 800.0
            assert payload["violation"]["provider"] == "dataaxle"

            # Check headers
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer token123"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_send_webhook_alert_no_url(self):
        """Test webhook alert when no URL configured"""
        config = AlertConfig(channel=AlertChannel.WEBHOOK, webhook_url=None)

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        with patch("httpx.AsyncClient") as mock_client:
            await self.manager._send_webhook_alert(config, message)

            # Should not attempt HTTP request
            mock_client.return_value.__aenter__.return_value.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_to_channel_exception_handling(self):
        """Test send_to_channel exception handling"""
        config = AlertConfig(channel=AlertChannel.SLACK, slack_webhook_url="https://hooks.slack.com/test")

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        with (
            patch.object(self.manager, "_send_slack_alert", side_effect=Exception("Slack error")),
            patch.object(self.manager.logger, "error") as mock_error,
        ):
            await self.manager._send_to_channel(config, message)

            mock_error.assert_called_once()
            assert "Slack error" in mock_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_alert_integration(self):
        """Test complete send_alert workflow"""
        # Add configs
        log_config = AlertConfig(channel=AlertChannel.LOG)
        email_config = AlertConfig(channel=AlertChannel.EMAIL, email_addresses=["admin@example.com"])
        self.manager.add_config(log_config)
        self.manager.add_config(email_config)

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(self.manager, "_send_to_channel", return_value=None) as mock_send:
            await self.manager.send_alert(violation)

            # Should send to both channels
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_send_alert_no_configs(self):
        """Test send_alert with no configurations"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(self.manager, "_send_to_channel") as mock_send:
            await self.manager.send_alert(violation)

            # Should not send to any channels
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_filtered_out(self):
        """Test send_alert when all configs are filtered out"""
        # Add config that filters out the violation
        config = AlertConfig(channel=AlertChannel.EMAIL, min_severity=AlertSeverity.CRITICAL)
        self.manager.add_config(config)

        # Warning violation should be filtered out
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(self.manager, "_send_to_channel") as mock_send:
            await self.manager.send_alert(violation)

            # Should not send to any channels
            mock_send.assert_not_called()


class TestUtilityFunctions:
    """Test utility functions"""

    @pytest.mark.asyncio
    async def test_send_cost_alert(self):
        """Test send_cost_alert convenience function"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(alert_manager, "send_alert") as mock_send:
            await send_cost_alert(violation)

            mock_send.assert_called_once_with(violation)

    def test_configure_alerts(self):
        """Test configure_alerts convenience function"""
        with patch.object(alert_manager, "add_config") as mock_add:
            config = configure_alerts(
                AlertChannel.SLACK,
                slack_webhook_url="https://hooks.slack.com/test",
                min_severity=AlertSeverity.CRITICAL,
            )

            assert isinstance(config, AlertConfig)
            assert config.channel == AlertChannel.SLACK
            assert str(config.slack_webhook_url) == "https://hooks.slack.com/test"
            assert config.min_severity == AlertSeverity.CRITICAL
            mock_add.assert_called_once_with(config)


class TestModuleGlobals:
    """Test module-level globals and imports"""

    def test_global_alert_manager_instance(self):
        """Test that global alert_manager instance exists"""
        from d0_gateway.guardrail_alerts import alert_manager as global_manager

        assert isinstance(global_manager, AlertManager)

    def test_alert_manager_singleton_behavior(self):
        """Test that module always returns same alert manager instance"""
        from d0_gateway.guardrail_alerts import alert_manager as manager1
        from d0_gateway.guardrail_alerts import alert_manager as manager2

        assert manager1 is manager2

    def test_logger_initialization(self):
        """Test that logger is properly initialized"""
        from d0_gateway.guardrail_alerts import logger

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")


class TestAlertsIntegration:
    """Integration tests for alert system"""

    @pytest.mark.asyncio
    async def test_complete_alert_workflow(self):
        """Test complete alert workflow from violation to delivery"""
        manager = AlertManager()
        manager._configs = []  # Clear defaults

        # Add multiple channel configs
        manager.add_config(AlertConfig(channel=AlertChannel.LOG))
        manager.add_config(AlertConfig(channel=AlertChannel.EMAIL, email_addresses=["admin@example.com"]))

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

        # Mock external dependencies
        with (
            patch.object(manager, "_send_log_alert") as mock_log,
            patch.object(manager, "_send_email_alert") as mock_email,
            patch("d0_gateway.guardrail_alerts.get_settings") as mock_settings,
        ):
            mock_settings.return_value.from_email = "noreply@example.com"
            mock_settings.return_value.from_name = "LeadFactory"

            await manager.send_alert(violation)

            # Both channels should be called
            mock_log.assert_called_once()
            mock_email.assert_called_once()

            # Verify message content
            log_message = mock_log.call_args[0][0]
            assert log_message.title == "Cost Alert - Critical Threshold"
            assert "dataaxle (search)" in log_message.message
            assert "95.0%" in log_message.message

    @pytest.mark.asyncio
    async def test_rate_limiting_workflow(self):
        """Test rate limiting across multiple alerts"""
        manager = AlertManager()
        manager._configs = []
        manager._alert_history = {}

        # Add config with strict rate limiting
        config = AlertConfig(channel=AlertChannel.EMAIL, max_alerts_per_hour=1, cooldown_minutes=5)
        manager.add_config(config)

        violation = GuardrailViolation(
            limit_name="rate_limit_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        with patch.object(manager, "_send_email_alert") as mock_email:
            # First alert should go through
            await manager.send_alert(violation)
            assert mock_email.call_count == 1

            # Second alert should be rate limited
            await manager.send_alert(violation)
            assert mock_email.call_count == 1  # Still only 1 call

            # Third alert should also be rate limited
            await manager.send_alert(violation)
            assert mock_email.call_count == 1  # Still only 1 call
