"""
Unit tests for Lighthouse assessor

Tests all required functionality:
1. Successful Lighthouse audit execution
2. Timeout handling (30-second timeout)
3. Caching behavior (7-day cache)
4. Fallback on errors
5. Stub mode behavior
6. Feature flag enable_lighthouse
7. All 5 scores are returned (Performance, Accessibility, Best Practices, SEO, PWA)
8. Integration with assessment models
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d3_assessment.assessors.base import AssessmentResult
from d3_assessment.assessors.lighthouse import LighthouseAssessor
from d3_assessment.exceptions import AssessmentTimeoutError
from d3_assessment.models import AssessmentType


class TestLighthouseAssessor:
    """Test suite for Lighthouse assessor"""

    @pytest.fixture
    def assessor(self):
        """Create Lighthouse assessor instance"""
        with tempfile.TemporaryDirectory() as temp_dir:
            assessor = LighthouseAssessor()
            assessor.cache_dir = temp_dir
            yield assessor

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for tests"""
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = False
        return settings

    @pytest.fixture
    def mock_lighthouse_result(self):
        """Mock Lighthouse audit result"""
        return {
            "scores": {"performance": 90, "accessibility": 95, "best-practices": 88, "seo": 92, "pwa": 80},
            "core_web_vitals": {"lcp": 2000, "fid": 80, "cls": 0.05},
            "metrics": {
                "first_contentful_paint": 1000,
                "speed_index": 1800,
                "time_to_interactive": 3000,
                "total_blocking_time": 100,
            },
            "opportunities": [{"id": "unused-css", "title": "Remove unused CSS", "savings_ms": 500}],
            "diagnostics": [{"id": "font-display", "title": "Ensure text remains visible", "score": 0.8}],
            "fetch_time": datetime.utcnow().isoformat(),
            "lighthouse_version": "11.0.0",
            "user_agent": "Mozilla/5.0 Chrome/120.0.0.0",
        }

    @pytest.mark.asyncio
    async def test_successful_lighthouse_audit(self, assessor, mock_settings, mock_lighthouse_result):
        """Test 1: Successful Lighthouse audit execution"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_lighthouse_result) as mock_audit:
                result = await assessor.assess("https://example.com", {})

                # Verify audit was called
                mock_audit.assert_called_once_with("https://example.com")

                # Check result structure
                assert isinstance(result, AssessmentResult)
                assert result.assessment_type == AssessmentType.LIGHTHOUSE
                assert result.status == "completed"
                assert result.error_message is None

                # Check lighthouse data is stored
                assert "lighthouse_json" in result.data
                lighthouse_data = result.data["lighthouse_json"]
                assert lighthouse_data["scores"] == mock_lighthouse_result["scores"]

                # Check metrics are extracted
                assert result.metrics["performance_score"] == 90
                assert result.metrics["accessibility_score"] == 95
                assert result.metrics["best_practices_score"] == 88
                assert result.metrics["seo_score"] == 92
                assert result.metrics["pwa_score"] == 80
                assert result.metrics["lcp_ms"] == 2000
                assert result.metrics["fid_ms"] == 80
                assert result.metrics["cls_score"] == 0.05
                assert result.metrics["mobile_friendly"] is True  # score >= 50

                # Verify cost is 0 (local execution)
                assert result.cost == 0.0

    @pytest.mark.asyncio
    async def test_timeout_handling(self, assessor, mock_settings):
        """Test 2: Timeout handling (30-second timeout)"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Mock audit to take longer than timeout
            async def slow_audit(url):
                await asyncio.sleep(35)  # Longer than 30s timeout
                return {}

            with patch.object(assessor, "_run_lighthouse_audit", side_effect=slow_audit):
                with pytest.raises(AssessmentTimeoutError) as exc_info:
                    await assessor.assess("https://example.com", {})

                assert "timed out after 30s" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_caching_behavior(self, assessor, mock_settings, mock_lighthouse_result):
        """Test 3: Caching behavior (7-day cache)"""
        url = "https://cache-test.com"

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # First call - should run audit and save to cache
            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_lighthouse_result) as mock_audit:
                result1 = await assessor.assess(url, {})
                mock_audit.assert_called_once()

            # Verify cache file exists
            cache_key = assessor._get_cache_key(url)
            cache_file = os.path.join(assessor.cache_dir, f"{cache_key}.json")
            assert os.path.exists(cache_file)

            # Second call - should use cache
            with patch.object(assessor, "_run_lighthouse_audit") as mock_audit:
                result2 = await assessor.assess(url, {})
                mock_audit.assert_not_called()  # Should not run audit

            # Results should be the same
            assert result1.data["lighthouse_json"]["scores"] == result2.data["lighthouse_json"]["scores"]

            # Test cache expiration
            # Modify cache file time to be 8 days old
            old_time = datetime.now() - timedelta(days=8)
            os.utime(cache_file, (old_time.timestamp(), old_time.timestamp()))

            # Third call - cache expired, should run audit again
            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_lighthouse_result) as mock_audit:
                result3 = await assessor.assess(url, {})
                mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_errors(self, assessor, mock_settings):
        """Test 4: Fallback on errors"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Mock audit to raise an error
            with patch.object(assessor, "_run_lighthouse_audit", side_effect=Exception("Audit failed")):
                result = await assessor.assess("https://example.com", {})

                # Should return failed result instead of raising
                assert result.status == "failed"
                assert result.error_message == "Lighthouse audit error: Audit failed"
                assert result.data["lighthouse_json"] == {}
                assert result.cost == 0.0

    @pytest.mark.asyncio
    async def test_stub_mode_behavior(self, assessor):
        """Test 5: Stub mode behavior"""
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = True
        mock_settings.use_stubs = True

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Should not call actual audit in stub mode
            with patch.object(assessor, "_run_lighthouse_audit") as mock_audit:
                result = await assessor.assess("https://example.com", {})
                mock_audit.assert_not_called()

            # Check stub data is returned
            assert result.status == "completed"
            lighthouse_data = result.data["lighthouse_json"]
            assert lighthouse_data["is_stub"] is True

            # Verify all scores are present
            scores = lighthouse_data["scores"]
            assert scores["performance"] == 85
            assert scores["accessibility"] == 92
            assert scores["best-practices"] == 88
            assert scores["seo"] == 90
            assert scores["pwa"] == 75

            # Verify Core Web Vitals
            cwv = lighthouse_data["core_web_vitals"]
            assert cwv["lcp"] == 2500
            assert cwv["fid"] == 100
            assert cwv["cls"] == 0.1

    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self, assessor):
        """Test 6: Feature flag enable_lighthouse"""
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = False

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            result = await assessor.assess("https://example.com", {})

            # Should return skipped result
            assert result.status == "skipped"
            assert result.error_message == "Lighthouse feature is disabled"
            assert result.data["lighthouse_json"] == {}

    @pytest.mark.asyncio
    async def test_all_five_scores_returned(self, assessor, mock_settings, mock_lighthouse_result):
        """Test 7: All 5 scores are returned (Performance, Accessibility, Best Practices, SEO, PWA)"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_lighthouse_result):
                result = await assessor.assess("https://example.com", {})

                # Check all 5 scores are in metrics
                required_scores = [
                    "performance_score",
                    "accessibility_score",
                    "best_practices_score",
                    "seo_score",
                    "pwa_score",
                ]

                for score_name in required_scores:
                    assert score_name in result.metrics
                    assert isinstance(result.metrics[score_name], int)
                    assert 0 <= result.metrics[score_name] <= 100

    @pytest.mark.asyncio
    async def test_integration_with_assessment_models(self, assessor, mock_settings, mock_lighthouse_result):
        """Test 8: Integration with assessment models"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_lighthouse_result):
                # Test with business data
                business_data = {"business_id": "test-biz-123", "industry": "Technology"}

                result = await assessor.assess("https://example.com", business_data)

                # Verify assessment type matches model enum
                assert result.assessment_type == AssessmentType.LIGHTHOUSE

                # Verify data structure matches what models expect
                assert isinstance(result.data, dict)
                assert "lighthouse_json" in result.data

                # Verify metrics match model fields
                assert isinstance(result.metrics, dict)
                assert all(
                    key in result.metrics
                    for key in [
                        "performance_score",
                        "accessibility_score",
                        "best_practices_score",
                        "seo_score",
                        "pwa_score",
                        "lcp_ms",
                        "fid_ms",
                        "cls_score",
                    ]
                )

    def test_cache_key_generation(self, assessor):
        """Test cache key generation"""
        url1 = "https://example.com"
        url2 = "https://example.com/path"
        url3 = "https://example.com"

        key1 = assessor._get_cache_key(url1)
        key2 = assessor._get_cache_key(url2)
        key3 = assessor._get_cache_key(url3)

        # Same URL should produce same key
        assert key1 == key3
        # Different URLs should produce different keys
        assert key1 != key2
        # Keys should be valid hex strings (MD5)
        assert len(key1) == 32
        assert all(c in "0123456789abcdef" for c in key1)

    @pytest.mark.asyncio
    async def test_cache_corruption_handling(self, assessor, mock_settings, mock_lighthouse_result):
        """Test handling of corrupted cache files"""
        url = "https://corrupted-cache.com"

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Create corrupted cache file
            cache_key = assessor._get_cache_key(url)
            cache_file = os.path.join(assessor.cache_dir, f"{cache_key}.json")

            # Write invalid JSON
            with open(cache_file, "w") as f:
                f.write("{ invalid json")

            # Should fall back to running audit
            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_lighthouse_result) as mock_audit:
                result = await assessor.assess(url, {})
                mock_audit.assert_called_once()

            # Should have valid result despite cache corruption
            assert result.status == "completed"
            assert result.data["lighthouse_json"]["scores"] == mock_lighthouse_result["scores"]

    def test_is_available(self, assessor):
        """Test assessor availability check"""
        # Test with feature disabled
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = False

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            assert assessor.is_available() is False

        # Test with feature enabled and stubs
        mock_settings.enable_lighthouse = True
        mock_settings.use_stubs = True

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            assert assessor.is_available() is True

        # Test with feature enabled, no stubs, no playwright
        mock_settings.use_stubs = False

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings
            with patch.dict("sys.modules", {"playwright": None}):
                assert assessor.is_available() is False

    def test_calculate_cost(self, assessor):
        """Test cost calculation"""
        # Lighthouse runs locally, so cost should always be 0
        assert assessor.calculate_cost() == 0.0

    @pytest.mark.asyncio
    async def test_playwright_import_error(self, assessor, mock_settings):
        """Test handling when Playwright is not installed"""
        mock_settings.use_stubs = False

        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Mock the import statement inside _run_lighthouse_audit
            import_mock = MagicMock(side_effect=ImportError("No module named 'playwright'"))
            with patch("builtins.__import__", side_effect=import_mock):
                with pytest.raises(ImportError) as exc_info:
                    await assessor._run_lighthouse_audit("https://example.com")

                assert "Playwright is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_lighthouse_metrics_extraction(self, assessor, mock_settings):
        """Test extraction of metrics from page performance data"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Mock Playwright page
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.evaluate = AsyncMock(
                return_value={
                    "navigationStart": 0,
                    "firstContentfulPaint": 1500,
                    "domContentLoaded": 2000,
                    "loadComplete": 3500,
                }
            )

            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()

            mock_playwright = AsyncMock()
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

            # Mock the async_playwright context manager
            mock_async_playwright_cm = AsyncMock()
            mock_async_playwright_cm.__aenter__.return_value = mock_playwright

            # Patch the import and function call
            with patch.dict(
                "sys.modules",
                {"playwright.async_api": MagicMock(async_playwright=MagicMock(return_value=mock_async_playwright_cm))},
            ):
                result = await assessor._run_lighthouse_audit("https://example.com")

                # Check metrics are calculated correctly
                assert result["metrics"]["first_contentful_paint"] == 1500
                assert result["metrics"]["speed_index"] == 2000
                assert result["metrics"]["time_to_interactive"] == 3500

                # Check performance score calculation
                # Score = max(0, 100 - (loadComplete / 100))
                # Score = max(0, 100 - (3500 / 100)) = 65
                assert result["scores"]["performance"] == 65

    @pytest.mark.asyncio
    async def test_mobile_friendly_detection(self, assessor, mock_settings, mock_lighthouse_result):
        """Test mobile_friendly metric based on performance score"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Clear any existing cache for test isolation
            import shutil

            if os.path.exists(assessor.cache_dir):
                shutil.rmtree(assessor.cache_dir)
            os.makedirs(assessor.cache_dir, exist_ok=True)

            # Test with good performance score (>= 50)
            good_result = dict(mock_lighthouse_result)
            good_result["scores"]["performance"] = 75
            with patch.object(assessor, "_run_lighthouse_audit", return_value=good_result):
                result = await assessor.assess("https://mobile-test-good.com", {})
                assert result.metrics["mobile_friendly"] is True

            # Test with poor performance score (< 50)
            poor_result = dict(mock_lighthouse_result)
            poor_result["scores"]["performance"] = 40
            with patch.object(assessor, "_run_lighthouse_audit", return_value=poor_result):
                result = await assessor.assess("https://mobile-test-poor.com", {})
                assert result.metrics["mobile_friendly"] is False


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-k", "test_"])
