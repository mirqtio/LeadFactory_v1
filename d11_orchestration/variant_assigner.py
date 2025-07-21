"""
D11 Orchestration Variant Assigner - Task 077

Deterministic variant assignment system for A/B testing with consistent
hashing, weight distribution, and control group handling.

Acceptance Criteria:
- Variant assignment works ✓
- Deterministic hashing ✓
- Weight distribution ✓
- Control group handled ✓
"""

import hashlib
from dataclasses import dataclass
from typing import Any

from core.exceptions import ValidationError

from .models import Experiment, ExperimentVariant, VariantType


@dataclass
class VariantWeight:
    """Weighted variant for assignment calculation"""

    variant: ExperimentVariant
    cumulative_weight: float


class VariantAssigner:
    """
    Deterministic variant assignment system

    Provides consistent, deterministic assignment of users to experiment
    variants using hashing algorithms and weight distribution.
    """

    def __init__(self, hash_algorithm: str = "sha256"):
        """
        Initialize variant assigner

        Args:
            hash_algorithm: Hash algorithm to use for deterministic assignment
        """
        self.hash_algorithm = hash_algorithm

    def assign_variant(self, experiment: Experiment, assignment_unit: str) -> ExperimentVariant:
        """
        Variant assignment works - Assign user to experiment variant

        Uses deterministic hashing and weight distribution to consistently
        assign the same variant to the same assignment unit.

        Args:
            experiment: The experiment to assign variant for
            assignment_unit: The unit to assign (user_id, session_id, etc.)

        Returns:
            ExperimentVariant: The assigned variant

        Raises:
            ValidationError: If experiment has no variants or invalid configuration
        """

        if not experiment.variants:
            raise ValidationError("Experiment has no variants")

        # Deterministic hashing - Generate consistent hash for assignment unit
        assignment_hash = self.calculate_hash(experiment.experiment_id, assignment_unit)

        # Weight distribution - Calculate weighted variant assignment
        variant = self._select_variant_by_weight(experiment.variants, assignment_hash)

        return variant

    def calculate_hash(self, experiment_id: str, assignment_unit: str) -> str:
        """
        Deterministic hashing - Calculate hash for consistent assignment

        Creates a deterministic hash based on experiment ID and assignment unit
        that will always produce the same result for the same inputs.

        Args:
            experiment_id: Unique experiment identifier
            assignment_unit: Unit being assigned (user_id, session_id, etc.)

        Returns:
            str: Hexadecimal hash string
        """

        # Combine experiment ID and assignment unit for unique hash
        combined_string = f"{experiment_id}:{assignment_unit}"

        # Create hash using specified algorithm
        if self.hash_algorithm == "md5":
            hasher = hashlib.md5()
        elif self.hash_algorithm == "sha1":
            hasher = hashlib.sha1()
        elif self.hash_algorithm == "sha256":
            hasher = hashlib.sha256()
        else:
            raise ValidationError(f"Unsupported hash algorithm: {self.hash_algorithm}")

        hasher.update(combined_string.encode("utf-8"))
        return hasher.hexdigest()

    def get_variant_weights(self, variants: list[ExperimentVariant]) -> dict[str, float]:
        """
        Weight distribution - Calculate normalized variant weights

        Converts variant weights to percentages that sum to 100%.
        Handles control group special weighting if needed.

        Args:
            variants: List of experiment variants

        Returns:
            Dict[str, float]: Mapping of variant keys to normalized weights (0-1)
        """

        if not variants:
            return {}

        # Calculate total weight
        total_weight = sum(variant.weight for variant in variants)

        if total_weight <= 0:
            # If no weights specified, distribute equally
            equal_weight = 1.0 / len(variants)
            return {variant.variant_key: equal_weight for variant in variants}

        # Normalize weights to sum to 1.0
        normalized_weights = {}
        for variant in variants:
            normalized_weights[variant.variant_key] = variant.weight / total_weight

        return normalized_weights

    def calculate_assignment_bucket(self, assignment_hash: str, bucket_count: int = 10000) -> int:
        """
        Calculate assignment bucket from hash for percentage-based assignment

        Converts hash to a bucket number for percentage calculations.
        Uses basis points (10000 buckets) for precise percentage handling.

        Args:
            assignment_hash: Hash string for assignment
            bucket_count: Number of buckets (default 10000 for basis points)

        Returns:
            int: Bucket number (0 to bucket_count-1)
        """

        # Use first 8 characters of hash for bucket calculation
        hash_prefix = assignment_hash[:8]

        # Convert to integer and mod by bucket count
        hash_int = int(hash_prefix, 16)
        return hash_int % bucket_count

    def is_in_control_group(self, experiment: Experiment, assignment_unit: str) -> bool:
        """
        Control group handled - Check if assignment unit is in control group

        Determines if the given assignment unit should be assigned to the
        control group based on control group percentage and deterministic hashing.

        Args:
            experiment: The experiment to check
            assignment_unit: The unit to check assignment for

        Returns:
            bool: True if unit should be in control group
        """

        # Find control variant
        control_variants = [v for v in experiment.variants if v.is_control]

        if not control_variants:
            return False

        # Calculate assignment hash
        assignment_hash = self.calculate_hash(experiment.experiment_id, assignment_unit)

        # Check if assigned to control variant
        assigned_variant = self._select_variant_by_weight(experiment.variants, assignment_hash)

        return assigned_variant.is_control

    def get_assignment_probability(self, experiment: Experiment, variant_key: str) -> float:
        """
        Get the probability of assignment to a specific variant

        Args:
            experiment: The experiment
            variant_key: Key of the variant to check

        Returns:
            float: Probability of assignment (0.0 to 1.0)
        """

        weights = self.get_variant_weights(experiment.variants)
        return weights.get(variant_key, 0.0)

    def validate_variant_distribution(self, variants: list[ExperimentVariant]) -> bool:
        """
        Validate that variant distribution is valid

        Checks that variants have valid weights and control group configuration.

        Args:
            variants: List of experiment variants

        Returns:
            bool: True if distribution is valid

        Raises:
            ValidationError: If distribution is invalid
        """

        if not variants:
            raise ValidationError("No variants provided")

        # Check for negative weights
        negative_weights = [v for v in variants if v.weight < 0]
        if negative_weights:
            raise ValidationError("Variant weights cannot be negative")

        # Check total weight
        total_weight = sum(v.weight for v in variants)
        if total_weight <= 0:
            raise ValidationError("Total variant weight must be greater than 0")

        # Control group handled - Validate control group configuration
        control_variants = [v for v in variants if v.is_control]
        if len(control_variants) > 1:
            raise ValidationError("Only one control variant is allowed")

        if control_variants:
            control_variant = control_variants[0]
            if control_variant.variant_type != VariantType.CONTROL:
                raise ValidationError("Control variant must have CONTROL type")

        # Check for duplicate variant keys
        variant_keys = [v.variant_key for v in variants]
        if len(variant_keys) != len(set(variant_keys)):
            raise ValidationError("Variant keys must be unique")

        return True

    def simulate_assignment_distribution(self, experiment: Experiment, sample_size: int = 10000) -> dict[str, float]:
        """
        Simulate variant assignment distribution for testing

        Generates sample assignments to verify weight distribution is working correctly.

        Args:
            experiment: The experiment to simulate
            sample_size: Number of assignments to simulate

        Returns:
            Dict[str, float]: Actual distribution percentages by variant key
        """

        assignment_counts = {v.variant_key: 0 for v in experiment.variants}

        # Simulate assignments
        for i in range(sample_size):
            # Use incrementing assignment units for simulation
            assignment_unit = f"user_{i}"

            try:
                assigned_variant = self.assign_variant(experiment, assignment_unit)
                assignment_counts[assigned_variant.variant_key] += 1
            except Exception:
                # Skip failed assignments in simulation
                continue

        # Calculate actual percentages
        actual_distribution = {}
        for variant_key, count in assignment_counts.items():
            actual_distribution[variant_key] = count / sample_size

        return actual_distribution

    def _select_variant_by_weight(self, variants: list[ExperimentVariant], assignment_hash: str) -> ExperimentVariant:
        """
        Weight distribution - Select variant based on weights and hash

        Uses the assignment hash to deterministically select a variant
        based on the configured weight distribution.

        Args:
            variants: List of available variants
            assignment_hash: Hash for deterministic selection

        Returns:
            ExperimentVariant: Selected variant
        """

        # Get bucket for assignment (0-9999 for basis points)
        assignment_bucket = self.calculate_assignment_bucket(assignment_hash)

        # Calculate cumulative weights
        weighted_variants = []
        total_weight = sum(v.weight for v in variants)
        cumulative_weight = 0.0

        for variant in variants:
            # Calculate normalized weight as basis points
            variant_weight = (variant.weight / total_weight) * 10000
            cumulative_weight += variant_weight

            weighted_variants.append(VariantWeight(variant=variant, cumulative_weight=cumulative_weight))

        # Find variant based on assignment bucket
        for weighted_variant in weighted_variants:
            if assignment_bucket < weighted_variant.cumulative_weight:
                return weighted_variant.variant

        # Fallback to last variant (handles floating point precision issues)
        return weighted_variants[-1].variant

    def get_deterministic_assignment_info(self, experiment: Experiment, assignment_unit: str) -> dict[str, Any]:
        """
        Get detailed information about deterministic assignment

        Useful for debugging and understanding how assignment works.

        Args:
            experiment: The experiment
            assignment_unit: The assignment unit

        Returns:
            Dict[str, Any]: Assignment debugging information
        """

        assignment_hash = self.calculate_hash(experiment.experiment_id, assignment_unit)
        assignment_bucket = self.calculate_assignment_bucket(assignment_hash)
        assigned_variant = self.assign_variant(experiment, assignment_unit)
        variant_weights = self.get_variant_weights(experiment.variants)

        return {
            "assignment_unit": assignment_unit,
            "assignment_hash": assignment_hash,
            "assignment_bucket": assignment_bucket,
            "bucket_percentage": assignment_bucket / 100.0,  # Convert to percentage
            "assigned_variant_key": assigned_variant.variant_key,
            "assigned_variant_type": assigned_variant.variant_type.value,
            "is_control": assigned_variant.is_control,
            "variant_weights": variant_weights,
            "experiment_id": experiment.experiment_id,
            "experiment_name": experiment.name,
        }
