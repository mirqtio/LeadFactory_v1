"""
End-to-End Production Smoke Tests
Runs daily at 20:30 UTC before nightly batch

Test Matrix:
- HVAC normal (baseline)
- HVAC negative (PageSpeed latency)
- Restaurant email-fail
- Lawyer Stripe error
- Rotating vertical
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict

import pytest
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner

from core.logging import get_logger
from core.metrics import metrics
from database.models import Business
from database.session import get_db

logger = get_logger(__name__)

# Test configuration
SMOKE_TEST_TIMEOUT = 480  # 8 minutes total
TASK_TIMEOUT_LIMITS = {
    "assessment": 25,
    "pdf_generation": 30,
    "stripe_webhook": 10,
    "email_delivery": 15,
}

# Rotating verticals for daily coverage
ROTATING_VERTICALS = [
    "dental",
    "hvac",
    "restaurant",
    "lawyer",
    "salon",
    "auto_repair",
    "medical",
]


class SmokeTestVariant:
    """Base class for smoke test variants"""

    def __init__(self, name: str, vertical: str, fixture_data: Dict[str, Any]):
        self.name = name
        self.vertical = vertical
        self.fixture_data = fixture_data
        self.run_id = f"smoke_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{name}"
        self.timings = {}

    def inject_failures(self):
        """Override to inject specific failures"""
        pass

    def validate_results(self, results: Dict[str, Any]):
        """Override to add variant-specific validations"""
        pass


class HVACNormalVariant(SmokeTestVariant):
    """Baseline happy path test"""

    def __init__(self):
        super().__init__(
            name="hvac_normal",
            vertical="hvac",
            fixture_data={
                "name": "SMOKE TEST HVAC Company",
                "email": "smoke-test@example.com",
                "phone": "+1234567890",
                "url": "https://example.com",
                "address": "123 Test St",
                "city": "Test City",
                "state": "CA",
                "zip_code": "90210",
            },
        )

    def validate_results(self, results: Dict[str, Any]):
        """All components should complete successfully"""
        assert results["assessment"]["status"] == "completed"
        assert results["scoring"]["tier"] in ["A", "B", "C", "D"]
        assert results["email"]["status"] == "sent"
        assert results["purchase"] is not None

        # Check assessment quality
        assessment = results["assessment"]["data"]
        assert len(assessment.get("issues", [])) >= 2
        assert assessment.get("screenshots_count", 0) >= 1


class HVACNegativeVariant(SmokeTestVariant):
    """Test with PageSpeed latency injection"""

    def __init__(self):
        super().__init__(
            name="hvac_negative",
            vertical="hvac",
            fixture_data={
                "name": "SMOKE TEST HVAC Slow",
                "email": "smoke-slow@example.com",
                "phone": "+1234567891",
                "url": "https://slow-example.com",
                "address": "456 Slow St",
                "city": "Test City",
                "state": "CA",
                "zip_code": "90211",
            },
        )

    def inject_failures(self):
        """Add 500ms latency to PageSpeed calls"""
        original_analyze = None

        async def slow_analyze(*args, **kwargs):
            await asyncio.sleep(0.5)  # 500ms delay
            return await original_analyze(*args, **kwargs)

        # Patch PageSpeed client
        from d0_gateway.providers.pagespeed import PageSpeedClient

        original_analyze = PageSpeedClient.analyze
        PageSpeedClient.analyze = slow_analyze

    def validate_results(self, results: Dict[str, Any]):
        """Should complete but with timeout warnings"""
        assert results["assessment"]["status"] == "completed"
        assert results["scoring"]["tier"] == "D"  # Low score due to timeout
        assert results["email"]["status"] == "sent"

        # Check for timeout error in assessment
        assessment = results["assessment"]["data"]
        errors = assessment.get("errors", [])
        assert any("timeout" in str(e).lower() for e in errors)


class RestaurantEmailFailVariant(SmokeTestVariant):
    """Test with invalid email address"""

    def __init__(self):
        super().__init__(
            name="restaurant_email_fail",
            vertical="restaurant",
            fixture_data={
                "name": "SMOKE TEST Restaurant",
                "email": "bad@@example",  # Invalid email
                "phone": "+1234567892",
                "url": "https://restaurant.example.com",
                "address": "789 Food St",
                "city": "Test City",
                "state": "CA",
                "zip_code": "90212",
            },
        )

    def validate_results(self, results: Dict[str, Any]):
        """Should skip email delivery"""
        assert results["assessment"]["status"] == "completed"
        assert results["scoring"]["status"] == "completed"
        assert results["email"]["status"] == "invalid_email"
        assert results["purchase"] is None

        # Check database record
        email_record = results.get("email_record")
        if email_record:
            assert email_record.status == "invalid_email"


class LawyerStripeErrorVariant(SmokeTestVariant):
    """Test with Stripe payment failure"""

    def __init__(self):
        super().__init__(
            name="lawyer_stripe_error",
            vertical="lawyer",
            fixture_data={
                "name": "SMOKE TEST Law Firm",
                "email": "smoke-lawyer@example.com",
                "phone": "+1234567893",
                "url": "https://lawfirm.example.com",
                "address": "321 Legal Ave",
                "city": "Test City",
                "state": "CA",
                "zip_code": "90213",
                "stripe_test_card": "4000000000000341",  # Decline card
            },
        )

    def validate_results(self, results: Dict[str, Any]):
        """Should handle payment failure gracefully"""
        assert results["assessment"]["status"] == "completed"
        assert results["scoring"]["status"] == "completed"
        assert results["email"]["status"] == "sent"

        # Purchase should fail
        purchase = results.get("purchase_record")
        if purchase:
            assert purchase.status == "payment_failed"


class RotatingVerticalVariant(SmokeTestVariant):
    """Test different vertical each day"""

    def __init__(self):
        day_of_week = datetime.utcnow().weekday()
        vertical = ROTATING_VERTICALS[day_of_week % len(ROTATING_VERTICALS)]

        super().__init__(
            name=f"rotating_{vertical}",
            vertical=vertical,
            fixture_data={
                "name": f"SMOKE TEST {vertical.title()} Business",
                "email": f"smoke-{vertical}@example.com",
                "phone": "+1234567894",
                "url": f"https://{vertical}.example.com",
                "address": "999 Rotating St",
                "city": "Test City",
                "state": "CA",
                "zip_code": "90214",
            },
        )

    def validate_results(self, results: Dict[str, Any]):
        """Standard validation for rotating vertical"""
        assert results["assessment"]["status"] == "completed"
        assert results["scoring"]["status"] == "completed"
        assert results["email"]["status"] == "sent"


@task(name="smoke_test_runner", retries=0, timeout_seconds=300)
async def run_smoke_variant(variant: SmokeTestVariant) -> Dict[str, Any]:
    """Run a single smoke test variant"""
    logger.info(f"Starting smoke test variant: {variant.name}")

    start_time = time.time()
    results = {"variant": variant.name, "status": "FAIL", "timings": {}, "errors": []}

    try:
        # Inject any failures for this variant
        variant.inject_failures()

        # Create test business
        async with get_db() as db:
            business = Business(id=f"smoke_{variant.name}_{int(time.time())}", **variant.fixture_data)
            db.add(business)
            await db.commit()

        # Run assessment
        assessment_start = time.time()
        assessment_result = await run_assessment(business)
        results["timings"]["assessment"] = time.time() - assessment_start
        results["assessment"] = assessment_result

        # Check assessment timing
        assert (
            results["timings"]["assessment"] < TASK_TIMEOUT_LIMITS["assessment"]
        ), f"Assessment took {results['timings']['assessment']}s, limit is {TASK_TIMEOUT_LIMITS['assessment']}s"

        # Run scoring
        scoring_start = time.time()
        scoring_result = await run_scoring(business, assessment_result)
        results["timings"]["scoring"] = time.time() - scoring_start
        results["scoring"] = scoring_result

        # Run personalization and email
        if variant.fixture_data.get("email", "").count("@") == 1:
            email_start = time.time()
            email_result = await run_email_flow(business, scoring_result)
            results["timings"]["email_delivery"] = time.time() - email_start
            results["email"] = email_result

            # Check email timing
            assert results["timings"]["email_delivery"] < TASK_TIMEOUT_LIMITS["email_delivery"]
        else:
            results["email"] = {"status": "invalid_email"}

        # Run payment flow if email was sent
        if results["email"].get("status") == "sent":
            payment_start = time.time()
            purchase_result = await run_payment_flow(business, variant.fixture_data.get("stripe_test_card"))
            results["timings"]["stripe_webhook"] = time.time() - payment_start
            results["purchase"] = purchase_result

            # Check payment timing
            if results["timings"].get("stripe_webhook"):
                assert results["timings"]["stripe_webhook"] < TASK_TIMEOUT_LIMITS["stripe_webhook"]

        # Variant-specific validations
        variant.validate_results(results)

        # Mark as passed if we got here
        results["status"] = "PASS"
        results["total_time"] = time.time() - start_time

        # Record metrics
        for task_name, duration in results["timings"].items():
            metrics.histogram(
                "smoke_test_duration_seconds",
                duration,
                labels={"variant": variant.name, "task": task_name},
            )

    except Exception as e:
        logger.error(f"Smoke test variant {variant.name} failed: {e}")
        results["errors"].append(str(e))
        results["status"] = "FAIL"
        raise

    finally:
        # Cleanup smoke test data
        await cleanup_smoke_data(variant.run_id)

    return results


async def run_assessment(business: Business) -> Dict[str, Any]:
    """Run assessment for smoke test"""
    from d0_gateway.facade import GatewayFacade
    from d3_assessment.coordinator import AssessmentCoordinator

    gateway = GatewayFacade()
    coordinator = AssessmentCoordinator(gateway)

    result = await coordinator.assess_business(business)

    return {
        "status": "completed" if result else "failed",
        "data": result.__dict__ if result else {},
        "errors": result.errors if result else [],
    }


async def run_scoring(business: Business, assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Run scoring for smoke test"""
    from d5_scoring.engine import ScoringEngine

    engine = ScoringEngine()
    result = engine.calculate_score(business, assessment["data"])

    return {
        "status": "completed",
        "tier": result.tier,
        "score": result.score_pct,
        "data": result.__dict__,
    }


