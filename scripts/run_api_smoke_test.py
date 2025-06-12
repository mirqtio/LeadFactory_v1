#!/usr/bin/env python3
"""
API-based smoke test for production deployment
Tests the LeadFactory API endpoints directly
"""
import asyncio
import aiohttp
import time
import json
from datetime import datetime
import sys


class APISmokeTest:
    """Run smoke tests against the API endpoints"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.run_id = f"smoke_{int(time.time())}"
        self.results = {
            "run_id": self.run_id,
            "started_at": datetime.utcnow().isoformat(),
            "base_url": base_url,
            "tests": {}
        }
    
    async def test_health(self, session):
        """Test health endpoint"""
        try:
            start = time.time()
            async with session.get(f"{self.base_url}/health") as resp:
                data = await resp.json()
                duration = time.time() - start
                
                assert resp.status == 200, f"Health check failed with status {resp.status}"
                assert data["status"] == "healthy", "API reports unhealthy"
                
                self.results["tests"]["health"] = {
                    "status": "PASSED",
                    "duration": duration,
                    "response": data
                }
                return True
        except Exception as e:
            self.results["tests"]["health"] = {
                "status": "FAILED",
                "error": str(e)
            }
            return False
    
    async def test_api_docs(self, session):
        """Test API documentation endpoint"""
        try:
            start = time.time()
            async with session.get(f"{self.base_url}/docs") as resp:
                duration = time.time() - start
                
                assert resp.status == 200, f"Docs endpoint failed with status {resp.status}"
                
                self.results["tests"]["api_docs"] = {
                    "status": "PASSED",
                    "duration": duration
                }
                return True
        except Exception as e:
            self.results["tests"]["api_docs"] = {
                "status": "FAILED",
                "error": str(e)
            }
            return False
    
    async def test_targeting_search(self, session):
        """Test targeting search endpoint"""
        try:
            start = time.time()
            payload = {
                "vertical": "HVAC",
                "location": "Denver, CO",
                "radius_miles": 10,
                "max_results": 5
            }
            
            async with session.post(f"{self.base_url}/api/v1/targeting/search", json=payload) as resp:
                data = await resp.json()
                duration = time.time() - start
                
                assert resp.status == 200, f"Targeting search failed with status {resp.status}"
                assert "targets" in data, "No targets in response"
                assert len(data["targets"]) > 0, "No targets found"
                
                self.results["tests"]["targeting_search"] = {
                    "status": "PASSED",
                    "duration": duration,
                    "targets_found": len(data["targets"])
                }
                return True
        except Exception as e:
            self.results["tests"]["targeting_search"] = {
                "status": "FAILED",
                "error": str(e)
            }
            return False
    
    async def test_assessment_analyze(self, session):
        """Test assessment endpoint"""
        try:
            start = time.time()
            payload = {
                "business_id": f"smoke_test_{self.run_id}",
                "url": "https://example.com",
                "force_refresh": True
            }
            
            async with session.post(f"{self.base_url}/api/v1/assessment/analyze", json=payload) as resp:
                data = await resp.json()
                duration = time.time() - start
                
                assert resp.status == 200, f"Assessment failed with status {resp.status}"
                assert "assessment" in data, "No assessment in response"
                
                self.results["tests"]["assessment"] = {
                    "status": "PASSED",
                    "duration": duration,
                    "has_issues": "issues" in data["assessment"]
                }
                return True
        except Exception as e:
            self.results["tests"]["assessment"] = {
                "status": "FAILED",
                "error": str(e)
            }
            return False
    
    async def test_analytics_funnel(self, session):
        """Test analytics funnel endpoint"""
        try:
            start = time.time()
            params = {
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
            
            async with session.get(f"{self.base_url}/api/v1/analytics/funnel", params=params) as resp:
                data = await resp.json()
                duration = time.time() - start
                
                assert resp.status == 200, f"Analytics funnel failed with status {resp.status}"
                
                self.results["tests"]["analytics_funnel"] = {
                    "status": "PASSED",
                    "duration": duration
                }
                return True
        except Exception as e:
            self.results["tests"]["analytics_funnel"] = {
                "status": "FAILED",
                "error": str(e)
            }
            return False
    
    async def test_orchestration_status(self, session):
        """Test orchestration status endpoint"""
        try:
            start = time.time()
            
            async with session.get(f"{self.base_url}/api/v1/orchestration/campaigns") as resp:
                data = await resp.json()
                duration = time.time() - start
                
                assert resp.status == 200, f"Orchestration status failed with status {resp.status}"
                
                self.results["tests"]["orchestration_status"] = {
                    "status": "PASSED",
                    "duration": duration,
                    "campaigns": len(data.get("campaigns", []))
                }
                return True
        except Exception as e:
            self.results["tests"]["orchestration_status"] = {
                "status": "FAILED",
                "error": str(e)
            }
            return False
    
    async def run_all_tests(self):
        """Run all smoke tests"""
        print(f"\n{'='*60}")
        print(f"LEADFACTORY API SMOKE TEST")
        print(f"Target: {self.base_url}")
        print(f"Run ID: {self.run_id}")
        print(f"{'='*60}\n")
        
        async with aiohttp.ClientSession() as session:
            tests = [
                ("Health Check", self.test_health),
                ("API Documentation", self.test_api_docs),
                ("Targeting Search", self.test_targeting_search),
                ("Assessment Analysis", self.test_assessment_analyze),
                ("Analytics Funnel", self.test_analytics_funnel),
                ("Orchestration Status", self.test_orchestration_status),
            ]
            
            passed = 0
            failed = 0
            
            for test_name, test_func in tests:
                print(f"Running: {test_name}...", end=" ")
                success = await test_func(session)
                if success:
                    print("✅ PASSED")
                    passed += 1
                else:
                    print("❌ FAILED")
                    failed += 1
            
            # Summary
            self.results["summary"] = {
                "total_tests": len(tests),
                "passed": passed,
                "failed": failed,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            print(f"\n{'='*60}")
            print(f"SMOKE TEST SUMMARY")
            print(f"{'='*60}")
            print(f"Total Tests: {len(tests)}")
            print(f"Passed: {passed}")
            print(f"Failed: {failed}")
            
            # Save results
            results_file = f"api_smoke_test_{self.run_id}.json"
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)
            print(f"\nResults saved to: {results_file}")
            
            if failed == 0:
                print("\n🎉 All smoke tests PASSED!")
                print("The API is functioning correctly.")
                return True
            else:
                print(f"\n❌ {failed} smoke tests FAILED!")
                print("Please check the results file for details.")
                return False


async def main():
    """Run the smoke test"""
    # Check if custom URL provided
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    test = APISmokeTest(base_url)
    success = await test.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)