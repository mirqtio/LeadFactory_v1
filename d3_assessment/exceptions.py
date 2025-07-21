"""
D3 Assessment exceptions
"""


class AssessmentError(Exception):
    """Base exception for assessment errors"""


class AssessmentTimeoutError(AssessmentError):
    """Raised when assessment times out"""


class AssessmentAPIError(AssessmentError):
    """Raised when external API call fails"""


class AssessmentValidationError(AssessmentError):
    """Raised when assessment data validation fails"""
