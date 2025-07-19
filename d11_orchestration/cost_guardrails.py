"""
Cost guardrail flows for Phase 0.5
Task OR-09: Prefect cost_guardrail & profit_snapshot flows
P2-040: Orchestration Budget Stop - Monthly circuit breaker

Monitors spending limits and profitability metrics to ensure
the system stays within budget and maintains positive unit economics.
Includes monthly budget circuit breaker to prevent exceeding planned spend.
"""

import asyncio
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Dict, List, Optional, Tuple

try:
    from prefect import flow, task
    from prefect.artifacts import create_markdown_artifact
    from prefect.deployments import Deployment
    from prefect.logging import get_run_logger
    from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule

    PREFECT_AVAILABLE = True
except ImportError:
    # Mock imports for testing
    PREFECT_AVAILABLE = False

    def flow(*args, **kwargs):
        def decorator(func):
            func.retries = kwargs.get("retries", 0)
            func.retry_delay_seconds = kwargs.get("retry_delay_seconds", 0)
            return func

        return decorator

    def task(*args, **kwargs):
        def decorator(func):
            func.retries = kwargs.get("retries", 0)
            func.retry_delay_seconds = kwargs.get("retry_delay_seconds", 0)
            return func

        return decorator

    def get_run_logger():
        import logging

        return logging.getLogger(__name__)

    class Deployment:
        @classmethod
        def build_from_flow(cls, **kwargs):
            return cls()

    class CronSchedule:
        def __init__(self, cron):
            self.cron = cron

    class IntervalSchedule:
        def __init__(self, interval):
            self.interval = interval

    def create_markdown_artifact(markdown, key):
        print(f"Artifact {key}: {markdown}")


from sqlalchemy import text

from core.config import get_settings
from d0_gateway.guardrail_alerts import send_cost_alert
from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope, guardrail_manager
from database.session import SessionLocal


# P2-040: Budget Circuit Breaker Implementation
class BudgetExceededException(Exception):
    """Raised when monthly budget is exceeded"""

    def __init__(self, current_spend: Decimal, monthly_limit: Decimal, message: str = None):
        self.current_spend = current_spend
        self.monthly_limit = monthly_limit
        self.message = message or f"Monthly budget exceeded: ${current_spend} / ${monthly_limit}"
        super().__init__(self.message)


def get_monthly_costs() -> Decimal:
    """Get current month's total costs"""
    with SessionLocal() as db:
        # Get first and last day of current month
        now = datetime.utcnow()
        first_day = now.replace(day=1).date()

        # Query monthly costs from both daily aggregates and individual costs
        query = text(
            """
            SELECT 
                COALESCE(SUM(total_cost_usd), 0) as monthly_cost
            FROM agg_daily_cost
            WHERE date >= :first_day AND date <= :today
            
            UNION ALL
            
            SELECT 
                COALESCE(SUM(cost_usd), 0) as monthly_cost
            FROM fct_api_cost
            WHERE DATE(timestamp) >= :first_day 
            AND DATE(timestamp) <= :today
            AND timestamp > (
                SELECT COALESCE(MAX(date), '1900-01-01') 
                FROM agg_daily_cost 
                WHERE date >= :first_day
            )
        """
        )

        result = db.execute(query, {"first_day": first_day, "today": now.date()}).fetchall()

        # Sum both aggregated and non-aggregated costs
        total_cost = sum(Decimal(str(row.monthly_cost)) for row in result)
        return total_cost


def check_monthly_budget_limit() -> tuple[bool, Decimal, Decimal]:
    """
    Check if monthly budget limit is exceeded

    Returns:
        (is_exceeded, current_spend, monthly_limit)
    """
    settings = get_settings()
    monthly_limit = Decimal(str(getattr(settings, "guardrail_global_monthly_limit", 3000.0)))
    current_spend = get_monthly_costs()

    is_exceeded = current_spend >= monthly_limit
    return is_exceeded, current_spend, monthly_limit


