"""Schema and validator for scoring rules YAML files

This module defines the Pydantic models representing the canonical
`scoring_rules.yaml` structure introduced in Phase-0 (S-1).

It also exposes a reusable `validate_rules(path)` helper that loads the YAML
file, validates it against the schema, and enforces a few additional business
rules (e.g. component weights must sum to **1.0**).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator, validator

from core.logging import get_logger

from .constants import (
    DEFAULT_SCORING_RULES_PATH,
    VALID_TIER_LABELS,
    WEIGHT_SUM_ERROR_THRESHOLD,
    WEIGHT_SUM_WARNING_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Constants & logging
# ---------------------------------------------------------------------------

_TOLERANCE_SOFT = WEIGHT_SUM_WARNING_THRESHOLD  # Warn if deviation > 0.005
_TOLERANCE_HARD = WEIGHT_SUM_ERROR_THRESHOLD  # Error if deviation > 0.05
_DEFAULT_RULES_PATH = Path(DEFAULT_SCORING_RULES_PATH)
_logger = get_logger("scoring.rules_schema")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TierConfig(BaseModel):
    """Configuration for a scoring tier."""

    min: float = Field(..., ge=0, le=100, description="Minimum score for this tier")
    label: str = Field(..., description="Tier label (A, B, C, or D)")

    @validator("label")
    def validate_label(cls, v):
        if v not in VALID_TIER_LABELS:
            raise ValueError(f"Tier label must be one of {VALID_TIER_LABELS}, got '{v}'")
        return v


class FactorConfig(BaseModel):
    """Configuration for a scoring factor within a component."""

    weight: float = Field(..., ge=0, le=1, description="Factor weight (0-1)")


class ComponentConfig(BaseModel):
    """Configuration for a scoring component."""

    weight: float = Field(..., ge=0, le=1, description="Component weight (0-1)")
    factors: dict[str, FactorConfig] = Field(..., description="Factors within this component")

    @validator("factors")
    def validate_factor_weights(cls, v):
        """Ensure factor weights sum to 1.0 within tolerance."""
        if not v:
            raise ValueError("Component must have at least one factor")

        total = sum(factor.weight for factor in v.values())
        diff = abs(total - 1.0)

        if diff > _TOLERANCE_HARD:
            raise ValueError(f"Factor weights sum to {total:.3f}, must be 1.0 ± {_TOLERANCE_HARD}")
        if diff > _TOLERANCE_SOFT:
            _logger.warning(f"Factor weights sum to {total:.3f}, should be 1.0 ± {_TOLERANCE_SOFT}")

        return v


class Rule(BaseModel):
    """Single atomic rule within a component."""

    condition: str = Field(..., description="Boolean expression evaluated at runtime")
    points: float = Field(..., ge=0, description="Points awarded if condition is true")
    description: str | None = None


class ScoringComponent(BaseModel):
    """Declarative description of a scoring component."""

    weight: float = Field(..., gt=0, description="Relative weight, expected to sum to 1.0 across components")
    description: str | None = None
    rules: list[Rule] = Field(default_factory=list)


class EngineConfig(BaseModel):
    """Top-level engine parameters that don’t affect schema validation heavily."""

    max_score: float = 100.0
    default_weight: float = 1.0
    fallback_enabled: bool = True
    logging_enabled: bool = True
    vertical_multiplier: float | None = None


class ScoringRulesSchema(BaseModel):
    """Root schema for the scoring rules document."""

    version: str = Field(..., pattern=r"^\d+\.\d+$", description="Configuration version")
    tiers: dict[str, TierConfig] = Field(..., description="Tier configurations")
    components: dict[str, ComponentConfig] = Field(..., description="Component configurations")
    formulas: dict[str, str] | None = Field(default=None, description="Excel formulas for scoring")

    # Legacy fields kept for compatibility
    vertical: str | None = None
    base_rules: str | None = None
    engine_config: EngineConfig | None = Field(default_factory=EngineConfig)
    scoring_components: dict[str, ScoringComponent] | None = None

    @validator("tiers")
    def validate_tiers(cls, v):
        """Ensure all tier labels are present and thresholds are valid."""
        labels = {tier.label for tier in v.values()}
        missing = set(VALID_TIER_LABELS) - labels
        if missing:
            raise ValueError(f"Missing tier configurations for: {missing}")

        # Check for duplicate labels
        if len(labels) != len(v):
            raise ValueError("Duplicate tier labels found")

        # Validate threshold ordering
        sorted_tiers = sorted(v.values(), key=lambda t: t.min, reverse=True)
        for i in range(len(sorted_tiers) - 1):
            if sorted_tiers[i].min <= sorted_tiers[i + 1].min:
                raise ValueError(
                    f"Tier thresholds must be in descending order. "
                    f"'{sorted_tiers[i].label}' min ({sorted_tiers[i].min}) must be > "
                    f"'{sorted_tiers[i + 1].label}' min ({sorted_tiers[i + 1].min})"
                )

        return v

    @model_validator(mode="after")
    def _validate_component_weights(self) -> ScoringRulesSchema:  # noqa: D401
        """Ensure component weights add up to ~1.0 within tolerance.

        * Hard error if total deviation > ``_TOLERANCE_HARD`` (0.05).
        * Warning if deviation > ``_TOLERANCE_SOFT`` (0.005).
        """
        # Support both new 'components' and legacy 'scoring_components'
        components = self.components or self.scoring_components
        if not components:
            raise ValueError("At least one component must be defined")

        # Calculate total weight based on component type
        if self.components:
            total_weight = sum(comp.weight for comp in self.components.values())
        else:
            total_weight = sum(comp.weight for comp in self.scoring_components.values())

        deviation = abs(total_weight - 1.0)

        if deviation > _TOLERANCE_HARD:
            raise ValueError(
                f"Component weights must sum to 1.0 ± {_TOLERANCE_HARD}. "
                f"Current total={total_weight:.4f} (deviation={deviation:.4f})."
            )

        if deviation > _TOLERANCE_SOFT:
            _logger.warning(
                "component_weights_outside_soft_tolerance",
                extra={"total_weight": total_weight, "deviation": deviation},
            )
        return self

    @model_validator(mode="after")
    def _validate_formulas(self) -> ScoringRulesSchema:
        """Validate Excel formulas if present."""
        if self.formulas:
            from .formula_evaluator import validate_formula

            for formula_name, formula in self.formulas.items():
                errors = validate_formula(formula)
                if errors:
                    raise ValueError(f"Invalid formula '{formula_name}': {'; '.join(errors)}")

        return self


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def resolve_rules_path() -> Path:
    """Return the effective scoring rules path.

    Checks ``SCORING_RULES_PATH`` env var first; falls back to the default path.
    """
    env_path = os.getenv("SCORING_RULES_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_RULES_PATH


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def validate_rules(path: os.PathLike | str) -> ScoringRulesSchema:  # noqa: D401
    """Load a YAML file and return a validated ``ScoringRulesSchema`` instance.

    Args:
        path: Path to a YAML file on disk.

    Raises:
        ValidationError: If the YAML structure does not match the schema.
        ValueError:       If business-rule validation fails (e.g., weight sum).
    """

    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Scoring rules file not found: {path_obj}")

    with path_obj.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    try:
        return ScoringRulesSchema.model_validate(data)
    except ValidationError as exc:
        # Re-raise with clearer context for CI logs
        raise ValidationError(f"Validation failed for scoring rules file '{path_obj}': {exc}") from exc


def check_missing_components(schema: ScoringRulesSchema, assessment_fields: list[str]) -> list[str]:
    """
    Check for components in config that don't exist in assessment.

    Args:
        schema: Validated scoring rules schema
        assessment_fields: List of available assessment field names

    Returns:
        List of component names that don't have matching assessment fields
    """
    missing = []
    components = schema.components or schema.scoring_components or {}
    for component_name in components:
        if component_name not in assessment_fields:
            _logger.warning(f"Component '{component_name}' in scoring rules has no matching assessment field")
            missing.append(component_name)
    return missing


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------


def __main__():
    """CLI interface for validating scoring rules."""
    if len(sys.argv) < 2:
        print("Usage: python -m d5_scoring.rules_schema validate <path>")
        sys.exit(1)

    command = sys.argv[1]
    if command != "validate":
        print(f"Unknown command: {command}")
        print("Usage: python -m d5_scoring.rules_schema validate <path>")
        sys.exit(1)

    if len(sys.argv) < 3:
        print("Usage: python -m d5_scoring.rules_schema validate <path>")
        sys.exit(1)

    path = sys.argv[2]

    try:
        schema = validate_rules(path)
        print(f"✓ Validation successful for {path}")
        print(f"  Version: {schema.version}")

        # Handle both new and legacy components
        if schema.components:
            print(f"  Components: {len(schema.components)}")
            total_weight = sum(c.weight for c in schema.components.values())
        elif schema.scoring_components:
            print(f"  Components: {len(schema.scoring_components)}")
            total_weight = sum(c.weight for c in schema.scoring_components.values())
        else:
            print("  Components: 0")
            total_weight = 0

        print(f"  Tiers: {', '.join(sorted(t.label for t in schema.tiers.values()))}")
        print(f"  Total component weight: {total_weight:.3f}")

    except Exception as e:
        print(f"✗ Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    __main__()
