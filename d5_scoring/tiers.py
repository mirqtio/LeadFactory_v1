"""
Tier Assignment System - Task 048

Creates a configurable tier assignment system for lead scoring with A/B/C/D tiers,
gate pass/fail logic, and distribution tracking.

Acceptance Criteria:
- A/B/C/D tiers assigned ✓
- Configurable boundaries ✓
- Gate pass/fail logic ✓
- Distribution tracking ✓
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LeadTier(Enum):
    """
    Lead tier classification using A/B/C/D system

    Acceptance Criteria: A/B/C/D tiers assigned
    """

    A = "A"  # Highest quality leads
    B = "B"  # High quality leads
    C = "C"  # Medium quality leads
    D = "D"  # Low quality leads
    FAILED = "FAILED"  # Failed to meet minimum gate threshold

    @property
    def priority_order(self) -> int:
        """Return numeric priority for sorting (lower = higher priority)"""
        order = {
            LeadTier.A: 1,
            LeadTier.B: 2,
            LeadTier.C: 3,
            LeadTier.D: 4,
            LeadTier.FAILED: 5,
        }
        return order[self]

    @property
    def description(self) -> str:
        """Human-readable description of tier"""
        descriptions = {
            LeadTier.A: "Premium leads with highest conversion potential",
            LeadTier.B: "High-quality leads with strong conversion potential",
            LeadTier.C: "Medium-quality leads requiring nurturing",
            LeadTier.D: "Lower-quality leads needing significant development",
            LeadTier.FAILED: "Leads that did not meet minimum qualification threshold",
        }
        return descriptions[self]


@dataclass
class TierBoundary:
    """
    Configurable tier boundary definition

    Acceptance Criteria: Configurable boundaries
    """

    tier: LeadTier
    min_score: float
    max_score: float
    description: str = ""

    def __post_init__(self):
        """Validate boundary configuration"""
        if self.min_score < 0 or self.max_score > 100:
            raise ValueError("Scores must be between 0 and 100")
        if self.min_score > self.max_score:
            raise ValueError("Min score cannot exceed max score")
        if not self.description:
            self.description = (
                f"Tier {self.tier.value} ({self.min_score}-{self.max_score} points)"
            )


@dataclass
class TierConfiguration:
    """
    Complete tier configuration with boundaries and gate logic

    Acceptance Criteria: Configurable boundaries, Gate pass/fail logic
    """

    name: str
    version: str
    gate_threshold: float  # Minimum score to pass gate
    boundaries: List[TierBoundary]
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    description: str = ""

    def __post_init__(self):
        """Validate configuration"""
        if not 0 <= self.gate_threshold <= 100:
            raise ValueError("Gate threshold must be between 0 and 100")

        # Validate no overlapping boundaries
        for i, boundary in enumerate(self.boundaries):
            for j, other in enumerate(self.boundaries[i + 1 :], i + 1):
                if boundary.tier != other.tier and self._boundaries_overlap(
                    boundary, other
                ):
                    raise ValueError(
                        f"Overlapping boundaries detected: {boundary.tier} and {other.tier}"
                    )

        # Sort boundaries by min_score for efficient lookup
        self.boundaries.sort(key=lambda b: b.min_score)

    def _boundaries_overlap(self, b1: TierBoundary, b2: TierBoundary) -> bool:
        """Check if two boundaries overlap"""
        return not (b1.max_score < b2.min_score or b2.max_score < b1.min_score)

    def find_tier_for_score(self, score: float) -> LeadTier:
        """Find appropriate tier for given score"""
        # Check gate threshold first
        if score < self.gate_threshold:
            return LeadTier.FAILED

        # Find matching tier boundary
        for boundary in self.boundaries:
            if boundary.min_score <= score <= boundary.max_score:
                return boundary.tier

        # Default to lowest tier if no boundary matches
        logger.warning(f"No tier boundary found for score {score}, defaulting to D")
        return LeadTier.D


@dataclass
class TierAssignment:
    """
    Individual tier assignment result
    """

    lead_id: str
    score: float
    tier: LeadTier
    passed_gate: bool
    configuration_used: str
    assignment_timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    notes: str = ""


@dataclass
class TierDistribution:
    """
    Distribution tracking for tier assignments

    Acceptance Criteria: Distribution tracking
    """

    configuration_name: str
    total_assignments: int = 0
    tier_counts: Dict[LeadTier, int] = field(
        default_factory=lambda: {tier: 0 for tier in LeadTier}
    )
    gate_pass_count: int = 0
    gate_fail_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def gate_pass_rate(self) -> float:
        """Percentage of leads that passed the gate"""
        if self.total_assignments == 0:
            return 0.0
        return (self.gate_pass_count / self.total_assignments) * 100

    @property
    def tier_percentages(self) -> Dict[LeadTier, float]:
        """Percentage distribution across tiers"""
        if self.total_assignments == 0:
            return {tier: 0.0 for tier in LeadTier}

        return {
            tier: (count / self.total_assignments) * 100
            for tier, count in self.tier_counts.items()
        }

    def add_assignment(self, assignment: TierAssignment):
        """Add a new assignment to distribution tracking"""
        self.total_assignments += 1
        self.tier_counts[assignment.tier] += 1

        if assignment.passed_gate:
            self.gate_pass_count += 1
        else:
            self.gate_fail_count += 1

        self.last_updated = datetime.now()


class TierAssignmentEngine:
    """
    Main engine for tier assignment with configurable boundaries and tracking

    Acceptance Criteria: All four criteria implemented
    """

    def __init__(self, configuration: Optional[TierConfiguration] = None):
        """
        Initialize tier assignment engine

        Args:
            configuration: Tier configuration to use (creates default if None)
        """
        self.configuration = configuration or self._create_default_configuration()
        self.distribution = TierDistribution(configuration_name=self.configuration.name)
        self.assignments: List[TierAssignment] = []
        self._lock = threading.Lock()  # Thread safety for distribution tracking

        logger.info(
            f"Initialized TierAssignmentEngine with configuration '{self.configuration.name}'"
        )

    def _create_default_configuration(self) -> TierConfiguration:
        """Create default A/B/C/D tier configuration"""
        # TODO Phase 0.5: Enable tier-based branching
        # For Phase 0, tiers are calculated but have zero gating effect (analytics only)
        return TierConfiguration(
            name="default_abcd",
            version="1.0.0",
            gate_threshold=0.0,  # Phase 0: No gating, all leads pass
            description="Default A/B/C/D tier configuration (Phase 0: analytics only)",
            boundaries=[
                TierBoundary(LeadTier.A, 80.0, 100.0, "Tier A: 80-100 points"),
                TierBoundary(
                    LeadTier.B, 60.0, 79.9, "Tier B: 60-79.9 points"
                ),
                TierBoundary(
                    LeadTier.C, 40.0, 59.9, "Tier C: 40-59.9 points"
                ),
                TierBoundary(
                    LeadTier.D, 0.0, 39.9, "Tier D: 0-39.9 points"
                ),
            ],
        )

    def assign_tier(
        self, lead_id: str, score: float, confidence: float = 1.0, notes: str = ""
    ) -> TierAssignment:
        """
        Assign tier to a lead based on score

        Args:
            lead_id: Unique identifier for the lead
            score: Numeric score (0-100)
            confidence: Confidence in the score (0-1)
            notes: Optional notes about the assignment

        Returns:
            TierAssignment with tier and gate status
        """
        if not 0 <= score <= 100:
            raise ValueError("Score must be between 0 and 100")

        # Determine tier and gate status
        tier = self.configuration.find_tier_for_score(score)
        passed_gate = score >= self.configuration.gate_threshold

        # Create assignment
        assignment = TierAssignment(
            lead_id=lead_id,
            score=score,
            tier=tier,
            passed_gate=passed_gate,
            configuration_used=self.configuration.name,
            confidence=confidence,
            notes=notes,
        )

        # Update tracking with thread safety
        with self._lock:
            self.assignments.append(assignment)
            self.distribution.add_assignment(assignment)

        logger.info(
            f"Assigned lead {lead_id} to tier {tier.value} (score: {score}, gate: {'PASS' if passed_gate else 'FAIL'})"
        )

        return assignment

    def batch_assign_tiers(self, lead_scores: Dict[str, float]) -> List[TierAssignment]:
        """
        Assign tiers to multiple leads in batch

        Args:
            lead_scores: Dictionary of lead_id -> score

        Returns:
            List of TierAssignment objects
        """
        assignments = []

        for lead_id, score in lead_scores.items():
            try:
                assignment = self.assign_tier(lead_id, score)
                assignments.append(assignment)
            except Exception as e:
                logger.error(f"Failed to assign tier for lead {lead_id}: {e}")
                continue

        logger.info(f"Batch assigned tiers for {len(assignments)} leads")
        return assignments

    def get_tier_distribution(self) -> TierDistribution:
        """
        Get current tier distribution statistics

        Returns:
            TierDistribution with current stats
        """
        with self._lock:
            return self.distribution

    def get_assignments_by_tier(self, tier: LeadTier) -> List[TierAssignment]:
        """Get all assignments for a specific tier"""
        with self._lock:
            return [
                assignment for assignment in self.assignments if assignment.tier == tier
            ]

    def get_qualified_leads(self) -> List[TierAssignment]:
        """Get all leads that passed the gate threshold"""
        with self._lock:
            return [
                assignment for assignment in self.assignments if assignment.passed_gate
            ]

    def get_failed_leads(self) -> List[TierAssignment]:
        """Get all leads that failed the gate threshold"""
        with self._lock:
            return [
                assignment
                for assignment in self.assignments
                if not assignment.passed_gate
            ]

    def update_configuration(self, new_configuration: TierConfiguration):
        """
        Update tier configuration (does not reassign existing leads)

        Args:
            new_configuration: New tier configuration to use
        """
        old_config = self.configuration.name
        self.configuration = new_configuration

        # Reset distribution tracking for new configuration
        with self._lock:
            self.distribution = TierDistribution(
                configuration_name=new_configuration.name
            )

        logger.info(
            f"Updated configuration from '{old_config}' to '{new_configuration.name}'"
        )

    def export_distribution_summary(self) -> Dict[str, Any]:
        """
        Export comprehensive distribution summary

        Returns:
            Dictionary with distribution statistics and configuration info
        """
        with self._lock:
            return {
                "configuration": {
                    "name": self.configuration.name,
                    "version": self.configuration.version,
                    "gate_threshold": self.configuration.gate_threshold,
                    "total_boundaries": len(self.configuration.boundaries),
                    "enabled": self.configuration.enabled,
                },
                "distribution": {
                    "total_assignments": self.distribution.total_assignments,
                    "gate_pass_rate": self.distribution.gate_pass_rate,
                    "gate_pass_count": self.distribution.gate_pass_count,
                    "gate_fail_count": self.distribution.gate_fail_count,
                    "tier_counts": {
                        tier.value: count
                        for tier, count in self.distribution.tier_counts.items()
                    },
                    "tier_percentages": {
                        tier.value: pct
                        for tier, pct in self.distribution.tier_percentages.items()
                    },
                    "last_updated": self.distribution.last_updated.isoformat(),
                },
                "summary": {
                    "highest_tier_leads": self.distribution.tier_counts.get(
                        LeadTier.A, 0
                    ),
                    "qualified_leads": self.distribution.gate_pass_count,
                    "total_processed": self.distribution.total_assignments,
                },
            }

    @classmethod
    def create_custom_configuration(
        cls,
        name: str,
        gate_threshold: float,
        tier_a_min: float = 80.0,
        tier_b_min: float = 65.0,
        tier_c_min: float = 50.0,
        tier_d_min: float = 30.0,
    ) -> TierConfiguration:
        """
        Helper method to create custom tier configuration

        Args:
            name: Configuration name
            gate_threshold: Minimum score to pass gate
            tier_a_min: Minimum score for tier A
            tier_b_min: Minimum score for tier B
            tier_c_min: Minimum score for tier C
            tier_d_min: Minimum score for tier D

        Returns:
            TierConfiguration with specified thresholds
        """
        return TierConfiguration(
            name=name,
            version="custom_1.0.0",
            gate_threshold=gate_threshold,
            description=f"Custom tier configuration '{name}'",
            boundaries=[
                TierBoundary(LeadTier.A, tier_a_min, 100.0),
                TierBoundary(LeadTier.B, tier_b_min, tier_a_min - 0.1),
                TierBoundary(LeadTier.C, tier_c_min, tier_b_min - 0.1),
                TierBoundary(LeadTier.D, tier_d_min, tier_c_min - 0.1),
            ],
        )

    @classmethod
    def from_configuration_file(cls, file_path: str) -> "TierAssignmentEngine":
        """Load tier assignment engine from JSON configuration file"""
        try:
            with open(file_path, "r") as f:
                config_data = json.load(f)

            # Parse boundaries
            boundaries = []
            for boundary_data in config_data["boundaries"]:
                boundaries.append(
                    TierBoundary(
                        tier=LeadTier(boundary_data["tier"]),
                        min_score=boundary_data["min_score"],
                        max_score=boundary_data["max_score"],
                        description=boundary_data.get("description", ""),
                    )
                )

            # Create configuration
            configuration = TierConfiguration(
                name=config_data["name"],
                version=config_data["version"],
                gate_threshold=config_data["gate_threshold"],
                boundaries=boundaries,
                description=config_data.get("description", ""),
                enabled=config_data.get("enabled", True),
            )

            return cls(configuration)

        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
            raise


# Convenience functions for common operations


def assign_lead_tier(
    lead_id: str, score: float, configuration: Optional[TierConfiguration] = None
) -> TierAssignment:
    """
    Quick function to assign a single lead tier

    Args:
        lead_id: Lead identifier
        score: Lead score (0-100)
        configuration: Optional custom configuration

    Returns:
        TierAssignment result
    """
    engine = TierAssignmentEngine(configuration)
    return engine.assign_tier(lead_id, score)


def create_standard_configuration(gate_threshold: float = 0.0) -> TierConfiguration:
    """
    Create standard A/B/C/D configuration with custom gate threshold

    Args:
        gate_threshold: Minimum score to qualify (default 0.0 for Phase 0)

    Returns:
        TierConfiguration with standard A/B/C/D boundaries
    """
    # TODO Phase 0.5: Re-enable gate threshold logic
    # For Phase 0, all leads pass (gate_threshold = 0.0)

    # Standard boundaries matching scoring_rules.yaml
    boundaries = [
        TierBoundary(LeadTier.A, 80.0, 100.0, "Tier A: 80-100 points"),
        TierBoundary(LeadTier.B, 60.0, 79.9, "Tier B: 60-79.9 points"),
        TierBoundary(LeadTier.C, 40.0, 59.9, "Tier C: 40-59.9 points"),
        TierBoundary(LeadTier.D, 0.0, 39.9, "Tier D: 0-39.9 points"),
    ]

    return TierConfiguration(
        name="standard_abcd",
        version="1.0.0",
        gate_threshold=gate_threshold,
        description="Standard A/B/C/D tier configuration (Phase 0: analytics only)",
        boundaries=boundaries,
    )
