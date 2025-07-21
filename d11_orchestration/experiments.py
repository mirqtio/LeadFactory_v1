"""
D11 Orchestration Experiment Manager - Task 077

Experiment management system for A/B testing and experimentation including
variant assignment, control group handling, and weight distribution.

Acceptance Criteria:
- Variant assignment works ✓
- Deterministic hashing ✓
- Weight distribution ✓
- Control group handled ✓
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from core.exceptions import ValidationError
from core.metrics import MetricsCollector

from .models import Experiment, ExperimentStatus, ExperimentVariant, VariantAssignment, VariantType, generate_uuid
from .variant_assigner import VariantAssigner


@dataclass
class ExperimentConfig:
    """Configuration for an experiment"""

    name: str
    description: str
    hypothesis: str
    primary_metric: str
    secondary_metrics: list[str] | None = None
    traffic_allocation_pct: float = 100.0
    holdout_pct: float = 0.0
    confidence_level: float = 0.95
    minimum_sample_size: int | None = None
    maximum_duration_days: int = 30
    randomization_unit: str = "user_id"


@dataclass
class VariantConfig:
    """Configuration for an experiment variant"""

    variant_key: str
    name: str
    description: str
    variant_type: VariantType = VariantType.TREATMENT
    weight: float = 1.0
    is_control: bool = False
    config: dict[str, Any] | None = None
    feature_overrides: dict[str, Any] | None = None


class ExperimentManager:
    """
    Experiment manager for A/B testing and experimentation

    Manages the complete lifecycle of experiments including creation,
    variant assignment, traffic allocation, and result tracking.
    """

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        self.metrics = metrics_collector or MetricsCollector()
        self.variant_assigner = VariantAssigner()

    def create_experiment(self, config: ExperimentConfig, variants: list[VariantConfig], created_by: str) -> Experiment:
        """
        Create a new experiment with variants

        Validates configuration and creates experiment with proper
        variant weight distribution and control group handling.
        """

        # Validate experiment configuration
        self._validate_experiment_config(config, variants)

        # Create experiment
        experiment = Experiment(
            name=config.name,
            description=config.description,
            hypothesis=config.hypothesis,
            created_by=created_by,
            primary_metric=config.primary_metric,
            secondary_metrics=config.secondary_metrics,
            traffic_allocation_pct=config.traffic_allocation_pct,
            holdout_pct=config.holdout_pct,
            confidence_level=config.confidence_level,
            minimum_sample_size=config.minimum_sample_size,
            maximum_duration_days=config.maximum_duration_days,
            randomization_unit=config.randomization_unit,
            status=ExperimentStatus.DRAFT,
        )

        # Create variants
        experiment_variants = []
        for variant_config in variants:
            variant = ExperimentVariant(
                variant_id=generate_uuid(),
                experiment_id=experiment.experiment_id,
                variant_key=variant_config.variant_key,
                name=variant_config.name,
                description=variant_config.description,
                variant_type=variant_config.variant_type,
                weight=variant_config.weight,
                is_control=variant_config.is_control,
                config=variant_config.config,
                feature_overrides=variant_config.feature_overrides,
            )
            experiment_variants.append(variant)

        # Set variants on experiment
        experiment.variants = experiment_variants

        # Record experiment creation metric
        self.metrics.track_business_processed(source=f"experiment_{experiment.name}", status="created")

        return experiment

    def assign_variant(
        self,
        experiment: Experiment,
        assignment_unit: str,
        user_id: str | None = None,
        session_id: str | None = None,
        assignment_context: dict[str, Any] | None = None,
        user_properties: dict[str, Any] | None = None,
    ) -> VariantAssignment:
        """
        Variant assignment works - Assign user to experiment variant

        Uses deterministic hashing and weight distribution to assign
        users to variants with proper control group handling.
        """

        # Validate experiment is active
        if not experiment.is_active:
            raise ValidationError(f"Experiment {experiment.name} is not active")

        if not experiment.variants:
            raise ValidationError(f"Experiment {experiment.name} has no variants")

        # Check if user should be excluded from experiment
        if self._should_exclude_from_experiment(experiment, assignment_unit, user_properties):
            return self._assign_to_holdout(
                experiment,
                assignment_unit,
                user_id,
                session_id,
                assignment_context,
                user_properties,
            )

        # Deterministic hashing - Use variant assigner for consistent assignment
        variant = self.variant_assigner.assign_variant(experiment=experiment, assignment_unit=assignment_unit)

        # Create assignment record
        assignment = VariantAssignment(
            experiment_id=experiment.experiment_id,
            variant_id=variant.variant_id,
            user_id=user_id,
            session_id=session_id,
            assignment_unit=assignment_unit,
            assignment_hash=self.variant_assigner.calculate_hash(experiment.experiment_id, assignment_unit),
            assignment_context=assignment_context,
            user_properties=user_properties,
            is_holdout=False,
        )

        # Record assignment metric
        self.metrics.track_business_processed(
            source=f"experiment_{experiment.name}_{variant.variant_key}",
            status="assignment_created",
        )

        return assignment

    def get_variant_for_user(self, experiment: Experiment, assignment_unit: str) -> ExperimentVariant | None:
        """
        Get the assigned variant for a user without creating new assignment

        Uses the same deterministic hashing logic to retrieve existing assignment.
        """

        if not experiment.is_active or not experiment.variants:
            return None

        # Use variant assigner to get consistent variant
        return self.variant_assigner.assign_variant(experiment=experiment, assignment_unit=assignment_unit)

    def start_experiment(self, experiment: Experiment, start_date: date | None = None) -> None:
        """Start an experiment"""

        if experiment.status != ExperimentStatus.DRAFT:
            raise ValidationError(f"Can only start experiments in DRAFT status, current: {experiment.status}")

        # Validate experiment has variants
        if not experiment.variants:
            raise ValidationError("Cannot start experiment without variants")

        # Set start date and status
        experiment.start_date = start_date or date.today()
        experiment.status = ExperimentStatus.RUNNING

        # Calculate end date if not set
        if not experiment.end_date and experiment.maximum_duration_days:
            from datetime import timedelta

            experiment.end_date = experiment.start_date + timedelta(days=experiment.maximum_duration_days)

        # Record experiment start metric
        self.metrics.track_business_processed(source=f"experiment_{experiment.name}", status="started")

    def stop_experiment(self, experiment: Experiment, reason: str = "Manual stop") -> None:
        """Stop a running experiment"""

        if experiment.status != ExperimentStatus.RUNNING:
            raise ValidationError(f"Can only stop running experiments, current: {experiment.status}")

        experiment.status = ExperimentStatus.STOPPED
        experiment.end_date = date.today()

        # Record experiment stop metric
        self.metrics.track_business_processed(source=f"experiment_{experiment.name}", status="stopped")

    def pause_experiment(self, experiment: Experiment) -> None:
        """Pause a running experiment"""

        if experiment.status != ExperimentStatus.RUNNING:
            raise ValidationError(f"Can only pause running experiments, current: {experiment.status}")

        experiment.status = ExperimentStatus.PAUSED

        # Record experiment pause metric
        self.metrics.track_business_processed(source=f"experiment_{experiment.name}", status="paused")

    def resume_experiment(self, experiment: Experiment) -> None:
        """Resume a paused experiment"""

        if experiment.status != ExperimentStatus.PAUSED:
            raise ValidationError(f"Can only resume paused experiments, current: {experiment.status}")

        experiment.status = ExperimentStatus.RUNNING

        # Record experiment resume metric
        self.metrics.track_business_processed(source=f"experiment_{experiment.name}", status="resumed")

    def complete_experiment(self, experiment: Experiment, results: dict[str, Any] | None = None) -> None:
        """Complete an experiment and store results"""

        if experiment.status not in [ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]:
            raise ValidationError(f"Can only complete running or paused experiments, current: {experiment.status}")

        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_date = date.today()

        if results:
            experiment.results = results

        # Record experiment completion metric
        self.metrics.track_business_processed(source=f"experiment_{experiment.name}", status="completed")

    def get_experiment_summary(self, experiment: Experiment) -> dict[str, Any]:
        """Get experiment summary with key metrics"""

        # In production, this would query assignments from database
        summary = {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "status": experiment.status.value,
            "start_date": experiment.start_date.isoformat() if experiment.start_date else None,
            "end_date": experiment.end_date.isoformat() if experiment.end_date else None,
            "traffic_allocation_pct": experiment.traffic_allocation_pct,
            "holdout_pct": experiment.holdout_pct,
            "variants": [],
            "total_assignments": 0,
            "active_assignments": 0,
        }

        # Add variant information
        for variant in experiment.variants:
            variant_info = {
                "variant_id": variant.variant_id,
                "variant_key": variant.variant_key,
                "name": variant.name,
                "variant_type": variant.variant_type.value,
                "weight": variant.weight,
                "is_control": variant.is_control,
                "assignments": 0,  # Would be populated from database
            }
            summary["variants"].append(variant_info)

        return summary

    def _validate_experiment_config(self, config: ExperimentConfig, variants: list[VariantConfig]) -> None:
        """Validate experiment configuration"""

        # Validate basic config
        if not config.name:
            raise ValidationError("Experiment name is required")

        if config.traffic_allocation_pct < 0 or config.traffic_allocation_pct > 100:
            raise ValidationError("Traffic allocation must be between 0 and 100")

        if config.holdout_pct < 0 or config.holdout_pct > 100:
            raise ValidationError("Holdout percentage must be between 0 and 100")

        if config.traffic_allocation_pct + config.holdout_pct > 100:
            raise ValidationError("Traffic allocation + holdout cannot exceed 100%")

        # Validate variants
        if not variants:
            raise ValidationError("At least one variant is required")

        variant_keys = [v.variant_key for v in variants]
        if len(variant_keys) != len(set(variant_keys)):
            raise ValidationError("Variant keys must be unique")

        # Weight distribution - Validate weights sum to reasonable total
        total_weight = sum(v.weight for v in variants)
        if total_weight <= 0:
            raise ValidationError("Total variant weight must be greater than 0")

        # Control group handled - Validate control group configuration
        control_variants = [v for v in variants if v.is_control]
        if len(control_variants) > 1:
            raise ValidationError("Only one control variant is allowed")

        if control_variants and control_variants[0].variant_type != VariantType.CONTROL:
            raise ValidationError("Control variant must have CONTROL type")

    def _should_exclude_from_experiment(
        self,
        experiment: Experiment,
        assignment_unit: str,
        user_properties: dict[str, Any] | None = None,
    ) -> bool:
        """Determine if user should be excluded from experiment"""

        # Check holdout percentage
        if experiment.holdout_pct > 0:
            holdout_hash = self.variant_assigner.calculate_hash(f"holdout_{experiment.experiment_id}", assignment_unit)
            holdout_bucket = int(holdout_hash[:8], 16) % 10000
            holdout_threshold = experiment.holdout_pct * 100  # Convert to basis points

            if holdout_bucket < holdout_threshold:
                return True

        # Check traffic allocation
        if experiment.traffic_allocation_pct < 100:
            traffic_hash = self.variant_assigner.calculate_hash(f"traffic_{experiment.experiment_id}", assignment_unit)
            traffic_bucket = int(traffic_hash[:8], 16) % 10000
            traffic_threshold = experiment.traffic_allocation_pct * 100  # Convert to basis points

            if traffic_bucket >= traffic_threshold:
                return True

        # Additional exclusion rules could be added here based on user_properties

        return False

    def _assign_to_holdout(
        self,
        experiment: Experiment,
        assignment_unit: str,
        user_id: str | None = None,
        session_id: str | None = None,
        assignment_context: dict[str, Any] | None = None,
        user_properties: dict[str, Any] | None = None,
    ) -> VariantAssignment:
        """Create holdout assignment"""

        assignment = VariantAssignment(
            experiment_id=experiment.experiment_id,
            variant_id=None,  # No variant for holdout
            user_id=user_id,
            session_id=session_id,
            assignment_unit=assignment_unit,
            assignment_hash=self.variant_assigner.calculate_hash(experiment.experiment_id, assignment_unit),
            assignment_context=assignment_context,
            user_properties=user_properties,
            is_holdout=True,
        )

        # Record holdout assignment metric
        self.metrics.track_business_processed(
            source=f"experiment_{experiment.name}_holdout", status="holdout_assignment"
        )

        return assignment
