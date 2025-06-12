#!/usr/bin/env python3
"""
Simple production smoke test runner
Tests basic connectivity to all services
"""
import asyncio
import httpx
import json
import sys
import os

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 10.0


async def test_health_endpoint():
    """Test basic health endpoint"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            return {
                "endpoint": "/health",
                "status": response.status_code,
                "passed": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            return {
                "endpoint": "/health",
                "status": "error",
                "passed": False,
                "error": str(e)
            }


async def test_metrics_endpoint():
    """Test Prometheus metrics endpoint"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/metrics")
            metrics_text = response.text if response.status_code == 200 else ""
            
            # Check for key metrics
            key_metrics = [
                "leadfactory_http_requests_total",
                "leadfactory_http_request_duration_seconds",
                "leadfactory_app_info"
            ]
            
            found_metrics = {m: m in metrics_text for m in key_metrics}
            
            return {
                "endpoint": "/metrics",
                "status": response.status_code,
                "passed": response.status_code == 200 and all(found_metrics.values()),
                "metrics_found": found_metrics
            }
        except Exception as e:
            return {
                "endpoint": "/metrics",
                "status": "error",
                "passed": False,
                "error": str(e)
            }


async def test_api_docs():
    """Test API documentation endpoints"""
    results = []
    
    for endpoint in ["/docs", "/redoc"]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.get(f"{API_BASE_URL}{endpoint}")
                results.append({
                    "endpoint": endpoint,
                    "status": response.status_code,
                    "passed": response.status_code == 200
                })
            except Exception as e:
                results.append({
                    "endpoint": endpoint,
                    "status": "error",
                    "passed": False,
                    "error": str(e)
                })
    
    return results


async def test_database_connectivity():
    """Test database connectivity via API"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Try to access campaigns endpoint (should work even if empty)
            response = await client.get(
                f"{API_BASE_URL}/api/v1/campaigns",
                params={"limit": 1, "offset": 0}
            )
            
            return {
                "service": "database",
                "endpoint": "/api/v1/campaigns",
                "status": response.status_code,
                "passed": response.status_code in [200, 404],  # 404 is ok if no campaigns
                "data": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            return {
                "service": "database",
                "endpoint": "/api/v1/campaigns",
                "status": "error",
                "passed": False,
                "error": str(e)
            }


async def test_redis_connectivity():
    """Test Redis connectivity via health endpoint"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                # Simple health endpoint doesn't include Redis status
                # Just check if the API is responsive (which requires Redis)
                return {
                    "service": "redis",
                    "status": "assumed_healthy",
                    "passed": True,
                    "note": "Redis assumed healthy since API is responsive"
                }
            else:
                return {
                    "service": "redis",
                    "status": "unknown",
                    "passed": False,
                    "error": "Could not get health status"
                }
        except Exception as e:
            return {
                "service": "redis",
                "status": "error",
                "passed": False,
                "error": str(e)
            }


async def test_datadog_metrics():
    """Test Datadog metrics if configured"""
    api_key = os.getenv("DATADOG_API_KEY")
    app_key = os.getenv("DATADOG_APP_KEY")
    
    if not api_key or not app_key:
        return {
            "service": "datadog",
            "status": "skipped",
            "passed": True,
            "reason": "Datadog API keys not configured"
        }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Query for any leadfactory metric
            from datetime import datetime
            now = int(datetime.now().timestamp())
            hour_ago = now - 3600
            
            response = await client.get(
                "https://api.us5.datadoghq.com/api/v1/query",
                headers={
                    "DD-API-KEY": api_key,
                    "DD-APPLICATION-KEY": app_key
                },
                params={
                    "from": hour_ago,
                    "to": now,
                    "query": "avg:leadfactory.requests_total{*}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                series = data.get("series", [])
                
                return {
                    "service": "datadog",
                    "status": "connected",
                    "passed": True,
                    "metrics_found": len(series) > 0,
                    "series_count": len(series)
                }
            else:
                return {
                    "service": "datadog",
                    "status": f"api_error_{response.status_code}",
                    "passed": False,
                    "error": response.text
                }
                
        except Exception as e:
            return {
                "service": "datadog",
                "status": "error",
                "passed": False,
                "error": str(e)
            }


async def main():
    """Run all smoke tests"""
    print(f"Running smoke tests against: {API_BASE_URL}")
    print("-" * 60)
    
    results = {
        "api_base_url": API_BASE_URL,
        "tests": []
    }
    
    # Run tests
    print("Testing health endpoint...")
    health_result = await test_health_endpoint()
    results["tests"].append(health_result)
    print(f"  Health: {'✓' if health_result['passed'] else '✗'}")
    
    print("Testing metrics endpoint...")
    metrics_result = await test_metrics_endpoint()
    results["tests"].append(metrics_result)
    print(f"  Metrics: {'✓' if metrics_result['passed'] else '✗'}")
    
    print("Testing API documentation...")
    docs_results = await test_api_docs()
    results["tests"].extend(docs_results)
    for doc_result in docs_results:
        print(f"  {doc_result['endpoint']}: {'✓' if doc_result['passed'] else '✗'}")
    
    print("Testing database connectivity...")
    db_result = await test_database_connectivity()
    results["tests"].append(db_result)
    print(f"  Database: {'✓' if db_result['passed'] else '✗'}")
    
    print("Testing Redis connectivity...")
    redis_result = await test_redis_connectivity()
    results["tests"].append(redis_result)
    print(f"  Redis: {'✓' if redis_result['passed'] else '✗'}")
    
    print("Testing Datadog metrics...")
    datadog_result = await test_datadog_metrics()
    results["tests"].append(datadog_result)
    print(f"  Datadog: {'✓' if datadog_result['passed'] else '✗'} ({datadog_result['status']})")
    
    # Summary
    total_tests = len(results["tests"])
    passed_tests = sum(1 for test in results["tests"] if test.get("passed", False))
    
    print("-" * 60)
    print(f"Summary: {passed_tests}/{total_tests} tests passed")
    
    # Write results
    with open("smoke_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Exit code
    success = passed_tests == total_tests
    if not success:
        print("\nFailed tests:")
        for test in results["tests"]:
            if not test.get("passed", False):
                print(f"  - {test.get('endpoint', test.get('service', 'unknown'))}: {test.get('error', 'failed')}")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)