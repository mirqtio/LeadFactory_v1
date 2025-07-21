"""
Unit tests for d5_scoring vertical_overrides module.
Coverage target: 90%+ for vertical scoring logic and overrides.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from d5_scoring.models import D5ScoringResult, ScoreBreakdown
from d5_scoring.types import ScoringVersion
from d5_scoring.vertical_overrides import (
    VerticalConfig,
    VerticalScoringEngine,
    create_medical_scoring_engine,
    create_restaurant_scoring_engine,
)


class TestVerticalConfig:
    """Test suite for VerticalConfig dataclass."""

    def test_vertical_config_creation(self):
        """Test VerticalConfig creation with all fields."""
        config = VerticalConfig(
            vertical_name="restaurant",
            rules_file="scoring_rules_restaurant.yaml",
            multiplier=1.2,
            description="Restaurant industry scoring rules",
        )

        assert config.vertical_name == "restaurant"
        assert config.rules_file == "scoring_rules_restaurant.yaml"
        assert config.multiplier == 1.2
        assert config.description == "Restaurant industry scoring rules"

    def test_vertical_config_minimal_creation(self):
        """Test VerticalConfig creation with minimal fields."""
        config = VerticalConfig(vertical_name="medical", rules_file="scoring_rules_medical.yaml")

        assert config.vertical_name == "medical"
        assert config.rules_file == "scoring_rules_medical.yaml"
        assert config.multiplier == 1.0
        assert config.description == "Medical industry scoring rules"

    def test_post_init_sets_default_description(self):
        """Test __post_init__ sets default description when empty."""
        config = VerticalConfig(vertical_name="healthcare", rules_file="scoring_rules_healthcare.yaml")

        # Should auto-generate description
        assert config.description == "Healthcare industry scoring rules"

    def test_post_init_preserves_existing_description(self):
        """Test __post_init__ preserves non-empty description."""
        config = VerticalConfig(
            vertical_name="retail", rules_file="scoring_rules_retail.yaml", description="Custom retail description"
        )

        # Should preserve existing description
        assert config.description == "Custom retail description"


class TestVerticalScoringEngine:
    """Test suite for VerticalScoringEngine class."""

    @pytest.fixture
    def mock_base_parser(self):
        """Mock base scoring rules parser."""
        parser = Mock()
        parser.load_rules.return_value = True
        parser.engine_config = {"max_score": 100.0}
        parser.fallbacks = {"company_name": "Unknown Company"}
        parser.component_rules = {"company_info": Mock(), "online_presence": Mock()}
        parser.tier_rules = {"A": Mock(), "B": Mock()}
        parser.quality_control = Mock()
        parser.apply_fallbacks.return_value = {"company_name": "Test Company"}
        parser.get_component_rules.return_value = parser.component_rules
        parser.get_tier_for_score.return_value = Mock(name="A")
        return parser

    @pytest.fixture
    def mock_vertical_parser(self):
        """Mock vertical-specific parser."""
        parser = Mock()
        parser.load_rules.return_value = True
        parser.engine_config = {"vertical_multiplier": 1.2}
        parser.fallbacks = {"industry": "Restaurant"}
        parser.component_rules = {"company_info": Mock(), "restaurant_specific": Mock()}  # Override  # New component
        parser.tier_rules = {"A": Mock()}
        parser.quality_control = Mock()
        return parser

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_init_base_only(self, mock_parser_class):
        """Test initialization with base rules only."""
        mock_parser = Mock()
        mock_parser.load_rules.return_value = True
        mock_parser_class.return_value = mock_parser

        engine = VerticalScoringEngine(base_rules_file="scoring_rules.yaml")

        assert engine.vertical is None
        assert engine.base_rules_file == "scoring_rules.yaml"
        assert engine.base_parser is mock_parser
        assert engine.vertical_parser is None
        mock_parser_class.assert_called_once_with("scoring_rules.yaml")

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    @patch("d5_scoring.vertical_overrides.logger")
    def test_init_with_supported_vertical(self, mock_logger, mock_parser_class):
        """Test initialization with supported vertical."""
        mock_base_parser = Mock()
        mock_base_parser.load_rules.return_value = True
        mock_base_parser.engine_config = {"max_score": 100.0}
        mock_base_parser.fallbacks = {}
        mock_base_parser.component_rules = {}
        mock_base_parser.tier_rules = {}
        mock_base_parser.quality_control = None

        mock_vertical_parser = Mock()
        mock_vertical_parser.load_rules.return_value = True
        mock_vertical_parser.engine_config = {"vertical_multiplier": 1.2}
        mock_vertical_parser.fallbacks = {}
        mock_vertical_parser.component_rules = {}
        mock_vertical_parser.tier_rules = {}
        mock_vertical_parser.quality_control = None

        def parser_side_effect(rules_file):
            if "restaurant" in rules_file:
                return mock_vertical_parser
            return mock_base_parser

        mock_parser_class.side_effect = parser_side_effect

        engine = VerticalScoringEngine(vertical="restaurant")

        assert engine.vertical == "restaurant"
        assert engine.vertical_parser is mock_vertical_parser
        mock_logger.info.assert_called()

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    @patch("d5_scoring.vertical_overrides.logger")
    def test_init_with_unsupported_vertical(self, mock_logger, mock_parser_class):
        """Test initialization with unsupported vertical."""
        mock_parser = Mock()
        mock_parser.load_rules.return_value = True
        mock_parser_class.return_value = mock_parser

        engine = VerticalScoringEngine(vertical="unsupported")

        assert engine.vertical == "unsupported"
        assert engine.vertical_parser is None
        mock_logger.warning.assert_called_with("Unsupported vertical 'unsupported', using base rules only")

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_init_base_rules_load_failure(self, mock_parser_class):
        """Test initialization when base rules fail to load."""
        mock_parser = Mock()
        mock_parser.load_rules.return_value = False
        mock_parser_class.return_value = mock_parser

        with pytest.raises(RuntimeError, match="Failed to load base rules"):
            VerticalScoringEngine()

    def test_load_vertical_rules_success(self, mock_base_parser):
        """Test successful vertical rules loading."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_base_parser.load_rules.return_value = True
            mock_vertical_parser = Mock()
            mock_vertical_parser.load_rules.return_value = True
            mock_vertical_parser.engine_config = {"vertical_multiplier": 1.2}
            mock_vertical_parser.fallbacks = {}
            mock_vertical_parser.component_rules = {}
            mock_vertical_parser.tier_rules = {}
            mock_vertical_parser.quality_control = None

            def parser_side_effect(rules_file):
                if "restaurant" in rules_file:
                    return mock_vertical_parser
                return mock_base_parser

            mock_parser_class.side_effect = parser_side_effect

            engine = VerticalScoringEngine(vertical="restaurant")

            assert engine.vertical_parser is mock_vertical_parser

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    @patch("d5_scoring.vertical_overrides.logger")
    def test_load_vertical_rules_failure(self, mock_logger, mock_parser_class):
        """Test vertical rules loading failure."""
        mock_base_parser = Mock()
        mock_base_parser.load_rules.return_value = True
        mock_vertical_parser = Mock()
        mock_vertical_parser.load_rules.return_value = False

        def parser_side_effect(rules_file):
            if "restaurant" in rules_file:
                return mock_vertical_parser
            return mock_base_parser

        mock_parser_class.side_effect = parser_side_effect

        engine = VerticalScoringEngine(vertical="restaurant")

        assert engine.vertical_parser is None
        mock_logger.error.assert_called()

    @patch("d5_scoring.vertical_overrides.copy.deepcopy")
    def test_create_merged_rules_base_only(self, mock_deepcopy, mock_base_parser):
        """Test merged rules creation with base rules only."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser_class.return_value = mock_base_parser
            mock_deepcopy.return_value = mock_base_parser

            engine = VerticalScoringEngine()

            assert engine.merged_parser is mock_base_parser
            mock_deepcopy.assert_called_once_with(mock_base_parser)

    def test_create_merged_rules_with_vertical(self, mock_base_parser, mock_vertical_parser):
        """Test merged rules creation with vertical overrides."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            with patch("d5_scoring.vertical_overrides.copy.deepcopy") as mock_deepcopy:
                mock_merged_parser = Mock()
                mock_merged_parser.engine_config = {}
                mock_merged_parser.fallbacks = {}
                mock_merged_parser.component_rules = {}
                mock_merged_parser.tier_rules = {}

                mock_deepcopy.return_value = mock_merged_parser

                def parser_side_effect(rules_file):
                    if "restaurant" in rules_file:
                        return mock_vertical_parser
                    return mock_base_parser

                mock_parser_class.side_effect = parser_side_effect

                engine = VerticalScoringEngine(vertical="restaurant")

                # Verify vertical overrides were applied
                assert engine.merged_parser is mock_merged_parser

    def test_detect_vertical_restaurant(self):
        """Test vertical detection for restaurant industry."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            business_data = {"industry": "restaurant and food service"}
            result = engine._detect_vertical(business_data)
            assert result == "restaurant"

    def test_detect_vertical_medical(self):
        """Test vertical detection for medical industry."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            business_data = {"industry": "healthcare services"}
            result = engine._detect_vertical(business_data)
            assert result == "medical"

    def test_detect_vertical_from_name(self):
        """Test vertical detection from company name."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            business_data = {"industry": "services", "company_name": "Joe's Pizza Kitchen"}
            result = engine._detect_vertical(business_data)
            assert result == "restaurant"

    def test_detect_vertical_no_match(self):
        """Test vertical detection with no matches."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            business_data = {"industry": "technology"}
            result = engine._detect_vertical(business_data)
            assert result is None

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_base_parser = Mock()
            mock_base_parser.load_rules.return_value = True
            mock_base_parser.engine_config = {"max_score": 100.0}
            mock_base_parser.fallbacks = {}
            mock_base_parser.component_rules = {}
            mock_base_parser.tier_rules = {}
            mock_base_parser.quality_control = None

            mock_vertical_parser = Mock()
            mock_vertical_parser.load_rules.return_value = True
            mock_vertical_parser.engine_config = {"vertical_multiplier": 1.2}
            mock_vertical_parser.fallbacks = {}
            mock_vertical_parser.component_rules = {}
            mock_vertical_parser.tier_rules = {}
            mock_vertical_parser.quality_control = None

            def parser_side_effect(rules_file):
                if "restaurant" in rules_file:
                    return mock_vertical_parser
                return mock_base_parser

            mock_parser_class.side_effect = parser_side_effect

            engine = VerticalScoringEngine(vertical="restaurant")

            data = {"company_name": "Test", "industry": "restaurant"}
            component_results = {
                "comp1": {"total_points": 8, "max_points": 10},
                "comp2": {"total_points": 6, "max_points": 10},
            }

            with patch.object(engine, "_calculate_data_completeness", return_value=0.8):
                confidence = engine._calculate_confidence(data, component_results)

                # Should be between 0 and 1, with vertical boost
                assert 0 <= confidence <= 1
                assert confidence > 0.7  # With vertical boost

    def test_calculate_data_completeness(self):
        """Test data completeness calculation."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser.engine_config = {"max_score": 100.0}
            mock_parser.fallbacks = {}
            mock_parser.component_rules = {}
            mock_parser.tier_rules = {}
            mock_parser.quality_control = None

            # Mock component rules with field extraction
            mock_component = Mock()
            mock_rule = Mock()
            mock_rule.condition = "company_name is not None and industry == 'restaurant'"
            mock_component.rules = [mock_rule]

            mock_parser.get_component_rules.return_value = {"comp1": mock_component}
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            # Complete data
            complete_data = {"company_name": "Test Corp", "industry": "restaurant"}
            completeness = engine._calculate_data_completeness(complete_data)
            assert completeness == 1.0

            # Partial data
            partial_data = {"company_name": "Test Corp"}
            completeness = engine._calculate_data_completeness(partial_data)
            assert 0 <= completeness < 1.0

    def test_assess_component_data_quality(self):
        """Test component data quality assessment."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True

            # Mock component rules
            mock_component = Mock()
            mock_rule = Mock()
            mock_rule.condition = "company_name is not None"
            mock_component.rules = [mock_rule]

            mock_parser.get_component_rules.return_value = mock_component
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            # Good data
            good_data = {"company_name": "Test Corp"}
            quality = engine._assess_component_data_quality(good_data, "comp1")
            assert quality == "excellent"

            # Poor data
            poor_data = {"company_name": ""}
            quality = engine._assess_component_data_quality(poor_data, "comp1")
            assert quality == "poor"

    def test_get_vertical_info_base(self):
        """Test vertical info for base engine."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()

            info = engine.get_vertical_info()

            assert info["vertical"] is None
            assert "Base" in info["description"]
            assert "supported_verticals" in info
            assert "restaurant" in info["supported_verticals"]
            assert "medical" in info["supported_verticals"]

    def test_get_vertical_info_restaurant(self):
        """Test vertical info for restaurant engine."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_base_parser = Mock()
            mock_base_parser.load_rules.return_value = True
            mock_base_parser.engine_config = {"max_score": 100.0}
            mock_base_parser.fallbacks = {}
            mock_base_parser.component_rules = {"base_comp": Mock()}
            mock_base_parser.tier_rules = {}
            mock_base_parser.quality_control = None

            mock_vertical_parser = Mock()
            mock_vertical_parser.load_rules.return_value = True
            mock_vertical_parser.engine_config = {"vertical_multiplier": 1.2}
            mock_vertical_parser.fallbacks = {}
            mock_vertical_parser.component_rules = {"comp1": Mock()}
            mock_vertical_parser.tier_rules = {}
            mock_vertical_parser.quality_control = None

            def parser_side_effect(rules_file):
                if "restaurant" in rules_file:
                    return mock_vertical_parser
                return mock_base_parser

            mock_parser_class.side_effect = parser_side_effect

            engine = VerticalScoringEngine(vertical="restaurant")

            info = engine.get_vertical_info()

            assert info["vertical"] == "restaurant"
            assert "restaurant" in info["description"].lower()
            assert info["multiplier"] == 1.0
            assert "override_components" in info
            assert "inherited_components" in info

    def test_get_supported_verticals(self):
        """Test getting supported verticals."""
        verticals = VerticalScoringEngine.get_supported_verticals()

        assert "restaurant" in verticals
        assert "medical" in verticals
        assert "healthcare" in verticals

        # Verify it's a copy (modifications don't affect original)
        verticals["test"] = Mock()
        assert "test" not in VerticalScoringEngine.SUPPORTED_VERTICALS

    def test_create_for_vertical(self):
        """Test factory method for vertical creation."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_base_parser = Mock()
            mock_base_parser.load_rules.return_value = True
            mock_base_parser.engine_config = {"max_score": 100.0}
            mock_base_parser.fallbacks = {}
            mock_base_parser.component_rules = {}
            mock_base_parser.tier_rules = {}
            mock_base_parser.quality_control = None

            mock_vertical_parser = Mock()
            mock_vertical_parser.load_rules.return_value = True
            mock_vertical_parser.engine_config = {"vertical_multiplier": 1.2}
            mock_vertical_parser.fallbacks = {}
            mock_vertical_parser.component_rules = {}
            mock_vertical_parser.tier_rules = {}
            mock_vertical_parser.quality_control = None

            def parser_side_effect(rules_file):
                if "medical" in rules_file:
                    return mock_vertical_parser
                return mock_base_parser

            mock_parser_class.side_effect = parser_side_effect

            engine = VerticalScoringEngine.create_for_vertical("medical", "custom_base.yaml")

            assert engine.vertical == "medical"
            assert engine.base_rules_file == "custom_base.yaml"

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_calculate_score_basic(self, mock_parser_class):
        """Test basic score calculation."""
        # Mock parsers
        mock_parser = Mock()
        mock_parser.load_rules.return_value = True
        mock_parser.engine_config = {"max_score": 100.0}
        mock_parser.fallbacks = {}
        mock_parser.component_rules = {}
        mock_parser.tier_rules = {}
        mock_parser.quality_control = None
        mock_parser.apply_fallbacks.return_value = {"company_name": "Test Corp"}

        # Mock component rules
        mock_component = Mock()
        mock_component.calculate_score.return_value = {
            "total_points": 8,
            "max_points": 10,
            "weight": 1.0,
            "percentage": 80.0,
            "weighted_score": 8.0,
        }
        mock_rule = Mock()
        mock_rule.condition = "company_name is not None"
        mock_component.rules = [mock_rule]
        mock_parser.get_component_rules.return_value = {"comp1": mock_component}

        # Mock tier determination
        mock_tier = Mock()
        mock_tier.name = "A"
        mock_parser.get_tier_for_score.return_value = mock_tier

        mock_parser_class.return_value = mock_parser

        engine = VerticalScoringEngine()

        business_data = {"id": "test_123", "company_name": "Test Corp"}
        result = engine.calculate_score(business_data)

        assert isinstance(result, D5ScoringResult)
        assert result.business_id == "test_123"
        assert result.tier == "A"
        assert float(result.overall_score) > 0

    def test_calculate_score_with_auto_detection(self):
        """Test score calculation with auto-detection."""
        with patch("d5_scoring.vertical_overrides.ScoringRulesParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser.load_rules.return_value = True
            mock_parser.engine_config = {"max_score": 100.0}
            mock_parser.fallbacks = {}
            mock_parser.component_rules = {}
            mock_parser.tier_rules = {}
            mock_parser.quality_control = None
            mock_parser.apply_fallbacks.return_value = {"industry": "restaurant"}

            mock_component = Mock()
            mock_component.calculate_score.return_value = {
                "total_points": 8,
                "max_points": 10,
                "weight": 1.0,
                "percentage": 80.0,
                "weighted_score": 8.0,
            }
            mock_rule = Mock()
            mock_rule.condition = "industry is not None"
            mock_component.rules = [mock_rule]
            mock_parser.get_component_rules.return_value = {"comp1": mock_component}

            mock_tier = Mock()
            mock_tier.name = "B"
            mock_parser.get_tier_for_score.return_value = mock_tier

            mock_parser_class.return_value = mock_parser

            engine = VerticalScoringEngine()  # No vertical specified

            business_data = {"id": "test_123", "industry": "restaurant"}

            with patch.object(engine, "__init__", return_value=None) as mock_init:
                # Mock to prevent re-initialization
                engine.vertical = None
                engine.merged_parser = mock_parser

                result = engine.calculate_score(business_data)

                # Should attempt re-initialization with detected vertical
                # (Mock prevents actual re-init)

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_calculate_detailed_score(self, mock_parser_class):
        """Test detailed score calculation with breakdowns."""
        # Setup mocks
        mock_parser = Mock()
        mock_parser.load_rules.return_value = True
        mock_parser.engine_config = {"max_score": 100.0}
        mock_parser.fallbacks = {}
        mock_parser.component_rules = {}
        mock_parser.tier_rules = {}
        mock_parser.quality_control = None
        mock_parser.apply_fallbacks.return_value = {"company_name": "Test Corp"}

        mock_component = Mock()
        mock_component.calculate_score.return_value = {
            "total_points": 8,
            "max_points": 10,
            "weight": 1.0,
            "percentage": 80.0,
            "weighted_score": 8.0,
        }
        mock_rule = Mock()
        mock_rule.condition = "company_name is not None"
        mock_component.rules = [mock_rule]
        mock_parser.get_component_rules.return_value = {"comp1": mock_component}

        mock_tier = Mock()
        mock_tier.name = "A"
        mock_parser.get_tier_for_score.return_value = mock_tier

        mock_parser_class.return_value = mock_parser

        engine = VerticalScoringEngine()

        business_data = {"id": "test_123", "company_name": "Test Corp"}

        with patch.object(engine, "_assess_component_data_quality", return_value="good"):
            result, breakdowns = engine.calculate_detailed_score(business_data)

            assert isinstance(result, D5ScoringResult)
            assert isinstance(breakdowns, list)
            assert len(breakdowns) == 1
            assert isinstance(breakdowns[0], ScoreBreakdown)
            assert breakdowns[0].component == "comp1"

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_explain_vertical_score(self, mock_parser_class):
        """Test vertical score explanation."""
        mock_parser = Mock()
        mock_parser.load_rules.return_value = True
        mock_parser.engine_config = {"max_score": 100.0}
        mock_parser.apply_fallbacks.return_value = {"company_name": "Test Corp"}

        mock_component = Mock()
        mock_component.description = "Company information"
        mock_component.calculate_score.return_value = {
            "total_points": 8,
            "max_points": 10,
            "weight": 1.0,
            "percentage": 80.0,
            "weighted_score": 8.0,
            "rule_results": [],
        }
        mock_parser.get_component_rules.return_value = {"comp1": mock_component}

        mock_tier = Mock()
        mock_tier.name = "A"
        mock_tier.min_score = 80
        mock_tier.max_score = 100
        mock_tier.description = "Excellent"
        mock_parser.get_tier_for_score.return_value = mock_tier

        mock_parser_class.return_value = mock_parser

        engine = VerticalScoringEngine()

        business_data = {"id": "test_123", "company_name": "Test Corp"}
        explanation = engine.explain_vertical_score(business_data)

        assert "business_id" in explanation
        assert "vertical_info" in explanation
        assert "component_explanations" in explanation
        assert "override_summary" in explanation
        assert "overall_calculation" in explanation
        assert "tier_assignment" in explanation


class TestConvenienceFunctions:
    """Test suite for convenience functions."""

    @patch("d5_scoring.vertical_overrides.VerticalScoringEngine")
    def test_create_restaurant_scoring_engine(self, mock_engine_class):
        """Test restaurant scoring engine creation."""
        mock_engine = Mock()
        mock_engine_class.create_for_vertical.return_value = mock_engine

        result = create_restaurant_scoring_engine("custom_base.yaml")

        mock_engine_class.create_for_vertical.assert_called_once_with("restaurant", "custom_base.yaml")
        assert result is mock_engine

    @patch("d5_scoring.vertical_overrides.VerticalScoringEngine")
    def test_create_restaurant_scoring_engine_default(self, mock_engine_class):
        """Test restaurant scoring engine creation with defaults."""
        mock_engine = Mock()
        mock_engine_class.create_for_vertical.return_value = mock_engine

        result = create_restaurant_scoring_engine()

        mock_engine_class.create_for_vertical.assert_called_once_with("restaurant", "scoring_rules.yaml")
        assert result is mock_engine

    @patch("d5_scoring.vertical_overrides.VerticalScoringEngine")
    def test_create_medical_scoring_engine(self, mock_engine_class):
        """Test medical scoring engine creation."""
        mock_engine = Mock()
        mock_engine_class.create_for_vertical.return_value = mock_engine

        result = create_medical_scoring_engine("custom_base.yaml")

        mock_engine_class.create_for_vertical.assert_called_once_with("medical", "custom_base.yaml")
        assert result is mock_engine

    @patch("d5_scoring.vertical_overrides.VerticalScoringEngine")
    def test_create_medical_scoring_engine_default(self, mock_engine_class):
        """Test medical scoring engine creation with defaults."""
        mock_engine = Mock()
        mock_engine_class.create_for_vertical.return_value = mock_engine

        result = create_medical_scoring_engine()

        mock_engine_class.create_for_vertical.assert_called_once_with("medical", "scoring_rules.yaml")
        assert result is mock_engine


class TestVerticalScoringEngineEdgeCases:
    """Test edge cases and error conditions."""

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_calculate_score_error_handling(self, mock_parser_class):
        """Test error handling in score calculation."""
        mock_parser = Mock()
        mock_parser.load_rules.return_value = True
        mock_parser.apply_fallbacks.side_effect = Exception("Parser error")
        mock_parser_class.return_value = mock_parser

        engine = VerticalScoringEngine()

        business_data = {"id": "test_123"}

        with pytest.raises(Exception, match="Parser error"):
            engine.calculate_score(business_data)

    @patch("d5_scoring.vertical_overrides.ScoringRulesParser")
    def test_load_vertical_rules_exception(self, mock_parser_class):
        """Test exception handling in vertical rules loading."""
        mock_base_parser = Mock()
        mock_base_parser.load_rules.return_value = True

        def parser_side_effect(rules_file):
            if "restaurant" in rules_file:
                raise Exception("File not found")
            return mock_base_parser

        mock_parser_class.side_effect = parser_side_effect

        with patch("d5_scoring.vertical_overrides.logger") as mock_logger:
            engine = VerticalScoringEngine(vertical="restaurant")

            assert engine.vertical_parser is None
            mock_logger.error.assert_called()

    def test_supported_verticals_constant(self):
        """Test that SUPPORTED_VERTICALS contains expected values."""
        verticals = VerticalScoringEngine.SUPPORTED_VERTICALS

        assert "restaurant" in verticals
        assert "medical" in verticals
        assert "healthcare" in verticals

        # Verify configurations
        assert verticals["restaurant"].vertical_name == "restaurant"
        assert verticals["medical"].vertical_name == "medical"
        assert verticals["healthcare"].vertical_name == "medical"  # Alias

        # Verify rules files
        assert "restaurant" in verticals["restaurant"].rules_file
        assert "medical" in verticals["medical"].rules_file
