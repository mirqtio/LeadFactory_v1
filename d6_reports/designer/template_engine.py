"""
Template Engine - P2-040 Dynamic Report Designer

Dynamic template system for report generation with component composition,
inheritance, and real-time rendering capabilities.

Features:
- Component-based template composition
- Template inheritance and extension
- Dynamic data binding
- Conditional rendering
- Template validation
- Multi-format output (HTML, PDF, JSON)
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from jinja2 import BaseLoader, Environment, Template
from pydantic import BaseModel, Field

from .component_library import ComponentConfig, ComponentLibrary, ReportComponent, component_library


class TemplateConfig(BaseModel):
    """Template configuration"""

    id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    version: str = Field(default="1.0.0", description="Template version")

    # Layout properties
    page_size: str = Field(default="A4", description="Page size (A4, Letter, etc.)")
    orientation: str = Field(default="portrait", description="Page orientation")
    margins: Dict[str, str] = Field(default={"top": "1in", "right": "1in", "bottom": "1in", "left": "1in"})

    # Styling
    theme: str = Field(default="default", description="Theme identifier")
    custom_css: Optional[str] = Field(None, description="Custom CSS styles")

    # Components
    components: List[ComponentConfig] = Field(default=[], description="Template components")

    # Data requirements
    data_sources: List[str] = Field(default=[], description="Required data sources")

    # Metadata
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(None, description="Creator identifier")
    tags: List[str] = Field(default=[], description="Template tags")


class TemplateResult(BaseModel):
    """Template rendering result"""

    template_id: str
    success: bool
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    json_structure: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    warnings: List[str] = Field(default=[])
    render_time_ms: int = 0
    component_count: int = 0
    required_data_sources: List[str] = Field(default=[])


@dataclass
class RenderContext:
    """Context for template rendering"""

    data: Dict[str, Any] = field(default_factory=dict)
    user_context: Optional[Dict[str, Any]] = None
    business_context: Optional[Dict[str, Any]] = None
    render_mode: str = "html"  # html, pdf, json
    include_debug: bool = False
    custom_filters: Optional[Dict[str, Any]] = None


class TemplateEngine:
    """Dynamic template engine for report generation"""

    def __init__(self):
        self.component_library = component_library
        self.jinja_env = Environment(loader=BaseLoader())
        self._setup_jinja_filters()
        self.templates: Dict[str, TemplateConfig] = {}
        self._load_default_templates()

    def _setup_jinja_filters(self):
        """Setup custom Jinja2 filters"""
        self.jinja_env.filters["currency"] = self._currency_filter
        self.jinja_env.filters["percentage"] = self._percentage_filter
        self.jinja_env.filters["date_format"] = self._date_format_filter
        self.jinja_env.filters["number_format"] = self._number_format_filter

    def _currency_filter(self, value: Union[int, float, str], currency: str = "USD") -> str:
        """Format number as currency"""
        try:
            num_value = float(value)
            return f"${num_value:,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _percentage_filter(self, value: Union[int, float, str], decimals: int = 1) -> str:
        """Format number as percentage"""
        try:
            num_value = float(value)
            return f"{num_value:.{decimals}f}%"
        except (ValueError, TypeError):
            return str(value)

    def _date_format_filter(self, value: Union[str, datetime], format: str = "%Y-%m-%d") -> str:
        """Format date string"""
        try:
            if isinstance(value, str):
                date_obj = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                date_obj = value
            return date_obj.strftime(format)
        except (ValueError, TypeError):
            return str(value)

    def _number_format_filter(self, value: Union[int, float, str], decimals: int = 2) -> str:
        """Format number with commas and decimals"""
        try:
            num_value = float(value)
            return f"{num_value:,.{decimals}f}"
        except (ValueError, TypeError):
            return str(value)

    def _load_default_templates(self):
        """Load default template configurations"""
        # Basic report template
        basic_template = TemplateConfig(
            id="basic_report",
            name="Basic Report",
            description="A simple report template with header, metrics, and table",
            components=[
                ComponentConfig(
                    id="header-1",
                    type="header",
                    title="Business Report",
                    custom_props={"subtitle": "Performance Overview"},
                ),
                ComponentConfig(
                    id="metrics-1",
                    type="metric",
                    title="Total Revenue",
                    data_source="revenue_data",
                    custom_props={"unit": "USD", "trend": "up"},
                ),
                ComponentConfig(
                    id="table-1",
                    type="table",
                    title="Performance Data",
                    data_source="performance_data",
                    custom_props={"columns": ["Metric", "Value", "Change"]},
                ),
            ],
            data_sources=["revenue_data", "performance_data"],
            tags=["basic", "business", "performance"],
        )

        # Executive summary template
        executive_template = TemplateConfig(
            id="executive_summary",
            name="Executive Summary",
            description="Executive-level summary with key metrics and charts",
            components=[
                ComponentConfig(
                    id="header-1",
                    type="header",
                    title="Executive Summary",
                    custom_props={"subtitle": "Key Performance Indicators"},
                ),
                ComponentConfig(
                    id="metrics-1",
                    type="metric",
                    title="Revenue Growth",
                    data_source="growth_data",
                    custom_props={"unit": "%", "trend": "up"},
                ),
                ComponentConfig(
                    id="metrics-2",
                    type="metric",
                    title="Customer Acquisition",
                    data_source="customer_data",
                    custom_props={"unit": "customers", "trend": "up"},
                ),
                ComponentConfig(
                    id="chart-1",
                    type="chart",
                    title="Revenue Trend",
                    data_source="revenue_trend",
                    custom_props={"chart_type": "line"},
                ),
            ],
            data_sources=["growth_data", "customer_data", "revenue_trend"],
            tags=["executive", "summary", "kpi"],
        )

        self.templates["basic_report"] = basic_template
        self.templates["executive_summary"] = executive_template

    def create_template(self, config: TemplateConfig) -> str:
        """Create a new template"""
        # Validate template configuration
        validation_errors = self.validate_template(config)
        if validation_errors:
            raise ValueError(f"Template validation failed: {', '.join(validation_errors)}")

        # Store template
        self.templates[config.id] = config

        return config.id

    def get_template(self, template_id: str) -> Optional[TemplateConfig]:
        """Get template by ID"""
        return self.templates.get(template_id)

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates"""
        templates = []
        for template_config in self.templates.values():
            templates.append(
                {
                    "id": template_config.id,
                    "name": template_config.name,
                    "description": template_config.description,
                    "version": template_config.version,
                    "component_count": len(template_config.components),
                    "data_sources": template_config.data_sources,
                    "tags": template_config.tags,
                    "created_at": template_config.created_at.isoformat() if template_config.created_at else None,
                    "updated_at": template_config.updated_at.isoformat() if template_config.updated_at else None,
                }
            )
        return templates

    def validate_template(self, config: TemplateConfig) -> List[str]:
        """Validate template configuration"""
        errors = []

        # Check basic requirements
        if not config.id:
            errors.append("Template ID is required")
        if not config.name:
            errors.append("Template name is required")

        # Validate components
        for component_config in config.components:
            component_errors = self.component_library.validate_component_config(component_config)
            errors.extend([f"Component {component_config.id}: {error}" for error in component_errors])

        # Check for duplicate component IDs
        component_ids = [comp.id for comp in config.components]
        if len(component_ids) != len(set(component_ids)):
            errors.append("Duplicate component IDs found")

        # Validate data sources
        template_data_sources = set()
        for component_config in config.components:
            if component_config.data_source:
                template_data_sources.add(component_config.data_source)

        missing_data_sources = template_data_sources - set(config.data_sources)
        if missing_data_sources:
            errors.append(f"Missing data sources in template config: {', '.join(missing_data_sources)}")

        return errors

    def render_template(self, template_id: str, context: RenderContext) -> TemplateResult:
        """Render template with provided context"""
        start_time = datetime.utcnow()

        # Get template
        template_config = self.get_template(template_id)
        if not template_config:
            return TemplateResult(
                template_id=template_id, success=False, error_message=f"Template not found: {template_id}"
            )

        try:
            # Create components
            components = []
            required_data_sources = []

            for component_config in template_config.components:
                component = self.component_library.create_component(component_config)
                components.append(component)
                required_data_sources.extend(component.get_required_data())

            # Render based on mode
            if context.render_mode == "html":
                html_content = self._render_html(template_config, components, context)
                css_content = self._render_css(template_config, components)

                render_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                return TemplateResult(
                    template_id=template_id,
                    success=True,
                    html_content=html_content,
                    css_content=css_content,
                    render_time_ms=int(render_time),
                    component_count=len(components),
                    required_data_sources=list(set(required_data_sources)),
                )

            elif context.render_mode == "json":
                json_structure = self._render_json(template_config, components, context)

                render_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                return TemplateResult(
                    template_id=template_id,
                    success=True,
                    json_structure=json_structure,
                    render_time_ms=int(render_time),
                    component_count=len(components),
                    required_data_sources=list(set(required_data_sources)),
                )

            else:
                return TemplateResult(
                    template_id=template_id,
                    success=False,
                    error_message=f"Unsupported render mode: {context.render_mode}",
                )

        except Exception as e:
            return TemplateResult(template_id=template_id, success=False, error_message=f"Render error: {str(e)}")

    def _render_html(
        self, template_config: TemplateConfig, components: List[ReportComponent], context: RenderContext
    ) -> str:
        """Render template as HTML"""
        # Generate component HTML
        component_html = []
        for component in components:
            try:
                html = component.render_html(context.data)
                component_html.append(html)
            except Exception as e:
                error_html = (
                    f'<div class="component-error">Error rendering component {component.config.id}: {str(e)}</div>'
                )
                component_html.append(error_html)

        # Generate full HTML document
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ template_name }}</title>
            <style>
                {{ css_content }}
            </style>
        </head>
        <body class="report-body">
            <div class="report-container">
                {{ components_html }}
            </div>
            {% if include_debug %}
            <div class="debug-info">
                <h4>Debug Information</h4>
                <p>Template: {{ template_id }}</p>
                <p>Components: {{ component_count }}</p>
                <p>Render time: {{ render_time }}ms</p>
            </div>
            {% endif %}
        </body>
        </html>
        """

        template = self.jinja_env.from_string(html_template)

        return template.render(
            template_name=template_config.name,
            template_id=template_config.id,
            components_html="\n".join(component_html),
            css_content=self._render_css(template_config, components),
            include_debug=context.include_debug,
            component_count=len(components),
            render_time=0,  # Will be calculated later
        )

    def _render_css(self, template_config: TemplateConfig, components: List[ReportComponent]) -> str:
        """Render CSS for template and components"""
        css_rules = []

        # Base styles
        css_rules.append(
            """
        .report-body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        
        .report-container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .component-error {
            background-color: #ffe6e6;
            border: 1px solid #ff9999;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            color: #cc0000;
        }
        
        .header-title {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 2em;
        }
        
        .header-subtitle {
            margin: 0 0 20px 0;
            color: #666;
            font-size: 1.2em;
            font-weight: normal;
        }
        
        .metric-container {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }
        
        .metric-title {
            margin: 0 0 10px 0;
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }
        
        .metric-value .unit {
            font-size: 0.6em;
            color: #999;
        }
        
        .trend-up { color: #28a745; }
        .trend-down { color: #dc3545; }
        .trend-stable { color: #6c757d; }
        
        .report-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        .report-table th,
        .report-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .report-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #333;
        }
        
        .chart-container {
            margin: 20px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }
        
        .chart-title,
        .table-title {
            margin: 0 0 15px 0;
            color: #333;
            font-size: 1.3em;
        }
        """
        )

        # Add custom CSS
        if template_config.custom_css:
            css_rules.append(template_config.custom_css)

        return "\n".join(css_rules)

    def _render_json(
        self, template_config: TemplateConfig, components: List[ReportComponent], context: RenderContext
    ) -> Dict[str, Any]:
        """Render template as JSON structure"""
        component_data = []

        for component in components:
            try:
                json_data = component.render_json()
                component_data.append(json_data)
            except Exception as e:
                error_data = {"type": "error", "component_id": component.config.id, "error": str(e)}
                component_data.append(error_data)

        return {
            "template": {
                "id": template_config.id,
                "name": template_config.name,
                "description": template_config.description,
                "version": template_config.version,
            },
            "layout": {
                "page_size": template_config.page_size,
                "orientation": template_config.orientation,
                "margins": template_config.margins,
            },
            "components": component_data,
            "data_sources": template_config.data_sources,
            "metadata": {
                "render_mode": context.render_mode,
                "component_count": len(components),
                "has_data": bool(context.data),
            },
        }

    def clone_template(self, template_id: str, new_name: str, new_id: str = None) -> str:
        """Clone an existing template"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Create new template config
        new_template = TemplateConfig(
            id=new_id or f"{template_id}_copy_{int(datetime.utcnow().timestamp())}",
            name=new_name,
            description=f"Copy of {template.name}",
            version=template.version,
            page_size=template.page_size,
            orientation=template.orientation,
            margins=template.margins.copy(),
            theme=template.theme,
            custom_css=template.custom_css,
            components=[ComponentConfig(**comp.dict()) for comp in template.components],
            data_sources=template.data_sources.copy(),
            tags=template.tags.copy(),
        )

        return self.create_template(new_template)

    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        if template_id in self.templates:
            del self.templates[template_id]
            return True
        return False


# Global template engine instance
template_engine = TemplateEngine()
