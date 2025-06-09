"""
D6 Reports Module - Task 050

Audit report generation system for creating conversion-optimized PDF reports
that provide business intelligence insights to customers.

Acceptance Criteria:
- Report generation tracked
- Template structure defined
- Mobile-responsive HTML
- Print-optimized CSS
"""

from .models import (
    ReportGeneration,
    ReportTemplate,
    ReportSection,
    ReportDelivery
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "ReportGeneration",
    "ReportTemplate",
    "ReportSection",
    "ReportDelivery"
]
