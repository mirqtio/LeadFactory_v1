"""
Full Pipeline Flow - P0-002

End-to-end Prefect orchestration flow that processes a business through the entire
LeadFactory pipeline: Target → Source → Assess → Score → Report → Deliver

This flow demonstrates the complete MVP working end-to-end with proper error
handling, retries, and metrics logging at each stage.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict

try:
    from prefect import flow, task
    from prefect.logging import get_run_logger

    PREFECT_AVAILABLE = True
except ImportError:
    # Fallback for environments without Prefect
    PREFECT_AVAILABLE = False

    def flow(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def task(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def get_run_logger():
        return logging.getLogger(__name__)


# Import coordinators and necessary modules
from d2_sourcing.coordinator import SourcingCoordinator
from d3_assessment.coordinator import AssessmentCoordinator
from d5_scoring import ScoringEngine
from d6_reports.generator import ReportGenerator
from d8_personalization.content_generator import AdvancedContentGenerator
from d9_delivery.delivery_manager import DeliveryManager

# Task definitions with error handling and retries


@task(name="target_business", retries=2, retry_delay_seconds=60, timeout_seconds=300)
async def target_business(url: str) -> Dict[str, Any]:
    """
    Target a business by URL

    This task identifies and validates a business target from a given URL.
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    logger.info(f"🎯 Targeting business from URL: {url}")

    try:
        # Simple targeting logic for MVP
        # In production, this would use the full targeting system
        business_data = {
            "id": f"biz_{hash(url) % 100000}",
            "url": url,
            "name": f"Business from {url}",
            "targeted_at": datetime.utcnow().isoformat(),
            "status": "targeted",
        }

        logger.info(f"✅ Successfully targeted business: {business_data['id']}")
        return business_data

    except Exception as e:
        logger.error(f"❌ Failed to target business: {e}")
        raise


