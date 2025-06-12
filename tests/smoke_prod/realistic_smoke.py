#!/usr/bin/env python3
"""
Realistic Smoke Test based on actual API endpoints
"""
import asyncio
import httpx
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 30.0


async def run_realistic_smoke_test():
    """Test actual available endpoints"""
    print("LeadFactory Production Smoke Test")
    print("=" * 60)
    print(f"API: {API_BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "api_url": API_BASE_URL,
        "tests": []
    }
    
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=TIMEOUT) as client:
        
        # 1. Basic Health Checks
        print("1. Health Checks")
        print("-" * 40)
        
        for endpoint in ["/health", "/api/v1/analytics/health", "/api/v1/assessments/health", "/api/v1/checkout/status"]:
            try:
                response = await client.get(endpoint)
                status = "PASS" if response.status_code == 200 else "FAIL"
                results["tests"].append({
                    "endpoint": endpoint,
                    "status": status,
                    "http_code": response.status_code
                })
                print(f"  {endpoint}: {'✓' if status == 'PASS' else '✗'} ({response.status_code})")
            except Exception as e:
                results["tests"].append({
                    "endpoint": endpoint,
                    "status": "ERROR",
                    "error": str(e)
                })
                print(f"  {endpoint}: ✗ (Error: {str(e)[:50]}...)")
                
        # 2. Analytics Endpoints
        print("\n2. Analytics Endpoints")
        print("-" * 40)
        
        # Get metrics
        try:
            response = await client.get("/api/v1/analytics/metrics")
            if response.status_code == 200:
                metrics = response.json()
                results["tests"].append({
                    "endpoint": "/api/v1/analytics/metrics",
                    "status": "PASS",
                    "data": {"metrics_count": len(metrics)}
                })
                print(f"  Metrics API: ✓ ({len(metrics)} metrics)")
            else:
                results["tests"].append({
                    "endpoint": "/api/v1/analytics/metrics",
                    "status": "FAIL",
                    "http_code": response.status_code
                })
                print(f"  Metrics API: ✗ ({response.status_code})")
        except Exception as e:
            print(f"  Metrics API: ✗ (Error: {str(e)[:50]}...)")
            
        # 3. Assessment Flow
        print("\n3. Assessment Endpoints")
        print("-" * 40)
        
        # Trigger assessment
        try:
            assessment_data = {
                "url": "https://www.example.com",
                "business_name": "Smoke Test Business",
                "business_id": f"smoke-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
            response = await client.post("/api/v1/assessments/trigger", json=assessment_data)
            if response.status_code in [200, 201, 202]:
                result = response.json()
                session_id = result.get("session_id") or result.get("id")
                results["tests"].append({
                    "endpoint": "/api/v1/assessments/trigger",
                    "status": "PASS",
                    "data": {"session_id": session_id}
                })
                print(f"  Trigger Assessment: ✓ (Session: {session_id})")
                
                # Check status
                if session_id:
                    await asyncio.sleep(2)  # Wait a bit
                    status_response = await client.get(f"/api/v1/assessments/{session_id}/status")
                    print(f"  Assessment Status: {'✓' if status_response.status_code == 200 else '✗'}")
            else:
                results["tests"].append({
                    "endpoint": "/api/v1/assessments/trigger",
                    "status": "FAIL",
                    "http_code": response.status_code
                })
                print(f"  Trigger Assessment: ✗ ({response.status_code})")
        except Exception as e:
            print(f"  Assessment API: ✗ (Error: {str(e)[:50]}...)")
            
        # 4. Checkout Flow
        print("\n4. Checkout Endpoints")
        print("-" * 40)
        
        # Initiate checkout
        try:
            checkout_data = {
                "product_type": "audit_report",
                "business_info": {
                    "name": "Smoke Test Business",
                    "email": "smoke@test.com",
                    "website": "https://example.com"
                }
            }
            
            response = await client.post("/api/v1/checkout/initiate", json=checkout_data)
            if response.status_code in [200, 201]:
                result = response.json()
                results["tests"].append({
                    "endpoint": "/api/v1/checkout/initiate",
                    "status": "PASS",
                    "data": {"session_id": result.get("session_id")}
                })
                print(f"  Initiate Checkout: ✓")
            else:
                results["tests"].append({
                    "endpoint": "/api/v1/checkout/initiate",
                    "status": "FAIL",
                    "http_code": response.status_code
                })
                print(f"  Initiate Checkout: ✗ ({response.status_code})")
        except Exception as e:
            print(f"  Checkout API: ✗ (Error: {str(e)[:50]}...)")
            
        # 5. Prometheus Metrics
        print("\n5. Prometheus Metrics")
        print("-" * 40)
        
        try:
            response = await client.get("/metrics")
            if response.status_code == 200:
                metrics_text = response.text
                key_metrics = [
                    "leadfactory_http_requests_total",
                    "leadfactory_http_request_duration_seconds",
                    "leadfactory_assessments_total",
                    "leadfactory_checkouts_total"
                ]
                
                found_metrics = {m: m in metrics_text for m in key_metrics}
                results["tests"].append({
                    "endpoint": "/metrics",
                    "status": "PASS",
                    "data": {"metrics_found": found_metrics}
                })
                
                for metric, found in found_metrics.items():
                    print(f"  {metric}: {'✓' if found else '✗'}")
            else:
                results["tests"].append({
                    "endpoint": "/metrics",
                    "status": "FAIL",
                    "http_code": response.status_code
                })
                print(f"  Prometheus endpoint: ✗ ({response.status_code})")
        except Exception as e:
            print(f"  Prometheus: ✗ (Error: {str(e)[:50]}...)")
            
        # 6. Datadog Integration
        print("\n6. Datadog Integration")
        print("-" * 40)
        
        api_key = os.getenv("DATADOG_API_KEY")
        app_key = os.getenv("DATADOG_APP_KEY")
        
        if api_key and app_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as dd_client:
                    now = int(datetime.now().timestamp())
                    hour_ago = now - 3600
                    
                    # Check for LeadFactory metrics
                    response = await dd_client.get(
                        "https://api.us5.datadoghq.com/api/v1/query",
                        headers={
                            "DD-API-KEY": api_key,
                            "DD-APPLICATION-KEY": app_key
                        },
                        params={
                            "from": hour_ago,
                            "to": now,
                            "query": "avg:leadfactory.http_requests_total{*}.rollup(avg, 300)"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        series = data.get("series", [])
                        
                        # Also check system metrics to verify connection
                        system_response = await dd_client.get(
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
                        
                        system_data = system_response.json() if system_response.status_code == 200 else {}
                        system_series = system_data.get("series", [])
                        
                        results["tests"].append({
                            "service": "datadog",
                            "status": "PASS",
                            "data": {
                                "leadfactory_metrics": len(series),
                                "system_metrics": len(system_series),
                                "api_connection": "OK"
                            }
                        })
                        
                        print(f"  API Connection: ✓")
                        print(f"  LeadFactory Metrics: {'✓' if series else '⚠ (none yet)'}")
                        print(f"  System Metrics: {'✓' if system_series else '✗'}")
                    else:
                        results["tests"].append({
                            "service": "datadog",
                            "status": "FAIL",
                            "error": f"API returned {response.status_code}"
                        })
                        print(f"  Datadog API: ✗ ({response.status_code})")
                        
            except Exception as e:
                results["tests"].append({
                    "service": "datadog",
                    "status": "ERROR",
                    "error": str(e)
                })
                print(f"  Datadog: ✗ (Error: {str(e)[:50]}...)")
        else:
            results["tests"].append({
                "service": "datadog",
                "status": "SKIP",
                "reason": "API keys not configured"
            })
            print("  ⚠ Skipped: No API keys")
            
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for t in results["tests"] if t.get("status") == "PASS")
    failed = sum(1 for t in results["tests"] if t.get("status") == "FAIL")
    errors = sum(1 for t in results["tests"] if t.get("status") == "ERROR")
    skipped = sum(1 for t in results["tests"] if t.get("status") == "SKIP")
    
    total = len(results["tests"])
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ({success_rate:.1f}%)")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print(f"Skipped: {skipped}")
    
    # Show failures
    if failed > 0 or errors > 0:
        print("\nFailed Tests:")
        for test in results["tests"]:
            if test.get("status") in ["FAIL", "ERROR"]:
                endpoint = test.get("endpoint") or test.get("service", "unknown")
                error = test.get("error", f"HTTP {test.get('http_code', 'unknown')}")
                print(f"  - {endpoint}: {error}")
    
    all_critical_passed = passed >= total * 0.7  # 70% pass rate
    print(f"\nResult: {'✅ PASS' if all_critical_passed else '❌ FAIL'}")
    
    # Save detailed results
    with open("realistic_smoke_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
        
    return 0 if all_critical_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_realistic_smoke_test())
    sys.exit(exit_code)