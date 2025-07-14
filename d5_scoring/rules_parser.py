"""
Scoring Rules Parser - Task 046

YAML rules loading and parsing functionality.
Handles loading, validation, and parsing of scoring rules configuration.

Acceptance Criteria:
- YAML rules loading
- Rule evaluation works
- Fallback values used
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ScoringRule:
    """Individual scoring rule with condition and points"""

    condition: str
    points: float
    description: str
    weight: float = 1.0

    def evaluate(self, data: Dict[str, Any]) -> float:
        """
        Evaluate rule condition against data

        Returns:
            Points awarded (0.0 if condition fails)
        """
        try:
            # Simple condition evaluation
            # In production, would use safer evaluation methods
            result = self._evaluate_condition(self.condition, data)
            return self.points if result else 0.0
        except Exception as e:
            logger.warning(f"Rule evaluation failed for '{self.condition}': {e}")
            return 0.0

    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """
        Safely evaluate condition string against data

        This is a simplified implementation. In production, would use
        a proper expression parser for security.
        """
        # Replace variables in condition with actual values
        safe_condition = condition

        # Handle string comparisons
        for key, value in data.items():
            if isinstance(value, str):
                # Escape single quotes in string values
                escaped_value = value.replace("'", "\\'")
                safe_condition = safe_condition.replace(key, f"'{escaped_value}'")
            else:
                safe_condition = safe_condition.replace(key, str(value))

        # Handle common operators
        safe_condition = safe_condition.replace(" in [", " in [")
        safe_condition = safe_condition.replace(" not in [", " not in [")

        # Basic safety check - only allow certain operations

        try:
            # Use eval with restricted globals for safety
            # In production, would use a proper expression evaluator
            restricted_globals = {
                "__builtins__": {},
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
            }

            return bool(eval(safe_condition, restricted_globals, {}))
        except Exception as e:
            logger.error(f"Failed to evaluate condition '{condition}': {e}")
            return False


@dataclass
class ComponentRules:
    """Collection of rules for a scoring component"""

    name: str
    weight: float
    description: str
    rules: List[ScoringRule] = field(default_factory=list)

    def calculate_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate component score by evaluating all rules

        Returns:
            Dictionary with score details
        """
        total_points = 0.0
        max_points = sum(rule.points for rule in self.rules)
        rule_results = []

        for rule in self.rules:
            points_awarded = rule.evaluate(data)
            total_points += points_awarded

            rule_results.append(
                {
                    "condition": rule.condition,
                    "description": rule.description,
                    "points_possible": rule.points,
                    "points_awarded": points_awarded,
                    "passed": points_awarded > 0,
                }
            )

        return {
            "component": self.name,
            "total_points": total_points,
            "max_points": max_points,
            "percentage": (total_points / max_points * 100) if max_points > 0 else 0.0,
            "weight": self.weight,
            "weighted_score": total_points * self.weight,
            "rule_results": rule_results,
        }


@dataclass
class TierRule:
    """Tier assignment rule"""

    name: str
    min_score: float
    max_score: float
    description: str
    priority: str

    def matches_score(self, score: float) -> bool:
        """Check if score falls within this tier's range"""
        return self.min_score <= score <= self.max_score


@dataclass
class QualityControlRules:
    """Quality control and validation rules"""

    min_data_completeness: float = 0.3
    confidence_threshold: float = 0.6
    manual_review_triggers: List[str] = field(default_factory=list)

    def requires_manual_review(self, data: Dict[str, Any], score_result: Dict[str, Any]) -> bool:
        """
        Check if scoring result requires manual review

        Returns:
            True if manual review is required
        """
        for trigger in self.manual_review_triggers:
            try:
                # Simple evaluation of trigger conditions
                if self._evaluate_trigger(trigger, data, score_result):
                    return True
            except Exception as e:
                logger.warning(f"Failed to evaluate manual review trigger '{trigger}': {e}")

        return False

    def _evaluate_trigger(self, trigger: str, data: Dict[str, Any], score_result: Dict[str, Any]) -> bool:
        """Evaluate manual review trigger condition"""
        # Combine data and score_result for evaluation
        evaluation_data = {**data, **score_result}

        # Simple condition evaluation
        try:
            # Replace variables with values
            condition = trigger
            for key, value in evaluation_data.items():
                if isinstance(value, str):
                    condition = condition.replace(key, f"'{value}'")
                else:
                    condition = condition.replace(key, str(value))

            restricted_globals = {"__builtins__": {}}
            return bool(eval(condition, restricted_globals, {}))
        except Exception:
            return False


