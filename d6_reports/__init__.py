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

from .finding_scorer import FindingScore, FindingScorer
from .generator import (
    GenerationOptions,
    GenerationResult,
    ReportGenerator,
    generate_audit_report,
)
from .models import (
    DeliveryMethod,
    ReportDelivery,
    ReportGeneration,
    ReportSection,
    ReportStatus,
    ReportTemplate,
    ReportType,
    TemplateFormat,
)
from .pdf_converter import (
    PDFConverter,
    PDFOptions,
    PDFResult,
    html_to_pdf,
    save_html_as_pdf,
)
from .prioritizer import FindingPrioritizer, PrioritizationResult
from .template_engine import TemplateData, TemplateEngine

__version__ = "1.0.0"

__all__ = [
    # Models
    "ReportGeneration",
    "ReportTemplate",
    "ReportSection",
    "ReportDelivery",
    "ReportStatus",
    "ReportType",
    "DeliveryMethod",
    "TemplateFormat",
    # Prioritization
    "FindingPrioritizer",
    "PrioritizationResult",
    "FindingScorer",
    "FindingScore",
    # PDF Conversion
    "PDFConverter",
    "PDFOptions",
    "PDFResult",
    "html_to_pdf",
    "save_html_as_pdf",
    # Template Engine
    "TemplateEngine",
    "TemplateData",
    # Report Generation
    "ReportGenerator",
    "GenerationOptions",
    "GenerationResult",
    "generate_audit_report",
]