def budget_circuit_breaker(flow_func):
    """
    P2-040: Decorator to check monthly budget before flow execution

    When ledger total > monthly cap, flows transition to Failed with custom message.
    Preserves state for auto-resume next month.
    """

    @wraps(flow_func)
    def wrapper(*args, **kwargs):
        # Check monthly budget
        is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

        if is_exceeded:
            # Send alert notification
            try:
                violation = GuardrailViolation(
                    limit_name="monthly_budget_circuit_breaker",
                    scope=LimitScope.GLOBAL,
                    severity=AlertSeverity.CRITICAL,
                    current_spend=current_spend,
                    limit_amount=monthly_limit,
                    percentage_used=float(current_spend / monthly_limit),
                    provider="global",
                    operation="flow_execution",
                    action_taken=[GuardrailAction.BLOCK],
                    metadata={
                        "flow_name": flow_func.__name__,
                        "current_spend": float(current_spend),
                        "monthly_limit": float(monthly_limit),
                        "exceeded_by": float(current_spend - monthly_limit),
                        "action": "flow_blocked",
                        "auto_resume": "next_month",
                    },
                )

                # Use asyncio to call the async function
                try:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(send_cost_alert(violation))
                except RuntimeError:
                    # No event loop running, create a new one
                    asyncio.run(send_cost_alert(violation))
            except Exception as e:
                logger = get_run_logger() if PREFECT_AVAILABLE else None
                if logger:
                    logger.error(f"Failed to send budget alert: {e}")

            # Raise exception to fail the flow with preserved state
            raise BudgetExceededException(current_spend, monthly_limit)

        # Budget OK - proceed with flow execution
        return flow_func(*args, **kwargs)

    return wrapper


@task(
    name="get-daily-costs",
    description="Get current day's costs by provider",
    retries=2,
    retry_delay_seconds=60,
)
def get_daily_costs() -> Dict[str, float]:
    """Get today's costs aggregated by provider"""
    logger = get_run_logger()

    with SessionLocal() as db:
        # Query aggregated daily costs
        today = datetime.utcnow().date()

        query = text(
            """
            SELECT 
                provider,
                SUM(total_cost_usd) as total_cost
            FROM agg_daily_cost
            WHERE date = :date
            GROUP BY provider
        """
        )

        results = db.execute(query, {"date": today}).fetchall()

        costs = {row.provider: float(row.total_cost) for row in results}

        # Also get total
        total_query = text(
            """
            SELECT COALESCE(SUM(total_cost_usd), 0) as total
            FROM agg_daily_cost
            WHERE date = :date
        """
        )

        total_result = db.execute(total_query, {"date": today}).fetchone()
        costs["total"] = float(total_result.total) if total_result else 0.0

    logger.info(f"Daily costs: ${costs.get('total', 0):.2f}")
    return costs


@task(
    name="check-budget-threshold",
    description="Check if spending is approaching budget limit",
    retries=1,
    retry_delay_seconds=30,
)
def check_budget_threshold(
    daily_costs: Dict[str, float], daily_budget: float, warning_threshold: float = 0.8
) -> Tuple[bool, float, str]:
    """
    Check if spending is approaching budget limit

    Returns:
        Tuple of (is_over_threshold, percentage_used, alert_level)
    """
    logger = get_run_logger()

    total_cost = daily_costs.get("total", 0.0)
    percentage_used = (total_cost / daily_budget) if daily_budget > 0 else 0.0

    if percentage_used >= 1.0:
        alert_level = "critical"
        is_over = True
        logger.error(f"CRITICAL: Daily budget exceeded! ${total_cost:.2f} / ${daily_budget:.2f}")
    elif percentage_used >= warning_threshold:
        alert_level = "warning"
        is_over = True
        logger.warning(f"WARNING: Approaching daily budget limit! ${total_cost:.2f} / ${daily_budget:.2f}")
    else:
        alert_level = "ok"
        is_over = False
        logger.info(f"Budget OK: ${total_cost:.2f} / ${daily_budget:.2f} ({percentage_used:.1%})")

    return is_over, percentage_used, alert_level


@task(
    name="pause-expensive-operations",
    description="Pause high-cost operations when over budget",
    retries=1,
    retry_delay_seconds=30,
)
def pause_expensive_operations(providers_to_pause: List[str]) -> Dict[str, bool]:
    """
    Pause operations for expensive providers

    In production, this would:
    1. Update feature flags to disable providers
    2. Notify the pipeline to skip expensive operations
    3. Send alerts to the team
    """
    logger = get_run_logger()

    paused = {}

    for provider in providers_to_pause:
        # In production, update feature flags or config
        logger.warning(f"Pausing operations for provider: {provider}")
        paused[provider] = True

    return paused