class ScoringRulesParser:
    """
    Main parser for scoring rules YAML configuration

    Acceptance Criteria: YAML rules loading
    """

    def __init__(self, rules_file: Optional[str] = None):
        """
        Initialize parser with rules file path

        Args:
            rules_file: Path to YAML rules file. Defaults to scoring_rules.yaml
        """
        self.rules_file = rules_file or "scoring_rules.yaml"
        self.config = {}
        self.component_rules = {}
        self.tier_rules = {}
        self.fallbacks = {}
        self.quality_control = None
        self.engine_config = {}

    def load_rules(self) -> bool:
        """
        Load and parse rules from YAML file

        Returns:
            True if successfully loaded
        """
        try:
            rules_path = Path(self.rules_file)
            if not rules_path.exists():
                # Try relative to project root
                project_root = Path(__file__).parent.parent
                rules_path = project_root / self.rules_file

            if not rules_path.exists():
                logger.error(f"Rules file not found: {self.rules_file}")
                return False

            with open(rules_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)

            # Parse configuration sections
            self._parse_engine_config()
            self._parse_fallbacks()
            self._parse_component_rules()
            self._parse_tier_rules()
            self._parse_quality_control()

            logger.info(f"Successfully loaded scoring rules from {rules_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load rules from {self.rules_file}: {e}")
            return False

    def _parse_engine_config(self):
        """Parse engine configuration section"""
        self.engine_config = self.config.get("engine_config", {})

        # Set defaults
        self.engine_config.setdefault("max_score", 100.0)
        self.engine_config.setdefault("default_weight", 1.0)
        self.engine_config.setdefault("fallback_enabled", True)
        self.engine_config.setdefault("logging_enabled", True)

    def _parse_fallbacks(self):
        """Parse fallback values section"""
        self.fallbacks = self.config.get("fallbacks", {})

        # Flatten nested fallbacks for easier access
        flattened = {}
        for category, values in self.fallbacks.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    flattened[key] = value
            else:
                flattened[category] = values

        self.fallbacks = flattened

    def _parse_component_rules(self):
        """Parse scoring components section"""
        components = self.config.get("scoring_components", {})

        for component_name, component_config in components.items():
            weight = component_config.get("weight", self.engine_config["default_weight"])
            description = component_config.get("description", f"{component_name} scoring")

            rules = []
            for rule_config in component_config.get("rules", []):
                rule = ScoringRule(
                    condition=rule_config["condition"],
                    points=rule_config["points"],
                    description=rule_config["description"],
                    weight=weight,
                )
                rules.append(rule)

            self.component_rules[component_name] = ComponentRules(
                name=component_name, weight=weight, description=description, rules=rules
            )

    def _parse_tier_rules(self):
        """Parse tier assignment rules"""
        tiers = self.config.get("tier_rules", {})

        for tier_name, tier_config in tiers.items():
            self.tier_rules[tier_name] = TierRule(
                name=tier_name,
                min_score=tier_config["min_score"],
                max_score=tier_config["max_score"],
                description=tier_config["description"],
                priority=tier_config.get("priority", "medium"),
            )

    def _parse_quality_control(self):
        """Parse quality control rules"""
        qc_config = self.config.get("quality_control", {})

        self.quality_control = QualityControlRules(
            min_data_completeness=qc_config.get("min_data_completeness", 0.3),
            confidence_threshold=qc_config.get("confidence_threshold", 0.6),
            manual_review_triggers=qc_config.get("manual_review_triggers", []),
        )

    def get_component_rules(
        self, component_name: Optional[str] = None
    ) -> Union[ComponentRules, Dict[str, ComponentRules]]:
        """
        Get component rules by name or all components

        Args:
            component_name: Specific component name, or None for all

        Returns:
            Single ComponentRules or dict of all components
        """
        if component_name:
            return self.component_rules.get(component_name)
        return self.component_rules

    def get_tier_for_score(self, score: float) -> Optional[TierRule]:
        """
        Get tier rule that matches the given score

        Args:
            score: Calculated score value

        Returns:
            Matching TierRule or None
        """
        for tier_rule in self.tier_rules.values():
            if tier_rule.matches_score(score):
                return tier_rule
        return None

    def apply_fallbacks(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply fallback values for missing data

        Acceptance Criteria: Fallback values used

        Args:
            data: Input business data

        Returns:
            Data with fallbacks applied
        """
        if not self.engine_config.get("fallback_enabled", True):
            return data

        result = data.copy()

        for key, fallback_value in self.fallbacks.items():
            if key not in result or result[key] is None or result[key] == "":
                result[key] = fallback_value
                logger.debug(f"Applied fallback for '{key}': {fallback_value}")

        return result

    def validate_rules(self) -> List[str]:
        """
        Validate loaded rules for consistency and correctness

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check if rules were loaded
        if not self.config:
            errors.append("No rules configuration loaded")
            return errors

        # Validate component rules
        if not self.component_rules:
            errors.append("No component rules defined")

        for name, component in self.component_rules.items():
            if not component.rules:
                errors.append(f"Component '{name}' has no rules defined")

            if component.weight <= 0:
                errors.append(f"Component '{name}' has invalid weight: {component.weight}")

        # Validate tier rules
        if not self.tier_rules:
            errors.append("No tier rules defined")

        # Check for score gaps in tier rules
        sorted_tiers = sorted(self.tier_rules.values(), key=lambda t: t.min_score)
        for i in range(len(sorted_tiers) - 1):
            current_max = sorted_tiers[i].max_score
            next_min = sorted_tiers[i + 1].min_score
            if current_max + 0.1 < next_min:  # Allow small gap for float precision
                errors.append(f"Score gap between tiers: {current_max} to {next_min}")

        # Validate quality control
        if self.quality_control:
            if not (0 <= self.quality_control.min_data_completeness <= 1):
                errors.append(f"Invalid min_data_completeness: {self.quality_control.min_data_completeness}")

            if not (0 <= self.quality_control.confidence_threshold <= 1):
                errors.append(f"Invalid confidence_threshold: {self.quality_control.confidence_threshold}")

        return errors

    def get_rules_summary(self) -> Dict[str, Any]:
        """
        Get summary of loaded rules for debugging/monitoring

        Returns:
            Dictionary with rules summary information
        """
        return {
            "version": self.config.get("version", "unknown"),
            "components_count": len(self.component_rules),
            "component_names": list(self.component_rules.keys()),
            "total_rules": sum(len(comp.rules) for comp in self.component_rules.values()),
            "tiers_count": len(self.tier_rules),
            "tier_names": list(self.tier_rules.keys()),
            "fallbacks_count": len(self.fallbacks),
            "engine_config": self.engine_config,
            "has_quality_control": self.quality_control is not None,
        }
