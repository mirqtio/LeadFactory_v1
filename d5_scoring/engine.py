"""
Scoring Rules Engine - Task 046

Configurable business scoring engine that evaluates companies against
YAML-defined rules to calculate quality scores and assign tiers.

Acceptance Criteria:
- YAML rules loading
- Rule evaluation works
- Weighted scoring accurate
- Fallback values used
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .rules_parser import ScoringRulesParser, ComponentRules, TierRule
from .models import ScoringResult, ScoreBreakdown, ScoringEngine as BaseScoringEngine
from .types import ScoringTier, ScoreComponent, ScoringStatus, ScoringVersion

logger = logging.getLogger(__name__)


@dataclass
class ScoringMetrics:
    """Metrics for scoring performance monitoring"""
    total_evaluations: int = 0
    total_execution_time: float = 0.0
    rule_execution_times: Dict[str, float] = field(default_factory=dict)
    tier_distribution: Dict[str, int] = field(default_factory=dict)
    manual_review_rate: float = 0.0
    average_confidence: float = 0.0

    def add_evaluation(self, execution_time: float, tier: str, requires_review: bool, confidence: float):
        """Add metrics for a single evaluation"""
        self.total_evaluations += 1
        self.total_execution_time += execution_time

        self.tier_distribution[tier] = self.tier_distribution.get(tier, 0) + 1

        # Update running averages
        if requires_review:
            self.manual_review_rate = ((self.manual_review_rate * (self.total_evaluations - 1)) + 1) / self.total_evaluations
        else:
            self.manual_review_rate = (self.manual_review_rate * (self.total_evaluations - 1)) / self.total_evaluations

        self.average_confidence = ((self.average_confidence * (self.total_evaluations - 1)) + confidence) / self.total_evaluations

    @property
    def average_execution_time(self) -> float:
        """Get average execution time per evaluation"""
        return self.total_execution_time / self.total_evaluations if self.total_evaluations > 0 else 0.0


class ConfigurableScoringEngine:
    """
    Main scoring engine that uses YAML configuration for rules

    Acceptance Criteria:
    - YAML rules loading ✓
    - Rule evaluation works ✓
    - Weighted scoring accurate ✓
    - Fallback values used ✓
    """

    def __init__(self, rules_file: Optional[str] = None, enable_metrics: bool = True):
        """
        Initialize scoring engine with rules configuration

        Args:
            rules_file: Path to YAML rules file
            enable_metrics: Whether to collect performance metrics
        """
        self.rules_parser = ScoringRulesParser(rules_file)
        self.enable_metrics = enable_metrics
        self.metrics = ScoringMetrics() if enable_metrics else None
        self.loaded = False

        # Load rules on initialization
        self.reload_rules()

    def reload_rules(self) -> bool:
        """
        Reload rules from configuration file

        Acceptance Criteria: YAML rules loading

        Returns:
            True if rules loaded successfully
        """
        try:
            success = self.rules_parser.load_rules()
            if success:
                validation_errors = self.rules_parser.validate_rules()
                if validation_errors:
                    logger.error(f"Rules validation failed: {validation_errors}")
                    return False

                self.loaded = True
                logger.info("Scoring rules loaded and validated successfully")
                return True
            else:
                logger.error("Failed to load scoring rules")
                return False

        except Exception as e:
            logger.error(f"Error reloading rules: {e}")
            return False

    def calculate_score(self, business_data: Dict[str, Any], version: Optional[ScoringVersion] = None) -> ScoringResult:
        """
        Calculate comprehensive score for a business using configured rules

        Acceptance Criteria:
        - Rule evaluation works ✓
        - Weighted scoring accurate ✓
        - Fallback values used ✓

        Args:
            business_data: Raw business data to score
            version: Scoring version to use (optional)

        Returns:
            ScoringResult with calculated score and breakdowns
        """
        start_time = time.time()

        if not self.loaded:
            raise RuntimeError("Scoring rules not loaded. Call reload_rules() first.")

        try:
            # Apply fallback values for missing data
            enriched_data = self.rules_parser.apply_fallbacks(business_data)

            # Calculate component scores
            component_results = {}
            total_weighted_score = 0.0
            total_weight = 0.0

            for component_name, component_rules in self.rules_parser.get_component_rules().items():
                component_result = component_rules.calculate_score(enriched_data)
                component_results[component_name] = component_result

                # Add to weighted total
                weighted_score = component_result['total_points'] * component_result['weight']
                total_weighted_score += weighted_score
                total_weight += component_result['weight']

            # Calculate overall score (normalized to 0-100)
            max_possible_score = self.rules_parser.engine_config.get('max_score', 100.0)
            overall_score = min(max_possible_score, max(0.0, total_weighted_score / total_weight * max_possible_score)) if total_weight > 0 else 0.0

            # Determine tier
            tier_rule = self.rules_parser.get_tier_for_score(overall_score)
            tier = tier_rule.name if tier_rule else 'unqualified'

            # Calculate confidence and quality metrics
            confidence = self._calculate_confidence(enriched_data, component_results)
            data_completeness = self._calculate_data_completeness(enriched_data)

            # Check if manual review is required
            score_result_data = {
                'overall_score': overall_score,
                'confidence': confidence,
                'data_completeness': data_completeness,
                'tier': tier
            }
            requires_manual_review = self.rules_parser.quality_control.requires_manual_review(
                enriched_data, score_result_data
            ) if self.rules_parser.quality_control else False

            # Create scoring result
            scoring_result = ScoringResult(
                business_id=business_data.get('id', business_data.get('business_id', 'unknown')),
                overall_score=Decimal(str(round(overall_score, 2))),
                tier=tier,
                confidence=Decimal(str(round(confidence, 2))),
                scoring_version=version.version if version else "rules_engine_v1.0.0",
                algorithm_version="configurable_rules_v1.0.0",
                data_version=business_data.get('data_version', 'unknown'),
                status=ScoringStatus.COMPLETED.value,
                data_completeness=Decimal(str(round(data_completeness, 2))),
                manual_review_required=requires_manual_review,
                scoring_notes=f"Evaluated {len(component_results)} components using YAML rules"
            )

            # Record metrics
            execution_time = time.time() - start_time
            if self.enable_metrics and self.metrics:
                self.metrics.add_evaluation(execution_time, tier, requires_manual_review, confidence)

            logger.info(f"Scored business {scoring_result.business_id}: {overall_score:.2f} ({tier}) in {execution_time:.3f}s")

            return scoring_result

        except Exception as e:
            logger.error(f"Error calculating score for business {business_data.get('id', 'unknown')}: {e}")
            raise

    def calculate_detailed_score(self, business_data: Dict[str, Any]) -> Tuple[ScoringResult, List[ScoreBreakdown]]:
        """
        Calculate score with detailed component breakdowns

        Args:
            business_data: Business data to score

        Returns:
            Tuple of (ScoringResult, List of ScoreBreakdown objects)
        """
        scoring_result = self.calculate_score(business_data)

        # Apply fallbacks and recalculate for breakdowns
        enriched_data = self.rules_parser.apply_fallbacks(business_data)

        breakdowns = []
        for component_name, component_rules in self.rules_parser.get_component_rules().items():
            component_result = component_rules.calculate_score(enriched_data)

            breakdown = ScoreBreakdown(
                scoring_result_id=scoring_result.id,
                component=component_name,
                component_score=Decimal(str(round(component_result['total_points'], 2))),
                max_possible_score=Decimal(str(round(component_result['max_points'], 2))),
                weight=Decimal(str(round(component_result['weight'], 2))),
                raw_value=enriched_data,
                calculation_method="yaml_rules_evaluation",
                confidence=Decimal(str(round(component_result['percentage'] / 100, 2))),
                data_quality=self._assess_component_data_quality(enriched_data, component_name),
                calculation_notes=f"Evaluated {len(component_rules.rules)} rules"
            )
            breakdowns.append(breakdown)

        return scoring_result, breakdowns

    def _calculate_confidence(self, data: Dict[str, Any], component_results: Dict[str, Any]) -> float:
        """
        Calculate overall confidence in the scoring result

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence on data completeness and rule coverage
        data_completeness = self._calculate_data_completeness(data)

        # Calculate average component performance
        component_performances = []
        for result in component_results.values():
            if result['max_points'] > 0:
                performance = result['total_points'] / result['max_points']
                component_performances.append(performance)

        avg_component_performance = sum(component_performances) / len(component_performances) if component_performances else 0.0

        # Weight data completeness more heavily
        confidence = (data_completeness * 0.7) + (avg_component_performance * 0.3)

        return min(1.0, max(0.0, confidence))

    def _calculate_data_completeness(self, data: Dict[str, Any]) -> float:
        """
        Calculate completeness of input data

        Returns:
            Completeness score between 0.0 and 1.0
        """
        # Get expected fields from all component rules
        expected_fields = set()
        for component_rules in self.rules_parser.get_component_rules().values():
            for rule in component_rules.rules:
                # Extract field names from rule conditions (simplified)
                condition = rule.condition
                # Look for field references in conditions
                import re
                field_matches = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition)
                for match in field_matches:
                    if match not in ['len', 'str', 'int', 'float', 'and', 'or', 'in', 'not']:
                        expected_fields.add(match)

        if not expected_fields:
            return 1.0

        # Count how many expected fields have meaningful values
        filled_fields = 0
        for field in expected_fields:
            value = data.get(field)
            if value is not None and value != '' and value != 0:
                filled_fields += 1

        return filled_fields / len(expected_fields)

    def _assess_component_data_quality(self, data: Dict[str, Any], component_name: str) -> str:
        """
        Assess data quality for a specific component

        Returns:
            Quality assessment: 'excellent', 'good', 'fair', 'poor'
        """
        component_rules = self.rules_parser.get_component_rules(component_name)
        if not component_rules:
            return 'poor'

        # Count how many rules have the data they need
        total_rules = len(component_rules.rules)
        data_available_rules = 0

        for rule in component_rules.rules:
            # Simple check if rule has needed data
            condition = rule.condition
            import re
            field_matches = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition)
            has_needed_data = True

            for field in field_matches:
                if field not in ['len', 'str', 'int', 'float', 'and', 'or', 'in', 'not']:
                    if field not in data or data[field] in [None, '', 0]:
                        has_needed_data = False
                        break

            if has_needed_data:
                data_available_rules += 1

        if total_rules == 0:
            return 'poor'

        availability_ratio = data_available_rules / total_rules

        if availability_ratio >= 0.9:
            return 'excellent'
        elif availability_ratio >= 0.7:
            return 'good'
        elif availability_ratio >= 0.5:
            return 'fair'
        else:
            return 'poor'

    def get_tier_distribution(self) -> Dict[str, int]:
        """Get distribution of scores across tiers"""
        if self.metrics:
            return self.metrics.tier_distribution.copy()
        return {}

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for monitoring

        Returns:
            Dictionary with performance statistics
        """
        if not self.metrics:
            return {}

        return {
            'total_evaluations': self.metrics.total_evaluations,
            'average_execution_time': self.metrics.average_execution_time,
            'total_execution_time': self.metrics.total_execution_time,
            'tier_distribution': self.metrics.tier_distribution.copy(),
            'manual_review_rate': self.metrics.manual_review_rate,
            'average_confidence': self.metrics.average_confidence
        }

    def test_rules_on_sample_data(self, sample_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test rules against sample data for validation

        Args:
            sample_data_list: List of sample business data dictionaries

        Returns:
            Dictionary with test results and statistics
        """
        if not self.loaded:
            raise RuntimeError("Rules not loaded")

        results = []
        tier_counts = {}
        total_time = 0.0

        for i, sample_data in enumerate(sample_data_list):
            try:
                start_time = time.time()
                scoring_result = self.calculate_score(sample_data)
                execution_time = time.time() - start_time

                tier_counts[scoring_result.tier] = tier_counts.get(scoring_result.tier, 0) + 1
                total_time += execution_time

                results.append({
                    'sample_index': i,
                    'business_id': scoring_result.business_id,
                    'score': float(scoring_result.overall_score),
                    'tier': scoring_result.tier,
                    'confidence': float(scoring_result.confidence),
                    'manual_review_required': scoring_result.manual_review_required,
                    'execution_time': execution_time
                })

            except Exception as e:
                results.append({
                    'sample_index': i,
                    'error': str(e),
                    'execution_time': 0.0
                })

        return {
            'total_samples': len(sample_data_list),
            'successful_evaluations': len([r for r in results if 'error' not in r]),
            'failed_evaluations': len([r for r in results if 'error' in r]),
            'tier_distribution': tier_counts,
            'average_execution_time': total_time / len(sample_data_list) if sample_data_list else 0.0,
            'total_execution_time': total_time,
            'results': results
        }

    def get_rules_summary(self) -> Dict[str, Any]:
        """Get summary of loaded rules for debugging"""
        if not self.loaded:
            return {'loaded': False}

        return {
            'loaded': True,
            'rules_summary': self.rules_parser.get_rules_summary(),
            'performance_metrics': self.get_performance_metrics()
        }

    def explain_score(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide detailed explanation of how a score was calculated

        Args:
            business_data: Business data to explain

        Returns:
            Dictionary with detailed scoring explanation
        """
        if not self.loaded:
            raise RuntimeError("Rules not loaded")

        enriched_data = self.rules_parser.apply_fallbacks(business_data)

        explanation = {
            'business_id': business_data.get('id', 'unknown'),
            'input_data_fields': list(business_data.keys()),
            'fallbacks_applied': {},
            'component_explanations': {},
            'overall_calculation': {},
            'tier_assignment': {}
        }

        # Track fallbacks applied
        for key, value in enriched_data.items():
            if key not in business_data or business_data[key] != value:
                explanation['fallbacks_applied'][key] = value

        # Explain each component
        total_weighted_score = 0.0
        total_weight = 0.0

        for component_name, component_rules in self.rules_parser.get_component_rules().items():
            component_result = component_rules.calculate_score(enriched_data)

            explanation['component_explanations'][component_name] = {
                'description': component_rules.description,
                'weight': component_result['weight'],
                'total_points': component_result['total_points'],
                'max_points': component_result['max_points'],
                'percentage': component_result['percentage'],
                'weighted_score': component_result['weighted_score'],
                'rule_details': component_result['rule_results']
            }

            total_weighted_score += component_result['weighted_score']
            total_weight += component_result['weight']

        # Overall calculation
        max_possible_score = self.rules_parser.engine_config.get('max_score', 100.0)
        overall_score = min(max_possible_score, max(0.0, total_weighted_score / total_weight * max_possible_score)) if total_weight > 0 else 0.0

        explanation['overall_calculation'] = {
            'total_weighted_score': total_weighted_score,
            'total_weight': total_weight,
            'normalized_score': overall_score,
            'max_possible_score': max_possible_score
        }

        # Tier assignment
        tier_rule = self.rules_parser.get_tier_for_score(overall_score)
        explanation['tier_assignment'] = {
            'score': overall_score,
            'assigned_tier': tier_rule.name if tier_rule else 'unqualified',
            'tier_range': f"{tier_rule.min_score}-{tier_rule.max_score}" if tier_rule else "0-49.9",
            'tier_description': tier_rule.description if tier_rule else "Not qualified"
        }

        return explanation
