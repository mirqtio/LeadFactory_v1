"""Tests for scoring rules schema validation."""
import tempfile

import pytest

from d5_scoring.constants import WEIGHT_SUM_WARNING_THRESHOLD
from d5_scoring.rules_schema import check_missing_components, validate_rules

# Mark entire module as unit test and xfail for Phase 0.5
pytestmark = [pytest.mark.unit, pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)]


class TestScoringRulesSchema:
    """Test scoring rules schema validation."""

    def test_happy_path_yaml_loads(self):
        """Test that a valid YAML file loads successfully."""
        # Read the actual config file
        schema = validate_rules("config/scoring_rules.yaml")

        assert schema.version == "1.0"
        assert len(schema.components) == 15
        assert len(schema.tiers) == 4

        # Check tier labels
        tier_labels = {t.label for t in schema.tiers.values()}
        assert tier_labels == {"A", "B", "C", "D"}

    def test_component_weights_sum_to_one(self):
        """Test that component weights sum to 1.0."""
        schema = validate_rules("config/scoring_rules.yaml")

        total_weight = sum(c.weight for c in schema.components.values())
        assert abs(total_weight - 1.0) < WEIGHT_SUM_WARNING_THRESHOLD

    def test_weights_not_equal_one_fails(self):
        """Test that weights != 1.0 fails validation."""
        yaml_content = """
version: "1.0"
tiers:
  A: {min: 80, label: "A"}
  B: {min: 60, label: "B"}
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components:
  comp1:
    weight: 0.5
    factors:
      factor1: {weight: 1.0}
  comp2:
    weight: 0.6  # Total = 1.1, should fail
    factors:
      factor1: {weight: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="must be 1.0"):
                validate_rules(f.name)

    def test_duplicate_tier_names_fail(self):
        """Test that duplicate tier names fail validation."""
        yaml_content = """
version: "1.0"
tiers:
  tier1: {min: 80, label: "A"}
  tier2: {min: 60, label: "A"}  # Duplicate label
  tier3: {min: 40, label: "C"}
  tier4: {min: 0, label: "D"}
components:
  comp1:
    weight: 1.0
    factors:
      factor1: {weight: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="Duplicate tier labels"):
                validate_rules(f.name)

    def test_missing_tier_labels_fail(self):
        """Test that missing tier labels fail validation."""
        yaml_content = """
version: "1.0"
tiers:
  tier1: {min: 80, label: "A"}
  tier2: {min: 60, label: "B"}
  # Missing C and D
components:
  comp1:
    weight: 1.0
    factors:
      factor1: {weight: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="Missing tier configurations"):
                validate_rules(f.name)

    def test_tier_threshold_ordering(self):
        """Test that tier thresholds must be in descending order."""
        yaml_content = """
version: "1.0"
tiers:
  A: {min: 60, label: "A"}  # Should be highest
  B: {min: 80, label: "B"}  # Out of order
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components:
  comp1:
    weight: 1.0
    factors:
      factor1: {weight: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="descending order"):
                validate_rules(f.name)

    def test_factor_weights_validation(self):
        """Test that factor weights within components sum to 1.0."""
        yaml_content = """
version: "1.0"
tiers:
  A: {min: 80, label: "A"}
  B: {min: 60, label: "B"}
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components:
  comp1:
    weight: 1.0
    factors:
      factor1: {weight: 0.4}
      factor2: {weight: 0.7}  # Total = 1.1, should fail
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="Factor weights sum"):
                validate_rules(f.name)

    def test_empty_components_fail(self):
        """Test that empty components list fails."""
        yaml_content = """
version: "1.0"
tiers:
  A: {min: 80, label: "A"}
  B: {min: 60, label: "B"}
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components: {}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError, match="At least one component"):
                validate_rules(f.name)

    def test_invalid_version_format(self):
        """Test that invalid version format fails."""
        yaml_content = """
version: "1.0.0"  # Should be X.Y format
tiers:
  A: {min: 80, label: "A"}
  B: {min: 60, label: "B"}
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components:
  comp1:
    weight: 1.0
    factors:
      factor1: {weight: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ValueError):
                validate_rules(f.name)

    def test_check_missing_components(self):
        """Test checking for missing assessment fields."""
        schema = validate_rules("config/scoring_rules.yaml")

        # Simulate assessment fields
        assessment_fields = [
            "company_info",
            "contact_info",
            "location_data",
            "business_validation",
            "online_presence"
            # Missing many others
        ]

        missing = check_missing_components(schema, assessment_fields)

        # Should find components not in assessment_fields
        assert "social_signals" in missing
        assert "revenue_indicators" in missing
        assert len(missing) > 5

    def test_weight_sum_warning_threshold(self):
        """Test warning threshold for weight sums."""
        yaml_content = """
version: "1.0"
tiers:
  A: {min: 80, label: "A"}
  B: {min: 60, label: "B"}
  C: {min: 40, label: "C"}
  D: {min: 0, label: "D"}
components:
  comp1:
    weight: 0.996  # Total = 0.996, within warning threshold
    factors:
      factor1: {weight: 1.0}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            # Should not raise, but would log warning
            schema = validate_rules(f.name)
            assert schema is not None

    def test_cli_validate_command(self, monkeypatch, capsys):
        """Test CLI validate command."""
        # Test successful validation
        monkeypatch.setattr("sys.argv", ["rules_schema.py", "validate", "config/scoring_rules.yaml"])

        from d5_scoring.rules_schema import __main__

        # Should exit with 0 on success
        with pytest.raises(SystemExit) as exc_info:
            __main__()

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "✓ Validation successful" in captured.out
        assert "Version: 1.0" in captured.out
        assert "Components: 15" in captured.out
        assert "Tiers: A, B, C, D" in captured.out
