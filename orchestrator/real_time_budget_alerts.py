"""
Real-Time Budget Alert System Enhancement for P2-040
Integrates orchestrator.budget_monitor with d0_gateway.guardrail_alerts

This module provides real-time alerting when budget limits are exceeded,
enhancing the existing alert infrastructure with immediate threshold monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from d0_gateway.guardrail_alerts import send_cost_alert
from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope
from orchestrator.budget_monitor import BudgetMonitor, BudgetStatus


class RealTimeBudgetAlertManager:
    """
    Real-time budget alert manager that integrates with existing alert infrastructure

    Features:
    - Immediate threshold breach detection
    - Progressive alert escalation
    - Integration with existing multi-channel alerts
    - Rate limiting and cooldown periods
    """

    def __init__(self):
        self.monitors: dict[str, BudgetMonitor] = {}
        self.last_alerts: dict[str, datetime] = {}
        self.alert_cooldown_minutes = 5  # Prevent spam

    def register_budget_monitor(self, monitor_id: str, monitor: BudgetMonitor):
        """Register a budget monitor for real-time alerting"""
        self.monitors[monitor_id] = monitor

    async def check_all_budgets(self, current_spending: dict[str, float]) -> list[GuardrailViolation]:
        """
        Check all registered budget monitors and trigger alerts

        Args:
            current_spending: Dict of monitor_id -> current spending amount

        Returns:
            List of violations that triggered alerts
        """
        violations = []

        for monitor_id, spending_amount in current_spending.items():
            if monitor_id in self.monitors:
                violation = await self.check_budget_and_alert(monitor_id, spending_amount)
                if violation:
                    violations.append(violation)

        return violations

    async def check_budget_and_alert(self, monitor_id: str, current_spend: float) -> GuardrailViolation | None:
        """
        Check specific budget monitor and send alert if threshold exceeded

        Args:
            monitor_id: Unique identifier for the budget monitor
            current_spend: Current spending amount

        Returns:
            GuardrailViolation if alert was sent, None otherwise
        """
        if monitor_id not in self.monitors:
            return None

        monitor = self.monitors[monitor_id]
        status = monitor.check_budget_status(current_spend)

        # Check if alert cooldown period has passed
        alert_key = f"{monitor_id}:{status.value}"
        now = datetime.utcnow()

        if alert_key in self.last_alerts:
            time_since_last = now - self.last_alerts[alert_key]
            if time_since_last < timedelta(minutes=self.alert_cooldown_minutes):
                return None  # Still in cooldown period

        # Determine if alert should be sent based on status
        if status == BudgetStatus.OK:
            return None  # No alert needed

        # Create violation based on status
        violation = self._create_violation(monitor_id, monitor, current_spend, status)

        # Send alert through existing infrastructure
        await send_cost_alert(violation)

        # Record alert timestamp
        self.last_alerts[alert_key] = now

        return violation

    def _create_violation(
        self, monitor_id: str, monitor: BudgetMonitor, current_spend: float, status: BudgetStatus
    ) -> GuardrailViolation:
        """Create GuardrailViolation from budget monitor status"""

        # Map BudgetStatus to AlertSeverity
        severity_map = {
            BudgetStatus.WARNING: AlertSeverity.WARNING,
            BudgetStatus.STOP: AlertSeverity.CRITICAL,
        }

        # Determine actions taken
        actions = []
        if status == BudgetStatus.WARNING:
            actions = [GuardrailAction.ALERT]
        elif status == BudgetStatus.STOP:
            actions = [GuardrailAction.BLOCK, GuardrailAction.ALERT]

        # Calculate usage percentage
        usage_percentage = current_spend / float(monitor.monthly_budget_usd)

        return GuardrailViolation(
            limit_name=f"monthly_budget_{monitor_id}",
            scope=LimitScope.GLOBAL,
            severity=severity_map.get(status, AlertSeverity.WARNING),
            current_spend=Decimal(str(current_spend)),
            limit_amount=monitor.monthly_budget_usd,
            percentage_used=usage_percentage,
            provider=monitor_id,
            operation="budget_monitoring",
            action_taken=actions,
            metadata={
                "monitor_id": monitor_id,
                "budget_status": status.value,
                "warning_threshold": monitor.warning_threshold,
                "stop_threshold": monitor.stop_threshold,
                "alert_timestamp": datetime.utcnow().isoformat(),
                "enhancement": "P2-040_real_time_alerts",
            },
        )

    async def monitor_continuous(self, spending_callback, check_interval_seconds: int = 60):
        """
        Continuously monitor budgets at specified intervals

        Args:
            spending_callback: Async function that returns current spending dict
            check_interval_seconds: How often to check budgets
        """
        while True:
            try:
                current_spending = await spending_callback()
                if current_spending:
                    violations = await self.check_all_budgets(current_spending)
                    if violations:
                        print(f"Budget alerts sent: {len(violations)} violations detected")

            except Exception as e:
                print(f"Error in continuous budget monitoring: {e}")

            await asyncio.sleep(check_interval_seconds)


class BudgetThresholdIntegrator:
    """
    Integrates budget thresholds with existing cost tracking systems
    """

    def __init__(self, alert_manager: RealTimeBudgetAlertManager):
        self.alert_manager = alert_manager

    def setup_default_monitors(self):
        """Setup default budget monitors with common thresholds"""

        # Global monthly budget monitor
        global_monitor = BudgetMonitor(
            monthly_budget_usd=3000.0,  # Default from settings
            warning_threshold=0.8,  # 80% warning
            stop_threshold=0.95,  # 95% stop
        )
        self.alert_manager.register_budget_monitor("global", global_monitor)

        # Provider-specific monitors
        providers = {"openai": 500.0, "dataaxle": 800.0, "hunter": 200.0, "sendgrid": 100.0, "stripe": 50.0}

        for provider, budget in providers.items():
            monitor = BudgetMonitor(
                monthly_budget_usd=budget,
                warning_threshold=0.75,  # Earlier warning for providers
                stop_threshold=0.90,  # Earlier stop for providers
            )
            self.alert_manager.register_budget_monitor(provider, monitor)

    async def get_current_spending(self) -> dict[str, float]:
        """
        Get current spending amounts for all monitored budgets

        This integrates with existing cost tracking systems
        """
        from sqlalchemy import text

        from d11_orchestration.cost_guardrails import get_monthly_costs
        from database.session import SessionLocal

        spending = {}

        try:
            # Get global spending
            global_spend = get_monthly_costs()
            spending["global"] = float(global_spend)

            # Get provider-specific spending
            with SessionLocal() as db:
                # Get current month provider costs
                now = datetime.utcnow()
                first_day = now.replace(day=1).date()

                query = text(
                    """
                    SELECT 
                        provider,
                        COALESCE(SUM(total_cost_usd), 0) as provider_cost
                    FROM agg_daily_cost
                    WHERE date >= :first_day AND date <= :today
                    GROUP BY provider
                """
                )

                results = db.execute(query, {"first_day": first_day, "today": now.date()}).fetchall()

                for row in results:
                    if row.provider:
                        spending[row.provider] = float(row.provider_cost)

        except Exception as e:
            print(f"Error getting current spending: {e}")

        return spending


# Singleton instances for global use
real_time_alert_manager = RealTimeBudgetAlertManager()
threshold_integrator = BudgetThresholdIntegrator(real_time_alert_manager)


async def initialize_p2040_enhancements():
    """Initialize P2-040 budget alert enhancements"""
    print("🚀 Initializing P2-040 Real-Time Budget Alert Enhancements...")

    # Setup default monitors
    threshold_integrator.setup_default_monitors()

    print(f"✅ Registered {len(real_time_alert_manager.monitors)} budget monitors")
    print("📡 Real-time alerting system ready!")

    return real_time_alert_manager


async def start_continuous_monitoring(check_interval: int = 300):
    """
    Start continuous budget monitoring

    Args:
        check_interval: Check interval in seconds (default: 5 minutes)
    """
    print(f"🔄 Starting continuous budget monitoring (every {check_interval}s)...")

    await real_time_alert_manager.monitor_continuous(
        spending_callback=threshold_integrator.get_current_spending, check_interval_seconds=check_interval
    )


# Integration functions for existing systems
async def check_budget_before_operation(provider: str, estimated_cost: float) -> bool:
    """
    Check if operation should proceed based on budget status

    Args:
        provider: Provider name
        estimated_cost: Estimated cost of operation

    Returns:
        True if operation should proceed, False if budget exceeded
    """
    if provider not in real_time_alert_manager.monitors:
        return True  # No budget monitor configured

    current_spending = await threshold_integrator.get_current_spending()
    provider_spend = current_spending.get(provider, 0.0)
    projected_spend = provider_spend + estimated_cost

    monitor = real_time_alert_manager.monitors[provider]
    status = monitor.check_budget_status(projected_spend)

    if status == BudgetStatus.STOP:
        # Trigger immediate alert for projected overage
        await real_time_alert_manager.check_budget_and_alert(provider, projected_spend)
        return False

    return True


if __name__ == "__main__":
    # Test the alert system
    async def test_alerts():
        await initialize_p2040_enhancements()

        # Simulate budget check
        test_spending = {
            "global": 2500.0,  # 83% of 3000 budget
            "openai": 450.0,  # 90% of 500 budget
            "dataaxle": 600.0,  # 75% of 800 budget
        }

        violations = await real_time_alert_manager.check_all_budgets(test_spending)
        print(f"Test generated {len(violations)} alerts")

    asyncio.run(test_alerts())
