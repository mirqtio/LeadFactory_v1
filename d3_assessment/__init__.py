"""
D3 Assessment - Website assessment and analysis

Provides comprehensive website assessment capabilities including PageSpeed
analysis,
technology stack detection, and AI-powered insights generation.
"""

from .assessors.visual_analyzer import VisualAnalyzer
from .models import (
    AIInsight,
    AssessmentCost,
    AssessmentResult,
    AssessmentSession,
    PageSpeedAssessment,
    TechStackDetection,
)
from .types import AssessmentStatus, AssessmentType, CostType, InsightCategory, PageSpeedMetric, TechCategory

__all__ = [
    # Models
    "AssessmentResult",
    "PageSpeedAssessment",
    "TechStackDetection",
    "AIInsight",
    "AssessmentSession",
    "AssessmentCost",
    # Types
    "AssessmentStatus",
    "AssessmentType",
    "PageSpeedMetric",
    "TechCategory",
    "InsightCategory",
    "CostType",
    # Analyzers
    "VisualAnalyzer",
]
