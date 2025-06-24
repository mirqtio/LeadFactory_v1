"""
Assessment assessors for PRD v1.2
"""
from typing import Dict, Type

from d3_assessment.assessors.base import BaseAssessor

# Import all assessors
from d3_assessment.assessors.pagespeed_assessor import PageSpeedAssessor
from d3_assessment.assessors.beautifulsoup_assessor import BeautifulSoupAssessor
from d3_assessment.assessors.semrush_assessor import SEMrushAssessor
from d3_assessment.assessors.yelp_fields_assessor import YelpSearchFieldsAssessor
from d3_assessment.assessors.gbp_profile_assessor import GBPProfileAssessor
from d3_assessment.assessors.screenshot_assessor import ScreenshotAssessor
from d3_assessment.assessors.vision_assessor import VisionAssessor

# Assessor registry
ASSESSOR_REGISTRY: Dict[str, Type[BaseAssessor]] = {
    "pagespeed": PageSpeedAssessor,
    "beautifulsoup": BeautifulSoupAssessor,
    "semrush": SEMrushAssessor,
    "yelp_fields": YelpSearchFieldsAssessor,
    "gbp_profile": GBPProfileAssessor,
    "screenshot": ScreenshotAssessor,
    "vision": VisionAssessor,
}

# Export all assessors
__all__ = [
    "BaseAssessor",
    "PageSpeedAssessor",
    "BeautifulSoupAssessor",
    "SEMrushAssessor",
    "YelpSearchFieldsAssessor",
    "GBPProfileAssessor",
    "ScreenshotAssessor",
    "VisionAssessor",
    "ASSESSOR_REGISTRY",
]
