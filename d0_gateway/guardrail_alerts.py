"""
Alert system for cost guardrail violations in P1-060
Handles notifications via multiple channels (email, Slack, webhooks)
"""
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, HttpUrl

from core.config import get_settings
from core.logging import get_logger
from d0_gateway.guardrails import AlertSeverity, GuardrailViolation

logger = get_logger("gateway.guardrail_alerts", domain="d0")


class AlertChannel(str, Enum):
    """Available alert channels"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG = "log"  # Default, always enabled


class AlertConfig(BaseModel):
    """Configuration for an alert channel"""

    channel: AlertChannel
    enabled: bool = True

    # Channel-specific settings
    email_addresses: Optional[List[str]] = None
    slack_webhook_url: Optional[HttpUrl] = None
    webhook_url: Optional[HttpUrl] = None
    webhook_headers: Optional[Dict[str, str]] = None

    # Filtering
    min_severity: AlertSeverity = AlertSeverity.WARNING
    providers: Optional[List[str]] = None  # None means all providers

    # Rate limiting
    max_alerts_per_hour: int = 10
    cooldown_minutes: int = 5  # Min time between similar alerts


class AlertMessage(BaseModel):
    """Formatted alert message"""

    title: str
    message: str
    severity: AlertSeverity
    violation: GuardrailViolation
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_slack_blocks(self) -> List[Dict]:
        """Format as Slack blocks"""
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#990000",
        }

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"🚨 {self.title}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": self.message}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:* {self.severity.value.upper()}"},
                    {"type": "mrkdwn", "text": f"*Limit:* {self.violation.limit_name}"},
                    {"type": "mrkdwn", "text": f"*Current Spend:* ${self.violation.current_spend:.2f}"},
                    {"type": "mrkdwn", "text": f"*Limit Amount:* ${self.violation.limit_amount:.2f}"},
                    {"type": "mrkdwn", "text": f"*Usage:* {self.violation.percentage_used:.1%}"},
                    {"type": "mrkdwn", "text": f"*Provider:* {self.violation.provider or 'All'}"},
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Occurred at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"}
                ],
            },
        ]

        return [{"attachments": [{"color": color_map.get(self.severity, "#808080"), "blocks": blocks}]}]

    def to_email_html(self) -> str:
        """Format as HTML email"""
        severity_colors = {
            AlertSeverity.INFO: "#28a745",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.CRITICAL: "#dc3545",
            AlertSeverity.EMERGENCY: "#721c24",
        }

        color = severity_colors.get(self.severity, "#6c757d")

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .alert-box {{ 
                    border: 2px solid {color}; 
                    border-radius: 5px; 
                    padding: 20px; 
                    margin: 20px 0;
                    background-color: #f8f9fa;
                }}
                .alert-title {{ 
                    color: {color}; 
                    margin-bottom: 10px;
                    font-size: 24px;
                    font-weight: bold;
                }}
                .metric {{ 
                    display: inline-block; 
                    margin: 10px 20px 10px 0; 
                }}
                .metric-label {{ 
                    font-weight: bold; 
                    color: #495057;
                }}
                .metric-value {{ 
                    color: #212529;
                    font-size: 18px;
                }}
                .footer {{ 
                    margin-top: 20px; 
                    font-size: 12px; 
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="alert-box">
                <div class="alert-title">🚨 {self.title}</div>
                <p>{self.message}</p>
                
                <div class="metrics">
                    <div class="metric">
                        <span class="metric-label">Severity:</span>
                        <span class="metric-value">{self.severity.value.upper()}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Limit:</span>
                        <span class="metric-value">{self.violation.limit_name}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Current Spend:</span>
                        <span class="metric-value">${self.violation.current_spend:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Limit Amount:</span>
                        <span class="metric-value">${self.violation.limit_amount:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Usage:</span>
                        <span class="metric-value">{self.violation.percentage_used:.1%}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Provider:</span>
                        <span class="metric-value">{self.violation.provider or 'All Providers'}</span>
                    </div>
                </div>
                
                <div class="footer">
                    Alert generated at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
                </div>
            </div>
        </body>
        </html>
        """


