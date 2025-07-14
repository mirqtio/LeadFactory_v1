"""
Test PageSpeed Assessor - Task 031

Comprehensive tests for PageSpeed assessment functionality.
Tests all acceptance criteria:
- Core Web Vitals extracted
- All scores captured
- Issue extraction works
- Mobile-first approach
"""
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

sys.path.insert(0, "/app")  # noqa: E402

from d3_assessment.models import AssessmentResult  # noqa: E402
from d3_assessment.pagespeed import PageSpeedAssessorLegacy as PageSpeedAssessor  # noqa: E402
from d3_assessment.pagespeed import PageSpeedBatchAssessor
from d3_assessment.types import AssessmentStatus, AssessmentType  # noqa: E402


class TestTask031AcceptanceCriteria:
    """Test that Task 031 meets all acceptance criteria"""

    @pytest.fixture
    def mock_pagespeed_result(self):
        """Mock PageSpeed API result"""
        return {
            "lighthouseResult": {
                "lighthouseVersion": "10.0.0",
                "userAgent": ("Mozilla/5.0 (Linux; Android 11; Pixel 4) " "AppleWebKit/537.36"),
                "categories": {
                    "performance": {"score": 0.85},
                    "accessibility": {"score": 0.92},
                    "best-practices": {"score": 0.88},
                    "seo": {"score": 0.95},
                    "pwa": {"score": 0.30},
                },
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.8,
                        "numericValue": 2500,
                        "displayValue": "2.5 s",
                        "description": (
                            "Largest Contentful Paint marks the time at " "which the largest text or image is painted."
                        ),
                    },
                    "max-potential-fid": {
                        "score": 0.9,
                        "numericValue": 50,
                        "displayValue": "50 ms",
                        "description": ("The maximum potential First Input Delay."),
                    },
                    "cumulative-layout-shift": {
                        "score": 0.95,
                        "numericValue": 0.1,
                        "displayValue": "0.1",
                        "description": (
                            "Cumulative Layout Shift measures the movement " "of visible elements within the viewport."
                        ),
                    },
                    "first-contentful-paint": {
                        "score": 0.85,
                        "numericValue": 1200,
                        "displayValue": "1.2 s",
                        "description": (
                            "First Contentful Paint marks the time at " "which the first text or image is painted."
                        ),
                    },
                    "speed-index": {
                        "score": 0.8,
                        "numericValue": 3200,
                        "displayValue": "3.2 s",
                        "description": (
                            "Speed Index shows how quickly the contents " "of a page are visibly populated."
                        ),
                    },
                    "interactive": {
                        "score": 0.75,
                        "numericValue": 4100,
                        "displayValue": "4.1 s",
                        "description": (
                            "Time to interactive is the amount of time it "
                            "takes for the page to become fully interactive."
                        ),
                    },
                    "total-blocking-time": {
                        "score": 0.7,
                        "numericValue": 150,
                        "displayValue": "150 ms",
                        "description": ("Sum of all time periods between FCP and " "Time to Interactive."),
                    },
                    "unused-css-rules": {
                        "score": 0.5,
                        "title": "Reduce unused CSS",
                        "description": "Remove dead rules from stylesheets.",
                        "details": {"overallSavingsMs": 1200},
                    },
                    "render-blocking-resources": {
                        "score": 0.3,
                        "title": "Eliminate render-blocking resources",
                        "description": ("Resources are blocking the first paint " "of your page."),
                        "details": {"overallSavingsMs": 800},
                    },
                    "uses-text-compression": {
                        "score": 0.8,
                        "title": "Enable text compression",
                        "description": ("Text-based resources should be served " "with compression."),
                        "details": {},
                    },
                },
            },
            "analysisUTCTimestamp": "2025-06-09T00:45:00.000Z",
        }

    @pytest.fixture
    def assessor(self):
        """Create PageSpeed assessor instance"""
        return PageSpeedAssessor(api_key="test-api-key")

    @pytest.mark.asyncio
    async def test_core_web_vitals_extracted(self, assessor, mock_pagespeed_result):
        """
        Test that Core Web Vitals are properly extracted

        Acceptance Criteria: Core Web Vitals extracted
        """
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                assessment = await assessor.assess_website(business_id="test-business-id", url="https://example.com")

                # Verify Core Web Vitals are extracted
                assert assessment.largest_contentful_paint == 2500  # LCP
                # FID (from max-potential-fid)
                assert assessment.first_input_delay == 50
                assert assessment.cumulative_layout_shift == 0.1  # CLS
                assert assessment.first_contentful_paint == 1200  # FCP
                assert assessment.speed_index == 3200  # Speed Index
                assert assessment.time_to_interactive == 4100  # TTI
                assert assessment.total_blocking_time == 150  # TBT

                print("✓ Core Web Vitals extracted correctly")

    @pytest.mark.asyncio
    async def test_all_scores_captured(self, assessor, mock_pagespeed_result):
        """
        Test that all Lighthouse scores are captured

        Acceptance Criteria: All scores captured
        """
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                assessment = await assessor.assess_website(business_id="test-business-id", url="https://example.com")

                # Verify all scores are captured (converted to 0-100 scale)
                assert assessment.performance_score == 85  # 0.85 * 100
                assert assessment.accessibility_score == 92  # 0.92 * 100
                assert assessment.best_practices_score == 88  # 0.88 * 100
                assert assessment.seo_score == 95  # 0.95 * 100
                assert assessment.pwa_score == 30  # 0.30 * 100

                print("✓ All scores captured correctly")

    @pytest.mark.asyncio
    async def test_issue_extraction_works(self, assessor, mock_pagespeed_result):
        """
        Test that performance issues are properly extracted

        Acceptance Criteria: Issue extraction works
        """
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                assessment = await assessor.assess_website(business_id="test-business-id", url="https://example.com")

                # Verify JSONB data contains extracted issues
                pagespeed_data = assessment.pagespeed_data
                assert "mobile" in pagespeed_data

                # Test opportunity extraction directly
                opportunities = assessor._extract_opportunities(mock_pagespeed_result)

                # Should extract opportunities with savings
                # unused-css-rules and render-blocking-resources
                assert len(opportunities) == 2

                # Check high-impact opportunity first (sorted by savings)
                high_impact = opportunities[0]
                # 1200ms savings
                assert high_impact["id"] == "unused-css-rules"
                assert high_impact["savings_ms"] == 1200
                assert high_impact["impact"] == "high"  # >= 1000ms
                assert high_impact["title"] == "Reduce unused CSS"

                # Check medium-impact opportunity
                medium_impact = opportunities[1]
                # 800ms savings
                assert medium_impact["id"] == "render-blocking-resources"
                assert medium_impact["savings_ms"] == 800
                assert medium_impact["impact"] == "medium"  # >= 500ms

                # Test diagnostic extraction
                diagnostics = assessor._extract_diagnostics(mock_pagespeed_result)
                # uses-text-compression (no savings)
                assert len(diagnostics) == 1

                diagnostic = diagnostics[0]
                assert diagnostic["id"] == "uses-text-compression"
                assert diagnostic["impact"] == "informational"

                print("✓ Issue extraction works correctly")

    @pytest.mark.asyncio
    async def test_mobile_first_approach(self, assessor, mock_pagespeed_result):
        """
        Test that mobile-first approach is implemented

        Acceptance Criteria: Mobile-first approach
        """
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                # Verify mobile_first is enabled by default
                assert assessor.mobile_first is True

                assessment = await assessor.assess_website(business_id="test-business-id", url="https://example.com")

                # Verify mobile analysis was called first
                calls = mock_analyze.call_args_list
                assert len(calls) == 2  # mobile + desktop

                # First call should be mobile
                mobile_call = calls[0][1]  # kwargs
                assert mobile_call["strategy"] == "mobile"
                assert mobile_call["url"] == "https://example.com"

                # Second call should be desktop
                desktop_call = calls[1][1]  # kwargs
                assert desktop_call["strategy"] == "desktop"

                # Verify mobile-first flag in stored data
                pagespeed_data = assessment.pagespeed_data
                assert pagespeed_data["mobile_first"] is True
                assert "mobile" in pagespeed_data
                assert "desktop" in pagespeed_data

                # Scores should come from mobile analysis (mobile-first)
                mobile_categories = mock_pagespeed_result["lighthouseResult"]["categories"]
                assert assessment.performance_score == int(mobile_categories["performance"]["score"] * 100)

                print("✓ Mobile-first approach implemented correctly")

    @pytest.mark.asyncio
    async def test_mobile_only_assessment(self, assessor, mock_pagespeed_result):
        """Test assessment with mobile-only (no desktop)"""
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                assessment = await assessor.assess_website(
                    business_id="test-business-id",
                    url="https://example.com",
                    include_desktop=False,
                )

                # Should only call mobile analysis
                assert mock_analyze.call_count == 1
                mobile_call = mock_analyze.call_args_list[0][1]
                assert mobile_call["strategy"] == "mobile"

                # Desktop data should be None
                pagespeed_data = assessment.pagespeed_data
                assert pagespeed_data["desktop"] is None
                assert pagespeed_data["mobile"] is not None

                print("✓ Mobile-only assessment works")

    @pytest.mark.asyncio
    async def test_assessment_cost_tracking(self, assessor, mock_pagespeed_result):
        """Test that assessment costs are properly tracked"""
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                # $0.004 per request
                mock_cost.return_value = Decimal("0.004")

                assessment = await assessor.assess_website(business_id="test-business-id", url="https://example.com")

                # Should track cost for both mobile and desktop
                # 2 requests * $0.004
                assert assessment.total_cost_usd == Decimal("0.008")

                print("✓ Assessment cost tracking works")

    @pytest.mark.asyncio
    async def test_error_handling(self, assessor):
        """Test proper error handling and failed assessment creation"""
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                await assessor.assess_website(business_id="test-business-id", url="https://example.com")

            print("✓ Error handling works correctly")

    def test_impact_categorization(self, assessor):
        """Test performance impact categorization"""
        # High impact (>= 1000ms)
        assert assessor._categorize_impact(1500) == "high"
        assert assessor._categorize_impact(1000) == "high"

        # Medium impact (>= 500ms, < 1000ms)
        assert assessor._categorize_impact(750) == "medium"
        assert assessor._categorize_impact(500) == "medium"

        # Low impact (< 500ms)
        assert assessor._categorize_impact(300) == "low"
        assert assessor._categorize_impact(0) == "low"

        print("✓ Impact categorization works")

    def test_domain_extraction(self, assessor):
        """Test domain extraction from URLs"""
        assert assessor._extract_domain("https://www.example.com/path") == "example.com"
        assert assessor._extract_domain("https://example.com") == "example.com"
        assert assessor._extract_domain("http://subdomain.example.com") == "subdomain.example.com"

        print("✓ Domain extraction works")

    @pytest.mark.asyncio
    async def test_batch_assessor(self, mock_pagespeed_result):
        """Test batch assessment functionality"""
        batch_assessor = PageSpeedBatchAssessor(api_key="test-key", max_concurrent=2)

        websites = [
            {"business_id": "biz1", "url": "https://example1.com"},
            {"business_id": "biz2", "url": "https://example2.com"},
        ]

        with patch.object(batch_assessor.assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(batch_assessor.assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                results = await batch_assessor.assess_multiple_websites(websites)

                assert len(results) == 2
                assert all(isinstance(result, AssessmentResult) for result in results)
                assert results[0].business_id == "biz1"
                assert results[1].business_id == "biz2"

                print("✓ Batch assessment works")

    @pytest.mark.asyncio
    async def test_comprehensive_assessment_flow(self, assessor, mock_pagespeed_result):
        """Test complete assessment flow with all components"""
        with patch.object(assessor.client, "analyze_url", new_callable=AsyncMock) as mock_analyze:
            with patch.object(assessor.client, "calculate_cost", new_callable=AsyncMock) as mock_cost:
                mock_analyze.return_value = mock_pagespeed_result
                mock_cost.return_value = Decimal("0.00")

                assessment = await assessor.assess_website(
                    business_id="test-business-id",
                    url="https://example.com",
                    session_id="test-session-id",
                )

                # Verify assessment structure
                assert assessment.id is not None
                assert assessment.business_id == "test-business-id"
                assert assessment.session_id == "test-session-id"
                assert assessment.assessment_type == AssessmentType.PAGESPEED
                assert assessment.status == AssessmentStatus.COMPLETED
                assert assessment.url == "https://example.com"
                assert assessment.domain == "example.com"

                # Verify timing
                assert assessment.started_at is not None
                assert assessment.completed_at is not None
                assert assessment.processing_time_ms is not None
                assert assessment.processing_time_ms > 0

                # Verify comprehensive data storage
                assert assessment.pagespeed_data is not None
                assert "mobile" in assessment.pagespeed_data
                assert "desktop" in assessment.pagespeed_data
                assert assessment.pagespeed_data["mobile_first"] is True

                print("✓ Comprehensive assessment flow works")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask031AcceptanceCriteria()

        print("🔍 Running Task 031 PageSpeed Assessor Tests...")
        print()

        try:
            # Create fixtures
            mock_result = test_instance.mock_pagespeed_result()
            assessor = test_instance.assessor()

            # Run all tests
            await test_instance.test_core_web_vitals_extracted(assessor, mock_result)
            await test_instance.test_all_scores_captured(assessor, mock_result)
            await test_instance.test_issue_extraction_works(assessor, mock_result)
            await test_instance.test_mobile_first_approach(assessor, mock_result)
            await test_instance.test_mobile_only_assessment(assessor, mock_result)
            await test_instance.test_assessment_cost_tracking(assessor, mock_result)
            await test_instance.test_error_handling(assessor)
            test_instance.test_impact_categorization(assessor)
            test_instance.test_domain_extraction(assessor)
            await test_instance.test_batch_assessor(mock_result)
            await test_instance.test_comprehensive_assessment_flow(assessor, mock_result)

            print()
            print("🎉 All Task 031 acceptance criteria tests pass!")
            print("   - Core Web Vitals extracted: ✓")
            print("   - All scores captured: ✓")
            print("   - Issue extraction works: ✓")
            print("   - Mobile-first approach: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run async tests
    asyncio.run(run_tests())
