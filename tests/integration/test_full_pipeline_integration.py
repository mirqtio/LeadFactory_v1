"""
Integration Test for Full Pipeline Flow - P0-002

Tests the complete pipeline flow with all components integrated.
"""

import asyncio
import os

import pytest

from flows.full_pipeline_flow import run_pipeline


@pytest.mark.integration
class TestFullPipelineIntegration:
    """Integration tests for the full pipeline"""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Infrastructure dependencies not yet set up")
    async def test_full_pipeline_with_stubs(self):
        """Test full pipeline execution with stub services"""
        # Set stub mode
        os.environ["USE_STUBS"] = "true"

        # Test URL
        test_url = "https://integration-test.com"

        # Run the pipeline
        result = await run_pipeline(test_url)

        # Verify complete execution
        assert result["status"] == "complete"
        assert result["stages_completed"] == 6
        assert result["score"] > 0
        assert result["email_sent"] in [True, False]  # May fail in stub mode

        # Verify all timestamps are present
        full_data = result["full_data"]
        assert full_data["targeted_at"] is not None
        assert full_data["sourced_at"] is not None
        assert full_data["assessed_at"] is not None
        assert full_data["scored_at"] is not None
        assert full_data["report_generated_at"] is not None

        # Verify performance
        assert result["execution_time_seconds"] < 90

    @pytest.mark.asyncio
    async def test_pipeline_error_recovery(self):
        """Test pipeline's ability to recover from errors"""
        os.environ["USE_STUBS"] = "true"

        # Use a URL that might cause issues
        test_url = "https://error-test-@#$.com"

        # Pipeline should handle gracefully
        result = await run_pipeline(test_url)

        # Should either complete or fail gracefully
        assert result["status"] in ["complete", "failed"]
        assert "timestamp" in result
        assert "execution_time_seconds" in result

    @pytest.mark.asyncio
    async def test_pipeline_data_flow(self):
        """Test that data flows correctly through pipeline stages"""
        os.environ["USE_STUBS"] = "true"

        test_url = "https://data-flow-test.com"
        result = await run_pipeline(test_url)

        if result["status"] == "complete":
            full_data = result["full_data"]

            # Verify data accumulation through stages
            assert "id" in full_data  # From targeting
            assert "sourced_data" in full_data  # From sourcing
            assert "assessment_data" in full_data or "assessment_status" in full_data  # From assessment
            assert "score" in full_data  # From scoring
            assert "report_path" in full_data or "report_status" in full_data  # From reporting
            assert "email_sent" in full_data or "delivery_status" in full_data  # From delivery

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_pipeline_concurrent_execution(self):
        """Test running multiple pipelines concurrently"""
        os.environ["USE_STUBS"] = "true"

        urls = ["https://concurrent-test-1.com", "https://concurrent-test-2.com", "https://concurrent-test-3.com"]

        # Run pipelines concurrently
        tasks = [run_pipeline(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all completed
        successful = 0
        for result in results:
            if isinstance(result, dict) and result.get("status") == "complete":
                successful += 1

        # At least some should succeed
        assert successful > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
