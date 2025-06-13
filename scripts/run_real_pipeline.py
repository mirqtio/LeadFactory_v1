#!/usr/bin/env python3
"""
Run the REAL pipeline with actual API calls
Shows actual results - no hiding failures
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

# Import our providers
from d0_gateway.providers.screenshotone import ScreenshotOneClient
from d0_gateway.providers.openai import OpenAIClient

# Test business
BUSINESS_ID = "07a80cdc-3c94-48df-9351-5ba097026806"
BUSINESS_URL = "https://investinyakima.com"
BUSINESS_NAME = "Yakima County Development Association"
BUSINESS_DATA = {
    "id": BUSINESS_ID,
    "name": BUSINESS_NAME,
    "website": BUSINESS_URL,
    "address": "10 North 9th Street",
    "city": "Yakima", 
    "state": "WA",
    "zip": "98901"
}


def print_section(title: str):
    """Print a section header"""
    print(f"\n{'=' * 80}")
    print(f"{title}")
    print(f"{'=' * 80}")


def print_result(label: str, success: bool, details: str = ""):
    """Print a result with clear success/failure indication"""
    icon = "✅" if success else "❌"
    status = "SUCCESS" if success else "FAILED"
    print(f"{icon} {label}: {status}")
    if details:
        print(f"   {details}")


async def test_assessment(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Test website assessment"""
    print_section("1. WEBSITE ASSESSMENT")
    
    try:
        # Trigger assessment
        assessment_data = {
            "business_id": BUSINESS_ID,
            "url": BUSINESS_URL,
            "business_name": BUSINESS_NAME,
            "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
            "industry": "nonprofit"
        }
        
        response = await client.post("/api/v1/assessments/trigger", json=assessment_data)
        
        if response.status_code in [200, 201, 202]:
            result = response.json()
            session_id = result.get("session_id")
            print_result("Assessment triggered", True, f"Session: {session_id}")
            
            # Wait for completion
            max_attempts = 30
            completed = False
            
            for attempt in range(max_attempts):
                await asyncio.sleep(5)
                
                status_response = await client.get(f"/api/v1/assessments/{session_id}/status")
                if status_response.status_code == 200:
                    status = status_response.json()
                    
                    if status.get("status") == "completed":
                        completed = True
                        print_result("Assessment completed", True)
                        
                        # Get results
                        results_response = await client.get(f"/api/v1/assessments/{session_id}/results")
                        if results_response.status_code == 200:
                            results = results_response.json()
                            
                            # Show actual results
                            if "pagespeed_results" in results:
                                ps = results["pagespeed_results"]
                                print(f"\n   PageSpeed Results:")
                                print(f"   - Performance Score: {ps.get('performance_score', 'N/A')}/100")
                                print(f"   - SEO Score: {ps.get('seo_score', 'N/A')}/100")
                                print(f"   - LCP: {ps.get('largest_contentful_paint', 'N/A')}ms")
                            
                            if "tech_stack_results" in results:
                                ts = results["tech_stack_results"]
                                print(f"\n   Tech Stack: {len(ts)} technologies detected")
                            
                            return results
                        else:
                            print_result("Get assessment results", False, 
                                       f"HTTP {results_response.status_code}: {results_response.text[:100]}")
                        break
                        
                    elif status.get("status") == "failed":
                        print_result("Assessment", False, "Status: failed")
                        break
            
            if not completed:
                print_result("Assessment completion", False, "Timeout after 2.5 minutes")
                
        else:
            print_result("Trigger assessment", False, 
                       f"HTTP {response.status_code}: {response.text[:200]}")
            
    except Exception as e:
        print_result("Assessment", False, f"Exception: {str(e)}")
        
    return {}


