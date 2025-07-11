"""
Heartbeat Health Check Tests
Runs every 2 hours to verify critical services

Checks:
- D0 Gateway API credentials
- Database connectivity
- Stripe authentication
- SendGrid authentication
- Redis cache
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List
import pytest

from prefect import flow, task
from sqlalchemy import text

from database.session import get_db
from d0_gateway.facade import GatewayFacade
from core.config import settings
from core.logging import get_logger
from core.metrics import metrics

logger = get_logger(__name__)

# Heartbeat timeout - must complete in 90 seconds
HEARTBEAT_TIMEOUT = 90
HEARTBEAT_INTERVAL = 7200  # 2 hours


class ServiceHealthCheck:
    """Base class for service health checks"""

    def __init__(self, name: str, critical: bool = True):
        self.name = name
        self.critical = critical
        self.start_time = None
        self.duration = None
        self.status = "pending"
        self.error = None

    async def check(self) -> Dict[str, Any]:
        """Run health check and return results"""
        self.start_time = time.time()

        try:
            result = await self._perform_check()
            self.status = "healthy" if result else "unhealthy"
            return result
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            logger.error(f"Health check failed for {self.name}: {e}")

            if self.critical:
                raise
            return False
        finally:
            self.duration = time.time() - self.start_time

    async def _perform_check(self) -> bool:
        """Override to implement specific health check"""
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting"""
        return {
            "service": self.name,
            "status": self.status,
            "critical": self.critical,
            "duration_ms": int(self.duration * 1000) if self.duration else None,
            "error": self.error,
            "timestamp": datetime.utcnow().isoformat(),
        }


class DatabaseHealthCheck(ServiceHealthCheck):
    """Check database connectivity and basic operations"""

    def __init__(self):
        super().__init__("database", critical=True)

    async def _perform_check(self) -> bool:
        """Test database connection and simple query"""
        async with get_db() as db:
            # Test connection
            result = await db.execute(text("SELECT 1"))
            assert result.scalar() == 1

            # Test table access
            result = await db.execute(
                text("SELECT COUNT(*) FROM businesses WHERE id LIKE 'heartbeat_%'")
            )

            # Cleanup old heartbeat records
            await db.execute(
                text(
                    """
                    DELETE FROM businesses 
                    WHERE id LIKE 'heartbeat_%' 
                    AND created_at < NOW() - INTERVAL '1 day'
                """
                )
            )
            await db.commit()

        return True


class RedisHealthCheck(ServiceHealthCheck):
    """Check Redis cache connectivity"""

    def __init__(self):
        super().__init__("redis", critical=False)

    async def _perform_check(self) -> bool:
        """Test Redis connection and basic operations"""
        from d0_gateway.cache import ResponseCache
        import redis.asyncio as redis

        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            cache = ResponseCache(redis_client)

            # Test set/get
            test_key = f"heartbeat_{int(time.time())}"
            test_value = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

            await cache.redis.set(test_key, json.dumps(test_value), ex=60)
            retrieved = await cache.redis.get(test_key)

            assert retrieved is not None
            assert json.loads(retrieved)["status"] == "ok"

            # Cleanup
            await cache.redis.delete(test_key)
            await redis_client.close()

            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False  # Non-critical, so return False instead of raising


# YelpAPIHealthCheck removed - Yelp has been removed from the codebase


class StripeHealthCheck(ServiceHealthCheck):
    """Check Stripe API authentication"""

    def __init__(self):
        super().__init__("stripe", critical=True)

    async def _perform_check(self) -> bool:
        """Test Stripe API access"""
        gateway = GatewayFacade()

        # List products (lightweight call)
        products = await gateway.stripe.Product.list_async(limit=1)

        # Verify we can access Stripe
        assert products is not None

        # Check webhook endpoint is configured
        if settings.STRIPE_WEBHOOK_SECRET:
            endpoints = await gateway.stripe.WebhookEndpoint.list_async(limit=1)
            assert endpoints is not None

        return True


class SendGridHealthCheck(ServiceHealthCheck):
    """Check SendGrid API authentication"""

    def __init__(self):
        super().__init__("sendgrid", critical=True)

    async def _perform_check(self) -> bool:
        """Test SendGrid API access"""
        gateway = GatewayFacade()

        # Get account details (lightweight call)
        response = await gateway.sendgrid.client.user.profile.get()

        assert response.status_code == 200

        # Check suppression list access
        response = await gateway.sendgrid.client.suppression.bounces.get(
            limit=1, offset=0
        )

        assert response.status_code in [200, 404]  # 404 if no bounces

        return True


class OpenAIHealthCheck(ServiceHealthCheck):
    """Check OpenAI API authentication"""

    def __init__(self):
        super().__init__("openai", critical=False)

    async def _perform_check(self) -> bool:
        """Test OpenAI API access"""
        gateway = GatewayFacade()

        # Test with minimal tokens
        response = await gateway.openai.complete(
            prompt="Say 'OK'", model="gpt-4o-mini", max_tokens=5, temperature=0
        )

        assert response is not None
        assert len(response) > 0

        return True


