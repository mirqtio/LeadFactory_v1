"""
Scoring Models - Task 045

Database models and business logic for scoring system including
result storage, score breakdowns, and scoring engines.

Acceptance Criteria:
- Scoring result model
- Score breakdown stored
- Version tracking
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base

from .types import ScoreComponent, ScoringStatus, ScoringTier, ScoringVersion

from database.base import UUID


# UUID handling for both PostgreSQL and SQLite
def get_uuid_column():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def get_uuid_foreign_key(table_name):
    return Column(UUID(as_uuid=True), ForeignKey(f"{table_name}.id"), nullable=False)


class D5ScoringResult(Base):
    """
    Main scoring result model

    Acceptance Criteria: Scoring result model
    """

    __tablename__ = "d5_scoring_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(50), nullable=False, index=True)

    # Core scoring data
    overall_score = Column(Numeric(5, 2), nullable=False)  # 0.00 to 100.00
    tier = Column(String(20), nullable=False)  # ScoringTier enum value
    confidence = Column(Numeric(3, 2))  # 0.00 to 1.00

    # Scoring metadata
    scoring_version = Column(String(50), nullable=False)
    algorithm_version = Column(String(50), nullable=False)
    data_version = Column(String(50))  # Version of input data used

    # Status and timing
    status = Column(String(20), default=ScoringStatus.PENDING.value, nullable=False)
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime)  # When this score becomes stale

    # Input data reference
    enrichment_result_id = Column(String(36))  # Link to enrichment data
    input_data_checksum = Column(String(64))  # Hash of input data

    # Quality metrics
    data_completeness = Column(Numeric(3, 2))  # 0.00 to 1.00
    data_freshness_days = Column(Integer)  # Age of data in days
    manual_adjustments = Column(JSON)  # Any manual score adjustments

    # Notes and context
    scoring_notes = Column(Text)
    manual_review_required = Column(Boolean, default=False)
    reviewer_notes = Column(Text)

    # Relationships
    breakdowns = relationship(
        "ScoreBreakdown", back_populates="scoring_result", cascade="all, delete-orphan"
    )
    history = relationship(
        "ScoreHistory", back_populates="scoring_result", cascade="all, delete-orphan"
    )

    # Indexing for performance
    __table_args__ = (
        Index("idx_scoring_results_business_tier", "business_id", "tier"),
        Index("idx_scoring_results_scored_at", "scored_at"),
        Index("idx_scoring_results_expires_at", "expires_at"),
        Index("idx_scoring_results_score", "overall_score"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at and self.scored_at:
            # Default expiration: 30 days
            self.expires_at = self.scored_at + timedelta(days=30)

    @property
    def is_expired(self) -> bool:
        """Check if score has expired"""
        return self.expires_at and datetime.utcnow() > self.expires_at

    @property
    def age_days(self) -> int:
        """Age of score in days"""
        if not self.scored_at:
            return 0
        return (datetime.utcnow() - self.scored_at).days

    @property
    def tier_enum(self) -> ScoringTier:
        """Get tier as enum"""
        return ScoringTier(self.tier)

    def update_tier_from_score(self):
        """Update tier based on current overall score"""
        # TODO Phase 0.5: Update to use rules_parser.get_tier_for_score()
        # For now, use simplified A/B/C/D mapping
        score = float(self.overall_score) if self.overall_score else 0
        if score >= 80:
            self.tier = "A"
        elif score >= 60:
            self.tier = "B"  
        elif score >= 40:
            self.tier = "C"
        else:
            self.tier = "D"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "business_id": self.business_id,
            "overall_score": float(self.overall_score) if self.overall_score else None,
            "tier": self.tier,
            "confidence": float(self.confidence) if self.confidence else None,
            "scoring_version": self.scoring_version,
            "algorithm_version": self.algorithm_version,
            "status": self.status,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "age_days": self.age_days,
            "is_expired": self.is_expired,
            "data_completeness": float(self.data_completeness)
            if self.data_completeness
            else None,
            "manual_review_required": self.manual_review_required,
        }


class ScoreBreakdown(Base):
    """
    Detailed breakdown of score components

    Acceptance Criteria: Score breakdown stored
    """

    __tablename__ = "score_breakdowns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scoring_result_id = Column(
        String(36), ForeignKey("d5_scoring_results.id"), nullable=False
    )

    # Component details
    component = Column(String(50), nullable=False)  # ScoreComponent enum value
    component_score = Column(Numeric(5, 2), nullable=False)  # Points earned
    max_possible_score = Column(Numeric(5, 2), nullable=False)  # Max points available
    weight = Column(Numeric(3, 2))  # Component weight in overall score

    # Calculation details
    raw_value = Column(JSON)  # Original data that contributed to score
    calculation_method = Column(String(100))  # How score was calculated
    confidence = Column(Numeric(3, 2))  # Confidence in this component score

    # Quality indicators
    data_quality = Column(String(20))  # Quality of input data
    data_sources = Column(JSON)  # Which data sources were used

    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    calculation_notes = Column(Text)

    # Relationships
    scoring_result = relationship("D5ScoringResult", back_populates="breakdowns")

    # Indexing
    __table_args__ = (
        Index(
            "idx_score_breakdowns_result_component", "scoring_result_id", "component"
        ),
        UniqueConstraint(
            "scoring_result_id", "component", name="uq_score_breakdown_component"
        ),
    )

    @property
    def component_enum(self) -> ScoreComponent:
        """Get component as enum"""
        return ScoreComponent(self.component)

    @property
    def score_percentage(self) -> float:
        """Percentage of max score achieved"""
        if not self.max_possible_score:
            return 0.0
        return round(float(self.component_score / self.max_possible_score * 100), 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "component": self.component,
            "component_score": float(self.component_score)
            if self.component_score
            else None,
            "max_possible_score": float(self.max_possible_score)
            if self.max_possible_score
            else None,
            "score_percentage": self.score_percentage,
            "weight": float(self.weight) if self.weight else None,
            "confidence": float(self.confidence) if self.confidence else None,
            "data_quality": self.data_quality,
            "calculation_method": self.calculation_method,
            "calculated_at": self.calculated_at.isoformat()
            if self.calculated_at
            else None,
        }


class ScoreHistory(Base):
    """
    Historical tracking of score changes

    Tracks how scores change over time for trend analysis
    """

    __tablename__ = "score_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scoring_result_id = Column(
        String(36), ForeignKey("d5_scoring_results.id"), nullable=False
    )
    business_id = Column(String(50), nullable=False, index=True)

    # Historical score data
    previous_score = Column(Numeric(5, 2))
    new_score = Column(Numeric(5, 2), nullable=False)
    score_change = Column(Numeric(5, 2))  # Calculated difference

    # Tier changes
    previous_tier = Column(String(20))
    new_tier = Column(String(20), nullable=False)
    tier_changed = Column(Boolean, default=False)

    # Change metadata
    change_reason = Column(String(200))  # Why score changed
    data_changes = Column(JSON)  # What data changed
    algorithm_changes = Column(JSON)  # Algorithm version changes

    # Timing
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    change_type = Column(String(50))  # "automatic", "manual", "recalculation"

    # Relationships
    scoring_result = relationship("D5ScoringResult", back_populates="history")

    # Indexing
    __table_args__ = (
        Index("idx_score_history_business_date", "business_id", "changed_at"),
        Index("idx_score_history_score_change", "score_change"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calculate score change if both scores provided
        if self.previous_score and self.new_score:
            self.score_change = self.new_score - self.previous_score
        # Check if tier changed
        if self.previous_tier and self.new_tier:
            self.tier_changed = self.previous_tier != self.new_tier

    @property
    def score_improvement(self) -> bool:
        """Whether this represents a score improvement"""
        return self.score_change and self.score_change > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "business_id": self.business_id,
            "previous_score": float(self.previous_score)
            if self.previous_score
            else None,
            "new_score": float(self.new_score),
            "score_change": float(self.score_change) if self.score_change else None,
            "previous_tier": self.previous_tier,
            "new_tier": self.new_tier,
            "tier_changed": self.tier_changed,
            "score_improvement": self.score_improvement,
            "change_reason": self.change_reason,
            "change_type": self.change_type,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
        }


@dataclass
class ScoringEngine:
    """
    Business logic for calculating scores

    Encapsulates scoring algorithms and business rules
    """

    version: ScoringVersion = field(default_factory=ScoringVersion.current)
    weights: Dict[ScoreComponent, float] = field(default_factory=dict)
    min_data_quality: float = 0.5

    def __post_init__(self):
        """Initialize default weights if not provided"""
        if not self.weights:
            self.weights = {
                component: component.max_points for component in ScoreComponent
            }

    def calculate_score(self, business_data: Dict[str, Any]) -> D5ScoringResult:
        """
        Calculate overall score for a business

        Args:
            business_data: Enriched business data to score

        Returns:
            D5ScoringResult with calculated score and tier
        """
        business_id = business_data.get("id", str(uuid.uuid4()))

        # Calculate component scores
        component_scores = {}
        total_weighted_score = 0.0
        total_weight = 0.0

        for component in ScoreComponent:
            score_info = self._calculate_component_score(component, business_data)
            component_scores[component] = score_info

            weighted_score = score_info["score"] * self.weights[component]
            total_weighted_score += weighted_score
            total_weight += self.weights[component]

        # Calculate overall score (0-100 scale)
        overall_score = (
            (total_weighted_score / total_weight) if total_weight > 0 else 0.0
        )
        overall_score = min(100.0, max(0.0, overall_score))  # Clamp to 0-100

        # Determine tier
        tier = ScoringTier.from_score(overall_score)

        # Calculate confidence and quality metrics
        confidence = self._calculate_confidence(business_data, component_scores)
        data_completeness = self._calculate_data_completeness(business_data)

        # Create scoring result
        scoring_result = D5ScoringResult(
            business_id=business_id,
            overall_score=Decimal(str(round(overall_score, 2))),
            tier=tier.value,
            confidence=Decimal(str(round(confidence, 2))),
            scoring_version=self.version.version,
            algorithm_version=self.version.algorithm_version,
            data_version=business_data.get("data_version", "unknown"),
            status=ScoringStatus.COMPLETED.value,
            data_completeness=Decimal(str(round(data_completeness, 2))),
            manual_review_required=confidence < 0.7 or data_completeness < 0.5,
        )

        return scoring_result

    def _calculate_component_score(
        self, component: ScoreComponent, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate score for individual component"""
        # This is a simplified scoring algorithm
        # In practice, each component would have sophisticated logic

        component_data = self._extract_component_data(component, data)
        raw_score = self._score_component_data(component, component_data)

        # Normalize to component's max points
        max_points = component.max_points
        normalized_score = min(max_points, max(0.0, raw_score))

        return {
            "score": normalized_score,
            "max_score": max_points,
            "raw_data": component_data,
            "confidence": min(1.0, normalized_score / max_points)
            if max_points > 0
            else 0.0,
        }

    def _extract_component_data(
        self, component: ScoreComponent, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract relevant data for scoring component"""
        # Map components to data fields
        field_mappings = {
            ScoreComponent.COMPANY_INFO: ["company_name", "description", "industry"],
            ScoreComponent.CONTACT_INFO: ["phone", "email", "website"],
            ScoreComponent.LOCATION_DATA: ["address", "city", "state", "country"],
            ScoreComponent.BUSINESS_VALIDATION: ["business_status", "legal_name"],
            ScoreComponent.ONLINE_PRESENCE: ["website", "domain", "social_links"],
            ScoreComponent.SOCIAL_SIGNALS: [
                "rating",
                "reviews_count",
                "social_mentions",
            ],
            ScoreComponent.REVENUE_INDICATORS: ["annual_revenue", "revenue_range"],
            ScoreComponent.EMPLOYEE_COUNT: ["employee_count", "employee_range"],
            ScoreComponent.FUNDING_STATUS: ["funding_total", "funding_stage"],
            ScoreComponent.INDUSTRY_RELEVANCE: ["industry", "industry_code", "tags"],
            ScoreComponent.MARKET_POSITION: ["competitor_analysis", "market_share"],
            ScoreComponent.GROWTH_INDICATORS: ["growth_rate", "expansion_signals"],
            ScoreComponent.TECHNOLOGY_STACK: ["tech_stack", "platforms"],
            ScoreComponent.DECISION_MAKER_ACCESS: ["contacts", "decision_makers"],
            ScoreComponent.TIMING_INDICATORS: ["recent_funding", "hiring_activity"],
        }

        relevant_fields = field_mappings.get(component, [])
        component_data = {}

        for field in relevant_fields:
            if field in data:
                component_data[field] = data[field]

        return component_data

    def _score_component_data(
        self, component: ScoreComponent, component_data: Dict[str, Any]
    ) -> float:
        """Score the extracted component data"""
        # Simplified scoring logic - in practice this would be much more sophisticated
        if not component_data:
            return 0.0

        # Base score on data completeness and quality
        completeness = len([v for v in component_data.values() if v]) / len(
            component_data
        )
        base_score = completeness * component.max_points * 0.7

        # Add quality bonuses based on specific data
        quality_bonus = 0.0

        # Example quality checks
        if component == ScoreComponent.COMPANY_INFO:
            if component_data.get("company_name"):
                quality_bonus += 1.0
            if component_data.get("description"):
                quality_bonus += 1.0
        elif component == ScoreComponent.REVENUE_INDICATORS:
            if component_data.get("annual_revenue"):
                quality_bonus += 2.0
        elif component == ScoreComponent.ONLINE_PRESENCE:
            if component_data.get("website") and "https://" in str(
                component_data["website"]
            ):
                quality_bonus += 1.5

        return base_score + quality_bonus

    def _calculate_confidence(
        self, data: Dict[str, Any], component_scores: Dict[ScoreComponent, Dict]
    ) -> float:
        """Calculate overall confidence in the score"""
        # Base confidence on data quality and component confidence
        component_confidences = [
            info["confidence"] for info in component_scores.values()
        ]
        avg_component_confidence = sum(component_confidences) / len(
            component_confidences
        )

        # Factor in data completeness
        data_completeness = self._calculate_data_completeness(data)

        # Weighted average
        confidence = (avg_component_confidence * 0.7) + (data_completeness * 0.3)
        return min(1.0, max(0.0, confidence))

    def _calculate_data_completeness(self, data: Dict[str, Any]) -> float:
        """Calculate how complete the input data is"""
        # Key fields we expect for good scoring
        key_fields = [
            "company_name",
            "industry",
            "website",
            "phone",
            "address",
            "employee_count",
            "annual_revenue",
            "business_status",
        ]

        filled_fields = sum(1 for field in key_fields if data.get(field))
        return filled_fields / len(key_fields)

    def get_scoring_summary(self, scoring_result: D5ScoringResult) -> Dict[str, Any]:
        """Get human-readable scoring summary"""
        return {
            "business_id": scoring_result.business_id,
            "overall_score": float(scoring_result.overall_score),
            "tier": scoring_result.tier,
            "tier_description": f"{scoring_result.tier.title()} tier business",
            "confidence": float(scoring_result.confidence)
            if scoring_result.confidence
            else None,
            "data_completeness": float(scoring_result.data_completeness)
            if scoring_result.data_completeness
            else None,
            "manual_review_required": scoring_result.manual_review_required,
            "scored_at": scoring_result.scored_at,
            "expires_at": scoring_result.expires_at,
            "algorithm_version": scoring_result.algorithm_version,
        }
