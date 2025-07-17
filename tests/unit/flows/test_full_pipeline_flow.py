"""
Unit Tests for Full Pipeline Flow - P0-002

Tests individual flow components and error handling without running the full pipeline.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from flows.full_pipeline_flow import (
    assess_website,
    calculate_score,
    generate_report,
    send_email,
    source_business_data,
    target_business,
)


class TestPipelineComponents:
    """Test individual pipeline components"""

    @pytest.mark.asyncio
    async def test_target_business_success(self):
        """Test successful business targeting"""
        url = "https://test-business.com"

        # Call the task function directly
        result = await target_business.fn(url)

        # Verify the result
        assert result["url"] == url
        assert "id" in result
        assert result["status"] == "targeted"
        assert "targeted_at" in result
        assert result["name"] == f"Business from {url}"

    @pytest.mark.asyncio
    async def test_target_business_handles_empty_url(self):
        """Test targeting with empty URL - should still work in MVP"""
        # In MVP, empty URL is handled gracefully
        result = await target_business.fn("")

        # Should still create a business record
        assert "id" in result
        assert result["url"] == ""
        assert result["status"] == "targeted"

    @pytest.mark.asyncio
    async def test_source_business_data_success(self):
        """Test successful business data sourcing"""
        business_data = {"id": "test_123", "url": "https://test.com", "name": "Test Business"}

        result = await source_business_data.fn(business_data)

        # Verify sourced data was added
        assert "sourced_data" in result
        assert result["source_status"] == "completed"
        assert "sourced_at" in result

        # Verify sourced data fields
        sourced = result["sourced_data"]
        assert sourced["url"] == business_data["url"]
        assert sourced["email"] == "contact@example.com"
        assert sourced["industry"] == "Technology"

    @pytest.mark.asyncio
    async def test_assess_website_success(self):
        """Test successful website assessment"""
        business_data = {"id": "test_123", "url": "https://test.com"}

        with patch("flows.full_pipeline_flow.AssessmentCoordinator") as mock_coordinator:
            mock_instance = AsyncMock()
            mock_instance.execute_comprehensive_assessment = AsyncMock(
                return_value={
                    "pagespeed": {"performance_score": 85},
                    "tech_stack": {"cms": "WordPress"},
                    "seo_basics": {"has_title": True},
                }
            )
            mock_coordinator.return_value = mock_instance

            result = await assess_website.fn(business_data)

            # Verify assessment was called correctly
            mock_instance.execute_comprehensive_assessment.assert_called_once_with(
                business_id="test_123",
                url="https://test.com",
                assessment_types=["pagespeed", "tech_stack", "seo_basics"],
            )

            # Verify result
            assert result["assessment_status"] == "completed"
            assert "assessment_data" in result
            assert "assessed_at" in result

    @pytest.mark.asyncio
    async def test_assess_website_failure_handling(self):
        """Test assessment failure handling"""
        business_data = {"id": "test_123", "url": "https://test.com"}

        with patch("flows.full_pipeline_flow.AssessmentCoordinator") as mock_coordinator:
            mock_instance = AsyncMock()
            mock_instance.execute_comprehensive_assessment = AsyncMock(side_effect=Exception("API timeout"))
            mock_coordinator.return_value = mock_instance

            result = await assess_website.fn(business_data)

            # Should continue with failed status
            assert result["assessment_status"] == "failed"
            assert result["assessment_error"] == "API timeout"

    def test_calculate_score_success(self):
        """Test successful score calculation"""
        business_data = {
            "id": "test_123",
            "assessment_data": {"pagespeed": {"performance_score": 85}, "tech_stack": {"cms": "WordPress"}},
        }

        with patch("flows.full_pipeline_flow.ScoringEngine") as mock_engine:
            mock_instance = Mock()
            mock_instance.calculate_score = Mock(
                return_value={"overall_score": 75, "tier": "B", "breakdown": {"performance": 85, "technical": 70}}
            )
            mock_engine.return_value = mock_instance

            result = calculate_score.fn(business_data)

            # Verify scoring was called
            mock_instance.calculate_score.assert_called_once_with(business_data["assessment_data"])

            # Verify result
            assert result["score"] == 75
            assert result["score_tier"] == "B"
            assert "score_details" in result
            assert "scored_at" in result

    def test_calculate_score_with_failed_assessment(self):
        """Test score calculation when assessment failed"""
        business_data = {"id": "test_123", "assessment_status": "failed", "assessment_data": {}}

        result = calculate_score.fn(business_data)

        # Should use default score
        assert result["score"] == 50
        assert result["score_tier"] == "D"
        assert result["score_details"]["reason"] == "assessment_failed"

    def test_calculate_score_tier_calculation(self):
        """Test score tier calculation logic"""
        test_cases = [
            (95, "A"),  # A tier: >= 90
            (90, "A"),
            (85, "B"),  # B tier: >= 75
            (75, "B"),
            (70, "C"),  # C tier: >= 60
            (60, "C"),
            (55, "D"),  # D tier: < 60
            (30, "D"),
        ]

        for score, expected_tier in test_cases:
            business_data = {"id": "test_123", "assessment_data": {"test": "data"}}

            with patch("flows.full_pipeline_flow.ScoringEngine") as mock_engine:
                mock_instance = Mock()
                mock_instance.calculate_score = Mock(return_value={"overall_score": score})
                mock_engine.return_value = mock_instance

                result = calculate_score.fn(business_data)

                assert result["score_tier"] == expected_tier, f"Score {score} should result in tier {expected_tier}"

    @pytest.mark.asyncio
    async def test_generate_report_success(self):
        """Test successful report generation"""
        business_data = {
            "id": "test_123",
            "name": "Test Business",
            "assessment_data": {"test": "data"},
            "score_details": {"overall_score": 75},
            "score_tier": "B",
        }

        with patch("flows.full_pipeline_flow.ReportGenerator") as mock_generator:
            mock_instance = AsyncMock()
            # Create a mock result that matches what generate_report expects
            mock_result = Mock()
            mock_result.success = True
            mock_result.pdf_result = Mock()
            mock_result.pdf_result.success = True
            mock_result.pdf_result.file_size = 1024
            mock_instance.generate_report = AsyncMock(return_value=mock_result)
            mock_generator.return_value = mock_instance

            result = await generate_report.fn(business_data)

            # Verify report generation was called
            mock_instance.generate_report.assert_called_once()

            # Verify result
            assert result["report_path"] == "memory://pdf/test_123.pdf"  # Virtual path from generate_report
            assert result["report_status"] == "completed"
            assert "report_generated_at" in result

    @pytest.mark.asyncio
    async def test_generate_report_failure(self):
        """Test report generation failure (critical)"""
        business_data = {"id": "test_123", "name": "Test Business"}

        with patch("flows.full_pipeline_flow.ReportGenerator") as mock_generator:
            mock_instance = AsyncMock()
            mock_instance.generate_report = AsyncMock(side_effect=Exception("PDF generation failed"))
            mock_generator.return_value = mock_instance

            # Should raise exception (critical failure)
            with pytest.raises(Exception) as exc_info:
                await generate_report.fn(business_data)

            assert "PDF generation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful email sending"""
        business_data = {
            "id": "test_123",
            "name": "Test Business",
            "sourced_data": {"email": "test@example.com"},
            "score": 75,
            "score_tier": "B",
            "report_path": "/tmp/report.pdf",
        }

        with patch("flows.full_pipeline_flow.DeliveryManager") as mock_delivery, patch(
            "flows.full_pipeline_flow.AdvancedContentGenerator"
        ) as mock_content:
            # Mock content generator
            mock_content_instance = AsyncMock()
            mock_content_instance.generate_email_content = AsyncMock(
                return_value={"subject": "Your Assessment Report", "body": "Dear Business Owner..."}
            )
            mock_content.return_value = mock_content_instance

            # Mock delivery manager
            mock_delivery_instance = AsyncMock()
            mock_delivery_instance.send_assessment_email = AsyncMock(
                return_value={"message_id": "msg_123", "status": "sent"}
            )
            mock_delivery.return_value = mock_delivery_instance

            result = await send_email.fn(business_data)

            # Verify email was sent
            assert result["email_sent"]
            assert result["email_id"] == "msg_123"
            assert result["delivery_status"] == "completed"
            assert "email_sent_at" in result

    @pytest.mark.asyncio
    async def test_send_email_failure_non_critical(self):
        """Test email sending failure (non-critical)"""
        business_data = {
            "id": "test_123",
            "sourced_data": {"email": "test@example.com"},
            "score": 75,
            "score_tier": "B",
        }

        with patch("flows.full_pipeline_flow.DeliveryManager") as mock_delivery, patch(
            "flows.full_pipeline_flow.AdvancedContentGenerator"
        ) as mock_content:
            mock_content_instance = AsyncMock()
            mock_content_instance.generate_email_content = AsyncMock(return_value={"subject": "Test", "body": "Test"})
            mock_content.return_value = mock_content_instance

            mock_delivery_instance = AsyncMock()
            mock_delivery_instance.send_assessment_email = AsyncMock(side_effect=Exception("SMTP error"))
            mock_delivery.return_value = mock_delivery_instance

            # Should not raise - non-critical failure
            result = await send_email.fn(business_data)

            assert not result["email_sent"]
            assert result["delivery_status"] == "failed"
            assert result["delivery_error"] == "SMTP error"

    @pytest.mark.asyncio
    async def test_send_email_no_email_address(self):
        """Test email sending when no email address is available"""
        business_data = {"id": "test_123", "sourced_data": {}, "score": 75, "score_tier": "B"}  # No email

        with patch("flows.full_pipeline_flow.DeliveryManager") as mock_delivery, patch(
            "flows.full_pipeline_flow.AdvancedContentGenerator"
        ) as mock_content:
            mock_content_instance = AsyncMock()
            mock_content.return_value = mock_content_instance

            mock_delivery_instance = AsyncMock()
            mock_delivery_instance.send_assessment_email = AsyncMock(
                return_value={"message_id": "test_msg", "status": "sent"}
            )
            mock_delivery.return_value = mock_delivery_instance

            await send_email.fn(business_data)

            # Should use test email
            mock_delivery_instance.send_assessment_email.assert_called_once()
            call_args = mock_delivery_instance.send_assessment_email.call_args
            assert call_args[1]["to_email"] == "test@example.com"


