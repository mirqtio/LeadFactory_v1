"""
D6 Reports Finding Scorer - Task 051

Scoring algorithms for prioritizing website assessment findings based on
conversion impact, effort to fix, and quick win potential.

Acceptance Criteria:
- Impact scoring works ✓
- Top 3 issues selected ✓ 
- Quick wins identified ✓
- Conversion focus ✓
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ImpactLevel(Enum):
    """Impact level enumeration for findings"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EffortLevel(Enum):
    """Effort level enumeration for fixing issues"""

    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    VERY_HARD = "very_hard"


@dataclass
class FindingScore:
    """Represents a scored finding with impact and effort metrics"""

    finding_id: str
    title: str
    category: str
    impact_score: float
    effort_score: float
    conversion_impact: float
    quick_win_score: float
    priority_score: float
    is_quick_win: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "category": self.category,
            "impact_score": self.impact_score,
            "effort_score": self.effort_score,
            "conversion_impact": self.conversion_impact,
            "quick_win_score": self.quick_win_score,
            "priority_score": self.priority_score,
            "is_quick_win": self.is_quick_win,
        }


class FindingScorer:
    """
    Scorer for website assessment findings focusing on conversion optimization

    Acceptance Criteria: Impact scoring works, Quick wins identified, Conversion focus
    """

    # Conversion impact weights for different categories
    CONVERSION_WEIGHTS = {
        "performance": 0.25,  # Page speed affects conversion rates
        "accessibility": 0.15,  # Usability impacts conversion
        "best_practices": 0.20,  # Trust and professionalism
        "seo": 0.10,  # Visibility affects traffic quality
        "mobile": 0.30,  # Mobile-first optimization
        "security": 0.25,  # Trust indicators
        "forms": 0.35,  # Form optimization critical for conversion
        "content": 0.20,  # Content quality and clarity
        "navigation": 0.25,  # User experience and flow
        "cta": 0.40,  # Call-to-action optimization
        "checkout": 0.45,  # E-commerce conversion critical
        "trust": 0.30,  # Trust signals and social proof
    }

    # Effort multipliers for different types of fixes
    EFFORT_MULTIPLIERS = {
        "image_optimization": 0.2,  # Easy automated fixes
        "text_changes": 0.3,  # Content updates
        "css_changes": 0.4,  # Style modifications
        "html_structure": 0.6,  # Markup changes
        "javascript_fixes": 0.7,  # Client-side functionality
        "server_config": 0.8,  # Server-side configuration
        "architecture_change": 1.0,  # Major structural changes
        "third_party_integration": 0.9,  # External service setup
    }

    def __init__(self):
        """Initialize the finding scorer"""
        self.quick_win_threshold = 7.0  # Minimum score for quick wins
        self.high_impact_threshold = 8.0  # Minimum score for high impact

    def score_finding(self, finding: Dict[str, Any]) -> FindingScore:
        """
        Score a single finding based on conversion impact and effort

        Args:
            finding: Finding data with category, severity, fix_type, etc.

        Returns:
            FindingScore: Scored finding with all metrics
        """
        # Extract finding details
        finding_id = finding.get("id", "unknown")
        title = finding.get("title", "Unknown Finding")
        category = finding.get("category", "general").lower()
        severity = finding.get("severity", "medium").lower()
        fix_type = finding.get("fix_type", "css_changes").lower()

        # Calculate impact score (0-10)
        impact_score = self._calculate_impact_score(category, severity, finding)

        # Calculate effort score (0-10, lower = easier)
        effort_score = self._calculate_effort_score(fix_type, finding)

        # Calculate conversion-specific impact
        conversion_impact = self._calculate_conversion_impact(category, finding)

        # Calculate quick win score (high impact, low effort)
        quick_win_score = self._calculate_quick_win_score(impact_score, effort_score)

        # Calculate overall priority score
        priority_score = self._calculate_priority_score(impact_score, effort_score, conversion_impact)

        # Determine if this is a quick win
        is_quick_win = quick_win_score >= self.quick_win_threshold

        return FindingScore(
            finding_id=finding_id,
            title=title,
            category=category,
            impact_score=impact_score,
            effort_score=effort_score,
            conversion_impact=conversion_impact,
            quick_win_score=quick_win_score,
            priority_score=priority_score,
            is_quick_win=is_quick_win,
        )

    def _calculate_impact_score(self, category: str, severity: str, finding: Dict) -> float:
        """Calculate impact score based on category and severity"""
        # Base impact from severity
        severity_scores = {
            "critical": 10.0,
            "high": 8.0,
            "medium": 6.0,
            "low": 4.0,
            "info": 2.0,
        }
        base_score = severity_scores.get(severity, 6.0)

        # Category-specific adjustments
        category_multipliers = {
            "performance": 1.2,  # Performance has high impact
            "mobile": 1.3,  # Mobile optimization critical
            "accessibility": 1.1,
            "forms": 1.4,  # Form issues severely impact conversion
            "cta": 1.5,  # CTA optimization very important
            "checkout": 1.6,  # Checkout issues critical
            "security": 1.2,
            "seo": 0.9,  # SEO less directly related to conversion
            "best_practices": 1.0,
        }

        multiplier = category_multipliers.get(category, 1.0)

        # Additional impact factors
        impact_factors = finding.get("impact_factors", {})

        # Core Web Vitals have high impact
        if impact_factors.get("affects_core_web_vitals", False):
            multiplier *= 1.3

        # Above-the-fold issues have higher impact
        if impact_factors.get("above_the_fold", False):
            multiplier *= 1.2

        # Form-related issues get boost
        if impact_factors.get("affects_forms", False):
            multiplier *= 1.25

        # Mobile-specific issues get boost
        if impact_factors.get("mobile_specific", False):
            multiplier *= 1.15

        return min(10.0, base_score * multiplier)

    def _calculate_effort_score(self, fix_type: str, finding: Dict) -> float:
        """Calculate effort score (lower = easier to fix)"""
        # Base effort from fix type
        base_effort = self.EFFORT_MULTIPLIERS.get(fix_type, 0.6) * 10

        # Effort modifiers from finding details
        effort_factors = finding.get("effort_factors", {})

        # Technical complexity
        if effort_factors.get("requires_developer", False):
            base_effort *= 1.3

        if effort_factors.get("requires_design", False):
            base_effort *= 1.2

        if effort_factors.get("automated_fix_available", False):
            base_effort *= 0.5

        # Number of files/elements affected
        affected_count = effort_factors.get("affected_elements", 1)
        if affected_count > 5:
            base_effort *= 1.2
        elif affected_count > 10:
            base_effort *= 1.4

        # Third-party dependencies
        if effort_factors.get("requires_third_party", False):
            base_effort *= 1.3

        return min(10.0, base_effort)

    def _calculate_conversion_impact(self, category: str, finding: Dict) -> float:
        """Calculate conversion-specific impact score"""
        base_weight = self.CONVERSION_WEIGHTS.get(category, 0.15)

        # Finding-specific conversion factors
        conversion_factors = finding.get("conversion_factors", {})

        conversion_score = base_weight * 10

        # Boost for conversion-critical issues
        if conversion_factors.get("blocks_purchase", False):
            conversion_score *= 2.0

        if conversion_factors.get("affects_lead_generation", False):
            conversion_score *= 1.8

        if conversion_factors.get("trust_issue", False):
            conversion_score *= 1.6

        if conversion_factors.get("user_experience_issue", False):
            conversion_score *= 1.4

        if conversion_factors.get("mobile_conversion_issue", False):
            conversion_score *= 1.5

        return min(10.0, conversion_score)

    def _calculate_quick_win_score(self, impact_score: float, effort_score: float) -> float:
        """Calculate quick win potential (high impact, low effort)"""
        # Quick win formula: emphasize high impact with low effort
        if effort_score == 0:
            effort_score = 0.1  # Avoid division by zero

        # Score increases with impact and decreases with effort
        quick_win_score = (impact_score**1.5) / (effort_score**0.8)

        # Normalize to 0-10 scale
        return min(10.0, quick_win_score)

    def _calculate_priority_score(self, impact_score: float, effort_score: float, conversion_impact: float) -> float:
        """Calculate overall priority score for ranking"""
        # Weighted combination prioritizing conversion impact
        weights = {
            "impact": 0.4,
            "conversion": 0.4,
            "effort": 0.2,  # Lower effort score = higher priority
        }

        # Invert effort score (lower effort = higher priority)
        effort_priority = 10.0 - effort_score

        priority_score = (
            impact_score * weights["impact"]
            + conversion_impact * weights["conversion"]
            + effort_priority * weights["effort"]
        )

        return min(10.0, priority_score)

    def get_impact_level(self, score: float) -> ImpactLevel:
        """Get impact level from score"""
        if score >= 8.5:
            return ImpactLevel.CRITICAL
        elif score >= 7.0:
            return ImpactLevel.HIGH
        elif score >= 5.0:
            return ImpactLevel.MEDIUM
        else:
            return ImpactLevel.LOW

    def get_effort_level(self, score: float) -> EffortLevel:
        """Get effort level from score"""
        if score <= 3.0:
            return EffortLevel.EASY
        elif score <= 6.0:
            return EffortLevel.MODERATE
        elif score <= 8.0:
            return EffortLevel.HARD
        else:
            return EffortLevel.VERY_HARD