@task(
    name="get-profit-metrics",
    description="Calculate current profitability metrics",
    retries=2,
    retry_delay_seconds=60,
)
def get_profit_metrics(lookback_days: int = 7) -> Dict[str, float]:
    """Get profit metrics for the specified period"""
    logger = get_run_logger()

    with SessionLocal() as db:
        # Query unit economics view
        start_date = datetime.utcnow().date() - timedelta(days=lookback_days)

        query = text(
            """
            SELECT 
                SUM(revenue_usd) as total_revenue,
                SUM(total_cost_usd) as total_cost,
                SUM(profit_usd) as total_profit,
                AVG(roi) as avg_roi,
                AVG(cost_per_acquisition) as avg_cpa,
                SUM(purchases) as total_purchases
            FROM unit_economics_day
            WHERE date >= :start_date
        """
        )

        result = db.execute(query, {"start_date": start_date}).fetchone()

        if result:
            metrics = {
                "total_revenue": float(result.total_revenue or 0),
                "total_cost": float(result.total_cost or 0),
                "total_profit": float(result.total_profit or 0),
                "avg_roi": float(result.avg_roi or 0),
                "avg_cpa": float(result.avg_cpa or 0),
                "total_purchases": int(result.total_purchases or 0),
            }
        else:
            metrics = {
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "total_profit": 0.0,
                "avg_roi": 0.0,
                "avg_cpa": 0.0,
                "total_purchases": 0,
            }

    logger.info(
        f"Profit metrics ({lookback_days}d): Revenue=${metrics['total_revenue']:.2f}, Profit=${metrics['total_profit']:.2f}"
    )
    return metrics


@task(
    name="create-profit-report",
    description="Create markdown report of profitability",
    retries=1,
)
def create_profit_report(metrics: Dict[str, float], bucket_performance: List[Dict], period_days: int) -> str:
    """Create a markdown report of profitability metrics"""
    get_run_logger()

    report = f"""# Profit Snapshot Report

**Period**: Last {period_days} days  
**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Summary Metrics

| Metric | Value |
|--------|-------|
| Total Revenue | ${metrics['total_revenue']:,.2f} |
| Total Cost | ${metrics['total_cost']:,.2f} |
| Total Profit | ${metrics['total_profit']:,.2f} |
| Average ROI | {metrics['avg_roi']:.1%} |
| Avg Cost per Acquisition | ${metrics['avg_cpa']:.2f} |
| Total Purchases | {metrics['total_purchases']:,} |

## Top Performing Buckets

| Geo Bucket | Vertical Bucket | Businesses | Revenue | Profit | ROI |
|------------|-----------------|------------|---------|--------|-----|
"""

    # Add top 5 performing buckets
    for bucket in bucket_performance[:5]:
        report += f"| {bucket.get('geo_bucket', 'unknown')} | {bucket.get('vert_bucket', 'unknown')} | "
        report += f"{bucket.get('total_businesses', 0):,} | ${bucket.get('total_revenue_usd', 0):,.2f} | "
        report += f"${bucket.get('profit_usd', 0):,.2f} | {bucket.get('roi', 0):.1%} |\n"

    report += "\n_Report generated by cost_guardrails flow_"

    return report


