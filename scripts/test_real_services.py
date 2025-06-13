#!/usr/bin/env python3
"""
Test each service individually to show real results
"""
import asyncio
import os
import json
from datetime import datetime

# Add project root to path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

# Import our providers directly
from d0_gateway.providers.screenshotone import ScreenshotOneClient
from d0_gateway.providers.google_places import GooglePlacesClient
from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient
from d0_gateway.providers.openai import OpenAIClient

# Test business
BUSINESS_NAME = "Yakima County Development Association"
BUSINESS_URL = "https://investinyakima.com"
BUSINESS_ADDRESS = "10 North 9th Street, Yakima, WA 98901"


async def test_screenshotone():
    """Test ScreenshotOne API"""
    print("\n1. TESTING SCREENSHOTONE")
    print("-" * 50)
    
    api_key = os.getenv("SCREENSHOTONE_API_KEY")
    if not api_key:
        print("❌ NO API KEY FOUND")
        return
    
    print(f"✓ API Key: {api_key[:10]}...")
    
    try:
        client = ScreenshotOneClient(api_key=api_key)
        print(f"  Capturing {BUSINESS_URL}...")
        
        screenshot_data = await client.capture_screenshot(
            url=BUSINESS_URL,
            full_page=False,  # Just viewport for speed
            viewport_width=1920,
            viewport_height=1080
        )
        
        if screenshot_data:
            filename = f"test_screenshot_{datetime.now().strftime('%H%M%S')}.png"
            with open(filename, "wb") as f:
                f.write(screenshot_data)
            print(f"✅ SUCCESS: Screenshot saved as {filename} ({len(screenshot_data)/1024:.1f} KB)")
        else:
            print("❌ FAILED: No screenshot data returned")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")


async def test_google_places():
    """Test Google Places API"""
    print("\n2. TESTING GOOGLE PLACES")
    print("-" * 50)
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ NO API KEY FOUND")
        return
    
    print(f"✓ API Key: {api_key[:10]}...")
    
    try:
        client = GooglePlacesClient(api_key=api_key)
        print(f"  Searching for: {BUSINESS_NAME}")
        
        # Search for business
        results = await client.search_businesses(
            query=f"{BUSINESS_NAME} Yakima WA"
        )
        
        if results:
            print(f"✅ SUCCESS: Found {len(results)} results")
            for i, place in enumerate(results[:3]):
                print(f"\n  Result {i+1}:")
                print(f"    Name: {place.get('name')}")
                print(f"    Address: {place.get('formatted_address')}")
                print(f"    Place ID: {place.get('place_id')}")
                print(f"    Types: {', '.join(place.get('types', [])[:3])}")
        else:
            print("❌ NO RESULTS FOUND")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")


async def test_dataaxle():
    """Test Data Axle API"""
    print("\n3. TESTING DATA AXLE")
    print("-" * 50)
    
    api_key = os.getenv("DATA_AXLE_API_KEY") or os.getenv("DATAAXLE_API_KEY")
    if not api_key:
        print("❌ NO API KEY FOUND")
        return
    
    print(f"✓ API Key: {api_key[:10]}...")
    
    try:
        client = DataAxleClient(api_key=api_key)
        print(f"  Matching business: {BUSINESS_NAME}")
        
        # Try to match business
        result = await client.match_business({
            "name": BUSINESS_NAME,
            "city": "Yakima",
            "state": "WA",
            "zip": "98901"
        })
        
        if result and result.get("data"):
            print("✅ SUCCESS: Business match found")
            data = result.get("data", {})
            print(f"    Confidence: {result.get('confidence', 0):.2f}")
            print(f"    Email: {data.get('email', 'NOT FOUND')}")
            print(f"    Phone: {data.get('phone', 'NOT FOUND')}")
            print(f"    Website: {data.get('website', 'NOT FOUND')}")
        else:
            print("❌ NO MATCH FOUND")
            if result:
                print(f"    Response: {json.dumps(result, indent=2)}")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")


async def test_hunter():
    """Test Hunter.io API"""
    print("\n4. TESTING HUNTER.IO")
    print("-" * 50)
    
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        print("❌ NO API KEY FOUND")
        return
    
    print(f"✓ API Key: {api_key[:10]}...")
    
    try:
        client = HunterClient(api_key=api_key)
        domain = "investinyakima.com"
        print(f"  Finding emails for: {domain}")
        
        # Find emails
        result = await client.find_email({
            "domain": domain,
            "company_name": BUSINESS_NAME
        })
        
        if result and result.get("emails"):
            print("✅ SUCCESS: Emails found")
            for email in result.get("emails", [])[:5]:
                print(f"    Email: {email.get('value')}")
                print(f"    Confidence: {email.get('confidence')}%")
                print(f"    Type: {email.get('type')}")
                print()
        else:
            print("❌ NO EMAILS FOUND")
            if result:
                print(f"    Response: {json.dumps(result, indent=2)}")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")


async def test_openai():
    """Test OpenAI API"""
    print("\n5. TESTING OPENAI")
    print("-" * 50)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ NO API KEY FOUND")
        return
    
    print(f"✓ API Key: {api_key[:20]}...")
    
    try:
        client = OpenAIClient(api_key=api_key)
        print("  Making test completion...")
        
        response = await client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'API is working!' in exactly 3 words."}
            ],
            model="gpt-3.5-turbo",  # Cheaper for testing
            temperature=0
        )
        
        if response and "choices" in response:
            content = response["choices"][0]["message"]["content"]
            print(f"✅ SUCCESS: {content}")
            usage = response.get("usage", {})
            print(f"    Tokens used: {usage.get('total_tokens', 'N/A')}")
        else:
            print("❌ NO RESPONSE")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("TESTING REAL API SERVICES")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    
    # Test each service
    await test_screenshotone()
    await test_google_places()
    await test_dataaxle()
    await test_hunter()
    await test_openai()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())