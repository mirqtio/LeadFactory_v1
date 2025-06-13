"""
Base assessor class for all website assessments
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from d3_assessment.models import AssessmentType


@dataclass
class AssessmentResult:
    """Result of an assessment"""
    assessment_type: AssessmentType
    status: str  # 'completed', 'failed', 'timeout'
    data: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    cost: float = 0.0
    

class BaseAssessor(ABC):
    """Abstract base class for all assessors"""
    
    @property
    @abstractmethod
    def assessment_type(self) -> AssessmentType:
        """Get the type of assessment this assessor performs"""
        pass
    
    @abstractmethod
    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Perform the assessment
        
        Args:
            url: Website URL to assess
            business_data: Business information for context
            
        Returns:
            AssessmentResult with data specific to the assessment type
        """
        pass
    
    @abstractmethod
    def calculate_cost(self) -> float:
        """Calculate the cost of this assessment in USD"""
        pass
    
    def is_available(self) -> bool:
        """Check if this assessor is available (has required API keys, etc)"""
        return True
    
    def get_timeout(self) -> int:
        """Get timeout in seconds for this assessment"""
        return getattr(self, 'timeout', 30)