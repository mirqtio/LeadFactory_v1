"""
Unit tests for cost guardrail alert system (P1-060)
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from d0_gateway.guardrail_alerts import (
    AlertChannel,
    AlertConfig,
    AlertManager,
    AlertMessage,
    AlertSeverity,
    configure_alerts,
    send_cost_alert,
)
from d0_gateway.guardrails import GuardrailViolation, LimitScope


class TestAlertConfig:
    """Test AlertConfig model"""

    def test_create_email_config(self):
        """Test creating email alert configuration"""
        config = AlertConfig(
            channel=AlertChannel.EMAIL,
            email_addresses=["admin@example.com", "ops@example.com"],
            min_severity=AlertSeverity.WARNING,
        )

        assert config.channel == AlertChannel.EMAIL
        assert config.enabled is True
        assert config.email_addresses == ["admin@example.com", "ops@example.com"]
        assert config.min_severity == AlertSeverity.WARNING
        assert config.max_alerts_per_hour == 10
        assert config.cooldown_minutes == 5

    def test_create_slack_config(self):
        """Test creating Slack alert configuration"""
        config = AlertConfig(
            channel=AlertChannel.SLACK,
            slack_webhook_url="https://hooks.slack.com/services/xxx",
            min_severity=AlertSeverity.CRITICAL,
            providers=["openai", "dataaxle"],
        )

        assert config.channel == AlertChannel.SLACK
        assert config.slack_webhook_url == "https://hooks.slack.com/services/xxx"
        assert config.providers == ["openai", "dataaxle"]

    def test_create_webhook_config(self):
        """Test creating webhook alert configuration"""
        config = AlertConfig(
            channel=AlertChannel.WEBHOOK,
            webhook_url="https://api.example.com/alerts",
            webhook_headers={"Authorization": "Bearer token"},
            max_alerts_per_hour=20,
        )

        assert config.channel == AlertChannel.WEBHOOK
        assert config.webhook_url == "https://api.example.com/alerts"
        assert config.webhook_headers == {"Authorization": "Bearer token"}
        assert config.max_alerts_per_hour == 20


class TestAlertMessage:
    """Test AlertMessage model"""

    def test_create_alert_message(self):
        """Test creating an alert message"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("80.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.8,
            provider="openai",
            action_taken=[],
        )

        message = AlertMessage(
            title="Cost Warning", message="Approaching daily limit", severity=AlertSeverity.WARNING, violation=violation
        )

        assert message.title == "Cost Warning"
        assert message.message == "Approaching daily limit"
        assert message.severity == AlertSeverity.WARNING
        assert message.violation == violation

    def test_to_slack_blocks(self):
        """Test formatting message as Slack blocks"""
        violation = GuardrailViolation(
            limit_name="openai_daily",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("95.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.95,
            provider="openai",
            action_taken=[],
        )

        message = AlertMessage(
            title="Critical Cost Alert",
            message="OpenAI spending at 95% of daily limit",
            severity=AlertSeverity.CRITICAL,
            violation=violation,
        )

        blocks = message.to_slack_blocks()

        assert len(blocks) == 1
        assert "attachments" in blocks[0]
        assert blocks[0]["attachments"][0]["color"] == "#ff0000"  # Critical = red

        # Check blocks content
        actual_blocks = blocks[0]["attachments"][0]["blocks"]
        assert actual_blocks[0]["type"] == "header"
        assert "Critical Cost Alert" in actual_blocks[0]["text"]["text"]
        assert actual_blocks[1]["type"] == "section"
        assert "95% of daily limit" in actual_blocks[1]["text"]["text"]

    def test_to_email_html(self):
        """Test formatting message as HTML email"""
        violation = GuardrailViolation(
            limit_name="global_daily",
            scope=LimitScope.GLOBAL,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1050.00"),
            limit_amount=Decimal("1000.00"),
            percentage_used=1.05,
            provider=None,
            action_taken=[],
        )

        message = AlertMessage(
            title="URGENT - Daily Budget Exceeded",
            message="Total spending has exceeded the daily budget limit",
            severity=AlertSeverity.EMERGENCY,
            violation=violation,
        )

        html = message.to_email_html()

        assert "<html>" in html
        assert "URGENT - Daily Budget Exceeded" in html
        assert "$1050.00" in html
        assert "$1000.00" in html
        assert "105.0%" in html
        assert "All Providers" in html


class TestAlertManager:
    """Test AlertManager functionality"""

    def test_default_configs(self):
        """Test default alert configurations are loaded"""
        with patch("d0_gateway.guardrail_alerts.get_settings") as mock_settings:
            mock_settings.return_value = Mock(slack_webhook_url=None, alert_email_addresses=None)

            manager = AlertManager()

            # Should have at least LOG channel
            assert any(c.channel == AlertChannel.LOG for c in manager._configs)

    def test_add_config(self):
        """Test adding alert configuration"""
        manager = AlertManager()

        config = AlertConfig(channel=AlertChannel.EMAIL, email_addresses=["test@example.com"])

        initial_count = len(manager._configs)
        manager.add_config(config)

        assert len(manager._configs) == initial_count + 1
        assert config in manager._configs

    def test_should_send_alert_severity(self):
        """Test alert filtering by severity"""
        manager = AlertManager()

        config = AlertConfig(channel=AlertChannel.SLACK, min_severity=AlertSeverity.WARNING)

        # Info severity - should not send
        info_violation = Mock(severity=AlertSeverity.INFO, limit_name="test", provider=None)
        assert not manager._should_send_alert(config, info_violation)

        # Warning severity - should send
        warning_violation = Mock(severity=AlertSeverity.WARNING, limit_name="test", provider=None)
        assert manager._should_send_alert(config, warning_violation)

    def test_should_send_alert_provider_filter(self):
        """Test alert filtering by provider"""
        manager = AlertManager()

        config = AlertConfig(channel=AlertChannel.EMAIL, providers=["openai", "dataaxle"])

        # Matching provider - should send
        openai_violation = Mock(severity=AlertSeverity.WARNING, limit_name="test", provider="openai")
        assert manager._should_send_alert(config, openai_violation)

        # Non-matching provider - should not send
        other_violation = Mock(severity=AlertSeverity.WARNING, limit_name="test", provider="hunter")
        assert not manager._should_send_alert(config, other_violation)

    def test_rate_limiting(self):
        """Test alert rate limiting"""
        manager = AlertManager()

        config = AlertConfig(channel=AlertChannel.EMAIL, max_alerts_per_hour=2, cooldown_minutes=5)

        violation = Mock(severity=AlertSeverity.WARNING, limit_name="test_limit", provider="openai")

        # First alert should send
        assert manager._should_send_alert(config, violation)

        # Second alert should send
        assert manager._should_send_alert(config, violation)

        # Third alert should be rate limited
        assert not manager._should_send_alert(config, violation)

    def test_cooldown_period(self):
        """Test alert cooldown period"""
        manager = AlertManager()

        config = AlertConfig(channel=AlertChannel.SLACK, cooldown_minutes=5)

        violation = Mock(severity=AlertSeverity.WARNING, limit_name="test_limit", provider="openai")

        # First alert should send
        assert manager._should_send_alert(config, violation)

        # Immediate second alert should not send (cooldown)
        assert not manager._should_send_alert(config, violation)

        # Simulate time passing
        key = f"{config.channel.value}:{violation.limit_name}"
        manager._alert_history[key] = [datetime.utcnow() - timedelta(minutes=6)]

        # Should send after cooldown
        assert manager._should_send_alert(config, violation)

    def test_create_alert_message(self):
        """Test creating alert message from violation"""
        manager = AlertManager()

        violation = GuardrailViolation(
            limit_name="openai_daily",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("95.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.95,
            provider="openai",
            operation="chat",
            action_taken=[],
            campaign_id=123,
        )

        message = manager._create_alert_message(violation)

        assert message.title == "Cost Alert - Critical Threshold"
        assert "openai (chat)" in message.message
        assert "95.0%" in message.message
        assert "$95.00 / $100.00" in message.message
        assert message.metadata["campaign_id"] == 123

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """Test sending alert through channels"""
        manager = AlertManager()

        # Add test config
        config = AlertConfig(channel=AlertChannel.LOG, min_severity=AlertSeverity.INFO)
        manager._configs = [config]

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.GLOBAL,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.00"),
            limit_amount=Decimal("1000.00"),
            percentage_used=0.8,
            action_taken=[],
        )

        with patch.object(manager, "_send_log_alert") as mock_log:
            await manager.send_alert(violation)
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_alert(self):
        """Test sending Slack alert"""
        manager = AlertManager()

        config = AlertConfig(channel=AlertChannel.SLACK, slack_webhook_url="https://hooks.slack.com/test")

        message = Mock(to_slack_blocks=Mock(return_value=[{"test": "blocks"}]))

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await manager._send_slack_alert(config, message)

            mock_client.post.assert_called_once_with(
                "https://hooks.slack.com/test", json={"test": "blocks"}, timeout=10.0
            )

    @pytest.mark.asyncio
    async def test_send_webhook_alert(self):
        """Test sending webhook alert"""
        manager = AlertManager()

        config = AlertConfig(
            channel=AlertChannel.WEBHOOK,
            webhook_url="https://api.example.com/alerts",
            webhook_headers={"X-API-Key": "secret"},
        )

        violation = GuardrailViolation(
            limit_name="test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("50.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.5,
            provider="openai",
            action_taken=[],
        )

        message = AlertMessage(
            title="Test Alert", message="Test message", severity=AlertSeverity.WARNING, violation=violation
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await manager._send_webhook_alert(config, message)

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.example.com/alerts"
            assert call_args[1]["headers"]["X-API-Key"] == "secret"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"

            payload = call_args[1]["json"]
            assert payload["title"] == "Test Alert"
            assert payload["severity"] == "warning"
            assert payload["violation"]["current_spend"] == 50.0


class TestConvenienceFunctions:
    """Test convenience functions"""

    @pytest.mark.asyncio
    async def test_send_cost_alert(self):
        """Test send_cost_alert convenience function"""
        violation = Mock()

        with patch("d0_gateway.guardrail_alerts.alert_manager") as mock_manager:
            mock_manager.send_alert = AsyncMock()

            await send_cost_alert(violation)

            mock_manager.send_alert.assert_called_once_with(violation)

    def test_configure_alerts(self):
        """Test configure_alerts convenience function"""
        with patch("d0_gateway.guardrail_alerts.alert_manager") as mock_manager:
            config = configure_alerts(
                channel=AlertChannel.EMAIL, email_addresses=["test@example.com"], min_severity=AlertSeverity.CRITICAL
            )

            assert config.channel == AlertChannel.EMAIL
            assert config.email_addresses == ["test@example.com"]
            assert config.min_severity == AlertSeverity.CRITICAL

            mock_manager.add_config.assert_called_once_with(config)
