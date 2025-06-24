"""Audit schema definitions for assessment findings."""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Any


class FindingSeverity(Enum):
    """Severity levels for audit findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(Enum):
    """Categories for audit findings."""

    PERFORMANCE = "performance"
    SEO = "seo"
    VISUAL = "visual"
    TRUST = "trust"
    CONTENT = "content"
    TECHNICAL = "technical"


@dataclass
class Evidence:
    """Evidence supporting an audit finding."""

    type: str
    value: Any
    source: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class AuditFinding:
    """Individual audit finding with impact and recommendations."""

    issue_id: str
    title: str
    description: str
    severity: FindingSeverity
    category: FindingCategory
    evidence: List[Evidence]
    conversion_impact: float
    effort_estimate: str
    recommendation: Optional[str] = None
    technical_details: Optional[str] = None
    source: Optional[str] = None
