"""
Dynamic Report Designer - P2-040

A flexible report building system with drag-and-drop interface for creating
custom reports with dynamic components and templates.

Architecture Components:
- ReportDesigner: Main designer orchestration
- ComponentLibrary: Reusable report components
- TemplateEngine: Dynamic template system
- DesignerAPI: REST endpoints for designer
- ComponentRenderer: Component rendering engine
- PreviewEngine: Real-time preview system
- ValidationEngine: Report validation and error checking

Design Philosophy:
- Component-based architecture for maximum flexibility
- Drag-and-drop interface for non-technical users
- Template inheritance and composition
- Real-time preview with validation
- Export to multiple formats (HTML, PDF, JSON)
"""

from .component_library import ComponentLibrary, ComponentType, ReportComponent
from .designer_api import router as designer_router
from .designer_core import DesignerConfig, DesignerResult, ReportDesigner
from .preview_engine import PreviewEngine, PreviewOptions, PreviewResult
from .template_engine import TemplateConfig, TemplateEngine, TemplateResult
from .validation_engine import ValidationEngine, ValidationResult, ValidationRule

__version__ = "1.0.0"

# Public API exports
__all__ = [
    # Core designer
    "ReportDesigner",
    "DesignerConfig",
    "DesignerResult",
    # Component system
    "ComponentLibrary",
    "ComponentType",
    "ReportComponent",
    # Template system
    "TemplateEngine",
    "TemplateConfig",
    "TemplateResult",
    # Preview system
    "PreviewEngine",
    "PreviewOptions",
    "PreviewResult",
    # Validation system
    "ValidationEngine",
    "ValidationResult",
    "ValidationRule",
    # API router
    "designer_router",
]
