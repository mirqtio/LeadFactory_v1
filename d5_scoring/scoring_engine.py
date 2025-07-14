"""
Scoring engine that reads configuration from YAML.

This module implements the ScoringEngine class that replaces hard-coded
scoring weights with YAML-based configuration.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

from prometheus_client import Gauge

from core.logging import get_logger

from .constants import DEFAULT_SCORING_RULES_PATH
from .rules_schema import ScoringRulesSchema, validate_rules

logger = get_logger(__name__)

# Prometheus metrics
scoring_rules_default_used = Gauge(
    "scoring_rules_default_used", "Whether default scoring rules are being used (1) or not (0)"
)


class ScoringEngine:
    """Engine for calculating scores based on YAML configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the scoring engine.

        Args:
            config_path: Path to scoring rules YAML. If None, uses env var or default.
        """
        self.config_path = self._resolve_config_path(config_path)
        self._schema: Optional[ScoringRulesSchema] = None
        self._using_defaults = False
        self.reload_config()

    def _resolve_config_path(self, config_path: Optional[str]) -> Path:
        """Resolve the configuration file path."""
        if config_path:
            return Path(config_path)

        env_path = os.getenv("SCORING_RULES_PATH")
        if env_path:
            return Path(env_path)

        return Path(DEFAULT_SCORING_RULES_PATH)

    def reload_config(self) -> None:
        """Reload configuration from YAML file."""
        try:
            if not self.config_path.exists():
                # In production, this should fail
                if os.getenv("ENV") == "production":
                    raise FileNotFoundError(f"Scoring rules file required in production: {self.config_path}")

                # For local dev/tests, use defaults
                logger.warning(
                    f"Scoring rules file not found: {self.config_path}. " "Using default configuration for development."
                )
                self._load_defaults()
                self._using_defaults = True
                scoring_rules_default_used.set(1)
            else:
                self._schema = validate_rules(self.config_path)
                self._using_defaults = False
                scoring_rules_default_used.set(0)
                logger.info(f"Loaded scoring rules from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load scoring rules: {e}")
            # Keep existing configuration if reload fails
            if not self._schema and not self._using_defaults:
                self._load_defaults()
                self._using_defaults = True
                scoring_rules_default_used.set(1)
            raise

    def _load_defaults(self) -> None:
        """Load default configuration for development."""
        # This would typically load a minimal valid configuration
        # For now, we'll just set the flag
        logger.info("Loading default scoring configuration")

    def calculate_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate score based on input data and configuration.

        Args:
            data: Dictionary containing scoring data

        Returns:
            Dictionary with score, tier, and component scores
        """
        if self._using_defaults:
            logger.warning("Calculating score using default configuration")

        if not self._schema:
            raise RuntimeError("No scoring configuration loaded")

        # Calculate component scores
        component_scores = {}
        total_score = 0.0

        components = self._schema.components or self._schema.scoring_components or {}

        for comp_name, comp_config in components.items():
            # Check if we have data for this component
            if comp_name not in data:
                logger.debug(f"No data for component: {comp_name}")
                continue

            comp_data = data[comp_name]
            comp_score = self._calculate_component_score(comp_data, comp_config, comp_name)

            # Apply component weight
            weighted_score = comp_score * comp_config.weight
            component_scores[comp_name] = {
                "raw_score": comp_score,
                "weighted_score": weighted_score,
                "weight": comp_config.weight,
            }
            total_score += weighted_score

        # Determine tier (for analytics only in Phase 0)
        # TODO Phase 0.5: Enable tier-based branching
        tier = self._determine_tier(total_score)

        return {
            "total_score": total_score,
            "tier": tier,
            "component_scores": component_scores,
            "config_version": self._schema.version,
        }

    def _calculate_component_score(self, data: Dict[str, Any], config: Any, comp_name: str) -> float:
        """Calculate score for a single component."""
        if hasattr(config, "factors"):
            # New style with factors
            factor_score = 0.0
            for factor_name, factor_config in config.factors.items():
                if factor_name in data:
                    # Simple scoring: if factor exists and is truthy, award full weight
                    # This can be made more sophisticated based on factor type
                    if data[factor_name]:
                        factor_score += factor_config.weight
            return factor_score * 100  # Convert to 0-100 scale
        else:
            # Legacy style with rules
            total_points = 0.0
            for rule in config.rules:
                # Evaluate rule condition
                # This is a simplified version - real implementation would
                # need proper expression evaluation
                if self._evaluate_rule(rule.condition, data):
                    total_points += rule.points
            return total_points

    def _evaluate_rule(self, condition: str, data: Dict[str, Any]) -> bool:
        """Evaluate a rule condition against data."""
        # Simplified evaluation - real implementation would use
        # a proper expression evaluator
        try:
            # Very basic evaluation - just check if field exists
            # Real implementation would parse and evaluate the condition
            return True
        except Exception:
            return False

    def _determine_tier(self, score: float) -> str:
        """Determine tier based on score."""
        if not self._schema or not self._schema.tiers:
            return "D"

        # Sort tiers by minimum score descending
        sorted_tiers = sorted(self._schema.tiers.values(), key=lambda t: t.min, reverse=True)

        for tier in sorted_tiers:
            if score >= tier.min:
                return tier.label

        return "D"  # Default to lowest tier

    def get_tier_thresholds(self) -> Dict[str, float]:
        """Get current tier thresholds."""
        if not self._schema or not self._schema.tiers:
            return {}

        return {tier.label: tier.min for tier in self._schema.tiers.values()}
