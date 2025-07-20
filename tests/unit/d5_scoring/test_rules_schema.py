"""
Test D5 Scoring Rules Schema module

Comprehensive unit tests for the scoring rules schema validation,
Pydantic models, and YAML configuration processing.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from d5_scoring.rules_schema import (
    ComponentConfig,
    EngineConfig,
    FactorConfig,
    Rule,
    ScoringComponent,
    ScoringRulesSchema,
    TierConfig,
    validate_rules,
)

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestTierConfig:
    """Test TierConfig Pydantic model"""

    def test_tier_config_creation_valid(self):
        """Test creating valid tier configuration"""
        tier = TierConfig(min=80.0, label="A")

        assert tier.min == 80.0
        assert tier.label == "A"

    def test_tier_config_valid_labels(self):
        """Test tier config accepts valid labels"""
        valid_labels = ["A", "B", "C", "D"]

        for label in valid_labels:
            tier = TierConfig(min=50.0, label=label)
            assert tier.label == label

    def test_tier_config_min_bounds(self):
        """Test tier config min value bounds"""
        # Valid bounds
        tier_min = TierConfig(min=0.0, label="D")
        tier_max = TierConfig(min=100.0, label="A")

        assert tier_min.min == 0.0
        assert tier_max.min == 100.0

    def test_tier_config_invalid_min_negative(self):
        """Test tier config rejects negative min values"""
        with pytest.raises(ValidationError):
            TierConfig(min=-1.0, label="D")

    def test_tier_config_invalid_min_over_100(self):
        """Test tier config rejects min values over 100"""
        with pytest.raises(ValidationError):
            TierConfig(min=101.0, label="A")

    def test_tier_config_invalid_label(self):
        """Test tier config rejects invalid labels"""
        with pytest.raises(ValidationError):
            TierConfig(min=50.0, label="X")


class TestFactorConfig:
    """Test FactorConfig Pydantic model"""

    def test_factor_config_creation(self):
        """Test creating factor configuration"""
        factor = FactorConfig(weight=0.3)

        assert factor.weight == 0.3

    def test_factor_config_weight_bounds(self):
        """Test factor config weight bounds"""
        # Valid bounds
        factor_min = FactorConfig(weight=0.0)
        factor_max = FactorConfig(weight=1.0)

        assert factor_min.weight == 0.0
        assert factor_max.weight == 1.0

    def test_factor_config_invalid_weight_negative(self):
        """Test factor config rejects negative weights"""
        with pytest.raises(ValidationError):
            FactorConfig(weight=-0.1)

    def test_factor_config_invalid_weight_over_1(self):
        """Test factor config rejects weights over 1"""
        with pytest.raises(ValidationError):
            FactorConfig(weight=1.1)


class TestComponentConfig:
    """Test ComponentConfig Pydantic model"""

    def test_component_config_creation(self):
        """Test creating component configuration"""
        factors = {"revenue": FactorConfig(weight=0.6), "growth": FactorConfig(weight=0.4)}

        component = ComponentConfig(weight=0.5, factors=factors)

        assert component.weight == 0.5
        assert len(component.factors) == 2

    def test_component_config_weight_bounds(self):
        """Test component config weight bounds"""
        factors = {"test": FactorConfig(weight=1.0)}

        # Valid bounds
        component_min = ComponentConfig(weight=0.0, factors=factors)
        component_max = ComponentConfig(weight=1.0, factors=factors)

        assert component_min.weight == 0.0
        assert component_max.weight == 1.0

    def test_component_config_empty_factors(self):
        """Test component config with empty factors - should fail validation"""
        with pytest.raises(ValidationError):
            ComponentConfig(weight=0.5, factors={})


class TestRule:
    """Test Rule Pydantic model"""

    def test_rule_creation(self):
        """Test creating rule configuration"""
        rule = Rule(condition="data.industry == 'tech'", points=5.0, description="Tech industry bonus")

        assert rule.condition == "data.industry == 'tech'"
        assert rule.points == 5.0
        assert rule.description == "Tech industry bonus"

    def test_rule_points_bounds(self):
        """Test rule points bounds"""
        # Valid bounds
        rule_min = Rule(condition="True", points=0.0)
        rule_max = Rule(condition="True", points=100.0)

        assert rule_min.points == 0.0
        assert rule_max.points == 100.0

    def test_rule_optional_description(self):
        """Test rule with no description"""
        rule = Rule(condition="True", points=1.0)
        assert rule.description is None


class TestScoringComponent:
    """Test ScoringComponent Pydantic model"""

    def test_scoring_component_creation(self):
        """Test creating scoring component"""
        rules = [Rule(condition="True", points=5.0)]

        component = ScoringComponent(weight=0.5, rules=rules, description="Test component")

        assert component.weight == 0.5
        assert len(component.rules) == 1
        assert component.description == "Test component"

    def test_scoring_component_empty_rules(self):
        """Test scoring component with empty rules"""
        component = ScoringComponent(weight=0.5, rules=[])
        assert len(component.rules) == 0


class TestEngineConfig:
    """Test EngineConfig Pydantic model"""

    def test_engine_config_creation(self):
        """Test creating engine configuration"""
        engine = EngineConfig(max_score=100.0, default_weight=1.0, fallback_enabled=True)

        assert engine.max_score == 100.0
        assert engine.default_weight == 1.0
        assert engine.fallback_enabled is True

    def test_engine_config_defaults(self):
        """Test engine config with default values"""
        engine = EngineConfig()

        assert engine.max_score == 100.0
        assert engine.default_weight == 1.0
        assert engine.fallback_enabled is True
        assert engine.logging_enabled is True


class TestScoringRulesSchema:
    """Test ScoringRulesSchema Pydantic model"""

    def test_scoring_rules_schema_creation(self):
        """Test creating complete scoring rules schema"""
        # Create all required tiers
        tiers = {
            "A": TierConfig(min=80.0, label="A"),
            "B": TierConfig(min=60.0, label="B"),
            "C": TierConfig(min=40.0, label="C"),
            "D": TierConfig(min=0.0, label="D"),
        }

        factors = {"factor1": FactorConfig(weight=1.0)}
        components = {"test_component": ComponentConfig(weight=1.0, factors=factors)}

        schema = ScoringRulesSchema(version="1.0", tiers=tiers, components=components)

        assert schema.version == "1.0"
        assert len(schema.tiers) == 4
        assert len(schema.components) == 1

    def test_scoring_rules_schema_has_expected_fields(self):
        """Test scoring rules schema has expected fields"""
        tiers = {
            "A": TierConfig(min=80.0, label="A"),
            "B": TierConfig(min=60.0, label="B"),
            "C": TierConfig(min=40.0, label="C"),
            "D": TierConfig(min=0.0, label="D"),
        }

        factors = {"factor1": FactorConfig(weight=1.0)}
        components = {"test_component": ComponentConfig(weight=1.0, factors=factors)}

        schema = ScoringRulesSchema(version="1.0", tiers=tiers, components=components)

        # Test that schema has expected attributes
        assert hasattr(schema, "version")
        assert hasattr(schema, "tiers")
        assert hasattr(schema, "components")
        assert hasattr(schema, "formulas")


class TestValidateRules:
    """Test validate_rules function"""

    def test_validate_rules_valid_yaml(self):
        """Test validating valid YAML rules file"""
        # Create valid rules YAML content
        rules_data = {
            "version": "1.0",
            "tiers": {
                "A": {"min": 80.0, "label": "A"},
                "B": {"min": 60.0, "label": "B"},
                "C": {"min": 40.0, "label": "C"},
                "D": {"min": 0.0, "label": "D"},
            },
            "components": {"test_component": {"weight": 1.0, "factors": {"factor1": {"weight": 1.0}}}},
        }

        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(rules_data, f)
            temp_path = f.name

        try:
            # Validate the rules
            schema = validate_rules(temp_path)

            assert isinstance(schema, ScoringRulesSchema)
            assert schema.version == "1.0"
            assert len(schema.components) == 1
        finally:
            # Clean up
            Path(temp_path).unlink()

    def test_validate_rules_file_not_found(self):
        """Test validate_rules with non-existent file"""
        with pytest.raises(FileNotFoundError):
            validate_rules("/non/existent/file.yaml")

    def test_validate_rules_invalid_yaml(self):
        """Test validate_rules with invalid YAML"""
        # Create invalid YAML content
        invalid_yaml = "invalid: yaml: content: ["

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            temp_path = f.name

        try:
            with pytest.raises(yaml.YAMLError):
                validate_rules(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_basic_validation_function(self):
        """Test that validate_rules function exists and is callable"""
        assert callable(validate_rules)
