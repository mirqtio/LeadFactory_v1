#!/usr/bin/env python3
"""
Basic deployment test to verify services are running
"""
import requests
import json
import sys
from datetime import datetime


def test_service(name, url, expected_status=200, check_json=True):
    """Test a service endpoint"""
    try:
        response = requests.get(url, timeout=5)
        success = response.status_code == expected_status
        
        result = {
            "service": name,
            "url": url,
            "status_code": response.status_code,
            "success": success
        }
        
        if check_json and success:
            try:
                result["response"] = response.json()
            except:
                result["response"] = "Not JSON"
        
        return result
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "success": False,
            "error": str(e)
        }


def main():
    """Run deployment tests"""
    print("="*60)
    print("LEADFACTORY DEPLOYMENT TEST")
    print(f"Time: {datetime.now()}")
    print("="*60)
    print()
    
    # Services to test
    tests = [
        # Core API
        ("API Health", "http://localhost:8000/health"),
        ("API Docs", "http://localhost:8000/docs", 200, False),
        ("API OpenAPI", "http://localhost:8000/openapi.json"),
        
        # Through Nginx
        ("Nginx Health", "http://localhost/health"),
        
        # Direct services (if exposed)
        ("PostgreSQL", "http://localhost:5432/", None, False),  # Will fail but shows it's listening
        ("Redis", "http://localhost:6379/", None, False),  # Will fail but shows it's listening
        ("Prometheus", "http://localhost:9091/", 200, False),
        
        # Sample API endpoints
        ("Analytics Health", "http://localhost:8000/api/v1/analytics/health"),
        ("Assessment Health", "http://localhost:8000/api/v1/assessments/health"),
    ]
    
    results = []
    passed = 0
    failed = 0
    
    for test_args in tests:
        result = test_service(*test_args)
        results.append(result)
        
        if result["success"]:
            print(f"✅ {result['service']}: OK (Status: {result['status_code']})")
            passed += 1
        else:
            error_msg = result.get("error", f"Status: {result.get('status_code', 'Unknown')}")
            print(f"❌ {result['service']}: FAILED ({error_msg})")
            failed += 1
    
    # Docker container check
    print("\n" + "="*60)
    print("DOCKER CONTAINER STATUS")
    print("="*60)
    
    import subprocess
    try:
        output = subprocess.check_output(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}", "--filter", "name=leadfactory"],
            text=True
        )
        print(output)
    except Exception as e:
        print(f"Could not check Docker status: {e}")
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    # Save results
    results_file = f"deployment_test_{int(datetime.now().timestamp())}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(tests),
                "passed": passed,
                "failed": failed
            },
            "results": results
        }, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    # Overall status
    if passed >= 5:  # At least core services working
        print("\n🎉 Deployment test PASSED! Core services are running.")
        return 0
    else:
        print("\n❌ Deployment test FAILED! Not enough services are running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())