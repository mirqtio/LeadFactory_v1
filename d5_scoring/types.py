"""
Scoring Types and Enumerations - Task 045

Type definitions for scoring system including tier enumeration,
score components, and versioning.

Acceptance Criteria:
- Tier enumeration
- Version tracking
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ScoringTier(Enum):
    """
    Business tier classification based on scoring

    Acceptance Criteria: Tier enumeration
    """

    PLATINUM = "platinum"  # 90-100 points
    GOLD = "gold"  # 80-89 points
    SILVER = "silver"  # 70-79 points
    BRONZE = "bronze"  # 60-69 points
    BASIC = "basic"  # 50-59 points
    UNQUALIFIED = "unqualified"  # < 50 points

    @classmethod
    def from_score(cls, score: float) -> "ScoringTier":
        """Convert numeric score to tier"""
        # DEPRECATED - Use YAML-based tier configuration instead
        # TODO Phase 0.5: Remove this method after migration to A/B/C/D tiers
        import logging

        logging.warning("ScoringTier.from_score is deprecated. Use rules_parser.get_tier_for_score() instead.")
        # Map to closest A/B/C/D tier for backwards compatibility
        if score >= 80:
            return cls.PLATINUM  # Maps to A
        if score >= 60:
            return cls.GOLD  # Maps to B
        if score >= 40:
            return cls.SILVER  # Maps to C
        return cls.BRONZE  # Maps to D

    @property
    def min_score(self) -> float:
        """Minimum score for this tier"""
        # DEPRECATED - Use YAML-based tier configuration instead
        import logging

        logging.warning("ScoringTier.min_score is deprecated. Use YAML configuration instead.")
        return 0.0  # Default for backwards compatibility

    @property
    def max_score(self) -> float:
        """Maximum score for this tier"""
        # DEPRECATED - Use YAML-based tier configuration instead
        import logging

        logging.warning("ScoringTier.max_score is deprecated. Use YAML configuration instead.")
        return 100.0  # Default for backwards compatibility


class ScoreComponent(Enum):
    """
    Individual components that contribute to overall business score

    Used for score breakdown and analysis
    """

    # Company data quality
    COMPANY_INFO = "company_info"  # Basic company information completeness
    CONTACT_INFO = "contact_info"  # Contact information quality
    LOCATION_DATA = "location_data"  # Address and location accuracy

    # Business validation
    BUSINESS_VALIDATION = "business_validation"  # Business legitimacy indicators
    ONLINE_PRESENCE = "online_presence"  # Website and digital footprint
    SOCIAL_SIGNALS = "social_signals"  # Social media and reviews

    # Financial indicators
    REVENUE_INDICATORS = "revenue_indicators"  # Revenue and financial data
    EMPLOYEE_COUNT = "employee_count"  # Company size indicators
    FUNDING_STATUS = "funding_status"  # Investment and funding info

    # Industry and market
    INDUSTRY_RELEVANCE = "industry_relevance"  # Target industry alignment
    MARKET_POSITION = "market_position"  # Competitive positioning
    GROWTH_INDICATORS = "growth_indicators"  # Growth signals and trends

    # Engagement potential
    TECHNOLOGY_STACK = "technology_stack"  # Tech stack compatibility
    DECISION_MAKER_ACCESS = "decision_maker_access"  # Contact accessibility
    TIMING_INDICATORS = "timing_indicators"  # Buying timing signals

    @property
    def max_points(self) -> float:
        """Maximum points this component can contribute"""
        # DEPRECATED – replaced by YAML configuration
        # TODO: Remove this method after all callers updated to use YAML config
        # For now, return a default value. Real weights come from config/scoring_rules.yaml
        import logging

        logging.warning(
            f"ScoreComponent.max_points is deprecated. "
            f"Component '{self.value}' should use weights from scoring_rules.yaml"
        )
        return 10.0  # Default weight for backwards compatibility

    @property
    def description(self) -> str:
        """Human-readable description of the component"""
        # DEPRECATED – replaced by YAML configuration
        # TODO: Remove this method after all callers updated to use YAML config
        # Descriptions should come from config/scoring_rules.yaml
        import logging

        logging.warning(
            f"ScoreComponent.description is deprecated. "
            f"Component '{self.value}' description should come from scoring_rules.yaml"
        )
        return f"Score component: {self.value}"


class ScoringStatus(Enum):
    """Status of scoring process"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"  # Score too old, needs refresh
    MANUAL_REVIEW = "manual_review"  # Requires human review


@dataclass
class ScoringVersion:
    """
    Version tracking for scoring system

    Acceptance Criteria: Version tracking
    """

    version: str
    created_at: datetime
    algorithm_version: str
    weights_version: str
    data_schema_version: str
    changelog: str | None = None
    deprecated: bool = False

    def __post_init__(self):
        """Ensure consistent version format"""
        if not self.version:
            self.version = f"v{self.created_at.strftime('%Y%m%d_%H%M%S')}"

    @classmethod
    def current(cls) -> "ScoringVersion":
        """Get current scoring version"""
        return cls(
            version="v1.0.0",
            created_at=datetime.utcnow(),
            algorithm_version="baseline_v1",
            weights_version="standard_v1",
            data_schema_version="2025_v1",
            changelog="Initial scoring system implementation",
        )

    def is_compatible_with(self, other: "ScoringVersion") -> bool:
        """Check if this version is compatible with another"""
        # Simple compatibility check - same major version
        try:
            self_major = int(self.version.split(".")[0].replace("v", ""))
            other_major = int(other.version.split(".")[0].replace("v", ""))
            return self_major == other_major
        except (ValueError, IndexError):
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "algorithm_version": self.algorithm_version,
            "weights_version": self.weights_version,
            "data_schema_version": self.data_schema_version,
            "changelog": self.changelog,
            "deprecated": self.deprecated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoringVersion":
        """Create from dictionary"""
        return cls(
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            algorithm_version=data["algorithm_version"],
            weights_version=data["weights_version"],
            data_schema_version=data["data_schema_version"],
            changelog=data.get("changelog"),
            deprecated=data.get("deprecated", False),
        )