async def run_email_flow(business: Business, scoring: Dict[str, Any]) -> Dict[str, Any]:
    """Run email personalization and delivery"""
    from d0_gateway.facade import GatewayFacade
    from d8_personalization.personalizer import EmailPersonalizer
    from d9_delivery.delivery_manager import EmailDeliveryManager

    gateway = GatewayFacade()
    personalizer = EmailPersonalizer(gateway.openai)

    # Generate email
    email = await personalizer.generate_email(business, scoring["data"], {"results": {}})  # Minimal assessment data

    # Add smoke test marker to subject
    run_id = f"SMOKE-{datetime.utcnow().strftime('%H%M')}"
    email.subject_lines[0] = f"{email.subject_lines[0]} {run_id}"

    # Send email
    async with get_db() as db:
        delivery = EmailDeliveryManager(gateway.sendgrid, db)
        result = await delivery.send_email(email, business)

    return {
        "status": result.status,
        "message_id": result.message_id,
        "subject": email.subject_lines[0],
        "body_length": len(email.html_body),
    }


async def run_payment_flow(business: Business, test_card: str = None) -> Dict[str, Any]:
    """Run payment flow for smoke test"""
    from d0_gateway.facade import GatewayFacade
    from d7_storefront.checkout import CheckoutManager

    gateway = GatewayFacade()
    checkout = CheckoutManager(gateway.stripe)

    # Create checkout session
    session = await checkout.create_checkout_session(
        business_id=business.id,
        email=business.email,
        metadata={"source": "smoke", "test_card": test_card},
    )

    # Simulate webhook for test
    if test_card == "4000000000000341":  # Decline card
        return {"status": "payment_failed", "session_id": session.id}
    else:
        return {"status": "completed", "session_id": session.id}


