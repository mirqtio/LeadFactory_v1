#!/usr/bin/env python3
"""
API Integration Smoke Test
Tests real data flow through the API endpoints
"""
import asyncio
import httpx
import json
import sys
import os
from datetime import datetime
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 30.0

# Test business for API
TEST_BUSINESS = {
    "name": f"SMOKE TEST Auto Shop {datetime.now().strftime('%H%M')}",
    "yelp_id": f"smoke-api-test-{int(time.time())}",
    "phone": "+15125551234",
    "email": "smoketest@example.com",
    "address": "123 Test St",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78701",
    "website": "https://www.example.com",
    "categories": ["autorepair"],
    "vertical": "auto_repair"
}


async def test_api_integration():
    """Test full API integration with real data"""
    print("API Integration Smoke Test")
    print("=" * 60)
    print(f"Testing against: {API_BASE_URL}")
    print()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "created_data": []
    }
    
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=TIMEOUT) as client:
        
        # 1. Test Campaign Creation
        print("1. Testing Campaign Creation...")
        try:
            campaign_data = {
                "name": f"Smoke Test Campaign {datetime.now().strftime('%Y%m%d_%H%M')}",
                "vertical": "auto_repair",
                "geo_targets": ["Austin, TX"],
                "daily_quota": 10,
                "status": "active"
            }
            
            response = await client.post("/api/v1/campaigns", json=campaign_data)
            if response.status_code == 201:
                campaign = response.json()
                results["tests"]["campaign_creation"] = {
                    "status": "PASS",
                    "campaign_id": campaign["id"]
                }
                results["created_data"].append(("campaign", campaign["id"]))
                print(f"  ✓ Created campaign: {campaign['id']}")
            else:
                results["tests"]["campaign_creation"] = {
                    "status": "FAIL",
                    "error": f"Status {response.status_code}: {response.text}"
                }
                print(f"  ✗ Failed: {response.status_code}")
        except Exception as e:
            results["tests"]["campaign_creation"] = {"status": "FAIL", "error": str(e)}
            print(f"  ✗ Error: {str(e)}")
            
        # 2. Test Target Search
        print("\n2. Testing Target Search...")
        try:
            search_data = {
                "location": "Austin, TX",
                "categories": ["autorepair"],
                "radius": 10000,
                "limit": 5
            }
            
            response = await client.post("/api/v1/targets/search", json=search_data)
            if response.status_code == 200:
                targets = response.json()
                results["tests"]["target_search"] = {
                    "status": "PASS",
                    "targets_found": len(targets.get("businesses", []))
                }
                print(f"  ✓ Found {len(targets.get('businesses', []))} targets")
                
                # Save first target for assessment
                if targets.get("businesses"):
                    first_target = targets["businesses"][0]
                    results["first_target"] = first_target
            else:
                results["tests"]["target_search"] = {
                    "status": "FAIL",
                    "error": f"Status {response.status_code}"
                }
                print(f"  ✗ Failed: {response.status_code}")
        except Exception as e:
            results["tests"]["target_search"] = {"status": "FAIL", "error": str(e)}
            print(f"  ✗ Error: {str(e)}")
            
        # 3. Test Assessment
        print("\n3. Testing Website Assessment...")
        try:
            # Use Google as a test website
            assessment_data = {
                "business_id": TEST_BUSINESS["yelp_id"],
                "business_name": TEST_BUSINESS["name"],
                "website_url": "https://www.google.com",
                "categories": ["autorepair"]
            }
            
            response = await client.post("/api/v1/assessments/analyze", json=assessment_data)
            if response.status_code in [200, 201]:
                assessment = response.json()
                results["tests"]["assessment"] = {
                    "status": "PASS",
                    "assessment_id": assessment.get("id"),
                    "issues_found": assessment.get("total_issues", 0)
                }
                print(f"  ✓ Assessment complete: {assessment.get('total_issues', 0)} issues")
            else:
                results["tests"]["assessment"] = {
                    "status": "FAIL",
                    "error": f"Status {response.status_code}"
                }
                print(f"  ✗ Failed: {response.status_code}")
        except Exception as e:
            results["tests"]["assessment"] = {"status": "FAIL", "error": str(e)}
            print(f"  ✗ Error: {str(e)}")
            
        # 4. Test Analytics
        print("\n4. Testing Analytics API...")
        try:
            response = await client.get("/api/v1/analytics/overview")
            if response.status_code in [200, 404]:  # 404 OK if no data
                results["tests"]["analytics"] = {
                    "status": "PASS",
                    "has_data": response.status_code == 200
                }
                print(f"  ✓ Analytics API working")
            else:
                results["tests"]["analytics"] = {
                    "status": "FAIL",
                    "error": f"Status {response.status_code}"
                }
                print(f"  ✗ Failed: {response.status_code}")
        except Exception as e:
            results["tests"]["analytics"] = {"status": "FAIL", "error": str(e)}
            print(f"  ✗ Error: {str(e)}")
            
        # 5. Test Storefront
        print("\n5. Testing Storefront API...")
        try:
            response = await client.get("/api/v1/storefront/products")
            if response.status_code == 200:
                products = response.json()
                results["tests"]["storefront"] = {
                    "status": "PASS",
                    "products_count": len(products)
                }
                print(f"  ✓ Found {len(products)} products")
            else:
                results["tests"]["storefront"] = {
                    "status": "FAIL",
                    "error": f"Status {response.status_code}"
                }
                print(f"  ✗ Failed: {response.status_code}")
        except Exception as e:
            results["tests"]["storefront"] = {"status": "FAIL", "error": str(e)}
            print(f"  ✗ Error: {str(e)}")
            
        # 6. Test Datadog Metrics
        print("\n6. Testing Datadog Integration...")
        api_key = os.getenv("DATADOG_API_KEY")
        app_key = os.getenv("DATADOG_APP_KEY")
        
        if api_key and app_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as dd_client:
                    now = int(datetime.now().timestamp())
                    hour_ago = now - 3600
                    
                    response = await dd_client.get(
                        "https://api.us5.datadoghq.com/api/v1/query",
                        headers={
                            "DD-API-KEY": api_key,
                            "DD-APPLICATION-KEY": app_key
                        },
                        params={
                            "from": hour_ago,
                            "to": now,
                            "query": "avg:system.cpu.user{*}"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        series = data.get("series", [])
                        results["tests"]["datadog"] = {
                            "status": "PASS",
                            "series_found": len(series),
                            "datapoints": len(series[0]["pointlist"]) if series else 0
                        }
                        print(f"  ✓ Datadog working: {len(series)} series found")
                    else:
                        results["tests"]["datadog"] = {
                            "status": "FAIL",
                            "error": f"API returned {response.status_code}"
                        }
                        print(f"  ✗ Datadog API error: {response.status_code}")
                        
            except Exception as e:
                results["tests"]["datadog"] = {"status": "FAIL", "error": str(e)}
                print(f"  ✗ Error: {str(e)}")
        else:
            results["tests"]["datadog"] = {
                "status": "SKIP",
                "reason": "API keys not configured"
            }
            print("  ⚠ Skipped: No API keys")
            
        # 7. Cleanup (if needed)
        print("\n7. Cleanup...")
        for entity_type, entity_id in results.get("created_data", []):
            if entity_type == "campaign":
                try:
                    await client.delete(f"/api/v1/campaigns/{entity_id}")
                    print(f"  ✓ Deleted campaign {entity_id}")
                except:
                    print(f"  ⚠ Could not delete campaign {entity_id}")
                    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for t in results["tests"].values() if t.get("status") == "PASS")
    failed = sum(1 for t in results["tests"].values() if t.get("status") == "FAIL")
    skipped = sum(1 for t in results["tests"].values() if t.get("status") == "SKIP")
    
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    
    all_passed = failed == 0
    print(f"\nResult: {'✅ PASS' if all_passed else '❌ FAIL'}")
    
    # Save results
    with open("api_integration_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
        
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_api_integration())
    sys.exit(exit_code)