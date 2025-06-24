"""
D3 Assessment exceptions
"""


class AssessmentError(Exception):
    """Base exception for assessment errors"""

    pass


class AssessmentTimeoutError(AssessmentError):
    """Raised when assessment times out"""

    pass


class AssessmentAPIError(AssessmentError):
    """Raised when external API call fails"""

    pass


class AssessmentValidationError(AssessmentError):
    """Raised when assessment data validation fails"""

    pass
