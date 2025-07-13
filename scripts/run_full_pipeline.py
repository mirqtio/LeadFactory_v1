#!/usr/bin/env python3
"""
Run full pipeline with assessments and report generation for test URLs
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import httpx
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test URLs provided by user
TEST_URLS = [
    {
        "business_id": "arctic_air",
        "business_name": "Arctic Air CT",
        "url": "http://arcticairct.com/",
        "vertical": "professional_services",
        "location": "Connecticut"
    },
    {
        "business_id": "aloha_snacks",
        "business_name": "Aloha Snacks VB",
        "url": "https://alohasnacksvb.com/",
        "vertical": "retail",
        "location": "Virginia Beach, VA"
    },
    {
        "business_id": "vision21",
        "business_name": "Vision 21",
        "url": "https://vision21.com/",
        "vertical": "healthcare",
        "location": "Unknown"
    },
    {
        "business_id": "life_in_motion",
        "business_name": "Life in Motion Physical Therapy",
        "url": "https://www.lifeinmotionphysicaltherapy.org/",
        "vertical": "healthcare",
        "location": "Unknown"
    },
    {
        "business_id": "power_design",
        "business_name": "Power Design CT",
        "url": "https://www.powerdesignct.com",
        "vertical": "professional_services",
        "location": "Connecticut"
    },
    {
        "business_id": "mandala_vet",
        "business_name": "Mandala Veterinary",
        "url": "https://mandalaveterinary.com/",
        "vertical": "healthcare",
        "location": "Unknown"
    },
    {
        "business_id": "invest_yakima",
        "business_name": "Invest in Yakima",
        "url": "https://www.investinyakima.com/",
        "vertical": "government",
        "location": "Yakima, WA"
    },
    {
        "business_id": "afc_mortgage",
        "business_name": "AFC Mortgage Group",
        "url": "https://www.afcmortgagegroup.net",
        "vertical": "financial_services",
        "location": "Unknown"
    },
    {
        "business_id": "bethel_it",
        "business_name": "Bethel IT Services",
        "url": "https://bethelitservices.com/",
        "vertical": "professional_services",
        "location": "Unknown"
    }
]

# API configuration
API_BASE_URL = "http://localhost:8000"
ASSESSMENT_ENDPOINT = f"{API_BASE_URL}/api/v1/assessments/trigger"
STATUS_ENDPOINT = f"{API_BASE_URL}/api/v1/assessments"
REPORT_ENDPOINT = f"{API_BASE_URL}/api/v1/reports/generate"


async def trigger_assessment(client: httpx.AsyncClient, business: Dict[str, Any]) -> str:
    """Trigger assessment for a business URL"""
    print(f"\n📊 Triggering assessment for {business['business_name']}...")

    payload = {
        "business_id": business["business_id"],
        "url": business["url"],
        "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
        "industry": business["vertical"],
        "session_config": {
            "business_name": business["business_name"],
            "location": business["location"]
        }
    }

    response = await client.post(ASSESSMENT_ENDPOINT, json=payload)
    if response.status_code != 200:
        print(f"❌ Failed to trigger assessment: {response.text}")
        return None

    data = response.json()
    session_id = data["session_id"]
    print(f"✅ Assessment started with session ID: {session_id}")
    return session_id


async def check_assessment_status(client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
    """Check assessment status"""
    url = f"{STATUS_ENDPOINT}/{session_id}/status"
    response = await client.get(url)
    return response.json()


async def get_assessment_results(client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
    """Get assessment results"""
    url = f"{STATUS_ENDPOINT}/{session_id}/results"
    response = await client.get(url)
    return response.json()


async def wait_for_completion(client: httpx.AsyncClient, session_id: str, business_name: str) -> bool:
    """Wait for assessment to complete"""
    print(f"⏳ Waiting for {business_name} assessment to complete...")

    max_attempts = 60  # 5 minutes max
    for attempt in range(max_attempts):
        status = await check_assessment_status(client, session_id)

        if status["status"] in ["completed", "failed", "partial"]:
            print(f"✅ Assessment {status['status']} for {business_name}")
            return True

        print(f"   Progress: {status.get('progress', 'Processing...')} ({attempt+1}/{max_attempts})")
        await asyncio.sleep(5)  # Check every 5 seconds

    print(f"❌ Assessment timed out for {business_name}")
    return False


async def generate_report(business: Dict[str, Any], assessment_results: Dict[str, Any], output_dir: Path):
    """Generate HTML and PDF reports using the report generator"""
    print(f"\n📝 Generating reports for {business['business_name']}...")

    try:
        # Use the API endpoint to generate reports
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Prepare report generation request
            payload = {
                "business_id": business["business_id"],
                "business_name": business["business_name"],
                "business_url": business["url"],
                "assessment_data": assessment_results,
                "include_pdf": True,
                "template_name": "basic_report"
            }

            response = await client.post(REPORT_ENDPOINT, json=payload)

            if response.status_code == 200:
                result = response.json()

                # Save HTML report
                if result.get("html_content"):
                    html_filename = output_dir / f"report_{business['business_id']}.html"
                    with open(html_filename, 'w') as f:
                        f.write(result["html_content"])
                    print(f"✅ HTML report saved: {html_filename}")

                # Save PDF if available
                if result.get("pdf_url"):
                    # Download PDF from URL
                    pdf_response = await client.get(result["pdf_url"])
                    if pdf_response.status_code == 200:
                        pdf_filename = output_dir / f"report_{business['business_id']}.pdf"
                        with open(pdf_filename, 'wb') as f:
                            f.write(pdf_response.content)
                        print(f"✅ PDF report saved: {pdf_filename}")
                    else:
                        print("⚠️  Could not download PDF report")

                print("✅ Report generation completed successfully")
            else:
                print(f"❌ Report generation failed: {response.text}")

    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()


async def save_assessment_data(session_id: str, business: Dict[str, Any], results: Dict[str, Any], output_dir: Path):
    """Save assessment results to JSON file"""
    filename = output_dir / f"assessment_{business['business_id']}_{session_id}.json"

    output = {
        "session_id": session_id,
        "business": business,
        "results": results,
        "generated_at": datetime.utcnow().isoformat()
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"💾 Assessment data saved to {filename}")


async def run_pipeline_for_business(client: httpx.AsyncClient, business: Dict[str, Any], output_dir: Path):
    """Run complete pipeline for a single business"""
    print(f"\n{'='*60}")
    print(f"🏢 Processing: {business['business_name']}")
    print(f"🌐 URL: {business['url']}")
    print(f"📊 Industry: {business['vertical']}")
    print(f"{'='*60}")

    # Step 1: Trigger assessment
    session_id = await trigger_assessment(client, business)
    if not session_id:
        return

    # Step 2: Wait for completion
    if not await wait_for_completion(client, session_id, business["business_name"]):
        return

    # Step 3: Get results
    try:
        results = await get_assessment_results(client, session_id)

        # Step 4: Save assessment data
        await save_assessment_data(session_id, business, results, output_dir)

        # Step 5: Generate reports
        await generate_report(business, results, output_dir)

        # Print summary
        print(f"\n📊 Summary for {business['business_name']}:")
        if results.get("pagespeed_results"):
            ps = results["pagespeed_results"]
            print(f"   Performance Score: {ps.get('performance_score', 'N/A')}/100")
            print(f"   SEO Score: {ps.get('seo_score', 'N/A')}/100")
            print(f"   Accessibility Score: {ps.get('accessibility_score', 'N/A')}/100")

        if results.get("tech_stack_results"):
            print(f"   Technologies Found: {len(results['tech_stack_results'])}")

        if results.get("ai_insights_results"):
            ai = results["ai_insights_results"]
            recs = ai.get("recommendations", [])
            print(f"   AI Recommendations: {len(recs)}")

    except Exception as e:
        print(f"❌ Pipeline failed for {business['business_name']}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run full pipeline for all test URLs"""
    print("🚀 Starting LeadFactory Full Pipeline")
    print(f"📍 API URL: {API_BASE_URL}")
    print(f"🔗 Processing {len(TEST_URLS)} URLs")

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"pipeline_results_{timestamp}")
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}")

    async with httpx.AsyncClient(timeout=300.0) as client:
        # First check if API is available
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                print("❌ API is not healthy. Please start the server first.")
                return
            print("✅ API is healthy")
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            print("Please run: python -m uvicorn main:app --reload")
            return

        # Process each business sequentially to avoid overwhelming the API
        for business in TEST_URLS:
            await run_pipeline_for_business(client, business, output_dir)

            # Small delay between businesses
            await asyncio.sleep(2)

    print(f"\n{'='*60}")
    print("✅ Full pipeline completed!")
    print(f"📁 All results saved in: {output_dir.absolute()}")
    print(f"{'='*60}")

    # List generated files
    print("\n📋 Generated files:")
    for file in sorted(output_dir.iterdir()):
        print(f"   - {file.name}")


if __name__ == "__main__":
    asyncio.run(main())
