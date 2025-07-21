"""
Assessment assessors for PRD v1.2
"""

from typing import Dict, Type

from d3_assessment.assessors.base import BaseAssessor
from d3_assessment.assessors.beautifulsoup_assessor import BeautifulSoupAssessor
from d3_assessment.assessors.gbp_profile_assessor import GBPProfileAssessor

# Import all assessors
from d3_assessment.assessors.lighthouse import LighthouseAssessor
from d3_assessment.assessors.llm_heuristic_assessor import LLMHeuristicAssessor
from d3_assessment.assessors.pagespeed_assessor import PageSpeedAssessor
from d3_assessment.assessors.screenshot_assessor import ScreenshotAssessor
from d3_assessment.assessors.semrush_assessor import SEMrushAssessor
from d3_assessment.assessors.vision_assessor import VisionAssessor
from d3_assessment.assessors.visual_analyzer import VisualAnalyzer

# Assessor registry
ASSESSOR_REGISTRY: dict[str, type[BaseAssessor]] = {
    "pagespeed": PageSpeedAssessor,
    "beautifulsoup": BeautifulSoupAssessor,
    "semrush": SEMrushAssessor,
    "gbp_profile": GBPProfileAssessor,
    "screenshot": ScreenshotAssessor,
    "vision": VisionAssessor,
    "lighthouse": LighthouseAssessor,
    "visual_analyzer": VisualAnalyzer,
    "llm_heuristic": LLMHeuristicAssessor,
}

# Export all assessors
__all__ = [
    "BaseAssessor",
    "PageSpeedAssessor",
    "BeautifulSoupAssessor",
    "SEMrushAssessor",
    "GBPProfileAssessor",
    "ScreenshotAssessor",
    "VisionAssessor",
    "LighthouseAssessor",
    "VisualAnalyzer",
    "LLMHeuristicAssessor",
    "ASSESSOR_REGISTRY",
]