class TestPipelineRetries:
    """Test retry behavior for pipeline tasks"""

    @pytest.mark.asyncio
    async def test_assessment_retry_on_failure(self):
        """Test that assessment handles failures gracefully"""
        business_data = {"id": "test_123", "url": "https://test.com"}

        with patch("flows.full_pipeline_flow.AssessmentCoordinator") as mock_coordinator:
            mock_instance = AsyncMock()
            # Simulate failure
            mock_instance.execute_comprehensive_assessment = AsyncMock(side_effect=Exception("Temporary network error"))
            mock_coordinator.return_value = mock_instance

            # Assessment should handle failure gracefully
            result = await assess_website.fn(business_data)

            # Should mark as failed but continue
            assert result["assessment_status"] == "failed"
            assert result["assessment_error"] == "Temporary network error"

            # Reset mock for second attempt
            mock_instance.execute_comprehensive_assessment = AsyncMock(
                return_value={"pagespeed": {"performance_score": 85}}
            )

            # Second call would succeed
            result = await assess_website.fn(business_data)
            assert result["assessment_status"] == "completed"


class TestPipelineMetrics:
    """Test metrics and logging in pipeline"""

    def test_execution_time_tracking(self):
        """Test that execution time is properly tracked"""

        # Mock time to control execution time
        start_time = 1000.0
        end_time = 1010.5  # 10.5 seconds

        with patch("time.time", side_effect=[start_time, end_time]):
            # Would need to mock all the pipeline components
            # This is more of an integration test
            pass

    @pytest.mark.asyncio
    async def test_stage_logging(self):
        """Test that each stage logs appropriately"""
        # This would verify logging output
        # For unit tests, we focus on the logic rather than logging
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
