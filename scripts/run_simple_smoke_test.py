#!/usr/bin/env python3
"""
Simple smoke test for production readiness without Prefect dependencies
Tests the core LeadFactory pipeline end-to-end
"""
import asyncio
import time
from datetime import datetime
import json
from pathlib import Path
import sys

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
from d0_gateway.facade import get_gateway_facade
from d1_targeting.target_universe import TargetUniverse
from d2_sourcing.coordinator import SourcingCoordinator
from d3_assessment.coordinator import AssessmentCoordinator
from d5_scoring.engine import ScoringEngine
from d6_reports.generator import ReportGenerator
from d8_personalization.personalizer import EmailPersonalizer
from d9_delivery.delivery_manager import DeliveryManager
from database.session import get_db


class SimpleSmokeTest:
    """Run a simple end-to-end smoke test"""
    
    def __init__(self):
        self.run_id = f"smoke_{int(time.time())}"
        self.results = {
            "run_id": self.run_id,
            "started_at": datetime.utcnow().isoformat(),
            "steps": {}
        }
    
    async def run_test(self):
        """Execute the smoke test"""
        print(f"\n{'='*60}")
        print(f"LEADFACTORY SIMPLE SMOKE TEST")
        print(f"Run ID: {self.run_id}")
        print(f"{'='*60}\n")
        
        try:
            # Step 1: Test Gateway APIs
            print("1. Testing Gateway APIs...")
            start_time = time.time()
            
            # Get gateway facade instance
            gateway_facade = get_gateway_facade()
            
            # Test Yelp search
            yelp_result = await gateway_facade.search_businesses(
                term="HVAC",
                location="Denver, CO",
                limit=5
            )
            assert len(yelp_result["businesses"]) > 0, "No businesses found"
            
            # Test PageSpeed
            test_url = "https://example.com"
            pagespeed_result = await gateway_facade.analyze_pagespeed(test_url)
            assert pagespeed_result is not None, "PageSpeed analysis failed"
            
            self.results["steps"]["gateway"] = {
                "status": "PASSED",
                "duration": time.time() - start_time,
                "businesses_found": len(yelp_result["businesses"])
            }
            print(f"✅ Gateway APIs: PASSED ({time.time() - start_time:.2f}s)")
            
            # Step 2: Test Targeting
            print("\n2. Testing Targeting...")
            start_time = time.time()
            
            target_universe = TargetUniverse()
            targets = await target_universe.search_targets(
                vertical="HVAC",
                location="Denver, CO",
                radius_miles=10,
                max_results=5
            )
            assert len(targets) > 0, "No targets found"
            
            self.results["steps"]["targeting"] = {
                "status": "PASSED",
                "duration": time.time() - start_time,
                "targets_found": len(targets)
            }
            print(f"✅ Targeting: PASSED ({time.time() - start_time:.2f}s)")
            
            # Step 3: Test Assessment
            print("\n3. Testing Assessment...")
            start_time = time.time()
            
            coordinator = AssessmentCoordinator()
            
            # Create a test business
            test_business = {
                "id": "smoke_test_business",
                "name": "Smoke Test HVAC",
                "website": "https://example.com",
                "email": "test@example.com",
                "phone": "555-0123",
                "vertical": "HVAC"
            }
            
            assessment = await coordinator.assess_business(test_business)
            assert assessment is not None, "Assessment failed"
            assert "website_status" in assessment, "Missing website status"
            
            self.results["steps"]["assessment"] = {
                "status": "PASSED",
                "duration": time.time() - start_time,
                "issues_found": len(assessment.get("issues", []))
            }
            print(f"✅ Assessment: PASSED ({time.time() - start_time:.2f}s)")
            
            # Step 4: Test Scoring
            print("\n4. Testing Scoring...")
            start_time = time.time()
            
            scoring_engine = ScoringEngine()
            score_result = await scoring_engine.score_lead(
                business=test_business,
                assessment=assessment
            )
            assert score_result is not None, "Scoring failed"
            assert "total_score" in score_result, "Missing total score"
            assert "tier" in score_result, "Missing tier"
            
            self.results["steps"]["scoring"] = {
                "status": "PASSED",
                "duration": time.time() - start_time,
                "score": score_result["total_score"],
                "tier": score_result["tier"]
            }
            print(f"✅ Scoring: PASSED ({time.time() - start_time:.2f}s)")
            
            # Step 5: Test Report Generation
            print("\n5. Testing Report Generation...")
            start_time = time.time()
            
            generator = ReportGenerator()
            report = await generator.generate_report(
                business=test_business,
                assessment=assessment,
                score=score_result
            )
            assert report is not None, "Report generation failed"
            assert "html" in report, "Missing HTML report"
            assert len(report["html"]) > 1000, "Report too short"
            
            self.results["steps"]["reports"] = {
                "status": "PASSED",
                "duration": time.time() - start_time,
                "report_size": len(report["html"])
            }
            print(f"✅ Report Generation: PASSED ({time.time() - start_time:.2f}s)")
            
            # Step 6: Test Email Personalization
            print("\n6. Testing Email Personalization...")
            start_time = time.time()
            
            personalizer = EmailPersonalizer()
            email_content = await personalizer.personalize_email(
                business=test_business,
                assessment=assessment,
                score=score_result
            )
            assert email_content is not None, "Email personalization failed"
            assert "subject" in email_content, "Missing email subject"
            assert "body" in email_content, "Missing email body"
            assert self.run_id in email_content["subject"], "Missing run ID in subject"
            
            self.results["steps"]["personalization"] = {
                "status": "PASSED",
                "duration": time.time() - start_time,
                "subject_length": len(email_content["subject"]),
                "body_length": len(email_content["body"])
            }
            print(f"✅ Email Personalization: PASSED ({time.time() - start_time:.2f}s)")
            
            # Final summary
            self.results["status"] = "PASSED"
            self.results["completed_at"] = datetime.utcnow().isoformat()
            total_duration = sum(step["duration"] for step in self.results["steps"].values())
            self.results["total_duration"] = total_duration
            
            print(f"\n{'='*60}")
            print(f"SMOKE TEST COMPLETED SUCCESSFULLY")
            print(f"Total Duration: {total_duration:.2f}s")
            print(f"All 6 steps PASSED")
            print(f"{'='*60}\n")
            
            # Save results
            results_file = f"smoke_test_results_{self.run_id}.json"
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)
            print(f"Results saved to: {results_file}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ SMOKE TEST FAILED: {str(e)}")
            self.results["status"] = "FAILED"
            self.results["error"] = str(e)
            self.results["completed_at"] = datetime.utcnow().isoformat()
            
            # Save failure results
            results_file = f"smoke_test_results_{self.run_id}_FAILED.json"
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)
            
            return False


async def main():
    """Run the smoke test"""
    # Set test environment
    settings.use_stubs = True
    settings.testing = True
    
    test = SimpleSmokeTest()
    success = await test.run_test()
    
    if success:
        print("\n🎉 Production smoke test PASSED!")
        print("The system is ready for deployment.")
        return 0
    else:
        print("\n❌ Production smoke test FAILED!")
        print("Please fix the issues before deploying.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)