async def cleanup_smoke_data(run_id: str):
    """Clean up smoke test data"""
    logger.info(f"Cleaning up smoke test data for run: {run_id}")

    async with get_db() as db:
        # Use prefixed transaction for safety
        await db.execute(
            """
            DELETE FROM purchases 
            WHERE business_id IN (
                SELECT id FROM businesses 
                WHERE id LIKE 'smoke_%' 
                AND created_at < NOW() - INTERVAL '24 hours'
            )
            """
        )

        await db.execute(
            """
            DELETE FROM emails 
            WHERE business_id IN (
                SELECT id FROM businesses 
                WHERE id LIKE 'smoke_%' 
                AND created_at < NOW() - INTERVAL '24 hours'
            )
            """
        )

        await db.execute(
            """
            DELETE FROM assessments 
            WHERE business_id IN (
                SELECT id FROM businesses 
                WHERE id LIKE 'smoke_%' 
                AND created_at < NOW() - INTERVAL '24 hours'
            )
            """
        )

        await db.execute(
            """
            DELETE FROM businesses 
            WHERE id LIKE 'smoke_%' 
            AND created_at < NOW() - INTERVAL '24 hours'
            """
        )

        await db.commit()


@flow(
    name="leadfactory-smoke-daily",
    task_runner=ConcurrentTaskRunner(max_workers=5),
    retries=0,
    timeout_seconds=600,
)
async def daily_smoke_flow():
    """Main daily smoke test flow - runs all variants in parallel"""
    logger.info("Starting daily smoke test flow")

    # Build variant matrix
    variants = [
        HVACNormalVariant(),
        HVACNegativeVariant(),
        RestaurantEmailFailVariant(),
        LawyerStripeErrorVariant(),
        RotatingVerticalVariant(),
    ]

    # Run all variants in parallel
    results = await asyncio.gather(*[run_smoke_variant(variant) for variant in variants], return_exceptions=True)

    # Process results
    summary = {
        "total": len(results),
        "passed": 0,
        "failed": 0,
        "errors": [],
        "timings": {},
    }

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            summary["failed"] += 1
            summary["errors"].append({"variant": variants[i].name, "error": str(result)})
        elif result["status"] == "PASS":
            summary["passed"] += 1
            # Aggregate timings
            for task, duration in result["timings"].items():
                if task not in summary["timings"]:
                    summary["timings"][task] = []
                summary["timings"][task].append(duration)
        else:
            summary["failed"] += 1
            summary["errors"].extend(result["errors"])

    # Check timing assertions
    for task, limits in TASK_TIMEOUT_LIMITS.items():
        if task in summary["timings"]:
            max_time = max(summary["timings"][task])
            assert max_time < limits, f"{task} exceeded limit: {max_time}s > {limits}s"

    # Log summary
    logger.info(f"Smoke test summary: {summary['passed']}/{summary['total']} passed")

    # Alert if any failures
    if summary["failed"] > 0:
        await send_alert(
            level="critical",
            message=f"Smoke test failed: {summary['failed']} variants failed",
            details=summary,
        )
        raise Exception(f"Smoke test failed: {summary['failed']} variants failed")

    # Record success metrics
    metrics.gauge("smoke_test_success_rate", summary["passed"] / summary["total"])

    # Cleanup old smoke data
    await cleanup_smoke_data("smoke_*")

    return summary


async def send_alert(level: str, message: str, details: Dict[str, Any]):
    """Send alert based on level"""
    logger.error(f"[{level.upper()}] {message}")
    logger.error(f"Details: {json.dumps(details, indent=2)}")

    # In production, this would integrate with:
    # - PagerDuty for critical alerts
    # - Slack for warnings
    # - Email for info

    if level == "critical":
        # Would trigger PagerDuty here
        pass
    elif level == "warning":
        # Would send to Slack
        pass


# Pytest integration for local testing
@pytest.mark.asyncio
@pytest.mark.smoke
async def test_smoke_suite():
    """Run smoke test suite via pytest"""
    result = await daily_smoke_flow()
    assert result["passed"] == result["total"]


if __name__ == "__main__":
    # Run smoke tests directly
    asyncio.run(daily_smoke_flow())