class AlertManager:
    """Manages alert delivery and rate limiting"""

    def __init__(self):
        self.logger = logger
        self._configs: List[AlertConfig] = []
        self._alert_history: Dict[str, List[datetime]] = {}
        self._load_default_configs()

    def _load_default_configs(self):
        """Load default alert configurations"""
        settings = get_settings()

        # Always log alerts
        self.add_config(AlertConfig(channel=AlertChannel.LOG, enabled=True, min_severity=AlertSeverity.INFO))

        # Add Slack if configured
        if hasattr(settings, "slack_webhook_url") and settings.slack_webhook_url:
            self.add_config(
                AlertConfig(
                    channel=AlertChannel.SLACK,
                    enabled=True,
                    slack_webhook_url=settings.slack_webhook_url,
                    min_severity=AlertSeverity.WARNING,
                )
            )

        # Add email if configured
        if hasattr(settings, "alert_email_addresses") and settings.alert_email_addresses:
            self.add_config(
                AlertConfig(
                    channel=AlertChannel.EMAIL,
                    enabled=True,
                    email_addresses=settings.alert_email_addresses.split(","),
                    min_severity=AlertSeverity.CRITICAL,
                )
            )

    def add_config(self, config: AlertConfig):
        """Add an alert configuration"""
        self._configs.append(config)
        self.logger.info(f"Added alert config: {config.channel.value} (min severity: {config.min_severity.value})")

    async def send_alert(self, violation: GuardrailViolation):
        """Send alert for a guardrail violation"""
        # Create alert message
        message = self._create_alert_message(violation)

        # Send to all configured channels
        tasks = []
        for config in self._configs:
            if self._should_send_alert(config, violation):
                tasks.append(self._send_to_channel(config, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _create_alert_message(self, violation: GuardrailViolation) -> AlertMessage:
        """Create formatted alert message from violation"""
        # Generate title based on severity
        title_map = {
            AlertSeverity.INFO: "Cost Tracking Update",
            AlertSeverity.WARNING: "Cost Warning - Approaching Limit",
            AlertSeverity.CRITICAL: "Cost Alert - Critical Threshold",
            AlertSeverity.EMERGENCY: "URGENT - Cost Limit Exceeded",
        }

        title = title_map.get(violation.severity, "Cost Guardrail Alert")

        # Generate message
        if violation.provider:
            provider_msg = f"Provider {violation.provider}"
            if violation.operation:
                provider_msg += f" ({violation.operation})"
        else:
            provider_msg = "All providers"

        message = (
            f"{provider_msg} has reached {violation.percentage_used:.1%} "
            f"of the {violation.limit_name} limit. "
            f"Current spend: ${violation.current_spend:.2f} / ${violation.limit_amount:.2f}. "
        )

        if violation.severity == AlertSeverity.EMERGENCY:
            message += "Further requests may be blocked!"
        elif violation.severity == AlertSeverity.CRITICAL:
            message += "Immediate attention required."

        return AlertMessage(
            title=title,
            message=message,
            severity=violation.severity,
            violation=violation,
            metadata={
                "actions_taken": [action.value for action in violation.action_taken],
                "campaign_id": violation.campaign_id,
            },
        )

    def _should_send_alert(self, config: AlertConfig, violation: GuardrailViolation) -> bool:
        """Check if alert should be sent based on config and rate limits"""
        if not config.enabled:
            return False

        # Check severity threshold
        severity_order = [AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
        if severity_order.index(violation.severity) < severity_order.index(config.min_severity):
            return False

        # Check provider filter
        if config.providers and violation.provider not in config.providers:
            return False

        # Check rate limits
        key = f"{config.channel.value}:{violation.limit_name}"
        now = datetime.utcnow()

        if key in self._alert_history:
            # Remove old entries
            self._alert_history[key] = [ts for ts in self._alert_history[key] if now - ts < timedelta(hours=1)]

            # Check rate limit
            if len(self._alert_history[key]) >= config.max_alerts_per_hour:
                return False

            # Check cooldown
            if self._alert_history[key]:
                last_alert = max(self._alert_history[key])
                if now - last_alert < timedelta(minutes=config.cooldown_minutes):
                    return False

        # Record this alert
        if key not in self._alert_history:
            self._alert_history[key] = []
        self._alert_history[key].append(now)

        return True

    async def _send_to_channel(self, config: AlertConfig, message: AlertMessage):
        """Send alert to specific channel"""
        try:
            if config.channel == AlertChannel.LOG:
                self._send_log_alert(message)
            elif config.channel == AlertChannel.SLACK:
                await self._send_slack_alert(config, message)
            elif config.channel == AlertChannel.EMAIL:
                await self._send_email_alert(config, message)
            elif config.channel == AlertChannel.WEBHOOK:
                await self._send_webhook_alert(config, message)
        except Exception as e:
            self.logger.error(f"Failed to send alert via {config.channel.value}: {e}")

    def _send_log_alert(self, message: AlertMessage):
        """Send alert to logs"""
        log_method = {
            AlertSeverity.INFO: self.logger.info,
            AlertSeverity.WARNING: self.logger.warning,
            AlertSeverity.CRITICAL: self.logger.error,
            AlertSeverity.EMERGENCY: self.logger.error,
        }.get(message.severity, self.logger.warning)

        log_method(
            f"GUARDRAIL ALERT: {message.title} - {message.message} "
            f"[{message.violation.limit_name}: ${message.violation.current_spend:.2f}/"
            f"${message.violation.limit_amount:.2f} ({message.violation.percentage_used:.1%})]"
        )

    async def _send_slack_alert(self, config: AlertConfig, message: AlertMessage):
        """Send alert to Slack"""
        if not config.slack_webhook_url:
            return

        async with httpx.AsyncClient() as client:
            blocks = message.to_slack_blocks()
            response = await client.post(str(config.slack_webhook_url), json=blocks[0], timeout=10.0)
            response.raise_for_status()

    async def _send_email_alert(self, config: AlertConfig, message: AlertMessage):
        """Send alert via email"""
        if not config.email_addresses:
            return

        # In a real implementation, this would use an email service
        # For now, just log that we would send an email
        self.logger.info(f"Would send email alert to {', '.join(config.email_addresses)}: " f"{message.title}")

        # TODO: Implement actual email sending via SendGrid or similar

    async def _send_webhook_alert(self, config: AlertConfig, message: AlertMessage):
        """Send alert to webhook"""
        if not config.webhook_url:
            return

        payload = {
            "title": message.title,
            "message": message.message,
            "severity": message.severity.value,
            "violation": {
                "limit_name": message.violation.limit_name,
                "scope": message.violation.scope.value,
                "current_spend": float(message.violation.current_spend),
                "limit_amount": float(message.violation.limit_amount),
                "percentage_used": message.violation.percentage_used,
                "provider": message.violation.provider,
                "operation": message.violation.operation,
                "campaign_id": message.violation.campaign_id,
            },
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata,
        }

        headers = config.webhook_headers or {}
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient() as client:
            response = await client.post(str(config.webhook_url), json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()


# Singleton instance
alert_manager = AlertManager()


# Convenience functions
async def send_cost_alert(violation: GuardrailViolation):
    """Send alert for a cost guardrail violation"""
    await alert_manager.send_alert(violation)


def configure_alerts(channel: AlertChannel, **kwargs) -> AlertConfig:
    """
    Configure a new alert channel

    Args:
        channel: Alert channel type
        **kwargs: Channel-specific configuration

    Returns:
        Created alert configuration
    """
    config = AlertConfig(channel=channel, **kwargs)
    alert_manager.add_config(config)
    return config
