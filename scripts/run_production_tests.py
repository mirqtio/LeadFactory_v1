#!/usr/bin/env python3
"""
Run production readiness tests before deployment

This script runs:
1. Heartbeat health checks
2. Full smoke test suite
3. Performance validation
4. Data quality checks

Usage:
    python scripts/run_production_tests.py [--smoke-only] [--heartbeat-only]
"""
import asyncio
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, Any, List
import json

# Add project root to path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.e2e.production_smoke import daily_smoke_flow
from tests.e2e.heartbeat import heartbeat_flow, quick_health_check
from core.logging import get_logger

logger = get_logger(__name__)


class ProductionTestRunner:
    """Orchestrate production readiness tests"""
    
    def __init__(self):
        self.results = {
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "total_duration": None,
            "overall_status": "pending",
            "tests": {}
        }
        
    async def run_heartbeat(self) -> Dict[str, Any]:
        """Run heartbeat health checks"""
        logger.info("=" * 60)
        logger.info("Running Heartbeat Health Checks")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        try:
            result = await heartbeat_flow()
            
            self.results["tests"]["heartbeat"] = {
                "status": "passed" if result["overall_status"] == "healthy" else "failed",
                "duration": time.time() - start_time,
                "details": result
            }
            
            # Print summary
            self._print_heartbeat_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Heartbeat failed with exception: {e}")
            self.results["tests"]["heartbeat"] = {
                "status": "error",
                "duration": time.time() - start_time,
                "error": str(e)
            }
            raise
            
    async def run_smoke_tests(self) -> Dict[str, Any]:
        """Run full smoke test suite"""
        logger.info("=" * 60)
        logger.info("Running Smoke Test Suite")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        try:
            result = await daily_smoke_flow()
            
            self.results["tests"]["smoke"] = {
                "status": "passed" if result["passed"] == result["total"] else "failed",
                "duration": time.time() - start_time,
                "details": result
            }
            
            # Print summary
            self._print_smoke_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Smoke tests failed with exception: {e}")
            self.results["tests"]["smoke"] = {
                "status": "error",
                "duration": time.time() - start_time,
                "error": str(e)
            }
            raise
            
    async def run_performance_checks(self) -> Dict[str, Any]:
        """Validate performance metrics"""
        logger.info("=" * 60)
        logger.info("Running Performance Validation")
        logger.info("=" * 60)
        
        start_time = time.time()
        checks_passed = []
        checks_failed = []
        
        # Quick health check performance
        health_start = time.time()
        health_result = await quick_health_check()
        health_duration = time.time() - health_start
        
        if health_duration < 1.0:
            checks_passed.append(f"Quick health check: {health_duration:.3f}s < 1s ✓")
        else:
            checks_failed.append(f"Quick health check: {health_duration:.3f}s > 1s ✗")
            
        # Database query performance
        from database.session import get_db
        from sqlalchemy import text
        
        async with get_db() as db:
            # Test indexed query
            query_start = time.time()
            result = await db.execute(
                text("SELECT COUNT(*) FROM businesses WHERE created_at > NOW() - INTERVAL '7 days'")
            )
            query_duration = time.time() - query_start
            
            if query_duration < 0.1:
                checks_passed.append(f"Database query: {query_duration:.3f}s < 0.1s ✓")
            else:
                checks_failed.append(f"Database query: {query_duration:.3f}s > 0.1s ✗")
                
        performance_result = {
            "total_checks": len(checks_passed) + len(checks_failed),
            "passed": len(checks_passed),
            "failed": len(checks_failed),
            "checks": {
                "passed": checks_passed,
                "failed": checks_failed
            }
        }
        
        self.results["tests"]["performance"] = {
            "status": "passed" if len(checks_failed) == 0 else "failed",
            "duration": time.time() - start_time,
            "details": performance_result
        }
        
        # Print results
        logger.info(f"\nPerformance Checks: {len(checks_passed)}/{performance_result['total_checks']} passed")
        for check in checks_passed:
            logger.info(f"  {check}")
        for check in checks_failed:
            logger.error(f"  {check}")
            
        return performance_result
        
    async def run_data_quality_checks(self) -> Dict[str, Any]:
        """Verify data quality and cleanup"""
        logger.info("=" * 60)
        logger.info("Running Data Quality Checks")
        logger.info("=" * 60)
        
        start_time = time.time()
        issues = []
        
        from database.session import get_db
        from sqlalchemy import text
        
        async with get_db() as db:
            # Check for orphaned records
            result = await db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM emails e 
                    LEFT JOIN businesses b ON e.business_id = b.id 
                    WHERE b.id IS NULL
                """)
            )
            orphaned_emails = result.scalar()
            if orphaned_emails > 0:
                issues.append(f"Found {orphaned_emails} orphaned email records")
                
            # Check for old test data
            result = await db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM businesses 
                    WHERE (id LIKE 'test_%' OR id LIKE 'smoke_%') 
                    AND created_at < NOW() - INTERVAL '7 days'
                """)
            )
            old_test_data = result.scalar()
            if old_test_data > 0:
                issues.append(f"Found {old_test_data} old test records")
                
            # Check for incomplete assessments
            result = await db.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM businesses b 
                    LEFT JOIN assessment_results a ON b.id = a.business_id 
                    WHERE b.created_at < NOW() - INTERVAL '1 day' 
                    AND a.id IS NULL
                """)
            )
            incomplete = result.scalar()
            if incomplete > 0:
                issues.append(f"Found {incomplete} businesses without assessments")
                
        data_quality_result = {
            "issues_found": len(issues),
            "issues": issues,
            "status": "clean" if len(issues) == 0 else "needs_attention"
        }
        
        self.results["tests"]["data_quality"] = {
            "status": "passed" if len(issues) == 0 else "warning",
            "duration": time.time() - start_time,
            "details": data_quality_result
        }
        
        # Print results
        if issues:
            logger.warning(f"\nData Quality Issues Found ({len(issues)}):")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("\nData Quality: ✓ No issues found")
            
        return data_quality_result
        
    def _print_heartbeat_summary(self, result: Dict[str, Any]):
        """Print heartbeat test summary"""
        logger.info(f"\nHeartbeat Status: {result['overall_status'].upper()}")
        logger.info(f"Checks: {result['healthy']}/{result['total_checks']} healthy")
        
        if result["critical_failures"]:
            logger.error("\nCritical Failures:")
            for failure in result["critical_failures"]:
                logger.error(f"  - {failure['service']}: {failure.get('error', 'unhealthy')}")
                
        if result["warnings"]:
            logger.warning("\nWarnings:")
            for warning in result["warnings"]:
                logger.warning(f"  - {warning['service']}: {warning.get('error', 'degraded')}")
                
    def _print_smoke_summary(self, result: Dict[str, Any]):
        """Print smoke test summary"""
        logger.info(f"\nSmoke Test Results: {result['passed']}/{result['total']} passed")
        
        if result.get("errors"):
            logger.error("\nFailed Variants:")
            for error in result["errors"]:
                logger.error(f"  - {error.get('variant', 'unknown')}: {error.get('error', 'failed')}")
                
        # Print timing summary
        if result.get("timings"):
            logger.info("\nTiming Summary:")
            for task, times in result["timings"].items():
                avg_time = sum(times) / len(times)
                max_time = max(times)
                logger.info(f"  - {task}: avg={avg_time:.2f}s, max={max_time:.2f}s")
                
    async def run_all_tests(self, smoke_only: bool = False, heartbeat_only: bool = False):
        """Run all production readiness tests"""
        overall_start = time.time()
        
        try:
            # Always run heartbeat first (it's quick)
            if not smoke_only:
                await self.run_heartbeat()
                
            # Run smoke tests if not heartbeat-only
            if not heartbeat_only:
                await self.run_smoke_tests()
                
            # Run additional checks if doing full suite
            if not smoke_only and not heartbeat_only:
                await self.run_performance_checks()
                await self.run_data_quality_checks()
                
            # Determine overall status
            all_passed = all(
                test.get("status") in ["passed", "warning"]
                for test in self.results["tests"].values()
            )
            
            self.results["overall_status"] = "passed" if all_passed else "failed"
            
        except Exception as e:
            self.results["overall_status"] = "error"
            self.results["error"] = str(e)
            
        finally:
            self.results["completed_at"] = datetime.utcnow().isoformat()
            self.results["total_duration"] = time.time() - overall_start
            
        # Print final summary
        self._print_final_summary()
        
        # Save results to file
        self._save_results()
        
        return self.results["overall_status"] == "passed"
        
    def _print_final_summary(self):
        """Print final test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("PRODUCTION READINESS TEST SUMMARY")
        logger.info("=" * 60)
        
        logger.info(f"\nOverall Status: {self.results['overall_status'].upper()}")
        logger.info(f"Total Duration: {self.results['total_duration']:.2f}s")
        
        logger.info("\nTest Results:")
        for test_name, test_result in self.results["tests"].items():
            status_icon = "✓" if test_result["status"] in ["passed", "warning"] else "✗"
            logger.info(
                f"  {status_icon} {test_name}: {test_result['status']} "
                f"({test_result['duration']:.2f}s)"
            )
            
        if self.results["overall_status"] == "passed":
            logger.info("\n🎉 All production readiness tests PASSED!")
            logger.info("The system is ready for deployment.")
        else:
            logger.error("\n❌ Production readiness tests FAILED!")
            logger.error("Please fix the issues before deploying.")
            
    def _save_results(self):
        """Save test results to file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"production_test_results_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
            
        logger.info(f"\nTest results saved to: {filename}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run production readiness tests")
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run only smoke tests"
    )
    parser.add_argument(
        "--heartbeat-only",
        action="store_true",
        help="Run only heartbeat checks"
    )
    
    args = parser.parse_args()
    
    # Print header
    logger.info("\n" + "=" * 60)
    logger.info("LEADFACTORY PRODUCTION READINESS TESTS")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.utcnow().isoformat()}")
    
    # Run tests
    runner = ProductionTestRunner()
    success = await runner.run_all_tests(
        smoke_only=args.smoke_only,
        heartbeat_only=args.heartbeat_only
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())