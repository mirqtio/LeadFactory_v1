"""
Production Smoke Test Runner
Comprehensive test suite that touches all LeadFactory domains
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.logging import get_logger
from core.config import get_settings
import os

# Set default API base URL
os.environ.setdefault("API_BASE_URL", "http://localhost:8000")
from database.session import get_db
from d0_gateway.facade import get_gateway_facade

logger = get_logger("smoke_test")
settings = get_settings()

# Synthetic SMB for testing
SYNTHETIC_SMB = {
    "business_name": "Smoke Test Plumbing & Heating",
    "domain": "smoketest-plumbing.example",
    "owner_email": "smoke-catcher@leadfactory.local",
    "phone": "+15125551234",
    "address": "123 Test St",
    "city": "Austin", 
    "state": "TX",
    "zip": "78701",
    "yelp_id": f"smoke-test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "website": "https://example.com",
    "categories": ["plumbing", "hvac"]
}


class SmokeTestRunner:
    """Runs comprehensive smoke tests against all domains"""
    
    def __init__(self):
        self.gateway = get_gateway_facade()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "domains": {},
            "metrics": {},
            "errors": []
        }
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run tests for all domains"""
        logger.info("Starting production smoke tests...")
        
        try:
            # D0: Gateway tests
            await self.test_d0_gateway()
            
            # D1: Targeting tests
            await self.test_d1_targeting()
            
            # D2: Sourcing tests
            await self.test_d2_sourcing()
            
            # D3: Assessment tests
            await self.test_d3_assessment()
            
            # D4: Enrichment tests
            await self.test_d4_enrichment()
            
            # D5: Scoring tests
            await self.test_d5_scoring()
            
            # D6: Reports tests
            await self.test_d6_reports()
            
            # D7: Storefront tests
            await self.test_d7_storefront()
            
            # D8: Personalization tests
            await self.test_d8_personalization()
            
            # D9: Delivery tests
            await self.test_d9_delivery()
            
            # D10: Analytics tests
            await self.test_d10_analytics()
            
            # D11: Orchestration tests
            await self.test_d11_orchestration()
            
            # Verify metrics
            await self.verify_metrics()
            
            # Verify Datadog metrics
            await self.verify_datadog_metrics()
            
            self.results["status"] = "SUCCESS"
            self.results["summary"] = self._generate_summary()
            
        except Exception as e:
            logger.error(f"Smoke test failed: {str(e)}")
            self.results["status"] = "FAILED"
            self.results["errors"].append(str(e))
            
        return self.results
        
    async def test_d0_gateway(self):
        """Test Gateway connectivity"""
        logger.info("Testing D0 Gateway...")
        
        domain_results = {
            "yelp": False,
            "pagespeed": False,
            "openai": False,
            "sendgrid": False,
            "stripe": False
        }
        
        try:
            # Test Yelp
            yelp_result = await self.gateway.search_businesses(
                term="plumbing",
                location="Austin, TX",
                limit=1
            )
            domain_results["yelp"] = bool(yelp_result.get("businesses"))
            
            # Test PageSpeed (with fallback domain)
            ps_result = await self.gateway.analyze_website(
                url="https://example.com",
                strategy="mobile",
                categories=["performance"]
            )
            domain_results["pagespeed"] = bool(ps_result.get("lighthouseResult"))
            
            # Test OpenAI
            openai_result = await self.gateway.generate_website_insights(
                pagespeed_data={"score": 85},
                business_context={"name": "Test Business"}
            )
            domain_results["openai"] = bool(openai_result)
            
            # Test SendGrid stats
            sendgrid_result = await self.gateway.get_email_stats(
                start_date=datetime.now().strftime("%Y-%m-%d"),
                aggregated_by="day"
            )
            domain_results["sendgrid"] = isinstance(sendgrid_result, dict)
            
            # Test Stripe (list products)
            stripe_result = await self.gateway.list_charges(limit=1)
            domain_results["stripe"] = isinstance(stripe_result, dict)
            
            self.results["domains"]["d0_gateway"] = {
                "status": "PASS" if all(domain_results.values()) else "FAIL",
                "providers": domain_results
            }
            
        except Exception as e:
            self.results["domains"]["d0_gateway"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d1_targeting(self):
        """Test Targeting API"""
        logger.info("Testing D1 Targeting...")
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            async with httpx.AsyncClient() as client:
                # List targets
                response = await client.get(
                    f"{api_base_url}/api/v1/targeting/targets",
                    params={"limit": 1}
                )
                
                self.results["domains"]["d1_targeting"] = {
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "api_health": response.status_code == 200
                }
                
        except Exception as e:
            self.results["domains"]["d1_targeting"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d2_sourcing(self):
        """Test Sourcing (read-only)"""
        logger.info("Testing D2 Sourcing...")
        
        try:
            # Just verify the models load (no API for d2_sourcing)
            from d2_sourcing.models import SourcedLocation, YelpMetadata
            from d2_sourcing.coordinator import SourcingCoordinator
            
            # Verify modules can be imported
            self.results["domains"]["d2_sourcing"] = {
                "status": "PASS",
                "models_loaded": True,
                "note": "No API endpoints - verified module imports"
            }
            
        except Exception as e:
            self.results["domains"]["d2_sourcing"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d3_assessment(self):
        """Test Assessment API"""
        logger.info("Testing D3 Assessment...")
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            async with httpx.AsyncClient() as client:
                # Get assessment status
                response = await client.get(
                    f"{api_base_url}/api/v1/assessments/status"
                )
                
                self.results["domains"]["d3_assessment"] = {
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "api_health": response.status_code == 200
                }
                
        except Exception as e:
            self.results["domains"]["d3_assessment"] = {
                "status": "FAIL", 
                "error": str(e)
            }
            
    async def test_d4_enrichment(self):
        """Test Enrichment (read-only)"""
        logger.info("Testing D4 Enrichment...")
        
        try:
            from d4_enrichment.models import EnrichmentResult
            
            self.results["domains"]["d4_enrichment"] = {
                "status": "PASS",
                "models_loaded": True
            }
            
        except Exception as e:
            self.results["domains"]["d4_enrichment"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d5_scoring(self):
        """Test Scoring Engine"""
        logger.info("Testing D5 Scoring...")
        
        try:
            from d5_scoring.engine import ConfigurableScoringEngine as ScoringEngine
            
            engine = ScoringEngine()
            
            # Create test data as dictionary (what the engine expects)
            business_data = {
                "id": "smoke-test",
                "name": SYNTHETIC_SMB["business_name"],
                "vertical": "hvac",
                "categories": ["plumbing", "hvac"],
                "has_website": True,
                "mobile_score": 75,
                "desktop_score": 80,
                "page_speed_issues": 2,
                "accessibility_issues": 1,
                "seo_issues": 1,
                "total_issues": 4
            }
            
            result = engine.calculate_score(business_data)
            
            self.results["domains"]["d5_scoring"] = {
                "status": "PASS",
                "test_score": float(result.overall_score),
                "test_tier": result.tier
            }
            
        except Exception as e:
            self.results["domains"]["d5_scoring"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d6_reports(self):
        """Test Report Generation"""
        logger.info("Testing D6 Reports...")
        
        try:
            from d6_reports.generator import ReportGenerator
            from d6_reports.models import ReportGeneration
            
            generator = ReportGenerator()
            
            # Verify template exists
            template_path = generator.template_engine.env.get_template("audit_report")
            
            self.results["domains"]["d6_reports"] = {
                "status": "PASS",
                "template_loaded": bool(template_path)
            }
            
        except Exception as e:
            self.results["domains"]["d6_reports"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d7_storefront(self):
        """Test Storefront API"""
        logger.info("Testing D7 Storefront...")
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            async with httpx.AsyncClient() as client:
                # Get products
                response = await client.get(
                    f"{api_base_url}/api/v1/checkout/products"
                )
                
                self.results["domains"]["d7_storefront"] = {
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "api_health": response.status_code == 200,
                    "products_available": len(response.json()) > 0 if response.status_code == 200 else False
                }
                
        except Exception as e:
            self.results["domains"]["d7_storefront"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d8_personalization(self):
        """Test Personalization"""
        logger.info("Testing D8 Personalization...")
        
        try:
            from d8_personalization.personalizer import EmailPersonalizer
            from d8_personalization.models import EmailTemplate
            
            personalizer = EmailPersonalizer(self.gateway)
            
            # Test spam checker
            from d8_personalization.spam_checker import SpamScoreChecker
            checker = SpamScoreChecker()
            
            spam_result = checker.check_spam_score(
                subject_line="Test Email",
                email_content="This is a test email content"
            )
            
            self.results["domains"]["d8_personalization"] = {
                "status": "PASS",
                "spam_checker_working": spam_result.overall_score < 5.0
            }
            
        except Exception as e:
            self.results["domains"]["d8_personalization"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d9_delivery(self):
        """Test Delivery (no actual sends)"""
        logger.info("Testing D9 Delivery...")
        
        try:
            from d9_delivery.models import EmailDelivery
            from d9_delivery.compliance import ComplianceManager as ComplianceChecker
            
            # Test compliance checker
            checker = ComplianceChecker()
            # Check suppression instead of validate (ComplianceManager doesn't have validate_email_address)
            is_suppressed = checker.check_suppression("test@example.com")
            is_valid = not is_suppressed  # Not suppressed means valid to send
            
            self.results["domains"]["d9_delivery"] = {
                "status": "PASS",
                "compliance_checker": is_valid
            }
            
        except Exception as e:
            self.results["domains"]["d9_delivery"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d10_analytics(self):
        """Test Analytics API"""
        logger.info("Testing D10 Analytics...")
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            async with httpx.AsyncClient() as client:
                # Get analytics overview
                response = await client.get(
                    f"{api_base_url}/api/v1/analytics/overview"
                )
                
                self.results["domains"]["d10_analytics"] = {
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "api_health": response.status_code == 200
                }
                
        except Exception as e:
            self.results["domains"]["d10_analytics"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def test_d11_orchestration(self):
        """Test Orchestration API"""
        logger.info("Testing D11 Orchestration...")
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            async with httpx.AsyncClient() as client:
                # Get campaigns
                response = await client.get(
                    f"{api_base_url}/api/v1/campaigns",
                    params={"limit": 1}
                )
                
                self.results["domains"]["d11_orchestration"] = {
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "api_health": response.status_code == 200
                }
                
        except Exception as e:
            self.results["domains"]["d11_orchestration"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def verify_metrics(self):
        """Verify Prometheus metrics"""
        logger.info("Verifying metrics...")
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            async with httpx.AsyncClient() as client:
                # Check metrics endpoint
                response = await client.get(f"{api_base_url}/metrics")
                
                if response.status_code == 200:
                    metrics_text = response.text
                    
                    # Look for key metrics
                    key_metrics = [
                        "leadfactory_requests_total",
                        "leadfactory_request_duration_seconds",
                        "leadfactory_active_connections",
                        "leadfactory_errors_total"
                    ]
                    
                    found_metrics = {}
                    for metric in key_metrics:
                        found_metrics[metric] = metric in metrics_text
                        
                    self.results["metrics"]["prometheus"] = {
                        "status": "PASS" if all(found_metrics.values()) else "FAIL",
                        "found": found_metrics
                    }
                else:
                    self.results["metrics"]["prometheus"] = {
                        "status": "FAIL",
                        "error": f"Status code: {response.status_code}"
                    }
                    
        except Exception as e:
            self.results["metrics"]["prometheus"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    async def verify_datadog_metrics(self):
        """Verify Datadog metrics via API"""
        logger.info("Verifying Datadog metrics...")
        
        try:
            # Get Datadog API credentials from environment
            api_key = os.getenv("DATADOG_API_KEY")
            app_key = os.getenv("DATADOG_APP_KEY")
            
            if not api_key or not app_key:
                self.results["metrics"]["datadog"] = {
                    "status": "SKIP",
                    "reason": "Datadog API keys not configured"
                }
                return
                
            async with httpx.AsyncClient() as client:
                # Query for leadfactory.leads_processed metric
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
                        "query": "avg:leadfactory.leads_processed{*}"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    series = data.get("series", [])
                    
                    self.results["metrics"]["datadog"] = {
                        "status": "PASS",
                        "metric_found": len(series) > 0,
                        "datapoints": len(series[0]["pointlist"]) if series else 0
                    }
                else:
                    self.results["metrics"]["datadog"] = {
                        "status": "FAIL",
                        "error": f"API returned {response.status_code}",
                        "response": response.text
                    }
                    
        except Exception as e:
            self.results["metrics"]["datadog"] = {
                "status": "FAIL",
                "error": str(e)
            }
            
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary"""
        domains_tested = len(self.results["domains"])
        domains_passed = sum(1 for d in self.results["domains"].values() if d.get("status") == "PASS")
        
        return {
            "domains_tested": domains_tested,
            "domains_passed": domains_passed,
            "success_rate": f"{(domains_passed/domains_tested)*100:.1f}%",
            "errors_count": len(self.results["errors"])
        }


async def main():
    """Main entry point"""
    runner = SmokeTestRunner()
    results = await runner.run_all_tests()
    
    # Output results
    print(json.dumps(results, indent=2))
    
    # Generate JUnit XML
    junit_xml = generate_junit_xml(results)
    with open("smoke_test_results.xml", "w") as f:
        f.write(junit_xml)
        
    # Exit with appropriate code
    sys.exit(0 if results["status"] == "SUCCESS" else 1)


def generate_junit_xml(results: Dict[str, Any]) -> str:
    """Generate JUnit XML report"""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom
    
    # Create root element
    testsuites = Element("testsuites")
    testsuite = SubElement(testsuites, "testsuite", {
        "name": "LeadFactory Smoke Tests",
        "timestamp": results["timestamp"],
        "tests": str(len(results["domains"])),
        "failures": str(sum(1 for d in results["domains"].values() if d.get("status") == "FAIL")),
        "errors": str(len(results["errors"]))
    })
    
    # Add test cases for each domain
    for domain, result in results["domains"].items():
        testcase = SubElement(testsuite, "testcase", {
            "classname": "SmokeTest",
            "name": domain
        })
        
        if result.get("status") == "FAIL":
            failure = SubElement(testcase, "failure", {
                "message": result.get("error", "Test failed")
            })
            failure.text = json.dumps(result, indent=2)
            
    # Pretty print
    rough_string = tostring(testsuites, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


if __name__ == "__main__":
    asyncio.run(main())