"""Core utilities and configuration for LeadFactory"""
from core.config import settings
from core.exceptions import ExternalAPIError, LeadFactoryError, ValidationError
from core.logging import get_logger

__all__ = [
    "settings",
    "get_logger",
    "LeadFactoryError",
    "ValidationError",
    "ExternalAPIError",
]

# Deployment test trigger for PRP-1058 workflow validation 2025-07-21T13:42:00Z
