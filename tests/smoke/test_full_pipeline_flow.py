"""
Smoke Test for Full Pipeline Flow - P0-002

Tests that the full pipeline flow processes a business end-to-end and produces
the expected outputs: PDF report, email record, and database entries.

Acceptance Criteria:
- Generates PDF within 90 seconds
- Creates email record in database
- Returns JSON with score and report path
"""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Import the flow we're testing
from flows.full_pipeline_flow import full_pipeline_flow, run_pipeline


@pytest.mark.xfail(reason="Full pipeline flow not fully implemented - missing components")
class TestFullPipelineFlow:
    """Test the complete end-to-end pipeline flow"""

    @pytest.fixture
    def mock_coordinators(self):
        """Mock all coordinator dependencies"""
        with patch('flows.full_pipeline_flow.SourcingCoordinator') as mock_sourcing, \
             patch('flows.full_pipeline_flow.AssessmentCoordinator') as mock_assessment, \
             patch('flows.full_pipeline_flow.ScoringEngine') as mock_scorer, \
             patch('flows.full_pipeline_flow.ReportGenerator') as mock_report, \
             patch('flows.full_pipeline_flow.AdvancedContentGenerator') as mock_personalizer, \
             patch('flows.full_pipeline_flow.DeliveryManager') as mock_email:

            # Configure sourcing coordinator
            mock_sourcing_instance = AsyncMock()
            mock_sourcing_instance.source_single_business = AsyncMock(return_value={
                "name": "Test Business",
                "email": "test@business.com",
                "phone": "555-1234",
                "address": "123 Test St",
                "industry": "Technology"
            })
            mock_sourcing.return_value = mock_sourcing_instance

            # Configure assessment coordinator
            mock_assessment_instance = AsyncMock()
            mock_assessment_instance.assess_business = AsyncMock(return_value={
                "pagespeed": {
                    "performance_score": 85,
                    "fcp": 1.2,
                    "lcp": 2.5,
                    "cls": 0.1,
                    "tti": 3.8
                },
                "tech_stack": {
                    "cms": "WordPress",
                    "analytics": ["Google Analytics"],
                    "frameworks": ["React"],
                    "hosting": "AWS"
                },
                "seo_basics": {
                    "has_title": True,
                    "has_meta_description": True,
                    "has_h1": True,
                    "mobile_friendly": True
                },
                "insights": [
                    "Strong performance metrics",
                    "Modern tech stack detected",
                    "SEO fundamentals in place"
                ],
                "summary": "Well-optimized website with good performance"
            })
            mock_assessment.return_value = mock_assessment_instance

            # Configure scoring engine
            mock_scorer_instance = AsyncMock()
            mock_scorer_instance.calculate_score = AsyncMock(return_value={
                "overall_score": 78,
                "tier": "standard",
                "breakdown": {
                    "performance": 85,
                    "technical": 75,
                    "seo": 70,
                    "user_experience": 80
                },
                "recommendations": [
                    "Improve page load time",
                    "Add structured data",
                    "Enhance mobile experience"
                ]
            })
            mock_scorer.return_value = mock_scorer_instance

            # Configure report generator
            mock_report_instance = AsyncMock()
            test_report_path = "/tmp/test_report.pdf"
            mock_report_instance.generate_report = AsyncMock(return_value=test_report_path)
            mock_report.return_value = mock_report_instance

            # Configure personalization generator
            mock_personalizer_instance = AsyncMock()
            mock_personalizer_instance.generate_email_content = AsyncMock(return_value={
                "subject": "Your Website Assessment Report - Score: 78/100",
                "body": "Dear Business Owner, Your website scored 78/100..."
            })
            mock_personalizer.return_value = mock_personalizer_instance

            # Configure delivery manager
            mock_email_instance = AsyncMock()
            mock_email_instance.deliver_report = AsyncMock(return_value={
                "message_id": "test_message_123",
                "status": "sent"
            })
            mock_email.return_value = mock_email_instance

            yield {
                'sourcing': mock_sourcing_instance,
                'assessment': mock_assessment_instance,
                'scorer': mock_scorer_instance,
                'report': mock_report_instance,
                'personalizer': mock_personalizer_instance,
                'email': mock_email_instance
            }

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, mock_coordinators):
        """
        Test successful end-to-end pipeline execution
        
        Acceptance Criteria: Must process a business from targeting through delivery
        """
        # Test URL
        test_url = "https://example-business.com"

        # Start timing
        start_time = time.time()

        # Run the pipeline
        result = await run_pipeline(test_url)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Verify acceptance criteria
        assert result["status"] == "complete", "Pipeline should complete successfully"
        assert result["score"] > 0, "Should have a valid score"
        assert result["report_path"] is not None, "Should generate a report path"
        assert result["email_sent"] == True, "Should send email"
        assert execution_time < 90, f"Should complete within 90 seconds, took {execution_time:.2f}s"

        # Verify all stages were executed
        assert result["stages_completed"] == 6

        # Verify coordinators were called correctly
        mock_coordinators['sourcing'].source_single_business.assert_called_once()
        mock_coordinators['assessment'].assess_business.assert_called_once()
        mock_coordinators['scorer'].calculate_score.assert_called_once()
        mock_coordinators['report'].generate_report.assert_called_once()
        mock_coordinators['personalizer'].generate_email_content.assert_called_once()
        mock_coordinators['email'].deliver_report.assert_called_once()

        # Verify result structure
        assert "business_id" in result
        assert "execution_time_seconds" in result
        assert "timestamp" in result
        assert "full_data" in result

        # Verify full_data contains all intermediate results
        full_data = result["full_data"]
        assert full_data["targeted_at"] is not None
        assert full_data["sourced_at"] is not None
        assert full_data["assessed_at"] is not None
        assert full_data["scored_at"] is not None
        assert full_data["report_generated_at"] is not None
        assert full_data["email_sent_at"] is not None

    @pytest.mark.asyncio
    async def test_pipeline_json_output(self, mock_coordinators):
        """
        Test that pipeline returns valid JSON with required fields
        
        Acceptance Criteria: JSON contains "score" and a PDF path
        """
        test_url = "https://test-business.com"

        # Run pipeline
        result = await run_pipeline(test_url)

        # Verify JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None

        # Parse back to verify structure
        parsed = json.loads(json_str)

        # Verify required fields per acceptance criteria
        assert "score" in parsed, "JSON must contain 'score' field"
        assert parsed["score"] == 78, "Score should match mock value"

        assert "report_path" in parsed, "JSON must contain 'report_path' field"
        assert parsed["report_path"] == "/tmp/test_report.pdf", "Report path should match mock"

    @pytest.mark.asyncio
    async def test_pipeline_with_assessment_failure(self, mock_coordinators):
        """Test pipeline behavior when assessment fails but continues"""
        # Make assessment fail
        mock_coordinators['assessment'].assess_business.side_effect = Exception("Assessment API error")

        test_url = "https://failing-assessment.com"
        result = await run_pipeline(test_url)

        # Pipeline should continue with default score
        assert result["status"] == "complete"
        assert result["score"] == 50  # Default score on assessment failure
        assert result["score_tier"] == "basic"

        # Other stages should still complete
        assert result["report_path"] is not None
        assert result["email_sent"] == True

    @pytest.mark.asyncio
    async def test_pipeline_with_email_failure(self, mock_coordinators):
        """Test pipeline behavior when email fails (non-critical)"""
        # Make email sending fail
        mock_coordinators['email'].deliver_report.side_effect = Exception("SMTP error")

        test_url = "https://email-fail.com"
        result = await run_pipeline(test_url)

        # Pipeline should still complete successfully
        assert result["status"] == "complete"
        assert result["email_sent"] == False
        assert result["full_data"]["delivery_status"] == "failed"
        assert "delivery_error" in result["full_data"]

        # Other stages should have completed
        assert result["score"] > 0
        assert result["report_path"] is not None

    @pytest.mark.asyncio
    async def test_pipeline_critical_failure(self, mock_coordinators):
        """Test pipeline behavior on critical failure (report generation)"""
        # Make report generation fail
        mock_coordinators['report'].generate_report.side_effect = Exception("PDF generation failed")

        test_url = "https://critical-fail.com"
        result = await run_pipeline(test_url)

        # Pipeline should fail
        assert result["status"] == "failed"
        assert "error" in result
        assert "PDF generation failed" in result["error"]

        # Partial data should be available
        assert "partial_data" in result
        assert result["partial_data"]["score"] > 0  # Score was calculated before failure

    @pytest.mark.asyncio
    async def test_pipeline_performance(self, mock_coordinators):
        """Test pipeline completes within performance requirements"""
        # Add delays to simulate real processing
        async def delayed_assessment(*args, **kwargs):
            await asyncio.sleep(2)  # Simulate 2 second assessment
            return mock_coordinators['assessment'].assess_business.return_value

        mock_coordinators['assessment'].assess_business = delayed_assessment

        test_url = "https://performance-test.com"

        start_time = time.time()
        result = await run_pipeline(test_url)
        execution_time = time.time() - start_time

        # Verify completes within 90 seconds even with delays
        assert execution_time < 90, f"Pipeline took {execution_time:.2f}s, should be < 90s"
        assert result["status"] == "complete"

        # Verify execution time is tracked
        assert result["execution_time_seconds"] > 2  # At least the assessment delay
        assert result["execution_time_seconds"] < 90

    def test_pipeline_flow_decorated(self):
        """Test that flow is properly decorated with Prefect"""
        # Verify the flow has Prefect attributes when available
        if hasattr(full_pipeline_flow, '__prefect_flow__'):
            assert full_pipeline_flow.name == "full_pipeline"
            assert full_pipeline_flow.timeout_seconds == 1800  # 30 minutes
            assert hasattr(full_pipeline_flow, 'description')


# Integration test that would run against real services
@pytest.mark.integration
@pytest.mark.skip(reason="Requires real services - run manually")
async def test_real_pipeline_integration():
    """
    Integration test against real services (marked skip by default)
    
    Run with: pytest -m integration tests/smoke/test_full_pipeline_flow.py::test_real_pipeline_integration
    """
    # Use a real test URL
    test_url = "https://www.example.com"

    # Set up test environment
    os.environ["USE_STUBS"] = "true"  # Use stub services

    start_time = time.time()
    result = await run_pipeline(test_url)
    execution_time = time.time() - start_time

    print(f"\nPipeline completed in {execution_time:.2f} seconds")
    print(f"Result: {json.dumps(result, indent=2)}")

    assert result["status"] == "complete"
    assert execution_time < 90
    assert result["score"] > 0
    assert Path(result["report_path"]).exists()


if __name__ == "__main__":
    # Allow running specific tests from command line
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "integration":
        asyncio.run(test_real_pipeline_integration())
    else:
        pytest.main([__file__, "-v"])
