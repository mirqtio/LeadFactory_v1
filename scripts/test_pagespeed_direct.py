#!/usr/bin/env python3
"""
Direct test of PageSpeed API to debug 400 errors
"""
import os
import asyncio
from d0_gateway.providers.pagespeed import PageSpeedClient
import json

async def test_pagespeed():
    """Test PageSpeed API directly"""
    client = PageSpeedClient()
    
    print(f"API Key: {client.api_key[:10]}...")
    print(f"Base URL: {client.base_url}")
    
    # Test direct HTTP request first
    import httpx
    
    url = "https://www.example.com"
    api_key = client.api_key
    
    print(f"\nMaking direct request to PageSpeed API...")
    print(f"URL to analyze: {url}")
    
    # Try with multiple category params
    base_params = {
        "url": url,
        "strategy": "mobile", 
        "key": api_key
    }
    
    # Test 1: No categories (default)
    print("\nTest 1: No category parameter")
    params = base_params.copy()
    
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params=params,
                timeout=60.0
            )
            
            print(f"\nResponse status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\nSuccess! Response keys:")
                print(json.dumps(list(data.keys()), indent=2))
                
                if "lighthouseResult" in data:
                    scores = data["lighthouseResult"].get("categories", {})
                    print("\nScores:")
                    for category, score_data in scores.items():
                        score = score_data.get('score')
                        if score is not None:
                            print(f"  {category}: {score * 100:.0f}")
                        else:
                            print(f"  {category}: N/A")
            else:
                print(f"Error response: {response.text}")
                
    except Exception as e:
        print(f"\nDirect request error: {type(e).__name__}: {e}")
    
    # Test 2: With category parameters using list of tuples
    print("\n\nTest 2: With category parameters")
    try:
        async with httpx.AsyncClient() as http_client:
            # httpx accepts params as list of tuples for multiple values with same key
            response = await http_client.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params=[
                    ("url", url),
                    ("strategy", "mobile"),
                    ("key", api_key),
                    ("category", "PERFORMANCE"),
                    ("category", "ACCESSIBILITY"), 
                    ("category", "BEST_PRACTICES"),
                    ("category", "SEO")
                ],
                timeout=60.0
            )
            
            print(f"\nResponse status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "lighthouseResult" in data:
                    scores = data["lighthouseResult"].get("categories", {})
                    print("\nScores with categories:")
                    for category, score_data in scores.items():
                        score = score_data.get('score')
                        if score is not None:
                            print(f"  {category}: {score * 100:.0f}")
            else:
                print(f"Error: {response.text[:200]}")
                
    except Exception as e:
        print(f"\nTest 2 error: {type(e).__name__}: {e}")
    
    # Now test through the client
    print("\n\nTesting through PageSpeedClient...")
    try:
        result = await client.analyze_url(
            url="https://www.example.com",
            strategy="mobile"
        )
        
        print("\nClient Success! Response keys:")
        print(json.dumps(list(result.keys()), indent=2))
                
    except Exception as e:
        print(f"\nClient Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_pagespeed())