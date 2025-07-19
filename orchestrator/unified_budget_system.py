"""
P2-040 Unified Budget Monitoring System
Integration bridge between PM-1's core monitoring and PM-2's alert enhancements

This module creates a seamless integration between:
- d11_orchestration.cost_guardrails (PM-1's comprehensive monitoring)
- orchestrator.real_time_budget_alerts (PM-2's alert enhancements)
"""
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from d0_gateway.guardrail_alerts import send_cost_alert
from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope
from d11_orchestration.cost_guardrails import (
    BudgetExceededException,
    budget_circuit_breaker,
    check_monthly_budget_limit,
    check_monthly_budget_threshold,
    get_budget_status_for_api,
    get_monthly_costs,
    monthly_budget_monitor_flow,
    real_time_cost_check,
)
from orchestrator.budget_monitor import BudgetMonitor, BudgetStatus
from orchestrator.real_time_budget_alerts import (
    RealTimeBudgetAlertManager,
    real_time_alert_manager,
    threshold_integrator,
)


class UnifiedBudgetSystem:
    """
    P2-040 Unified Budget Monitoring System

    Coordinates PM-1's comprehensive monitoring with PM-2's real-time enhancements
    to provide a single, coherent budget management solution.
    """

    def __init__(self):
        self.pm1_integration = PM1CoreIntegration()
        self.pm2_integration = PM2AlertIntegration()
        self.is_initialized = False

    async def initialize(self):
        """Initialize the unified budget system"""
        print("🚀 Initializing P2-040 Unified Budget Monitoring System...")

        # Initialize PM-2 alert enhancements
        await self.pm2_integration.initialize()

        # Setup PM-1 integration
        await self.pm1_integration.initialize()

        # Create unified monitoring bridge
        await self._create_unified_bridge()

        self.is_initialized = True
        print("✅ P2-040 Unified Budget System ready!")

    async def _create_unified_bridge(self):
        """Create bridge between PM-1 and PM-2 systems"""
        # Sync PM-1's budget settings with PM-2's monitors
        await self._sync_budget_configurations()

        # Setup unified alert coordination
        await self._setup_unified_alerting()

        print("🔗 Unified budget monitoring bridge established")

    async def _sync_budget_configurations(self):
        """Sync budget configurations between PM-1 and PM-2 systems"""
        # Get PM-1's budget settings
        pm1_config = await self.pm1_integration.get_budget_configuration()

        # Update PM-2 monitors to match PM-1 settings
        await self.pm2_integration.sync_with_pm1_config(pm1_config)

    async def _setup_unified_alerting(self):
        """Setup coordinated alerting between both systems"""
        # Register PM-1's flows with PM-2's alert manager
        self.pm2_integration.register_pm1_flows(self.pm1_integration)

        # Configure PM-1 to use PM-2's enhanced alerting
        self.pm1_integration.register_pm2_alerts(self.pm2_integration)

    async def check_unified_budget_status(self) -> Dict[str, any]:
        """Get comprehensive budget status from both systems"""
        # Get PM-1 status
        pm1_status = await self.pm1_integration.get_status()

        # Get PM-2 status
        pm2_status = await self.pm2_integration.get_status()

        # Merge statuses
        unified_status = {
            "system_status": "unified",
            "pm1_core_monitoring": pm1_status,
            "pm2_realtime_alerts": pm2_status,
            "global_budget": {
                "current_spend": pm1_status.get("current_spend", 0.0),
                "monthly_limit": pm1_status.get("monthly_limit", 0.0),
                "percentage_used": pm1_status.get("percentage_used", 0.0),
                "alert_level": pm1_status.get("alert_level", "ok"),
            },
            "alert_coordination": {
                "pm1_flows_active": pm1_status.get("flows_active", False),
                "pm2_monitors_active": len(pm2_status.get("monitors", [])),
                "unified_alerting": True,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return unified_status

    async def trigger_unified_budget_check(self) -> Dict[str, any]:
        """Trigger coordinated budget check across both systems"""
        results = {}

        # Trigger PM-1 monthly monitoring
        try:
            pm1_result = await self.pm1_integration.trigger_monthly_monitor()
            results["pm1_monitoring"] = pm1_result
        except Exception as e:
            results["pm1_monitoring"] = {"error": str(e)}

        # Trigger PM-2 real-time checks
        try:
            pm2_result = await self.pm2_integration.trigger_realtime_check()
            results["pm2_alerts"] = pm2_result
        except Exception as e:
            results["pm2_alerts"] = {"error": str(e)}

        # Coordinate results
        results["coordination"] = await self._coordinate_check_results(results)
        results["timestamp"] = datetime.utcnow().isoformat()

        return results

    async def _coordinate_check_results(self, results: Dict) -> Dict[str, any]:
        """Coordinate and analyze results from both systems"""
        coordination = {
            "overall_status": "ok",
            "alerts_sent": 0,
            "actions_taken": [],
            "recommendations": [],
        }

        # Analyze PM-1 results
        pm1_data = results.get("pm1_monitoring", {})
        if pm1_data.get("alert_sent"):
            coordination["alerts_sent"] += 1
            coordination["actions_taken"].append("pm1_threshold_alert")

        # Analyze PM-2 results
        pm2_data = results.get("pm2_alerts", {})
        alerts_count = pm2_data.get("alerts_sent", 0)
        if isinstance(alerts_count, str):
            alerts_count = int(alerts_count) if alerts_count.isdigit() else 0
        coordination["alerts_sent"] += alerts_count

        if alerts_count > 0:
            coordination["actions_taken"].append("pm2_realtime_alerts")

        # Determine overall status
        if any("error" in result for result in results.values() if isinstance(result, dict)):
            coordination["overall_status"] = "error"
        elif coordination["alerts_sent"] > 0:
            coordination["overall_status"] = "alerts_active"

        return coordination


class PM1CoreIntegration:
    """Integration adapter for PM-1's core budget monitoring system"""

    def __init__(self):
        self.flows_initialized = False

    async def initialize(self):
        """Initialize PM-1 integration"""
        self.flows_initialized = True
        print("✅ PM-1 core monitoring integration ready")

    async def get_budget_configuration(self) -> Dict[str, any]:
        """Get PM-1's budget configuration"""
        from core.config import get_settings

        settings = get_settings()
        monthly_limit = getattr(settings, "guardrail_global_monthly_limit", 3000.0)

        return {
            "monthly_limit": float(monthly_limit),
            "global_budget": True,
            "provider_budgets": {
                "openai": 500.0,
                "dataaxle": 800.0,
                "hunter": 200.0,
                "sendgrid": 100.0,
                "stripe": 50.0,
            },
            "warning_threshold": 0.8,
            "stop_threshold": 0.95,
        }

    async def get_status(self) -> Dict[str, any]:
        """Get PM-1 system status"""
        # Use PM-1's existing functions
        is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

        return {
            "system": "pm1_core",
            "current_spend": float(current_spend),
            "monthly_limit": float(monthly_limit),
            "percentage_used": percentage_used,
            "alert_level": alert_level,
            "is_over_threshold": is_over,
            "flows_active": self.flows_initialized,
            "circuit_breaker_active": percentage_used >= 1.0,
        }

    async def trigger_monthly_monitor(self) -> Dict[str, any]:
        """Trigger PM-1's monthly budget monitoring flow"""
        try:
            # Call PM-1's monthly monitoring flow
            result = monthly_budget_monitor_flow()
            return {
                "status": "success",
                "pm1_flow_result": result,
                "alert_sent": result.get("alert_sent", False),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "alert_sent": False,
            }

    def register_pm2_alerts(self, pm2_integration):
        """Register PM-2's enhanced alerting with PM-1 flows"""
        self.pm2_integration = pm2_integration
        print("🔗 PM-1 registered with PM-2 enhanced alerting")


class PM2AlertIntegration:
    """Integration adapter for PM-2's real-time alert enhancements"""

    def __init__(self):
        self.alert_manager = real_time_alert_manager
        self.threshold_integrator = threshold_integrator

    async def initialize(self):
        """Initialize PM-2 alert enhancements"""
        from orchestrator.real_time_budget_alerts import initialize_p2040_enhancements

        await initialize_p2040_enhancements()
        print("✅ PM-2 real-time alerts integration ready")

    async def sync_with_pm1_config(self, pm1_config: Dict[str, any]):
        """Sync PM-2 monitors with PM-1 configuration"""
        # Update global monitor
        if "global" in self.alert_manager.monitors:
            global_monitor = self.alert_manager.monitors["global"]
            global_monitor.monthly_budget_usd = Decimal(str(pm1_config["monthly_limit"]))
            global_monitor.warning_threshold = pm1_config["warning_threshold"]
            global_monitor.stop_threshold = pm1_config["stop_threshold"]

        # Update provider monitors
        for provider, budget in pm1_config.get("provider_budgets", {}).items():
            if provider in self.alert_manager.monitors:
                monitor = self.alert_manager.monitors[provider]
                monitor.monthly_budget_usd = Decimal(str(budget))

        print("🔄 PM-2 monitors synced with PM-1 configuration")

    async def get_status(self) -> Dict[str, any]:
        """Get PM-2 system status"""
        current_spending = await self.threshold_integrator.get_current_spending()
        monitors = []

        for monitor_id, monitor in self.alert_manager.monitors.items():
            spend = current_spending.get(monitor_id, 0.0)
            status = monitor.check_budget_status(spend)

            monitors.append(
                {
                    "monitor_id": monitor_id,
                    "status": status.value,
                    "current_spend": spend,
                    "monthly_budget": float(monitor.monthly_budget_usd),
                    "usage_percentage": spend / float(monitor.monthly_budget_usd),
                }
            )

        return {
            "system": "pm2_realtime",
            "monitors": monitors,
            "total_monitors": len(monitors),
            "alerts_active": len([m for m in monitors if m["status"] != "ok"]),
            "alert_cooldown_minutes": self.alert_manager.alert_cooldown_minutes,
        }

    async def trigger_realtime_check(self) -> Dict[str, any]:
        """Trigger PM-2's real-time budget checks"""
        try:
            current_spending = await self.threshold_integrator.get_current_spending()
            violations = await self.alert_manager.check_all_budgets(current_spending)

            return {
                "status": "success",
                "monitors_checked": str(len(current_spending)),
                "alerts_sent": str(len(violations)),
                "violations": [
                    {
                        "monitor_id": v.provider,
                        "severity": v.severity.value,
                        "percentage_used": v.percentage_used,
                    }
                    for v in violations
                ],
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "alerts_sent": "0",
            }

    def register_pm1_flows(self, pm1_integration):
        """Register PM-1 flows with PM-2 alert system"""
        self.pm1_integration = pm1_integration
        print("🔗 PM-2 registered with PM-1 core monitoring")


# Singleton instance for global use
unified_budget_system = UnifiedBudgetSystem()


async def initialize_unified_p2040_system():
    """Initialize the complete P2-040 unified budget monitoring system"""
    print("🏗️ Initializing P2-040 Unified Budget Monitoring System...")
    await unified_budget_system.initialize()
    return unified_budget_system


async def get_unified_budget_status() -> Dict[str, any]:
    """Get unified budget status from both PM-1 and PM-2 systems"""
    if not unified_budget_system.is_initialized:
        await unified_budget_system.initialize()

    return await unified_budget_system.check_unified_budget_status()


async def trigger_unified_budget_check() -> Dict[str, any]:
    """Trigger coordinated budget check across both systems"""
    if not unified_budget_system.is_initialized:
        await unified_budget_system.initialize()

    return await unified_budget_system.trigger_unified_budget_check()


# Enhanced integration functions
async def check_unified_operation_budget(provider: str, estimated_cost: float) -> Dict[str, any]:
    """
    Check operation budget using unified PM-1 and PM-2 systems

    Combines PM-1's real-time cost checking with PM-2's enhanced alerting
    """
    results = {}

    # Use PM-1's real-time cost check
    try:
        pm1_check = real_time_cost_check(estimated_cost, provider)
        results["pm1_analysis"] = pm1_check
    except Exception as e:
        results["pm1_analysis"] = {"error": str(e)}

    # Use PM-2's pre-operation check
    try:
        from orchestrator.real_time_budget_alerts import check_budget_before_operation

        pm2_can_proceed = await check_budget_before_operation(provider, estimated_cost)
        results["pm2_analysis"] = {"can_proceed": pm2_can_proceed}
    except Exception as e:
        results["pm2_analysis"] = {"error": str(e)}

    # Unified decision
    pm1_proceed = results.get("pm1_analysis", {}).get("should_proceed", True)
    pm2_proceed = results.get("pm2_analysis", {}).get("can_proceed", True)

    unified_decision = pm1_proceed and pm2_proceed

    return {
        "unified_decision": unified_decision,
        "pm1_analysis": results.get("pm1_analysis", {}),
        "pm2_analysis": results.get("pm2_analysis", {}),
        "provider": provider,
        "estimated_cost": estimated_cost,
        "checked_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    # Test unified system
    async def test_unified_system():
        print("Testing P2-040 Unified Budget System...")

        # Initialize
        system = await initialize_unified_p2040_system()

        # Get status
        status = await get_unified_budget_status()
        print(f"System Status: {status['global_budget']['alert_level']}")

        # Trigger check
        check_result = await trigger_unified_budget_check()
        print(f"Check Result: {check_result['coordination']['overall_status']}")

        # Test operation check
        op_check = await check_unified_operation_budget("openai", 50.0)
        print(f"Operation Check: {op_check['unified_decision']}")

    asyncio.run(test_unified_system())
