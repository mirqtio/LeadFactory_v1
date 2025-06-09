"""
Scoring Types and Enumerations - Task 045

Type definitions for scoring system including tier enumeration,
score components, and versioning.

Acceptance Criteria:
- Tier enumeration
- Version tracking
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


class ScoringTier(Enum):
    """
    Business tier classification based on scoring

    Acceptance Criteria: Tier enumeration
    """
    PLATINUM = "platinum"    # 90-100 points
    GOLD = "gold"           # 80-89 points
    SILVER = "silver"       # 70-79 points
    BRONZE = "bronze"       # 60-69 points
    BASIC = "basic"         # 50-59 points
    UNQUALIFIED = "unqualified"  # < 50 points

    @classmethod
    def from_score(cls, score: float) -> 'ScoringTier':
        """Convert numeric score to tier"""
        if score >= 90:
            return cls.PLATINUM
        elif score >= 80:
            return cls.GOLD
        elif score >= 70:
            return cls.SILVER
        elif score >= 60:
            return cls.BRONZE
        elif score >= 50:
            return cls.BASIC
        else:
            return cls.UNQUALIFIED

    @property
    def min_score(self) -> float:
        """Minimum score for this tier"""
        tier_ranges = {
            self.PLATINUM: 90.0,
            self.GOLD: 80.0,
            self.SILVER: 70.0,
            self.BRONZE: 60.0,
            self.BASIC: 50.0,
            self.UNQUALIFIED: 0.0
        }
        return tier_ranges[self]

    @property
    def max_score(self) -> float:
        """Maximum score for this tier"""
        tier_ranges = {
            self.PLATINUM: 100.0,
            self.GOLD: 89.9,
            self.SILVER: 79.9,
            self.BRONZE: 69.9,
            self.BASIC: 59.9,
            self.UNQUALIFIED: 49.9
        }
        return tier_ranges[self]


class ScoreComponent(Enum):
    """
    Individual components that contribute to overall business score

    Used for score breakdown and analysis
    """
    # Company data quality
    COMPANY_INFO = "company_info"          # Basic company information completeness
    CONTACT_INFO = "contact_info"          # Contact information quality
    LOCATION_DATA = "location_data"        # Address and location accuracy

    # Business validation
    BUSINESS_VALIDATION = "business_validation"  # Business legitimacy indicators
    ONLINE_PRESENCE = "online_presence"          # Website and digital footprint
    SOCIAL_SIGNALS = "social_signals"            # Social media and reviews

    # Financial indicators
    REVENUE_INDICATORS = "revenue_indicators"    # Revenue and financial data
    EMPLOYEE_COUNT = "employee_count"            # Company size indicators
    FUNDING_STATUS = "funding_status"            # Investment and funding info

    # Industry and market
    INDUSTRY_RELEVANCE = "industry_relevance"    # Target industry alignment
    MARKET_POSITION = "market_position"          # Competitive positioning
    GROWTH_INDICATORS = "growth_indicators"      # Growth signals and trends

    # Engagement potential
    TECHNOLOGY_STACK = "technology_stack"        # Tech stack compatibility
    DECISION_MAKER_ACCESS = "decision_maker_access"  # Contact accessibility
    TIMING_INDICATORS = "timing_indicators"      # Buying timing signals

    @property
    def max_points(self) -> float:
        """Maximum points this component can contribute"""
        # Weight different components by importance
        weights = {
            self.COMPANY_INFO: 8.0,
            self.CONTACT_INFO: 6.0,
            self.LOCATION_DATA: 4.0,
            self.BUSINESS_VALIDATION: 10.0,
            self.ONLINE_PRESENCE: 8.0,
            self.SOCIAL_SIGNALS: 6.0,
            self.REVENUE_INDICATORS: 12.0,
            self.EMPLOYEE_COUNT: 8.0,
            self.FUNDING_STATUS: 6.0,
            self.INDUSTRY_RELEVANCE: 10.0,
            self.MARKET_POSITION: 8.0,
            self.GROWTH_INDICATORS: 6.0,
            self.TECHNOLOGY_STACK: 4.0,
            self.DECISION_MAKER_ACCESS: 8.0,
            self.TIMING_INDICATORS: 6.0
        }
        return weights.get(self, 5.0)

    @property
    def description(self) -> str:
        """Human-readable description of the component"""
        descriptions = {
            self.COMPANY_INFO: "Basic company information completeness and accuracy",
            self.CONTACT_INFO: "Quality and completeness of contact information",
            self.LOCATION_DATA: "Address accuracy and location verification",
            self.BUSINESS_VALIDATION: "Legitimacy and operational status indicators",
            self.ONLINE_PRESENCE: "Website quality and digital footprint strength",
            self.SOCIAL_SIGNALS: "Social media presence and customer reviews",
            self.REVENUE_INDICATORS: "Revenue data and financial health signals",
            self.EMPLOYEE_COUNT: "Company size and headcount indicators",
            self.FUNDING_STATUS: "Investment history and funding status",
            self.INDUSTRY_RELEVANCE: "Alignment with target industry and use cases",
            self.MARKET_POSITION: "Competitive positioning and market presence",
            self.GROWTH_INDICATORS: "Growth trajectory and expansion signals",
            self.TECHNOLOGY_STACK: "Technology compatibility and stack alignment",
            self.DECISION_MAKER_ACCESS: "Accessibility of key decision makers",
            self.TIMING_INDICATORS: "Buying readiness and timing signals"
        }
        return descriptions.get(self, "Score component")


class ScoringStatus(Enum):
    """Status of scoring process"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"      # Score too old, needs refresh
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
    changelog: Optional[str] = None
    deprecated: bool = False

    def __post_init__(self):
        """Ensure consistent version format"""
        if not self.version:
            self.version = f"v{self.created_at.strftime('%Y%m%d_%H%M%S')}"

    @classmethod
    def current(cls) -> 'ScoringVersion':
        """Get current scoring version"""
        return cls(
            version="v1.0.0",
            created_at=datetime.utcnow(),
            algorithm_version="baseline_v1",
            weights_version="standard_v1",
            data_schema_version="2025_v1",
            changelog="Initial scoring system implementation"
        )

    def is_compatible_with(self, other: 'ScoringVersion') -> bool:
        """Check if this version is compatible with another"""
        # Simple compatibility check - same major version
        try:
            self_major = int(self.version.split('.')[0].replace('v', ''))
            other_major = int(other.version.split('.')[0].replace('v', ''))
            return self_major == other_major
        except (ValueError, IndexError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'algorithm_version': self.algorithm_version,
            'weights_version': self.weights_version,
            'data_schema_version': self.data_schema_version,
            'changelog': self.changelog,
            'deprecated': self.deprecated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoringVersion':
        """Create from dictionary"""
        return cls(
            version=data['version'],
            created_at=datetime.fromisoformat(data['created_at']),
            algorithm_version=data['algorithm_version'],
            weights_version=data['weights_version'],
            data_schema_version=data['data_schema_version'],
            changelog=data.get('changelog'),
            deprecated=data.get('deprecated', False)
        )
