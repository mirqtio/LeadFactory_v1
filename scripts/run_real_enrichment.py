#!/usr/bin/env python3
"""
Run REAL enrichment using actual API services
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import configs
from core.config import settings
from core.logging import get_logger

# Import enrichers
from d4_enrichment.dataaxle_enricher import DataAxleEnricher
from d4_enrichment.hunter_enricher import HunterEnricher
from d4_enrichment.gbp_enricher import GBPEnricher

# Import API clients with proper initialization
from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient

logger = get_logger(__name__)

# Test business data
BUSINESS_DATA = {
    "business_id": "07a80cdc-3c94-48df-9351-5ba097026806",
    "name": "Yakima County Development Association",
    "website": "investinyakima.com",  # Domain only for Hunter
    "address": "10 North 9th Street",
    "city": "Yakima",
    "state": "WA",
    "zip": "98901",
    "url": "https://investinyakima.com"
}


async def test_real_dataaxle():
    """Test real Data Axle API"""
    print("\n📧 Testing REAL Data Axle API...")
    
    try:
        # Get API key from environment
        api_key = os.getenv("DATA_AXLE_API_KEY") or os.getenv("DATAAXLE_API_KEY")
        if not api_key:
            print("  ✗ No Data Axle API key found in environment")
            return None
            
        print(f"  → Using API key: {api_key[:10]}...")
        
        # Initialize client properly
        client = DataAxleClient(api_key=api_key)
        enricher = DataAxleEnricher(client=client)
        
        # Try to enrich
        result = await enricher.enrich_business(
            BUSINESS_DATA,
            BUSINESS_DATA["business_id"]
        )
        
        if result:
            print(f"  ✓ Data Axle match found!")
            print(f"    Email: {result.email}")
            print(f"    Phone: {result.phone}")
            print(f"    Confidence: {result.confidence_score:.0%}")
            return {
                "email": result.email,
                "phone": result.phone,
                "contact_name": result.contact_name,
                "confidence": result.confidence_score
            }
        else:
            print("  ✗ No Data Axle match found")
            return None
            
    except Exception as e:
        print(f"  ✗ Data Axle error: {str(e)}")
        logger.exception("Data Axle enrichment failed")
        return None


async def test_real_hunter():
    """Test real Hunter.io API"""
    print("\n🎯 Testing REAL Hunter.io API...")
    
    try:
        # Get API key
        api_key = os.getenv("HUNTER_API_KEY")
        if not api_key:
            print("  ✗ No Hunter API key found in environment")
            return None
            
        print(f"  → Using API key: {api_key[:10]}...")
        
        # Initialize client
        client = HunterClient(api_key=api_key)
        enricher = HunterEnricher(client=client)
        
        # Try to find emails
        result = await enricher.enrich_business(
            BUSINESS_DATA,
            BUSINESS_DATA["business_id"]
        )
        
        if result:
            print(f"  ✓ Hunter.io email found!")
            print(f"    Email: {result.email}")
            print(f"    Confidence: {result.confidence_score:.0%}")
            return {
                "email": result.email,
                "confidence": result.confidence_score
            }
        else:
            print("  ✗ No Hunter.io emails found")
            return None
            
    except Exception as e:
        print(f"  ✗ Hunter.io error: {str(e)}")
        logger.exception("Hunter enrichment failed")
        return None


async def test_real_gbp():
    """Test real Google Business Profile"""
    print("\n🗺️  Testing REAL Google Business Profile API...")
    
    try:
        # GBP uses Google API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("  ✗ No Google API key found")
            return None
            
        print(f"  → Using Google API key: {api_key[:10]}...")
        
        # Initialize GBP enricher (doesn't take use_mock param)
        enricher = GBPEnricher()
        
        # Search for business
        results = await enricher.search_business(
            name=BUSINESS_DATA["name"],
            address=BUSINESS_DATA["address"],
            city=BUSINESS_DATA["city"],
            state=BUSINESS_DATA["state"]
        )
        
        if results:
            print(f"  ✓ Found {len(results)} GBP matches!")
            best_match = results[0]
            print(f"    Name: {best_match.name}")
            print(f"    Address: {best_match.formatted_address}")
            print(f"    Phone: {best_match.phone_number}")
            print(f"    Rating: {best_match.rating}")
            return best_match.to_dict()
        else:
            print("  ✗ No GBP matches found")
            return None
            
    except Exception as e:
        print(f"  ✗ GBP error: {str(e)}")
        logger.exception("GBP enrichment failed")
        return None


async def test_openai_analysis(data: Dict[str, Any]):
    """Test real OpenAI GPT-4 analysis"""
    print("\n🤖 Testing REAL ChatGPT 4o API...")
    
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("  ✗ No OpenAI API key found")
            return None
            
        print(f"  → Using OpenAI API key: {api_key[:20]}...")
        
        # Import OpenAI
        import openai
        openai.api_key = api_key
        
        # Prepare prompt with all our data
        prompt = f"""
        Analyze this business for lead generation potential:
        
        Business: {BUSINESS_DATA['name']}
        Website: {BUSINESS_DATA['url']}
        
        Assessment Results:
        - PageSpeed Performance: 53/100
        - Mobile Friendly: Yes
        - Largest Contentful Paint: 8.5 seconds
        - Tech Stack: WordPress on WP Engine
        
        Enrichment Data:
        {json.dumps(data, indent=2)}
        
        Provide:
        1. Lead score (0-100)
        2. Key opportunities for improvement
        3. Personalized engagement strategy
        4. Estimated project value
        """
        
        # Make actual API call
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a lead qualification expert for a web development agency."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        analysis = response.choices[0].message.content
        print("  ✓ Real GPT-4 analysis complete!")
        print(f"\nAnalysis Preview:\n{analysis[:200]}...")
        
        return {"gpt4_analysis": analysis}
        
    except Exception as e:
        print(f"  ✗ OpenAI error: {str(e)}")
        logger.exception("OpenAI analysis failed")
        return None


async def capture_real_screenshot():
    """Check if we can capture real screenshots"""
    print("\n📸 Checking for REAL screenshot capability...")
    
    # Check if Playwright is available
    try:
        from playwright.async_api import async_playwright
        
        print("  ✓ Playwright is available!")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            print(f"  → Navigating to {BUSINESS_DATA['url']}...")
            await page.goto(BUSINESS_DATA['url'])
            
            # Take screenshot
            screenshot_path = f"screenshot_{BUSINESS_DATA['business_id']}.png"
            await page.screenshot(path=screenshot_path)
            
            # Get page info
            title = await page.title()
            
            await browser.close()
            
            print(f"  ✓ Real screenshot captured!")
            print(f"    Title: {title}")
            print(f"    Saved to: {screenshot_path}")
            
            return {
                "screenshot_path": screenshot_path,
                "page_title": title,
                "captured_at": datetime.now().isoformat()
            }
            
    except ImportError:
        print("  ✗ Playwright not installed (pip install playwright)")
        print("    Run: playwright install chromium")
        return None
    except Exception as e:
        print(f"  ✗ Screenshot error: {str(e)}")
        return None


async def run_real_enrichment():
    """Run enrichment with REAL API calls"""
    print("=" * 80)
    print("LeadFactory REAL Enrichment Test")
    print("=" * 80)
    print(f"Business: {BUSINESS_DATA['name']}")
    print(f"Website: {BUSINESS_DATA['url']}")
    print(f"Time: {datetime.now().isoformat()}")
    
    results = {}
    
    # 1. Real Screenshot
    screenshot = await capture_real_screenshot()
    if screenshot:
        results["screenshot"] = screenshot
    
    # 2. Real GBP
    gbp_data = await test_real_gbp()
    if gbp_data:
        results["google_business_profile"] = gbp_data
    
    # 3. Real Data Axle
    dataaxle = await test_real_dataaxle()
    if dataaxle:
        results["data_axle"] = dataaxle
    
    # 4. Real Hunter.io
    if not dataaxle or not dataaxle.get("email"):
        hunter = await test_real_hunter()
        if hunter:
            results["hunter_io"] = hunter
    
    # 5. Real GPT-4 Analysis
    gpt_analysis = await test_openai_analysis(results)
    if gpt_analysis:
        results["ai_analysis"] = gpt_analysis
    
    # Summary
    print("\n" + "=" * 80)
    print("REAL ENRICHMENT SUMMARY")
    print("=" * 80)
    
    print(f"{'✅' if results.get('screenshot') else '❌'} Real screenshot captured")
    print(f"{'✅' if results.get('google_business_profile') else '❌'} Real GBP data retrieved")
    print(f"{'✅' if results.get('data_axle') else '❌'} Real Data Axle match")
    print(f"{'✅' if results.get('hunter_io') else '❌'} Real Hunter.io email")
    print(f"{'✅' if results.get('ai_analysis') else '❌'} Real GPT-4 analysis")
    
    # Save results
    output_file = f"real_enrichment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 Results saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    results = asyncio.run(run_real_enrichment())