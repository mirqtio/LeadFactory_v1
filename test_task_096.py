#!/usr/bin/env python3
"""
Simple test for Task 096 - Test Pipeline Execution
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.test_pipeline import PipelineTestRunner

async def test_pipeline_script():
    """Test that the pipeline test script works correctly"""
    print("Testing Task 096: Pipeline Test Script")
    
    # Test in dry run mode
    test_runner = PipelineTestRunner(limit=5, dry_run=True)
    
    # Run the test
    success = await test_runner.run_complete_test()
    
    # Generate report
    report = test_runner.generate_test_report()
    
    # Validate key acceptance criteria
    assert success, "Pipeline test should succeed in dry run mode"
    assert report["overall_status"] == "PASS", "Overall status should be PASS"
    
    criteria = report["acceptance_criteria_results"]
    assert criteria["businesses_processed"]["status"] == "PASS", "Should process businesses"
    assert criteria["emails_generated"]["status"] == "PASS", "Should generate emails"
    assert criteria["no_errors_logged"]["status"] == "PASS", "Should have no errors"
    assert criteria["metrics_recorded"]["status"] == "PASS", "Should record metrics"
    
    print("✅ All acceptance criteria passed!")
    print(f"   - Businesses processed: {report['execution_details']['businesses_processed']}")
    print(f"   - Emails generated: {report['execution_details']['emails_generated']}")
    print(f"   - Metrics recorded: {report['execution_details']['metrics_recorded_count']}")
    print(f"   - Execution time: {report['execution_details']['execution_time_seconds']}s")
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_pipeline_script())
    print("🎉 Task 096 test passed!" if result else "❌ Task 096 test failed!")
    sys.exit(0 if result else 1)