async def test_screenshot() -> Dict[str, Any]:
    """Test ScreenshotOne integration"""
    print_section("2. SCREENSHOT CAPTURE")
    
    api_key = os.getenv("SCREENSHOTONE_API_KEY")
    if not api_key:
        print_result("ScreenshotOne API key", False, "Not found in .env")
        return {}
    
    try:
        client = ScreenshotOneClient(api_key=api_key)
        
        # Capture screenshot
        print(f"   Capturing screenshot of {BUSINESS_URL}...")
        screenshot_data = await client.capture_screenshot(
            url=BUSINESS_URL,
            full_page=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        if screenshot_data:
            # Save screenshot
            filename = f"screenshot_{BUSINESS_ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(filename, "wb") as f:
                f.write(screenshot_data)
            
            print_result("Screenshot captured", True, 
                       f"Saved as {filename} ({len(screenshot_data)/1024:.1f} KB)")
            
            return {
                "screenshot_path": filename,
                "size_bytes": len(screenshot_data),
                "captured_at": datetime.now().isoformat()
            }
        else:
            print_result("Screenshot capture", False, "No data returned")
            
    except Exception as e:
        print_result("Screenshot capture", False, f"Exception: {str(e)}")
        
    return {}


async def test_enrichment(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Test enrichment API"""
    print_section("3. BUSINESS ENRICHMENT")
    
    try:
        # Call enrichment API
        enrichment_request = {
            "business_id": BUSINESS_ID,
            "business_data": BUSINESS_DATA,
            "sources": ["internal", "data_axle", "hunter_io"],
            "priority": "high",
            "skip_if_recent": False
        }
        
        response = await client.post("/api/v1/enrichment/enrich", json=enrichment_request)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("status") == "success":
                print_result("Enrichment", True, f"Source: {result.get('successful_source')}")
                
                data = result.get("enrichment_data", {})
                if data:
                    print("\n   Enriched Data Found:")
                    if data.get("email"):
                        print(f"   - Email: {data['email']}")
                    if data.get("phone"):
                        print(f"   - Phone: {data['phone']}")
                    if data.get("company_name"):
                        print(f"   - Company: {data['company_name']}")
                    if data.get("address"):
                        print(f"   - Address: {data['address']}")
                    
                    confidence = result.get("confidence_score", 0)
                    print(f"   - Confidence: {confidence:.2f}")
                else:
                    print("   No enrichment data returned")
                    
            else:
                print_result("Enrichment", False, f"Status: {result.get('status')}")
                print(f"   Sources attempted: {result.get('sources_attempted', [])}")
                
            return result
            
        else:
            print_result("Enrichment API", False, 
                       f"HTTP {response.status_code}: {response.text[:200]}")
            
    except Exception as e:
        print_result("Enrichment", False, f"Exception: {str(e)}")
        
    return {}


async def test_openai_analysis(all_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test OpenAI analysis"""
    print_section("4. AI ANALYSIS (OpenAI)")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print_result("OpenAI API key", False, "Not found in .env")
        return {}
    
    try:
        client = OpenAIClient(api_key=api_key)
        
        # Prepare analysis prompt
        messages = [
            {
                "role": "system",
                "content": "You are a lead qualification expert for a web development agency. Analyze business data and provide actionable insights in JSON format."
            },
            {
                "role": "user",
                "content": f"""
Analyze this business for lead qualification:

Business: {BUSINESS_NAME}
Website: {BUSINESS_URL}

Assessment Data:
{json.dumps(all_data.get('assessment', {}), indent=2)}

Enrichment Data:
{json.dumps(all_data.get('enrichment', {}), indent=2)}

Provide a JSON response with:
{{
    "lead_score": <0-100>,
    "opportunities": ["opportunity 1", "opportunity 2", "opportunity 3"],
    "estimated_value": "$X,XXX - $XX,XXX",
    "engagement_strategy": "...",
    "key_points": ["point 1", "point 2", "point 3"]
}}
"""
            }
        ]
        
        print("   Calling OpenAI GPT-4...")
        response = await client.chat_completion(
            messages=messages,
            model="gpt-4",
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        if response and "choices" in response:
            content = response["choices"][0]["message"]["content"]
            
            try:
                analysis = json.loads(content)
                print_result("AI Analysis", True)
                
                print("\n   Analysis Results:")
                print(f"   - Lead Score: {analysis.get('lead_score', 'N/A')}/100")
                print(f"   - Estimated Value: {analysis.get('estimated_value', 'N/A')}")
                print(f"   - Strategy: {analysis.get('engagement_strategy', 'N/A')[:100]}...")
                
                return analysis
                
            except json.JSONDecodeError:
                print_result("Parse AI response", False, "Invalid JSON")
                print(f"   Raw response: {content[:200]}...")
                
        else:
            print_result("OpenAI API call", False, "No response")
            
    except Exception as e:
        print_result("AI Analysis", False, f"Exception: {str(e)}")
        
    return {}


async def run_real_pipeline():
    """Run the complete pipeline with real results"""
    print("=" * 80)
    print("LEADFACTORY REAL PIPELINE EXECUTION")
    print("=" * 80)
    print(f"Business: {BUSINESS_NAME}")
    print(f"Website: {BUSINESS_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    
    all_results = {
        "business_id": BUSINESS_ID,
        "timestamp": datetime.now().isoformat(),
        "results": {}
    }
    
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=120.0) as client:
        # 1. Assessment
        assessment_results = await test_assessment(client)
        all_results["results"]["assessment"] = assessment_results
        
        # 2. Screenshot
        screenshot_results = await test_screenshot()
        all_results["results"]["screenshot"] = screenshot_results
        
        # 3. Enrichment
        enrichment_results = await test_enrichment(client)
        all_results["results"]["enrichment"] = enrichment_results
        
        # 4. AI Analysis
        ai_results = await test_openai_analysis({
            "assessment": assessment_results,
            "enrichment": enrichment_results
        })
        all_results["results"]["ai_analysis"] = ai_results
    
    # Final Summary
    print_section("PIPELINE SUMMARY")
    
    # Count successes
    successes = 0
    total = 4
    
    if all_results["results"]["assessment"]:
        successes += 1
    if all_results["results"]["screenshot"]:
        successes += 1
    if all_results["results"]["enrichment"] and all_results["results"]["enrichment"].get("status") == "success":
        successes += 1
    if all_results["results"]["ai_analysis"]:
        successes += 1
    
    print(f"\nSuccess Rate: {successes}/{total} ({successes/total*100:.0f}%)")
    
    # Save full results
    output_file = f"real_pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    return all_results


if __name__ == "__main__":
    results = asyncio.run(run_real_pipeline())