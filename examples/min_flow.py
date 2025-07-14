"""
Minimal Prefect flow example for P0-002

This demonstrates the basic structure of a Prefect flow that:
1. Chains multiple tasks together
2. Handles errors with retries
3. Logs metrics at each stage
4. Returns JSON output
"""

import json
import time
from datetime import datetime

from prefect import flow, task
from prefect.task_runners import SequentialTaskRunner


@task(retries=2, retry_delay_seconds=5)
def target_business(business_name: str) -> dict:
    """Simulate targeting a business"""
    print(f"Targeting business: {business_name}")
    time.sleep(0.5)  # Simulate work
    return {"business_id": "123", "name": business_name, "targeted_at": datetime.now().isoformat()}


@task(retries=2, retry_delay_seconds=5)
def assess_website(business: dict) -> dict:
    """Simulate website assessment"""
    print(f"Assessing website for: {business['name']}")
    time.sleep(0.5)  # Simulate work
    business["assessment"] = {"has_website": True, "score": 85, "assessed_at": datetime.now().isoformat()}
    return business


@task(retries=1)
def generate_report(business: dict) -> dict:
    """Simulate report generation"""
    print(f"Generating report for: {business['name']}")
    time.sleep(0.5)  # Simulate work
    business["report"] = {
        "pdf_path": f"/tmp/report_{business['business_id']}.pdf",
        "generated_at": datetime.now().isoformat(),
    }
    return business


@flow(
    name="minimal-pipeline",
    description="Minimal example of full pipeline flow",
    task_runner=SequentialTaskRunner(),
)
def minimal_pipeline_flow(business_name: str = "Test Business") -> str:
    """
    Minimal pipeline that chains: Target → Assess → Report

    Returns:
        JSON string with results including score and PDF path
    """
    # Log start
    print(f"Starting pipeline for: {business_name}")

    # Chain tasks
    business = target_business(business_name)
    business = assess_website(business)
    business = generate_report(business)

    # Log metrics
    print(f"Pipeline complete. Score: {business['assessment']['score']}")
    print(f"PDF generated at: {business['report']['pdf_path']}")

    # Return JSON result
    return json.dumps(business, indent=2)


if __name__ == "__main__":
    # Run the flow
    result = minimal_pipeline_flow("Acme Corp")
    print("Result:")
    print(result)
