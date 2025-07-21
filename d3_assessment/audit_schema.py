"""Audit schema definitions for assessment findings."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


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
    source: str | None = None
    confidence: float | None = None


@dataclass
class AuditFinding:
    """Individual audit finding with impact and recommendations."""

    issue_id: str
    title: str
    description: str
    severity: FindingSeverity
    category: FindingCategory
    evidence: list[Evidence]
    conversion_impact: float
    effort_estimate: str
    recommendation: str | None = None
    technical_details: str | None = None
    source: str | None = None