class PageSpeedHealthCheck(ServiceHealthCheck):
    """Check PageSpeed API access"""

    def __init__(self):
        super().__init__("pagespeed", critical=False)

    async def _perform_check(self) -> bool:
        """Test PageSpeed API access"""
        gateway = GatewayFacade()

        # Check with Google's own site (always fast)
        result = await gateway.pagespeed.analyze(
            url="https://www.google.com",
            strategy="mobile",
            categories=["performance"],  # Minimal categories
        )

        assert "lighthouseResult" in result
        assert (
            result["lighthouseResult"]["categories"]["performance"]["score"] is not None
        )

        return True


@task(name="run_health_checks", timeout_seconds=30)
async def run_health_checks(checks: List[ServiceHealthCheck]) -> List[Dict[str, Any]]:
    """Run all health checks concurrently"""
    results = await asyncio.gather(
        *[check.check() for check in checks], return_exceptions=True
    )

    health_results = []
    for i, result in enumerate(results):
        check = checks[i]

        if isinstance(result, Exception):
            check.status = "error"
            check.error = str(result)

        health_results.append(check.to_dict())

        # Record metrics
        metrics.gauge(
            "heartbeat_health_status",
            1 if check.status == "healthy" else 0,
            labels={"service": check.name},
        )

        if check.duration:
            metrics.histogram(
                "heartbeat_check_duration_seconds",
                check.duration,
                labels={"service": check.name},
            )

    return health_results


@flow(name="leadfactory-heartbeat", retries=0, timeout_seconds=HEARTBEAT_TIMEOUT)
async def heartbeat_flow() -> Dict[str, Any]:
    """Main heartbeat flow - checks all critical services"""
    logger.info("Starting heartbeat health check")

    start_time = time.time()

    # Define health checks
    checks = [
        DatabaseHealthCheck(),
        RedisHealthCheck(),
        # YelpAPIHealthCheck removed - Yelp has been removed from the codebase
        StripeHealthCheck(),
        SendGridHealthCheck(),
        OpenAIHealthCheck(),
        PageSpeedHealthCheck(),
    ]

    # Run checks
    results = await run_health_checks(checks)

    # Analyze results
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "duration_seconds": time.time() - start_time,
        "total_checks": len(results),
        "healthy": sum(1 for r in results if r["status"] == "healthy"),
        "unhealthy": sum(1 for r in results if r["status"] == "unhealthy"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "critical_failures": [],
        "warnings": [],
        "checks": results,
    }

    # Categorize issues
    for result in results:
        if result["status"] != "healthy":
            if result["critical"]:
                summary["critical_failures"].append(result)
            else:
                summary["warnings"].append(result)

    # Determine overall status
    if summary["critical_failures"]:
        summary["overall_status"] = "critical"
        await send_heartbeat_alert("critical", summary)
    elif summary["warnings"]:
        summary["overall_status"] = "degraded"
        await send_heartbeat_alert("warning", summary)
    else:
        summary["overall_status"] = "healthy"

    # Log summary
    logger.info(
        f"Heartbeat complete: {summary['overall_status']} "
        f"({summary['healthy']}/{summary['total_checks']} healthy)"
    )

    # Record overall metrics
    metrics.gauge(
        "heartbeat_overall_health", 1 if summary["overall_status"] == "healthy" else 0
    )
    metrics.histogram("heartbeat_total_duration_seconds", summary["duration_seconds"])

    # Check duration
    if summary["duration_seconds"] > HEARTBEAT_TIMEOUT:
        await send_heartbeat_alert(
            "warning",
            {
                "message": f"Heartbeat exceeded timeout: {summary['duration_seconds']}s > {HEARTBEAT_TIMEOUT}s",
                **summary,
            },
        )

    return summary


async def send_heartbeat_alert(level: str, details: Dict[str, Any]):
    """Send heartbeat alerts"""

    if level == "critical":
        # Critical failures - would page on-call
        logger.error("CRITICAL: Heartbeat detected failures")
        logger.error(
            f"Failed services: {[f['service'] for f in details.get('critical_failures', [])]}"
        )

        # In production: PagerDuty API call here

    elif level == "warning":
        # Degraded service - Slack notification
        logger.warning("WARNING: Heartbeat detected degraded services")
        logger.warning(
            f"Affected services: {[w['service'] for w in details.get('warnings', [])]}"
        )

        # In production: Slack webhook here


# Quick health check endpoint for load balancers
async def quick_health_check() -> Dict[str, Any]:
    """Minimal health check for load balancers (< 1 second)"""
    try:
        # Just check database
        async with get_db() as db:
            result = await db.execute(text("SELECT 1"))
            assert result.scalar() == 1

        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Pytest integration
@pytest.mark.asyncio
@pytest.mark.heartbeat
async def test_heartbeat():
    """Run heartbeat test via pytest"""
    result = await heartbeat_flow()
    assert result["overall_status"] in ["healthy", "degraded"]
    assert result["critical_failures"] == []


@pytest.mark.asyncio
async def test_quick_health():
    """Test quick health check"""
    result = await quick_health_check()
    assert result["status"] == "healthy"


if __name__ == "__main__":
    # Run heartbeat directly
    import json

    result = asyncio.run(heartbeat_flow())
    print(json.dumps(result, indent=2))
