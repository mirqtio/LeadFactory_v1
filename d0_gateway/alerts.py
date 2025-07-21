"""
Alert system and notifications for P1-060 Cost guardrails
Provides unified interface for multi-channel alerting with throttling
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

import httpx
from pydantic import BaseModel, Field

from core.config import get_settings
from core.logging import get_logger
from d0_gateway.guardrails import AlertSeverity, GuardrailViolation
from d0_gateway.providers.sendgrid import SendGridClient

logger = get_logger("gateway.alerts", domain="d0")


class AlertChannel(str, Enum):
    """Available alert channels"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG = "log"  # Default, always enabled


class AlertLevel(str, Enum):
    """Alert severity levels for better granularity"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    HALT = "halt"  # System should halt operations


class AlertTemplate(BaseModel):
    """Template for alert messages"""

    subject: str
    body: str
    html_body: str | None = None
    slack_blocks: list[dict] | None = None


class AlertContext(BaseModel):
    """Context data for alert templating"""

    violation: GuardrailViolation
    current_spend: Decimal
    limit: Decimal
    percentage: float
    provider: str | None = None
    operation: str | None = None
    campaign_id: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Additional context
    spend_rate_per_hour: float | None = None
    time_to_limit: str | None = None
    recommended_action: str | None = None


class AlertThrottle(BaseModel):
    """Throttling configuration for alerts"""

    max_alerts_per_hour: int = 10
    cooldown_minutes: int = 5
    aggregation_window_minutes: int = 15

    # Severity-based overrides
    critical_cooldown_minutes: int = 2
    halt_cooldown_minutes: int = 0  # Never throttle halt alerts


class AlertHistory(BaseModel):
    """Track alert history for throttling"""

    channel: str
    limit_name: str
    last_sent: datetime
    count_this_hour: int = 1
    aggregated_violations: list[GuardrailViolation] = []


class AlertManager:
    """
    Centralized alert management with multi-channel support,
    throttling, and template-based notifications
    """

    def __init__(self):
        self.logger = logger
        self.settings = get_settings()
        self._history: dict[str, AlertHistory] = {}
        self._templates = self._load_templates()
        self._sendgrid = None

    def _load_templates(self) -> dict[str, AlertTemplate]:
        """Load notification templates"""
        return {
            "warning": AlertTemplate(
                subject="Cost Warning: {provider} approaching {percentage:.0%} of limit",
                body=(
                    "WARNING: {provider} has reached {percentage:.0%} of the {limit_name} limit.\n\n"
                    "Current spend: ${current_spend:.2f}\n"
                    "Limit: ${limit:.2f}\n"
                    "Spend rate: ${spend_rate_per_hour:.2f}/hour\n"
                    "Time to limit: {time_to_limit}\n\n"
                    "Recommended action: {recommended_action}"
                ),
                html_body=self._get_email_html_template("warning"),
            ),
            "critical": AlertTemplate(
                subject="CRITICAL: {provider} at {percentage:.0%} of limit - Action Required",
                body=(
                    "CRITICAL ALERT: {provider} has reached {percentage:.0%} of the {limit_name} limit!\n\n"
                    "Current spend: ${current_spend:.2f}\n"
                    "Limit: ${limit:.2f}\n"
                    "Remaining budget: ${remaining:.2f}\n\n"
                    "IMMEDIATE ACTION REQUIRED: {recommended_action}\n\n"
                    "Operations may be throttled or blocked soon."
                ),
                html_body=self._get_email_html_template("critical"),
            ),
            "halt": AlertTemplate(
                subject="EMERGENCY: {provider} HALTED - Budget Exceeded",
                body=(
                    "EMERGENCY: {provider} operations have been HALTED due to budget exceeded!\n\n"
                    "Current spend: ${current_spend:.2f}\n"
                    "Limit: ${limit:.2f}\n"
                    "Overage: ${overage:.2f}\n\n"
                    "All {provider} operations are now BLOCKED.\n"
                    "Manual intervention required to resume operations.\n\n"
                    "Contact: {support_contact}"
                ),
                html_body=self._get_email_html_template("halt"),
            ),
        }

    def _get_email_html_template(self, severity: str) -> str:
        """Get HTML email template"""
        colors = {
            "warning": "#ff9900",
            "critical": "#ff0000",
            "halt": "#990000",
        }

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{{{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}}}
                .header {{{{
                    background-color: {colors.get(severity, "#000")};
                    color: white;
                    padding: 20px;
                    border-radius: 5px 5px 0 0;
                    text-align: center;
                }}}}
                .content {{{{
                    background-color: #f8f9fa;
                    padding: 30px;
                    border: 1px solid #dee2e6;
                    border-radius: 0 0 5px 5px;
                }}}}
                .metric {{{{
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}}}
                .metric:last-child {{{{
                    border-bottom: none;
                }}}}
                .metric-label {{{{
                    font-weight: bold;
                    color: #6c757d;
                }}}}
                .metric-value {{{{
                    font-weight: bold;
                    color: {colors.get(severity, "#000")};
                }}}}
                .action-box {{{{
                    background-color: #fff;
                    border: 2px solid {colors.get(severity, "#000")};
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}}}
                .footer {{{{
                    margin-top: 30px;
                    font-size: 12px;
                    color: #6c757d;
                    text-align: center;
                }}}}
                .button {{{{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: {colors.get(severity, "#000")};
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 15px;
                }}}}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{subject}}</h1>
            </div>
            <div class="content">
                <div class="metrics">
                    <div class="metric">
                        <span class="metric-label">Provider:</span>
                        <span class="metric-value">{{provider}}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Current Spend:</span>
                        <span class="metric-value">${{current_spend:.2f}}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Limit:</span>
                        <span class="metric-value">${{limit:.2f}}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Usage:</span>
                        <span class="metric-value">{{percentage:.1%}}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Spend Rate:</span>
                        <span class="metric-value">${{spend_rate_per_hour:.2f}}/hour</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Time to Limit:</span>
                        <span class="metric-value">{{time_to_limit}}</span>
                    </div>
                </div>
                
                <div class="action-box">
                    <h3>Recommended Action:</h3>
                    <p>{{recommended_action}}</p>
                    <a href="{{dashboard_url}}" class="button">View Dashboard</a>
                </div>
                
                <div class="footer">
                    <p>This alert was generated by LeadFactory Cost Guardrail System</p>
                    <p>{{timestamp}}</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def send_alert(
        self,
        violation: GuardrailViolation,
        channels: list[AlertChannel] | None = None,
    ) -> dict[str, bool]:
        """
        Send alert through specified channels

        Args:
            violation: The guardrail violation
            channels: List of channels to use (None = all configured)

        Returns:
            Dict mapping channel to success status
        """
        # Determine severity level
        level = self._get_alert_level(violation)

        # Build context
        context = self._build_context(violation)

        # Determine channels to use
        if channels is None:
            channels = self._get_configured_channels()

        # Check throttling
        results = {}
        for channel in channels:
            if self._should_send(channel, violation, level):
                try:
                    success = await self._send_to_channel(channel, context, level)
                    results[channel] = success

                    if success:
                        self._record_sent(channel, violation)
                except Exception as e:
                    self.logger.error(f"Failed to send alert via {channel}: {e}")
                    results[channel] = False
            else:
                self.logger.debug(f"Alert throttled for {channel}")
                results[channel] = False

        return results

    def _get_alert_level(self, violation: GuardrailViolation) -> AlertLevel:
        """Map violation severity to alert level"""
        if violation.percentage_used >= 1.0:
            return AlertLevel.HALT
        if violation.severity == AlertSeverity.EMERGENCY or violation.severity == AlertSeverity.CRITICAL:
            return AlertLevel.CRITICAL
        if violation.severity == AlertSeverity.WARNING:
            return AlertLevel.WARNING
        return AlertLevel.INFO

    def _build_context(self, violation: GuardrailViolation) -> AlertContext:
        """Build context for alert templating"""
        # Calculate spend rate (last hour)
        spend_rate = self._calculate_spend_rate(violation)

        # Calculate time to limit
        remaining = float(violation.limit_amount - violation.current_spend)
        if spend_rate > 0:
            hours_to_limit = remaining / spend_rate
            if hours_to_limit < 1:
                time_to_limit = f"{int(hours_to_limit * 60)} minutes"
            elif hours_to_limit < 24:
                time_to_limit = f"{hours_to_limit:.1f} hours"
            else:
                time_to_limit = f"{hours_to_limit / 24:.1f} days"
        else:
            time_to_limit = "N/A (no recent spending)"

        # Determine recommended action
        if violation.percentage_used >= 1.0:
            action = "Increase limit or stop all operations immediately"
        elif violation.percentage_used >= 0.95:
            action = "Review and reduce usage immediately, consider increasing limit"
        elif violation.percentage_used >= 0.8:
            action = "Monitor closely and plan to reduce usage"
        else:
            action = "Monitor spending patterns"

        return AlertContext(
            violation=violation,
            current_spend=violation.current_spend,
            limit=violation.limit_amount,
            percentage=violation.percentage_used,
            provider=violation.provider,
            operation=violation.operation,
            campaign_id=violation.campaign_id,
            spend_rate_per_hour=spend_rate,
            time_to_limit=time_to_limit,
            recommended_action=action,
        )

    def _calculate_spend_rate(self, violation: GuardrailViolation) -> float:
        """Calculate spending rate per hour"""
        # This is a simplified calculation
        # In production, would query actual spending history
        return float(violation.current_spend) * 0.1  # Placeholder

    def _get_configured_channels(self) -> list[AlertChannel]:
        """Get list of configured alert channels"""
        channels = [AlertChannel.LOG]  # Always log

        if self.settings.guardrail_alert_email:
            channels.append(AlertChannel.EMAIL)

        if self.settings.guardrail_alert_slack_webhook:
            channels.append(AlertChannel.SLACK)

        return channels

    def _should_send(
        self,
        channel: AlertChannel,
        violation: GuardrailViolation,
        level: AlertLevel,
    ) -> bool:
        """Check if alert should be sent based on throttling rules"""
        # Never throttle halt alerts
        if level == AlertLevel.HALT:
            return True

        # Check history
        key = f"{channel.value}:{violation.limit_name}"
        now = datetime.utcnow()

        if key in self._history:
            history = self._history[key]

            # Check cooldown
            if level == AlertLevel.CRITICAL:
                cooldown = timedelta(minutes=2)
            else:
                cooldown = timedelta(minutes=5)

            if now - history.last_sent < cooldown:
                return False

            # Check hourly limit
            if history.count_this_hour >= 10:
                return False

        return True

    def _record_sent(self, channel: AlertChannel, violation: GuardrailViolation):
        """Record that an alert was sent"""
        key = f"{channel.value}:{violation.limit_name}"
        now = datetime.utcnow()

        if key in self._history:
            history = self._history[key]
            # Reset hourly count if needed
            if now - history.last_sent > timedelta(hours=1):
                history.count_this_hour = 1
            else:
                history.count_this_hour += 1
            history.last_sent = now
        else:
            self._history[key] = AlertHistory(
                channel=channel.value,
                limit_name=violation.limit_name,
                last_sent=now,
            )

    async def _send_to_channel(
        self,
        channel: AlertChannel,
        context: AlertContext,
        level: AlertLevel,
    ) -> bool:
        """Send alert to specific channel"""
        if channel == AlertChannel.LOG:
            return self._send_log_alert(context, level)
        if channel == AlertChannel.EMAIL:
            return await self._send_email_alert(context, level)
        if channel == AlertChannel.SLACK:
            return await self._send_slack_alert(context, level)
        if channel == AlertChannel.WEBHOOK:
            return await self._send_webhook_alert(context, level)
        return False

    def _send_log_alert(self, context: AlertContext, level: AlertLevel) -> bool:
        """Send alert to logs"""
        log_method = {
            AlertLevel.INFO: self.logger.info,
            AlertLevel.WARNING: self.logger.warning,
            AlertLevel.CRITICAL: self.logger.error,
            AlertLevel.HALT: self.logger.error,
        }.get(level, self.logger.warning)

        log_method(
            f"COST ALERT [{level.value.upper()}]: "
            f"{context.provider or 'Global'} at {context.percentage:.1%} "
            f"(${context.current_spend:.2f}/${context.limit:.2f}) "
            f"- {context.recommended_action}"
        )
        return True

    async def _send_email_alert(self, context: AlertContext, level: AlertLevel) -> bool:
        """Send email alert"""
        if not self.settings.guardrail_alert_email:
            return False

        # Get template
        template_key = level.value if level.value != "info" else "warning"
        template = self._templates.get(template_key)
        if not template:
            return False

        # Format content
        template_data = {
            "subject": template.subject.format(**context.model_dump()),
            "provider": context.provider or "All Providers",
            "current_spend": context.current_spend,
            "limit": context.limit,
            "limit_name": context.violation.limit_name,
            "percentage": context.percentage,
            "spend_rate_per_hour": context.spend_rate_per_hour or 0,
            "time_to_limit": context.time_to_limit,
            "recommended_action": context.recommended_action,
            "remaining": float(context.limit - context.current_spend),
            "overage": float(max(0, context.current_spend - context.limit)),
            "support_contact": "support@leadfactory.com",
            "dashboard_url": f"{self.settings.base_url}/dashboard/costs",
            "timestamp": context.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        # Send via SendGrid
        if not self._sendgrid:
            self._sendgrid = SendGridClient()

        try:
            result = await self._sendgrid.send_email(
                to_email=self.settings.guardrail_alert_email,
                subject=template_data["subject"],
                html_content=template.html_body.format(**template_data),
                from_email=self.settings.from_email,
                from_name=self.settings.from_name,
                text_content=template.body.format(**template_data),
                custom_args={"category": "cost-alert", "alert_type": level.value},
            )
            return result.get("success", False)
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False

    async def _send_slack_alert(self, context: AlertContext, level: AlertLevel) -> bool:
        """Send Slack alert"""
        if not self.settings.guardrail_alert_slack_webhook:
            return False

        # Build Slack message
        color_map = {
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ff9900",
            AlertLevel.CRITICAL: "#ff0000",
            AlertLevel.HALT: "#990000",
        }

        message = {
            "attachments": [
                {
                    "color": color_map.get(level, "#808080"),
                    "title": f"Cost Alert: {context.provider or 'Global'} at {context.percentage:.0%}",
                    "fields": [
                        {"title": "Severity", "value": level.value.upper(), "short": True},
                        {"title": "Limit", "value": context.violation.limit_name, "short": True},
                        {"title": "Current Spend", "value": f"${context.current_spend:.2f}", "short": True},
                        {"title": "Limit Amount", "value": f"${context.limit:.2f}", "short": True},
                        {"title": "Usage", "value": f"{context.percentage:.1%}", "short": True},
                        {"title": "Time to Limit", "value": context.time_to_limit, "short": True},
                    ],
                    "text": context.recommended_action,
                    "footer": "LeadFactory Cost Guardrails",
                    "ts": int(context.timestamp.timestamp()),
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.settings.guardrail_alert_slack_webhook,
                    json=message,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
            return False

    async def _send_webhook_alert(self, context: AlertContext, level: AlertLevel) -> bool:
        """Send generic webhook alert"""
        # Not implemented in base configuration
        return False


# Singleton instance
alert_manager = AlertManager()


# Convenience functions
async def send_cost_alert(violation: GuardrailViolation, channels: list[str] | None = None):
    """Send cost alert through configured channels"""
    channel_enums = None
    if channels:
        channel_enums = [AlertChannel(ch) for ch in channels]
    return await alert_manager.send_alert(violation, channel_enums)


def get_alert_manager() -> AlertManager:
    """Get the alert manager instance"""
    return alert_manager