@flow(
    name="cost-guardrail-flow",
    description="Monitor costs and pause operations if over budget",
    retries=2,
    retry_delay_seconds=300,
)
def cost_guardrail_flow(
    daily_budget_override: Optional[float] = None,
    warning_threshold: float = 0.8,
    expensive_providers: List[str] = ["openai", "dataaxle", "hunter"],
) -> Dict[str, any]:
    """
    Cost guardrail flow to monitor and control spending

    Args:
        daily_budget_override: Override config daily budget
        warning_threshold: Threshold to trigger warnings (0.8 = 80%)
        expensive_providers: Providers to pause when over budget
    """
    logger = get_run_logger()
    logger.info("Starting cost guardrail check")

    # Get configuration
    settings = get_settings()
    daily_budget = daily_budget_override or settings.cost_budget_usd

    # Get current costs
    daily_costs = get_daily_costs()

    # Check budget threshold
    is_over, percentage_used, alert_level = check_budget_threshold(daily_costs, daily_budget, warning_threshold)

    # Take action if needed
    paused_providers = {}
    if alert_level == "critical":
        paused_providers = pause_expensive_operations(expensive_providers)

    # Create result summary
    result = {
        "daily_costs": daily_costs,
        "budget_used_percentage": percentage_used,
        "alert_level": alert_level,
        "paused_providers": paused_providers,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Create artifact for UI
    if PREFECT_AVAILABLE:
        artifact_markdown = f"""# Cost Guardrail Alert

**Status**: {alert_level.upper()}  
**Budget Used**: {percentage_used:.1%} (${daily_costs.get('total', 0):.2f} / ${daily_budget:.2f})  
**Time**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Provider Breakdown
"""
        for provider, cost in daily_costs.items():
            if provider != "total":
                artifact_markdown += f"- **{provider}**: ${cost:.2f}\n"

        if paused_providers:
            artifact_markdown += "\n## Paused Providers\n"
            for provider in paused_providers:
                artifact_markdown += f"- {provider}\n"

        create_markdown_artifact(markdown=artifact_markdown, key="cost-guardrail-alert")

    logger.info(f"Cost guardrail check complete: {alert_level}")
    return result


@flow(
    name="profit-snapshot-flow",
    description="Generate profitability report",
    retries=2,
    retry_delay_seconds=300,
)
def profit_snapshot_flow(lookback_days: int = 7, top_buckets_count: int = 5) -> Dict[str, any]:
    """
    Generate profit snapshot report

    Args:
        lookback_days: Days to look back for metrics
        top_buckets_count: Number of top buckets to show
    """
    logger = get_run_logger()
    logger.info(f"Generating profit snapshot for last {lookback_days} days")

    # Get profit metrics
    metrics = get_profit_metrics(lookback_days)

    # Get bucket performance
    with SessionLocal() as db:
        query = text(
            """
            SELECT 
                geo_bucket,
                vert_bucket,
                total_businesses,
                total_revenue_usd,
                profit_usd,
                roi
            FROM bucket_performance
            WHERE total_revenue_usd > 0
            ORDER BY profit_usd DESC
            LIMIT :limit
        """
        )

        results = db.execute(query, {"limit": top_buckets_count}).fetchall()

        bucket_performance = [
            {
                "geo_bucket": row.geo_bucket,
                "vert_bucket": row.vert_bucket,
                "total_businesses": row.total_businesses,
                "total_revenue_usd": float(row.total_revenue_usd),
                "profit_usd": float(row.profit_usd),
                "roi": float(row.roi) if row.roi else 0,
            }
            for row in results
        ]

    # Create report
    report = create_profit_report(metrics, bucket_performance, lookback_days)

    # Create artifact
    if PREFECT_AVAILABLE:
        create_markdown_artifact(markdown=report, key="profit-snapshot")

    result = {
        "metrics": metrics,
        "top_buckets": bucket_performance,
        "report": report,
        "period_days": lookback_days,
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(f"Profit snapshot complete: ROI={metrics['avg_roi']:.1%}")
    return result


def create_guardrail_deployment() -> Deployment:
    """Create deployment for cost guardrail monitoring"""

    deployment = Deployment.build_from_flow(
        flow=cost_guardrail_flow,
        name="cost-guardrail-monitor",
        schedule=IntervalSchedule(interval=timedelta(hours=1)),  # Check every hour
        work_queue_name="monitoring",
        parameters={
            "warning_threshold": 0.8,
            "expensive_providers": ["openai", "dataaxle", "hunter"],
        },
        description="Hourly cost monitoring with automatic guardrails",
        tags=["cost-control", "monitoring", "phase-0.5"],
    )

    return deployment


def create_profit_snapshot_deployment() -> Deployment:
    """Create deployment for daily profit snapshot"""

    deployment = Deployment.build_from_flow(
        flow=profit_snapshot_flow,
        name="daily-profit-snapshot",
        schedule=CronSchedule(cron="0 6 * * *"),  # 6 AM UTC daily
        work_queue_name="reporting",
        parameters={"lookback_days": 7, "top_buckets_count": 10},
        description="Daily profitability report generation",
        tags=["reporting", "profit", "phase-0.5"],
    )

    return deployment


# Manual triggers for testing
async def check_costs_now() -> Dict[str, any]:
    """Manually trigger cost guardrail check"""
    result = cost_guardrail_flow()
    return result


async def generate_profit_report_now(days: int = 7) -> Dict[str, any]:
    """Manually generate profit report"""
    result = profit_snapshot_flow(lookback_days=days)
    return result


if __name__ == "__main__":
    # Test flows
    import asyncio

    async def test():
        # Test cost guardrail
        print("Testing cost guardrail...")
        guardrail_result = await check_costs_now()
        print(f"Alert level: {guardrail_result['alert_level']}")
        print(f"Budget used: {guardrail_result['budget_used_percentage']:.1%}")

        # Test profit snapshot
        print("\nTesting profit snapshot...")
        profit_result = await generate_profit_report_now(days=7)
        print(f"Total profit: ${profit_result['metrics']['total_profit']:.2f}")
        print(f"ROI: {profit_result['metrics']['avg_roi']:.1%}")

    asyncio.run(test())
