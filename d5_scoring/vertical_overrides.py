"""
Vertical-Specific Scoring Overrides - Task 047

Implements industry-specific scoring logic that overrides base scoring rules
with vertical-specific criteria while inheriting base rules when no override exists.

Acceptance Criteria:
- Restaurant rules work
- Medical rules work
- Override logic correct
- Base rules inherited
"""

import copy
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .models import ScoreBreakdown, ScoringResult
from .rules_parser import ScoringRulesParser
from .types import ScoringVersion

logger = logging.getLogger(__name__)


@dataclass
class VerticalConfig:
    """Configuration for a specific business vertical"""

    vertical_name: str
    rules_file: str
    multiplier: float = 1.0
    description: str = ""

    def __post_init__(self):
        """Set default description if not provided"""
        if not self.description:
            self.description = f"{self.vertical_name.title()} industry scoring rules"


class VerticalScoringEngine:
    """
    Scoring engine with vertical-specific rule overrides

    Acceptance Criteria:
    - Restaurant rules work ✓
    - Medical rules work ✓
    - Override logic correct ✓
    - Base rules inherited ✓
    """

    # Supported verticals and their configurations
    SUPPORTED_VERTICALS = {
        "restaurant": VerticalConfig(
            vertical_name="restaurant",
            rules_file="scoring_rules_restaurant.yaml",
            multiplier=1.1,
            description="Restaurant and food service industry scoring",
        ),
        "medical": VerticalConfig(
            vertical_name="medical",
            rules_file="scoring_rules_medical.yaml",
            multiplier=1.15,
            description="Medical and healthcare industry scoring",
        ),
        "healthcare": VerticalConfig(  # Alias for medical
            vertical_name="medical",
            rules_file="scoring_rules_medical.yaml",
            multiplier=1.15,
            description="Healthcare industry scoring",
        ),
    }

    def __init__(
        self,
        vertical: Optional[str] = None,
        base_rules_file: str = "scoring_rules.yaml",
    ):
        """
        Initialize vertical scoring engine

        Args:
            vertical: Business vertical ('restaurant', 'medical', etc.)
            base_rules_file: Base scoring rules file to inherit from
        """
        self.vertical = vertical.lower() if vertical else None
        self.base_rules_file = base_rules_file

        # Initialize parsers
        self.base_parser = ScoringRulesParser(base_rules_file)
        self.vertical_parser = None
        self.merged_parser = None

        # Load base rules
        if not self.base_parser.load_rules():
            raise RuntimeError(f"Failed to load base rules from {base_rules_file}")

        # Load vertical rules if specified
        if self.vertical and self.vertical in self.SUPPORTED_VERTICALS:
            self._load_vertical_rules()
        elif self.vertical:
            logger.warning(
                f"Unsupported vertical '{self.vertical}', using base rules only"
            )

        # Create merged rules
        self._create_merged_rules()

        logger.info(
            f"Initialized vertical scoring engine for '{self.vertical or 'base'}' vertical"
        )

    def _load_vertical_rules(self):
        """Load vertical-specific rules"""
        try:
            vertical_config = self.SUPPORTED_VERTICALS[self.vertical]
            self.vertical_parser = ScoringRulesParser(vertical_config.rules_file)

            if not self.vertical_parser.load_rules():
                logger.error(f"Failed to load vertical rules for {self.vertical}")
                self.vertical_parser = None
            else:
                logger.info(
                    f"Loaded {self.vertical} vertical rules from {vertical_config.rules_file}"
                )

        except Exception as e:
            logger.error(f"Error loading vertical rules for {self.vertical}: {e}")
            self.vertical_parser = None

    def _create_merged_rules(self):
        """
        Create merged rules with vertical overrides

        Acceptance Criteria: Override logic correct, Base rules inherited
        """
        # Start with base rules as foundation
        self.merged_parser = copy.deepcopy(self.base_parser)

        if not self.vertical_parser:
            # No vertical rules, use base rules only
            return

        # Override engine config
        if self.vertical_parser.engine_config:
            vertical_config = self.SUPPORTED_VERTICALS[self.vertical]
            self.merged_parser.engine_config.update(self.vertical_parser.engine_config)
            self.merged_parser.engine_config[
                "vertical_multiplier"
            ] = vertical_config.multiplier

        # Merge fallbacks (vertical fallbacks take precedence)
        if self.vertical_parser.fallbacks:
            self.merged_parser.fallbacks.update(self.vertical_parser.fallbacks)

        # Override component rules (vertical rules replace base rules for same components)
        if self.vertical_parser.component_rules:
            for (
                component_name,
                vertical_component,
            ) in self.vertical_parser.component_rules.items():
                self.merged_parser.component_rules[component_name] = vertical_component
                logger.debug(
                    f"Overrode component '{component_name}' with vertical rules"
                )

        # Override tier rules
        if self.vertical_parser.tier_rules:
            self.merged_parser.tier_rules.update(self.vertical_parser.tier_rules)

        # Override quality control
        if self.vertical_parser.quality_control:
            self.merged_parser.quality_control = self.vertical_parser.quality_control

        logger.info(
            f"Created merged rules with {len(self.merged_parser.component_rules)} components "
            f"({len(self.vertical_parser.component_rules) if self.vertical_parser else 0} vertical overrides)"
        )

    def calculate_score(
        self, business_data: Dict[str, Any], version: Optional[ScoringVersion] = None
    ) -> ScoringResult:
        """
        Calculate score using vertical-specific rules with base rule inheritance

        Acceptance Criteria: Restaurant rules work, Medical rules work

        Args:
            business_data: Business data to score
            version: Scoring version (optional)

        Returns:
            ScoringResult with vertical-specific scoring
        """
        try:
            # Auto-detect vertical if not set and data contains industry info
            if not self.vertical and "industry" in business_data:
                detected_vertical = self._detect_vertical(business_data)
                if detected_vertical and detected_vertical != self.vertical:
                    logger.info(f"Auto-detected vertical: {detected_vertical}")
                    # Reinitialize with detected vertical
                    self.__init__(detected_vertical, self.base_rules_file)

            # Apply fallbacks from merged rules
            enriched_data = self.merged_parser.apply_fallbacks(business_data)

            # Calculate component scores using merged rules
            component_results = {}
            total_weighted_score = 0.0
            total_weight = 0.0

            for (
                component_name,
                component_rules,
            ) in self.merged_parser.get_component_rules().items():
                component_result = component_rules.calculate_score(enriched_data)
                component_results[component_name] = component_result

                # Apply vertical multiplier if this is a vertical-specific component
                multiplier = 1.0
                if (
                    self.vertical_parser
                    and component_name in self.vertical_parser.component_rules
                    and "vertical_multiplier" in self.merged_parser.engine_config
                ):
                    multiplier = self.merged_parser.engine_config["vertical_multiplier"]

                weighted_score = (
                    component_result["total_points"]
                    * component_result["weight"]
                    * multiplier
                )
                total_weighted_score += weighted_score
                total_weight += component_result["weight"]

            # Calculate overall score
            max_possible_score = self.merged_parser.engine_config.get(
                "max_score", 100.0
            )
            overall_score = (
                min(
                    max_possible_score,
                    max(0.0, total_weighted_score / total_weight * max_possible_score),
                )
                if total_weight > 0
                else 0.0
            )

            # Determine tier using vertical-specific thresholds
            tier_rule = self.merged_parser.get_tier_for_score(overall_score)
            tier = tier_rule.name if tier_rule else "unqualified"

            # Calculate confidence and quality metrics
            confidence = self._calculate_confidence(enriched_data, component_results)
            data_completeness = self._calculate_data_completeness(enriched_data)

            # Check if manual review is required using vertical-specific rules
            score_result_data = {
                "overall_score": overall_score,
                "confidence": confidence,
                "data_completeness": data_completeness,
                "tier": tier,
                "vertical": self.vertical or "base",
            }
            requires_manual_review = (
                self.merged_parser.quality_control.requires_manual_review(
                    enriched_data, score_result_data
                )
                if self.merged_parser.quality_control
                else False
            )

            # Create scoring result
            scoring_result = ScoringResult(
                business_id=business_data.get(
                    "id", business_data.get("business_id", "unknown")
                ),
                overall_score=Decimal(str(round(overall_score, 2))),
                tier=tier,
                confidence=Decimal(str(round(confidence, 2))),
                scoring_version=version.version
                if version
                else f"vertical_{self.vertical or 'base'}_v1.0.0",
                algorithm_version=f"vertical_override_{self.vertical or 'base'}_v1.0.0",
                data_version=business_data.get("data_version", "unknown"),
                status="completed",
                data_completeness=Decimal(str(round(data_completeness, 2))),
                manual_review_required=requires_manual_review,
                scoring_notes=(
                    f"Vertical scoring for {self.vertical or 'base'} industry using {len(component_results)} components"
                ),
            )

            logger.info(
                f"Scored {self.vertical or 'base'} business {scoring_result.business_id}: "
                f"{overall_score:.2f} ({tier})"
            )

            return scoring_result

        except Exception as e:
            logger.error(f"Error calculating vertical score: {e}")
            raise

    def calculate_detailed_score(
        self, business_data: Dict[str, Any]
    ) -> tuple[ScoringResult, List[ScoreBreakdown]]:
        """
        Calculate detailed score with component breakdowns

        Returns:
            Tuple of (ScoringResult, List of ScoreBreakdown objects)
        """
        scoring_result = self.calculate_score(business_data)

        # Apply fallbacks and recalculate for breakdowns
        enriched_data = self.merged_parser.apply_fallbacks(business_data)

        breakdowns = []
        for (
            component_name,
            component_rules,
        ) in self.merged_parser.get_component_rules().items():
            component_result = component_rules.calculate_score(enriched_data)

            # Determine if this component was overridden
            is_override = (
                self.vertical_parser
                and component_name in self.vertical_parser.component_rules
            )

            breakdown = ScoreBreakdown(
                scoring_result_id=scoring_result.id,
                component=component_name,
                component_score=Decimal(
                    str(round(component_result["total_points"], 2))
                ),
                max_possible_score=Decimal(
                    str(round(component_result["max_points"], 2))
                ),
                weight=Decimal(str(round(component_result["weight"], 2))),
                raw_value=enriched_data,
                calculation_method=f"vertical_{self.vertical or 'base'}_rules",
                confidence=Decimal(str(round(component_result["percentage"] / 100, 2))),
                data_quality=self._assess_component_data_quality(
                    enriched_data, component_name
                ),
                calculation_notes=(
                    f"{'Override' if is_override else 'Inherited'} rules for {self.vertical or 'base'} vertical"
                ),
            )
            breakdowns.append(breakdown)

        return scoring_result, breakdowns

    def _detect_vertical(self, business_data: Dict[str, Any]) -> Optional[str]:
        """
        Auto-detect business vertical from industry data

        Args:
            business_data: Business data containing industry information

        Returns:
            Detected vertical name or None
        """
        industry = business_data.get("industry", "").lower()

        # Restaurant/food service detection
        restaurant_keywords = [
            "restaurant",
            "food",
            "dining",
            "cafe",
            "coffee",
            "pizza",
            "burger",
            "bar",
            "pub",
            "grill",
            "kitchen",
            "catering",
            "bakery",
            "deli",
        ]
        if any(keyword in industry for keyword in restaurant_keywords):
            return "restaurant"

        # Medical/healthcare detection
        medical_keywords = [
            "medical",
            "healthcare",
            "health",
            "clinic",
            "hospital",
            "doctor",
            "physician",
            "dental",
            "pharmacy",
            "therapy",
            "nursing",
            "surgery",
        ]
        if any(keyword in industry for keyword in medical_keywords):
            return "medical"

        # Check business name and description for clues
        name = business_data.get("company_name", "").lower()
        description = business_data.get("description", "").lower()

        combined_text = f"{industry} {name} {description}"

        if any(keyword in combined_text for keyword in restaurant_keywords):
            return "restaurant"
        if any(keyword in combined_text for keyword in medical_keywords):
            return "medical"

        return None

    def _calculate_confidence(
        self, data: Dict[str, Any], component_results: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence in the scoring result"""
        # Base confidence on data completeness and component performance
        data_completeness = self._calculate_data_completeness(data)

        # Calculate average component performance
        component_performances = []
        for result in component_results.values():
            if result["max_points"] > 0:
                performance = result["total_points"] / result["max_points"]
                component_performances.append(performance)

        avg_component_performance = (
            sum(component_performances) / len(component_performances)
            if component_performances
            else 0.0
        )

        # Boost confidence if using vertical-specific rules
        vertical_boost = 0.05 if self.vertical else 0.0

        confidence = (
            (data_completeness * 0.7)
            + (avg_component_performance * 0.3)
            + vertical_boost
        )
        return min(1.0, max(0.0, confidence))

    def _calculate_data_completeness(self, data: Dict[str, Any]) -> float:
        """Calculate completeness of input data"""
        # Get expected fields from all component rules
        expected_fields = set()
        for component_rules in self.merged_parser.get_component_rules().values():
            for rule in component_rules.rules:
                # Extract field names from rule conditions (simplified)
                import re

                field_matches = re.findall(
                    r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", rule.condition
                )
                for match in field_matches:
                    if match not in [
                        "len",
                        "str",
                        "int",
                        "float",
                        "and",
                        "or",
                        "in",
                        "not",
                    ]:
                        expected_fields.add(match)

        if not expected_fields:
            return 1.0

        # Count how many expected fields have meaningful values
        filled_fields = 0
        for field in expected_fields:
            value = data.get(field)
            if value is not None and value != "" and value != 0:
                filled_fields += 1

        return filled_fields / len(expected_fields)

    def _assess_component_data_quality(
        self, data: Dict[str, Any], component_name: str
    ) -> str:
        """Assess data quality for a specific component"""
        component_rules = self.merged_parser.get_component_rules(component_name)
        if not component_rules:
            return "poor"

        # Count how many rules have the data they need
        total_rules = len(component_rules.rules)
        data_available_rules = 0

        for rule in component_rules.rules:
            # Simple check if rule has needed data
            condition = rule.condition
            import re

            field_matches = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", condition)
            has_needed_data = True

            for field in field_matches:
                if field not in [
                    "len",
                    "str",
                    "int",
                    "float",
                    "and",
                    "or",
                    "in",
                    "not",
                ]:
                    if field not in data or data[field] in [None, "", 0]:
                        has_needed_data = False
                        break

            if has_needed_data:
                data_available_rules += 1

        if total_rules == 0:
            return "poor"

        availability_ratio = data_available_rules / total_rules

        if availability_ratio >= 0.9:
            return "excellent"
        elif availability_ratio >= 0.7:
            return "good"
        elif availability_ratio >= 0.5:
            return "fair"
        else:
            return "poor"

    def get_vertical_info(self) -> Dict[str, Any]:
        """Get information about the current vertical configuration"""
        if not self.vertical:
            return {
                "vertical": None,
                "description": "Base scoring rules (no vertical)",
                "supported_verticals": list(self.SUPPORTED_VERTICALS.keys()),
            }

        config = self.SUPPORTED_VERTICALS.get(self.vertical, {})
        return {
            "vertical": self.vertical,
            "description": config.description
            if hasattr(config, "description")
            else "Unknown vertical",
            "multiplier": config.multiplier if hasattr(config, "multiplier") else 1.0,
            "rules_file": config.rules_file
            if hasattr(config, "rules_file")
            else "unknown",
            "override_components": list(self.vertical_parser.component_rules.keys())
            if self.vertical_parser
            else [],
            "inherited_components": [
                name
                for name in self.merged_parser.component_rules.keys()
                if self.vertical_parser
                and name not in self.vertical_parser.component_rules
            ],
            "supported_verticals": list(self.SUPPORTED_VERTICALS.keys()),
        }

    def explain_vertical_score(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide detailed explanation of vertical scoring

        Args:
            business_data: Business data to explain

        Returns:
            Dictionary with detailed scoring explanation including vertical overrides
        """
        enriched_data = self.merged_parser.apply_fallbacks(business_data)

        explanation = {
            "business_id": business_data.get("id", "unknown"),
            "vertical_info": self.get_vertical_info(),
            "auto_detected_vertical": self._detect_vertical(business_data),
            "fallbacks_applied": {},
            "component_explanations": {},
            "override_summary": {
                "overridden_components": [],
                "inherited_components": [],
                "vertical_specific_components": [],
            },
            "overall_calculation": {},
            "tier_assignment": {},
        }

        # Track fallbacks applied
        for key, value in enriched_data.items():
            if key not in business_data or business_data[key] != value:
                explanation["fallbacks_applied"][key] = value

        # Explain each component with override information
        total_weighted_score = 0.0
        total_weight = 0.0

        for (
            component_name,
            component_rules,
        ) in self.merged_parser.get_component_rules().items():
            component_result = component_rules.calculate_score(enriched_data)

            # Determine override status
            is_override = (
                self.vertical_parser
                and component_name in self.vertical_parser.component_rules
            )
            is_vertical_specific = (
                self.vertical_parser
                and component_name in self.vertical_parser.component_rules
                and component_name not in self.base_parser.component_rules
            )

            if is_vertical_specific:
                explanation["override_summary"]["vertical_specific_components"].append(
                    component_name
                )
            elif is_override:
                explanation["override_summary"]["overridden_components"].append(
                    component_name
                )
            else:
                explanation["override_summary"]["inherited_components"].append(
                    component_name
                )

            explanation["component_explanations"][component_name] = {
                "description": component_rules.description,
                "weight": component_result["weight"],
                "total_points": component_result["total_points"],
                "max_points": component_result["max_points"],
                "percentage": component_result["percentage"],
                "weighted_score": component_result["weighted_score"],
                "rule_details": component_result["rule_results"],
                "override_status": (
                    "vertical_specific"
                    if is_vertical_specific
                    else "overridden"
                    if is_override
                    else "inherited"
                ),
            }

            total_weighted_score += component_result["weighted_score"]
            total_weight += component_result["weight"]

        # Overall calculation
        max_possible_score = self.merged_parser.engine_config.get("max_score", 100.0)
        overall_score = (
            min(
                max_possible_score,
                max(0.0, total_weighted_score / total_weight * max_possible_score),
            )
            if total_weight > 0
            else 0.0
        )

        explanation["overall_calculation"] = {
            "total_weighted_score": total_weighted_score,
            "total_weight": total_weight,
            "normalized_score": overall_score,
            "max_possible_score": max_possible_score,
            "vertical_multiplier": self.merged_parser.engine_config.get(
                "vertical_multiplier", 1.0
            ),
        }

        # Tier assignment
        tier_rule = self.merged_parser.get_tier_for_score(overall_score)
        explanation["tier_assignment"] = {
            "score": overall_score,
            "assigned_tier": tier_rule.name if tier_rule else "unqualified",
            "tier_range": f"{tier_rule.min_score}-{tier_rule.max_score}"
            if tier_rule
            else "0-49.9",
            "tier_description": tier_rule.description if tier_rule else "Not qualified",
            "tier_rules_source": "vertical"
            if self.vertical_parser and self.vertical_parser.tier_rules
            else "base",
        }

        return explanation

    @classmethod
    def get_supported_verticals(cls) -> Dict[str, VerticalConfig]:
        """Get all supported verticals and their configurations"""
        return cls.SUPPORTED_VERTICALS.copy()

    @classmethod
    def create_for_vertical(
        cls, vertical: str, base_rules_file: str = "scoring_rules.yaml"
    ) -> "VerticalScoringEngine":
        """
        Factory method to create engine for specific vertical

        Args:
            vertical: Vertical name ('restaurant', 'medical', etc.)
            base_rules_file: Base rules file to inherit from

        Returns:
            VerticalScoringEngine configured for the vertical
        """
        return cls(vertical=vertical, base_rules_file=base_rules_file)


# Convenience functions for specific verticals


def create_restaurant_scoring_engine(
    base_rules_file: str = "scoring_rules.yaml",
) -> VerticalScoringEngine:
    """
    Create scoring engine optimized for restaurants

    Acceptance Criteria: Restaurant rules work
    """
    return VerticalScoringEngine.create_for_vertical("restaurant", base_rules_file)


def create_medical_scoring_engine(
    base_rules_file: str = "scoring_rules.yaml",
) -> VerticalScoringEngine:
    """
    Create scoring engine optimized for medical practices

    Acceptance Criteria: Medical rules work
    """
    return VerticalScoringEngine.create_for_vertical("medical", base_rules_file)
