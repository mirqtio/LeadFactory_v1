#!/usr/bin/env python3
"""
Run assessments on test URLs to generate reports
"""
import asyncio
import json
from datetime import datetime
import httpx
from typing import Dict, Any

# Test URLs to assess - updated with realistic business info for GBP lookups
TEST_URLS = [
    {
        "business_id": "test_001",
        "business_name": "Yakima Valley Dental",
        "url": "https://yakimavalleydental.com",
        "vertical": "healthcare",
        "location": "Yakima, WA",
        "address": "5811 Summitview Ave"
    },
    {
        "business_id": "test_002", 
        "business_name": "Northtown Coffee",
        "url": "https://www.northtowncoffeehouse.com",
        "vertical": "retail",
        "location": "Yakima, WA",
        "address": "32 N Front St"
    },
    {
        "business_id": "test_003",
        "business_name": "Bob's Kustom City",
        "url": "https://bobskustomcity.com",
        "vertical": "retail",
        "location": "Yakima, WA",
        "address": "802 S 1st St"
    },
    {
        "business_id": "test_004",
        "business_name": "Essencia Artisan Bakery",
        "url": "https://essenciaartisanbakery.com",
        "vertical": "retail",
        "location": "Yakima, WA",
        "address": "4 N 3rd St"
    },
    {
        "business_id": "test_005",
        "business_name": "The Seasons Performance Hall",
        "url": "https://www.theseasonsperformancehall.com",
        "vertical": "arts",
        "location": "Yakima, WA",
        "address": "101 N Naches Ave"
    },
    {
        "business_id": "test_006",
        "business_name": "Yakima Chief Hops",
        "url": "https://www.yakimachief.com",
        "vertical": "other",
        "location": "Yakima, WA",
        "address": "306 Division St"
    },
    {
        "business_id": "test_007",
        "business_name": "Living Hope Church",
        "url": "https://www.livinghopeyakima.com",
        "vertical": "nonprofit",
        "location": "Yakima, WA",
        "address": "508 N 35th Ave"
    },
    {
        "business_id": "test_008",
        "business_name": "Chase Bank",
        "url": "https://www.chase.com",
        "vertical": "finance",
        "location": "Yakima, WA",
        "address": "430 W Yakima Ave"
    },
    {
        "business_id": "test_009",
        "business_name": "Selah Schools", 
        "url": "https://www.selahschools.org",
        "vertical": "nonprofit",
        "location": "Selah, WA",
        "address": "801 N 1st St"
    }
]

# API configuration
API_BASE_URL = "http://localhost:8000"
ASSESSMENT_ENDPOINT = f"{API_BASE_URL}/api/v1/assessments/trigger"
STATUS_ENDPOINT = f"{API_BASE_URL}/api/v1/assessments"


async def trigger_assessment(client: httpx.AsyncClient, business: Dict[str, Any]) -> str:
    """Trigger assessment for a business URL"""
    print(f"\n📊 Triggering assessment for {business['business_name']}...")
    
    payload = {
        "business_id": business["business_id"],
        "url": business["url"],
        "assessment_types": ["pagespeed", "tech_stack", "ai_insights", "business_info"],
        "industry": business["vertical"],
        "session_config": {
            "business_name": business["business_name"],
            "location": business["location"]
        },
        "business_data": {
            "business_id": business["business_id"],
            "name": business["business_name"],
            "website": business["url"],
            "address": business.get("address", ""),
            "city": business["location"].split(",")[0].strip(),
            "state": business["location"].split(",")[1].strip() if "," in business["location"] else ""
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


async def save_results(session_id: str, business: Dict[str, Any], results: Dict[str, Any]):
    """Save assessment results to file"""
    filename = f"assessment_{business['business_id']}_{session_id}.json"
    
    output = {
        "session_id": session_id,
        "business": business,
        "results": results,
        "generated_at": datetime.utcnow().isoformat()
    }
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"💾 Results saved to {filename}")


async def main():
    """Run assessments for all test URLs"""
    print("🚀 Starting LeadFactory Assessment Tests")
    print(f"📍 API URL: {API_BASE_URL}")
    print(f"🔗 Testing {len(TEST_URLS)} URLs")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
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
        
        # Trigger assessments for all URLs
        sessions = []
        for business in TEST_URLS:
            session_id = await trigger_assessment(client, business)
            if session_id:
                sessions.append((session_id, business))
        
        if not sessions:
            print("❌ No assessments were triggered successfully")
            return
        
        # Wait for all assessments to complete
        print(f"\n⏳ Waiting for {len(sessions)} assessments to complete...")
        completed = []
        
        for session_id, business in sessions:
            if await wait_for_completion(client, session_id, business["business_name"]):
                completed.append((session_id, business))
        
        # Get and save results
        print(f"\n📥 Retrieving results for {len(completed)} completed assessments...")
        
        for session_id, business in completed:
            try:
                results = await get_assessment_results(client, session_id)
                await save_results(session_id, business, results)
                
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
                print(f"❌ Failed to get results for {business['business_name']}: {e}")
    
    print("\n✅ Assessment test completed!")
    print("📁 Check the generated JSON files for detailed results")


if __name__ == "__main__":
    asyncio.run(main())