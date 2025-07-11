"""Unit tests for severity rubric mapper."""
import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from d3_assessment.rubric import map_severity


def test_visual_cta_below_fold():
    """Test that visual hierarchy 'cta_below_fold' returns severity 3."""
    # Test with different metric formats
    assert map_severity("visual", {"name": "cta_below_fold", "value": True}) == 3
    assert map_severity("visual", {"cta_below_fold": True}) == 3
    assert map_severity("Visual", {"name": "CTA_below_fold", "value": True}) == 3


def test_performance_severity():
    """Test performance metric severity mappings."""
    # Page load time
    assert (
        map_severity("performance", {"name": "page_load_time", "value": 2.5}) == 1
    )  # < 3s
    assert (
        map_severity("performance", {"name": "page_load_time", "value": 4.0}) == 2
    )  # 3-5s
    assert (
        map_severity("performance", {"name": "page_load_time", "value": 7.0}) == 3
    )  # 5-10s
    assert (
        map_severity("performance", {"name": "page_load_time", "value": 12.0}) == 4
    )  # > 10s

    # Mobile score (inverse - lower is worse)
    assert (
        map_severity("performance", {"name": "mobile_score", "value": 85}) == 1
    )  # > 70
    assert (
        map_severity("performance", {"name": "mobile_score", "value": 60}) == 2
    )  # 50-70
    assert (
        map_severity("performance", {"name": "mobile_score", "value": 40}) == 3
    )  # 30-50
    assert (
        map_severity("performance", {"name": "mobile_score", "value": 25}) == 4
    )  # < 30


def test_seo_severity():
    """Test SEO metric severity mappings."""
    assert map_severity("seo", {"name": "missing_title", "value": True}) == 4
    assert map_severity("seo", {"name": "missing_title", "value": False}) == 1
    assert map_severity("seo", {"name": "missing_h1", "value": True}) == 3
    assert map_severity("seo", {"name": "robots_blocked", "value": True}) == 4


def test_trust_severity():
    """Test trust metric severity mappings."""
    # Review count
    assert map_severity("trust", {"name": "review_count", "value": 3}) == 4  # < 5
    assert map_severity("trust", {"name": "review_count", "value": 10}) == 3  # 5-20
    assert map_severity("trust", {"name": "review_count", "value": 30}) == 2  # 20-50
    assert map_severity("trust", {"name": "review_count", "value": 100}) == 1  # > 50

    # Rating
    assert map_severity("trust", {"name": "rating", "value": 2.5}) == 4  # < 3.0
    assert map_severity("trust", {"name": "rating", "value": 3.5}) == 3  # 3.0-4.0
    assert map_severity("trust", {"name": "rating", "value": 4.2}) == 2  # 4.0-4.5
    assert map_severity("trust", {"name": "rating", "value": 4.8}) == 1  # 4.5-5.0


def test_unknown_category():
    """Test that unknown categories default to severity 2."""
    assert map_severity("unknown", {"name": "test", "value": 100}) == 2


def test_special_cases():
    """Test special case handling."""
    # Trust with inline review_count
    assert map_severity("trust", {"review_count": 15, "rating": 4.5}) == 3
    assert map_severity("trust", {"review_count": 50, "rating": 3.5}) == 3
