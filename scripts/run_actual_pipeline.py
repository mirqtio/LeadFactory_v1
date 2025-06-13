#!/usr/bin/env python3
"""
Run ACTUAL enrichment pipeline with real services
- Uses real API keys from .env
- No simulations
- Implements ScreenshotOne for screenshots
- Uses proper GBP enrichment
"""
import asyncio
import httpx
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from core.logging import get_logger
from d4_enrichment.coordinator import EnrichmentCoordinator
from d4_enrichment.models import EnrichmentSource

logger = get_logger(__name__)

# Test business
BUSINESS_ID = "07a80cdc-3c94-48df-9351-5ba097026806"
BUSINESS_URL = "https://investinyakima.com"
BUSINESS_NAME = "Yakima County Development Association"


async def trigger_assessment_with_screenshot(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Trigger assessment (PageSpeed, Tech Stack, AI Insights)"""
    print("\n1. Triggering Assessment with Real APIs")
    print("-" * 50)
    
    assessment_data = {
        "business_id": BUSINESS_ID,
        "url": BUSINESS_URL,
        "business_name": BUSINESS_NAME,
        "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
        "industry": "nonprofit",
        "session_config": {
            "priority": "high",
            "enable_caching": False,  # Force fresh assessment
            "timeout_seconds": 120
        }
    }
    
    response = await client.post("/api/v1/assessments/trigger", json=assessment_data)
    
    if response.status_code in [200, 201, 202]:
        result = response.json()
        session_id = result.get("session_id")
        print(f"✓ Assessment triggered: {session_id}")
        
        # Wait for completion
        max_attempts = 30
        for attempt in range(max_attempts):
            await asyncio.sleep(5)
            
            status_response = await client.get(f"/api/v1/assessments/{session_id}/status")
            if status_response.status_code == 200:
                status = status_response.json()
                if status.get("status") == "completed":
                    print(f"✓ Assessment completed")
                    
                    # Get results
                    results_response = await client.get(f"/api/v1/assessments/{session_id}/results")
                    if results_response.status_code == 200:
                        return results_response.json()
                    else:
                        print(f"✗ Failed to get results: {results_response.status_code}")
                        return None
                elif status.get("status") == "failed":
                    print(f"✗ Assessment failed")
                    return None
                else:
                    print(f"\r  Progress: {status.get('completed_assessments', 0)}/{status.get('total_assessments', 0)}", end="")
        
        print("\n✗ Assessment timeout")
        return None
    else:
        print(f"✗ Failed to trigger assessment: {response.status_code}")
        print(f"  Response: {response.text}")
        return None


async def capture_screenshot_with_screenshotone(url: str) -> Optional[Dict[str, Any]]:
    """Capture screenshot using ScreenshotOne API"""
    print("\n2. Capturing Screenshot with ScreenshotOne")
    print("-" * 50)
    
    # Get API key - check various possible names
    api_key = (
        os.getenv("SCREENSHOTONE_API_KEY") or 
        os.getenv("SCREENSHOT_ONE_API_KEY") or
        os.getenv("SCREENSHOT_API_KEY")
    )
    
    if not api_key:
        print("✗ No ScreenshotOne API key found in .env")
        print("  Checked: SCREENSHOTONE_API_KEY, SCREENSHOT_ONE_API_KEY, SCREENSHOT_API_KEY")
        return None
    
    print(f"✓ Using ScreenshotOne API key: {api_key[:10]}...")
    
    try:
        # ScreenshotOne API endpoint
        screenshot_url = "https://api.screenshotone.com/take"
        
        params = {
            "access_key": api_key,
            "url": url,
            "full_page": "true",
            "format": "png",
            "viewport_width": 1920,
            "viewport_height": 1080,
            "device_scale_factor": 1,
            "cache": "false"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(screenshot_url, params=params, timeout=30.0)
            
            if response.status_code == 200:
                # Save screenshot
                filename = f"screenshot_{BUSINESS_ID}.png"
                with open(filename, "wb") as f:
                    f.write(response.content)
                
                print(f"✓ Screenshot captured successfully")
                print(f"  Saved to: {filename}")
                print(f"  Size: {len(response.content) / 1024:.1f} KB")
                
                return {
                    "screenshot_path": filename,
                    "screenshot_url": url,
                    "captured_at": datetime.now().isoformat(),
                    "size_bytes": len(response.content)
                }
            else:
                print(f"✗ ScreenshotOne API error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return None
                
    except Exception as e:
        print(f"✗ Screenshot capture error: {str(e)}")
        return None


async def run_enrichment_coordinator() -> Dict[str, Any]:
    """Run enrichment using the coordinator with all available sources"""
    print("\n3. Running Enrichment Coordinator")
    print("-" * 50)
    
    # Initialize coordinator
    coordinator = EnrichmentCoordinator()
    
    # Business data for enrichment
    business_data = {
        "id": BUSINESS_ID,
        "name": BUSINESS_NAME,
        "website": BUSINESS_URL,
        "address": "10 North 9th Street",
        "city": "Yakima", 
        "state": "WA",
        "zip": "98901",
        "phone": None,  # Will try to find
        "categories": ["Economic Development", "Non-Profit"]
    }
    
    print("✓ Enrichment sources available:")
    for source, enricher in coordinator.enrichers.items():
        print(f"  - {source.value}: {enricher.__class__.__name__}")
    
    # Run batch enrichment
    results = await coordinator.batch_enrich_businesses(
        businesses=[business_data],
        sources=[
            EnrichmentSource.INTERNAL,  # GBP
            EnrichmentSource.DATA_AXLE,
            EnrichmentSource.HUNTER_IO
        ],
        skip_existing=False,
        priority="high"
    )
    
    print(f"\n✓ Enrichment completed")
    print(f"  Total processed: {results.total_processed}")
    print(f"  Successful: {results.successful_enrichments}")
    print(f"  Failed: {results.failed_enrichments}")
    print(f"  Skipped: {results.skipped_enrichments}")
    
    if results.results:
        enrichment = results.results[0]
        if enrichment:
            print(f"\n  Enrichment Details:")
            print(f"  - Source: {enrichment.source}")
            print(f"  - Match confidence: {enrichment.match_confidence}")
            print(f"  - Email: {enrichment.email or 'Not found'}")
            print(f"  - Phone: {enrichment.phone or 'Not found'}")
            print(f"  - Website: {enrichment.website or 'Not found'}")
            
            return {
                "enrichment_result": {
                    "source": enrichment.source,
                    "confidence": enrichment.match_confidence,
                    "email": enrichment.email,
                    "phone": enrichment.phone,
                    "website": enrichment.website,
                    "company_name": enrichment.company_name,
                    "address": enrichment.headquarters_address
                }
            }
    
    return {"enrichment_result": None}


async def analyze_with_openai(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Send data to OpenAI for analysis"""
    print("\n4. Analyzing with OpenAI GPT-4")
    print("-" * 50)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("✗ No OpenAI API key found")
        return None
    
    print(f"✓ Using OpenAI API key: {api_key[:20]}...")
    
    try:
        # Use httpx to call OpenAI API directly
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
        Analyze this business assessment and enrichment data for lead qualification:
        
        Business: {BUSINESS_NAME}
        Website: {BUSINESS_URL}
        
        Assessment Results:
        {json.dumps(data.get('assessment_results', {}), indent=2)}
        
        Enrichment Data:
        {json.dumps(data.get('enrichment_result', {}), indent=2)}
        
        Provide:
        1. Lead score (0-100)
        2. Top 3 opportunities for improvement
        3. Personalized outreach strategy
        4. Estimated project value range
        5. Key talking points
        
        Format as JSON.
        """
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a lead qualification expert for a web development agency. Analyze businesses and provide actionable insights."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content']
                
                print("✓ GPT-4 analysis completed")
                
                # Try to parse as JSON
                try:
                    analysis_data = json.loads(analysis)
                    return analysis_data
                except:
                    return {"raw_analysis": analysis}
            else:
                print(f"✗ OpenAI API error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return None
                
    except Exception as e:
        print(f"✗ OpenAI error: {str(e)}")
        return None


async def run_actual_pipeline():
    """Run the complete pipeline with real services"""
    print("=" * 80)
    print("LeadFactory ACTUAL Pipeline Execution")
    print("=" * 80)
    print(f"Business: {BUSINESS_NAME}")
    print(f"Website: {BUSINESS_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    
    results = {
        "business_id": BUSINESS_ID,
        "timestamp": datetime.now().isoformat(),
        "stages": {}
    }
    
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=120.0) as client:
        # 1. Run Assessment
        assessment_results = await trigger_assessment_with_screenshot(client)
        if assessment_results:
            results["assessment_results"] = assessment_results
            results["stages"]["assessment"] = "completed"
        else:
            results["stages"]["assessment"] = "failed"
    
    # 2. Capture Screenshot
    screenshot_data = await capture_screenshot_with_screenshotone(BUSINESS_URL)
    if screenshot_data:
        results["screenshot"] = screenshot_data
        results["stages"]["screenshot"] = "completed"
    else:
        results["stages"]["screenshot"] = "failed"
    
    # 3. Run Enrichment
    enrichment_data = await run_enrichment_coordinator()
    results.update(enrichment_data)
    results["stages"]["enrichment"] = "completed" if enrichment_data.get("enrichment_result") else "failed"
    
    # 4. AI Analysis
    ai_analysis = await analyze_with_openai(results)
    if ai_analysis:
        results["ai_analysis"] = ai_analysis
        results["stages"]["ai_analysis"] = "completed"
    else:
        results["stages"]["ai_analysis"] = "failed"
    
    # Summary
    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    
    for stage, status in results["stages"].items():
        icon = "✅" if status == "completed" else "❌"
        print(f"{icon} {stage.title()}: {status}")
    
    # Key Results
    if results.get("assessment_results", {}).get("pagespeed_results"):
        ps = results["assessment_results"]["pagespeed_results"]
        print(f"\n📊 PageSpeed Score: {ps.get('performance_score', 0)}/100")
    
    if results.get("enrichment_result"):
        er = results["enrichment_result"]
        print(f"📧 Email Found: {er.get('email', 'No')}")
        print(f"📞 Phone Found: {er.get('phone', 'No')}")
    
    if results.get("ai_analysis"):
        ai = results["ai_analysis"]
        if isinstance(ai, dict):
            print(f"🤖 Lead Score: {ai.get('lead_score', 'N/A')}")
        
    # Save results
    output_file = f"actual_pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 Full results saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    results = asyncio.run(run_actual_pipeline())