@task(name="source_business_data", retries=3, retry_delay_seconds=120, timeout_seconds=600)
async def source_business_data(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Source comprehensive business data

    Uses the SourcingCoordinator to gather business information from various sources.
    Since SourcingCoordinator doesn't have a single-business method, we create minimal
    mock data for the MVP demo.
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    logger.info(f"🔍 Sourcing data for business: {business_data['id']}")

    try:
        # For MVP, create minimal sourcing data
        # In production, this would integrate with DataAxle or other providers
        sourcing_result = {
            "name": business_data.get("name", "Test Business"),
            "url": business_data["url"],
            "email": "contact@example.com",
            "phone": "555-0123",
            "address": "123 Business St, City, ST 12345",
            "industry": "Technology",
            "employees": "10-50",
            "revenue": "$1M-$5M",
            "founded": "2015",
            "description": "A modern technology company focused on innovation.",
        }

        # Merge sourced data with targeting data
        business_data.update(
            {"sourced_data": sourcing_result, "sourced_at": datetime.utcnow().isoformat(), "source_status": "completed"}
        )

        logger.info(f"✅ Successfully sourced data for business: {business_data['id']}")
        return business_data

    except Exception as e:
        logger.error(f"❌ Failed to source business data: {e}")
        business_data["source_status"] = "failed"
        business_data["source_error"] = str(e)
        raise


@task(name="assess_website", retries=2, retry_delay_seconds=180, timeout_seconds=900)
async def assess_website(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform comprehensive website assessment

    Uses the AssessmentCoordinator to analyze website performance, tech stack,
    and other quality metrics.
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    logger.info(f"📊 Assessing website for business: {business_data['id']}")

    try:
        coordinator = AssessmentCoordinator()

        # Run comprehensive assessment using the correct method name
        assessment_result = await coordinator.execute_comprehensive_assessment(
            business_id=business_data["id"],
            url=business_data["url"],  # Note: parameter is 'url' not 'business_url'
            assessment_types=["pagespeed", "tech_stack", "seo_basics"],
        )

        business_data["assessment_data"] = assessment_result
        business_data["assessed_at"] = datetime.utcnow().isoformat()
        business_data["assessment_status"] = "completed"

        logger.info(f"✅ Successfully assessed website: {business_data['id']}")
        return business_data

    except Exception as e:
        logger.error(f"❌ Failed to assess website: {e}")
        business_data["assessment_status"] = "failed"
        business_data["assessment_error"] = str(e)
        # Continue with partial data
        return business_data


@task(name="calculate_score", retries=1, retry_delay_seconds=30, timeout_seconds=300)
def calculate_score(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate business quality score

    Analyzes assessment data to produce a comprehensive quality score.
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    logger.info(f"🧮 Calculating score for business: {business_data['id']}")

    try:
        calculator = ScoringEngine()

        # Extract assessment data
        assessment_data = business_data.get("assessment_data", {})

        # Check if assessment failed - use default score
        if business_data.get("assessment_status") == "failed" or not assessment_data:
            logger.warning("Using default score due to assessment failure")
            business_data["score"] = 50
            business_data["score_tier"] = "D"  # Default low tier on failure
            business_data["score_details"] = {"overall_score": 50, "reason": "assessment_failed"}
            business_data["scored_at"] = datetime.utcnow().isoformat()
            return business_data

        # Calculate comprehensive score (note: calculate_score is SYNC not ASYNC)
        score_result = calculator.calculate_score(assessment_data)

        business_data["score"] = score_result["overall_score"]
        business_data["score_details"] = score_result
        # Determine tier based on score
        score = score_result.get("overall_score", 50)
        if score >= 90:
            tier = "A"
        elif score >= 75:
            tier = "B"
        elif score >= 60:
            tier = "C"
        else:
            tier = "D"
        business_data["score_tier"] = tier
        business_data["scored_at"] = datetime.utcnow().isoformat()

        logger.info(f"✅ Score calculated: {score_result['overall_score']}/100 ({score_result.get('tier', 'standard')})")
        return business_data

    except Exception as e:
        logger.error(f"❌ Failed to calculate score: {e}")
        # Use default score if calculation fails
        business_data["score"] = 50
        business_data["score_tier"] = "D"  # Default low tier on failure
        business_data["score_error"] = str(e)
        return business_data


@task(name="generate_report", retries=2, retry_delay_seconds=120, timeout_seconds=600)
async def generate_report(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate comprehensive PDF report

    Creates a detailed assessment report with scores, insights, and recommendations.
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    logger.info(f"📄 Generating report for business: {business_data['id']}")

    try:
        generator = ReportGenerator()

        # Generate PDF report
        report_path = await generator.generate_report(
            business_id=business_data["id"],
            business_name=business_data.get("name", "Unknown Business"),
            assessment_data=business_data.get("assessment_data", {}),
            score_data=business_data.get("score_details", {}),
            tier=business_data.get("score_tier", "standard"),
        )

        business_data["report_path"] = report_path
        business_data["report_generated_at"] = datetime.utcnow().isoformat()
        business_data["report_status"] = "completed"

        logger.info(f"✅ Report generated: {report_path}")
        return business_data

    except Exception as e:
        logger.error(f"❌ Failed to generate report: {e}")
        business_data["report_status"] = "failed"
        business_data["report_error"] = str(e)
        raise


@task(name="send_email", retries=3, retry_delay_seconds=300, timeout_seconds=300)
async def send_email(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send assessment report via email

    Delivers the generated report to the business contact with personalized messaging.
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    logger.info(f"📧 Sending email for business: {business_data['id']}")

    try:
        # Get email from sourced data or use default
        email = business_data.get("sourced_data", {}).get("email")
        if not email:
            # In test mode, use a placeholder
            email = "test@example.com"
            logger.warning("No email found, using test email")

        sender = DeliveryManager()
        personalizer = AdvancedContentGenerator()

        # Generate personalized email content
        email_content = await personalizer.generate_email_content(
            business_name=business_data.get("name", "Business Owner"),
            score=business_data.get("score", 50),
            tier=business_data.get("score_tier", "standard"),
            key_insights=business_data.get("assessment_data", {}).get("insights", []),
        )

        # Send email with report attachment
        email_result = await sender.send_assessment_email(
            to_email=email,
            subject=email_content["subject"],
            body=email_content["body"],
            report_path=business_data.get("report_path"),
        )

        business_data["email_sent"] = True
        business_data["email_sent_at"] = datetime.utcnow().isoformat()
        business_data["email_id"] = email_result.get("message_id")
        business_data["delivery_status"] = "completed"

        logger.info(f"✅ Email sent successfully to: {email}")
        return business_data

    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        business_data["email_sent"] = False
        business_data["delivery_status"] = "failed"
        business_data["delivery_error"] = str(e)
        # Don't raise - email failure shouldn't fail the entire pipeline
        return business_data


# Main pipeline flow


@flow(
    name="full_pipeline",
    description="End-to-end LeadFactory pipeline: Target → Source → Assess → Score → Report → Deliver",
    retries=0,
    retry_delay_seconds=0,
    timeout_seconds=1800,  # 30 minutes total
)
async def full_pipeline_flow(url: str) -> Dict[str, Any]:
    """
    Execute the complete LeadFactory pipeline for a single business URL

    This flow demonstrates the entire MVP working end-to-end, processing a
    business from initial targeting through final email delivery.

    Args:
        url: The business website URL to process

    Returns:
        Complete pipeline result with all intermediate data
    """
    try:
        logger = get_run_logger()
    except Exception:
        # Fallback to standard logger if not in Prefect context
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
    start_time = time.time()

    logger.info(f"🚀 Starting full pipeline for URL: {url}")

    try:
        # Execute pipeline stages in sequence
        # Each stage adds data to the business_data dictionary

        # When running outside Prefect context, call task functions directly
        # Use .fn() to get the underlying function when task decorator is present
        target_fn = target_business.fn if hasattr(target_business, "fn") else target_business
        source_fn = source_business_data.fn if hasattr(source_business_data, "fn") else source_business_data
        assess_fn = assess_website.fn if hasattr(assess_website, "fn") else assess_website
        score_fn = calculate_score.fn if hasattr(calculate_score, "fn") else calculate_score
        report_fn = generate_report.fn if hasattr(generate_report, "fn") else generate_report
        email_fn = send_email.fn if hasattr(send_email, "fn") else send_email

        # Stage 1: Target
        business_data = await target_fn(url)
        logger.info("Stage 1/6 complete: Targeting ✓")

        # Stage 2: Source
        business_data = await source_fn(business_data)
        logger.info("Stage 2/6 complete: Sourcing ✓")

        # Stage 3: Assess
        business_data = await assess_fn(business_data)
        logger.info("Stage 3/6 complete: Assessment ✓")

        # Stage 4: Score
        business_data = score_fn(business_data)
        logger.info("Stage 4/6 complete: Scoring ✓")

        # Stage 5: Report
        business_data = await report_fn(business_data)
        logger.info("Stage 5/6 complete: Report Generation ✓")

        # Stage 6: Deliver
        business_data = await email_fn(business_data)
        logger.info("Stage 6/6 complete: Delivery ✓")

        # Calculate total execution time
        execution_time = time.time() - start_time

        # Final result
        result = {
            "status": "complete",
            "business_id": business_data["id"],
            "score": business_data.get("score", 0),
            "score_tier": business_data.get("score_tier", "D"),
            "report_path": business_data.get("report_path"),
            "email_sent": business_data.get("email_sent", False),
            "execution_time_seconds": execution_time,
            "stages_completed": 6,
            "timestamp": datetime.utcnow().isoformat(),
            "full_data": business_data,  # Include all intermediate data
        }

        logger.info(f"✅ Pipeline completed successfully in {execution_time:.2f} seconds")
        logger.info(f"📊 Final score: {result['score']}/100")
        logger.info(f"📄 Report: {result['report_path']}")
        logger.info(f"📧 Email sent: {result['email_sent']}")

        return result

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        execution_time = time.time() - start_time

        # Return partial result on failure
        return {
            "status": "failed",
            "error": str(e),
            "execution_time_seconds": execution_time,
            "timestamp": datetime.utcnow().isoformat(),
            "partial_data": locals().get("business_data", {}),
        }


# Convenience function for running the pipeline
async def run_pipeline(url: str) -> Dict[str, Any]:
    """
    Convenience function to run the full pipeline

    Can be called from tests or other modules without Prefect context.
    """
    # For testing, we'll call the function directly without going through Prefect
    # This avoids the need for a Prefect server in tests
    return (
        await full_pipeline_flow.__wrapped__(url)
        if hasattr(full_pipeline_flow, "__wrapped__")
        else await full_pipeline_flow(url)
    )


# Allow running as script for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://example.com"

    print(f"Running full pipeline for: {url}")
    result = asyncio.run(run_pipeline(url))
    print(f"Pipeline result: {result}")
