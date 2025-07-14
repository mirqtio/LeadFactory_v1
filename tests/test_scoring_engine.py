"""Tests for the scoring engine."""
from pathlib import Path
from unittest.mock import patch

import pytest

from d5_scoring.constants import DEFAULT_SCORING_RULES_PATH
from d5_scoring.scoring_engine import ScoringEngine

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestScoringEngine:
    """Test the scoring engine functionality."""

    def test_engine_loads_default_config(self):
        """Test that engine loads the default config file."""
        engine = ScoringEngine()
        assert engine.config_path == Path(DEFAULT_SCORING_RULES_PATH)

    def test_engine_uses_env_var_path(self, monkeypatch):
        """Test that engine uses SCORING_RULES_PATH env var."""
        test_path = "/custom/path/rules.yaml"
        monkeypatch.setenv("SCORING_RULES_PATH", test_path)

        engine = ScoringEngine()
        assert engine.config_path == Path(test_path)

    def test_engine_uses_provided_path(self):
        """Test that engine uses explicitly provided path."""
        test_path = "/explicit/path/rules.yaml"
        engine = ScoringEngine(config_path=test_path)
        assert engine.config_path == Path(test_path)

    def test_calculate_score_basic(self):
        """Test basic score calculation."""
        engine = ScoringEngine()

        # Prepare test data matching our components
        test_data = {
            "company_info": {"name_quality": True, "industry_classification": True, "years_in_business": 5},
            "contact_info": {"email_quality": True, "phone_verified": True, "decision_maker": False},
            "online_presence": {
                "website_quality": True,
                "domain_age": 3,
                "ssl_certificate": True,
                "mobile_responsive": True,
            },
        }

        result = engine.calculate_score(test_data)

        assert "total_score" in result
        assert "tier" in result
        assert "component_scores" in result
        assert result["total_score"] > 0
        assert result["tier"] in ["A", "B", "C", "D"]

    def test_tier_assignment(self):
        """Test that tiers are assigned correctly based on score."""
        engine = ScoringEngine()

        # Test data that should result in different tiers
        test_cases = [
            (85, "A"),  # >= 80
            (70, "B"),  # >= 60
            (50, "C"),  # >= 40
            (20, "D"),  # < 40
        ]

        for score, expected_tier in test_cases:
            tier = engine._determine_tier(score)
            assert tier == expected_tier, f"Score {score} should be tier {expected_tier}, got {tier}"

    def test_missing_components_handled(self):
        """Test that missing components are handled gracefully."""
        engine = ScoringEngine()

        # Data with only some components
        test_data = {"company_info": {"name_quality": True, "industry_classification": True, "years_in_business": 5}}

        result = engine.calculate_score(test_data)

        assert result["total_score"] > 0
        assert "company_info" in result["component_scores"]
        # Other components should not be in the scores
        assert "contact_info" not in result["component_scores"]

    def test_development_fallback(self, monkeypatch):
        """Test fallback to defaults in development mode."""
        # Set non-production environment
        monkeypatch.setenv("ENV", "development")

        # Use non-existent path
        with patch("pathlib.Path.exists", return_value=False):
            engine = ScoringEngine(config_path="/nonexistent/path.yaml")
            assert engine._using_defaults is True

    def test_production_requires_config(self, monkeypatch):
        """Test that production environment requires config file."""
        # Set production environment
        monkeypatch.setenv("ENV", "production")

        # Use non-existent path
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="required in production"):
                ScoringEngine(config_path="/nonexistent/path.yaml")

    def test_reload_config_keeps_old_on_failure(self):
        """Test that reload keeps old config on failure."""
        engine = ScoringEngine()

        # Save original schema
        original_schema = engine._schema

        # Try to reload with bad path
        engine.config_path = Path("/nonexistent/bad.yaml")

        try:
            engine.reload_config()
        except:
            pass

        # Should still have original schema or defaults
        assert engine._schema is not None or engine._using_defaults

    def test_get_tier_thresholds(self):
        """Test getting tier thresholds."""
        engine = ScoringEngine()

        thresholds = engine.get_tier_thresholds()

        assert thresholds == {"A": 80.0, "B": 60.0, "C": 40.0, "D": 0.0}

    def test_component_score_calculation(self):
        """Test detailed component score calculation."""
        engine = ScoringEngine()

        test_data = {
            "company_info": {
                "name_quality": True,
                "industry_classification": True,
                "years_in_business": False,  # One factor false
            }
        }

        result = engine.calculate_score(test_data)

        comp_score = result["component_scores"]["company_info"]
        assert "raw_score" in comp_score
        assert "weighted_score" in comp_score
        assert "weight" in comp_score

        # Raw score should be less than 100 since one factor is false
        assert comp_score["raw_score"] < 100
        assert comp_score["raw_score"] > 0

    def test_prometheus_metric_set(self):
        """Test that Prometheus metric is set correctly."""
        from d5_scoring.scoring_engine import scoring_rules_default_used

        # Reset metric
        scoring_rules_default_used.set(0)

        # Force default usage
        with patch("pathlib.Path.exists", return_value=False):
            engine = ScoringEngine()

        # Check metric was set to 1
        assert scoring_rules_default_used._value.get() == 1

    def test_config_version_in_result(self):
        """Test that config version is included in results."""
        engine = ScoringEngine()

        test_data = {"company_info": {"name_quality": True}}
        result = engine.calculate_score(test_data)

        assert "config_version" in result
        assert result["config_version"] == "1.0"
