"""
Component Library - P2-040 Dynamic Report Designer

Provides a comprehensive library of reusable report components with drag-and-drop
functionality. Components are configurable and composable building blocks for reports.

Component Types:
- Layout: Headers, footers, sections, columns
- Data: Tables, charts, metrics, lists
- Text: Paragraphs, headings, formatted text
- Media: Images, logos, icons
- Interactive: Forms, buttons, links
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    """Component type enumeration"""

    # Layout components
    HEADER = "header"
    FOOTER = "footer"
    SECTION = "section"
    COLUMN = "column"
    SPACER = "spacer"

    # Data components
    TABLE = "table"
    CHART = "chart"
    METRIC = "metric"
    LIST = "list"
    CARD = "card"

    # Text components
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    FORMATTED_TEXT = "formatted_text"

    # Media components
    IMAGE = "image"
    LOGO = "logo"
    ICON = "icon"

    # Interactive components
    LINK = "link"
    BUTTON = "button"


class ComponentConfig(BaseModel):
    """Base configuration for report components"""

    id: str = Field(..., description="Unique component identifier")
    type: ComponentType = Field(..., description="Component type")
    title: str = Field(..., description="Component display title")
    description: Optional[str] = Field(None, description="Component description")

    # Layout properties
    width: Optional[Union[int, str]] = Field("100%", description="Component width")
    height: Optional[Union[int, str]] = Field("auto", description="Component height")
    margin: Optional[str] = Field("0", description="Component margin")
    padding: Optional[str] = Field("0", description="Component padding")

    # Styling properties
    background_color: Optional[str] = Field(None, description="Background color")
    border: Optional[str] = Field(None, description="Border style")
    border_radius: Optional[str] = Field(None, description="Border radius")

    # Behavior properties
    draggable: bool = Field(True, description="Can be dragged in designer")
    resizable: bool = Field(True, description="Can be resized in designer")
    deletable: bool = Field(True, description="Can be deleted in designer")

    # Data properties
    data_source: Optional[str] = Field(None, description="Data source identifier")
    data_filters: Optional[Dict[str, Any]] = Field(None, description="Data filters")

    # Custom properties (component-specific)
    custom_props: Optional[Dict[str, Any]] = Field(None, description="Custom properties")


class ReportComponent(ABC):
    """Abstract base class for all report components"""

    def __init__(self, config: ComponentConfig):
        self.config = config
        self.validate_config()

    @abstractmethod
    def validate_config(self) -> None:
        """Validate component configuration"""
        pass

    @abstractmethod
    def render_html(self, context: Dict[str, Any] = None) -> str:
        """Render component as HTML"""
        pass

    @abstractmethod
    def render_json(self) -> Dict[str, Any]:
        """Render component as JSON for API"""
        pass

    @abstractmethod
    def get_required_data(self) -> List[str]:
        """Get list of required data fields"""
        pass

    def get_css_classes(self) -> List[str]:
        """Get CSS classes for component"""
        return [f"component-{self.config.type.value}", f"component-{self.config.id}"]

    def get_inline_styles(self) -> str:
        """Get inline CSS styles for component"""
        styles = []

        if self.config.width:
            styles.append(f"width: {self.config.width}")
        if self.config.height:
            styles.append(f"height: {self.config.height}")
        if self.config.margin:
            styles.append(f"margin: {self.config.margin}")
        if self.config.padding:
            styles.append(f"padding: {self.config.padding}")
        if self.config.background_color:
            styles.append(f"background-color: {self.config.background_color}")
        if self.config.border:
            styles.append(f"border: {self.config.border}")
        if self.config.border_radius:
            styles.append(f"border-radius: {self.config.border_radius}")

        return "; ".join(styles)


class HeaderComponent(ReportComponent):
    """Header component for report layouts"""

    def validate_config(self) -> None:
        """Validate header configuration"""
        if not self.config.title:
            raise ValueError("Header component requires a title")

    def render_html(self, context: Dict[str, Any] = None) -> str:
        """Render header as HTML"""
        css_classes = " ".join(self.get_css_classes())
        inline_styles = self.get_inline_styles()

        subtitle = self.config.custom_props.get("subtitle", "") if self.config.custom_props else ""
        subtitle_html = f"<h3 class='header-subtitle'>{subtitle}</h3>" if subtitle else ""

        return f"""
        <header class="{css_classes}" style="{inline_styles}">
            <h1 class="header-title">{self.config.title}</h1>
            {subtitle_html}
        </header>
        """

    def render_json(self) -> Dict[str, Any]:
        """Render header as JSON"""
        return {
            "type": self.config.type.value,
            "id": self.config.id,
            "title": self.config.title,
            "subtitle": self.config.custom_props.get("subtitle") if self.config.custom_props else None,
            "styles": self.get_inline_styles(),
            "classes": self.get_css_classes(),
        }

    def get_required_data(self) -> List[str]:
        """Get required data fields"""
        return []


class TableComponent(ReportComponent):
    """Table component for displaying tabular data"""

    def validate_config(self) -> None:
        """Validate table configuration"""
        if not self.config.data_source:
            raise ValueError("Table component requires a data source")

    def render_html(self, context: Dict[str, Any] = None) -> str:
        """Render table as HTML"""
        css_classes = " ".join(self.get_css_classes())
        inline_styles = self.get_inline_styles()

        columns = self.config.custom_props.get("columns", []) if self.config.custom_props else []
        if not columns:
            columns = ["Column 1", "Column 2", "Column 3"]

        # Generate table headers
        headers = "".join([f"<th>{col}</th>" for col in columns])

        # Generate sample data rows (would be replaced with actual data)
        sample_rows = []
        for i in range(3):
            row_data = "".join([f"<td>Sample {i+1}-{j+1}</td>" for j in range(len(columns))])
            sample_rows.append(f"<tr>{row_data}</tr>")

        rows = "".join(sample_rows)

        return f"""
        <div class="{css_classes}" style="{inline_styles}">
            <h3 class="table-title">{self.config.title}</h3>
            <table class="report-table">
                <thead>
                    <tr>{headers}</tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def render_json(self) -> Dict[str, Any]:
        """Render table as JSON"""
        return {
            "type": self.config.type.value,
            "id": self.config.id,
            "title": self.config.title,
            "data_source": self.config.data_source,
            "columns": self.config.custom_props.get("columns", []) if self.config.custom_props else [],
            "filters": self.config.data_filters,
            "styles": self.get_inline_styles(),
            "classes": self.get_css_classes(),
        }

    def get_required_data(self) -> List[str]:
        """Get required data fields"""
        return [self.config.data_source] if self.config.data_source else []


class ChartComponent(ReportComponent):
    """Chart component for data visualization"""

    def validate_config(self) -> None:
        """Validate chart configuration"""
        if not self.config.data_source:
            raise ValueError("Chart component requires a data source")

        chart_type = self.config.custom_props.get("chart_type") if self.config.custom_props else None
        if chart_type and chart_type not in ["bar", "line", "pie", "scatter"]:
            raise ValueError(f"Invalid chart type: {chart_type}")

    def render_html(self, context: Dict[str, Any] = None) -> str:
        """Render chart as HTML"""
        css_classes = " ".join(self.get_css_classes())
        inline_styles = self.get_inline_styles()

        chart_type = self.config.custom_props.get("chart_type", "bar") if self.config.custom_props else "bar"
        chart_id = f"chart-{self.config.id}"

        return f"""
        <div class="{css_classes}" style="{inline_styles}">
            <h3 class="chart-title">{self.config.title}</h3>
            <div class="chart-container">
                <canvas id="{chart_id}" data-chart-type="{chart_type}" data-data-source="{self.config.data_source}"></canvas>
            </div>
            <script>
                // Chart initialization would be handled by front-end JavaScript
                console.log('Chart {chart_id} ready for initialization');
            </script>
        </div>
        """

    def render_json(self) -> Dict[str, Any]:
        """Render chart as JSON"""
        return {
            "type": self.config.type.value,
            "id": self.config.id,
            "title": self.config.title,
            "chart_type": self.config.custom_props.get("chart_type", "bar") if self.config.custom_props else "bar",
            "data_source": self.config.data_source,
            "filters": self.config.data_filters,
            "styles": self.get_inline_styles(),
            "classes": self.get_css_classes(),
        }

    def get_required_data(self) -> List[str]:
        """Get required data fields"""
        return [self.config.data_source] if self.config.data_source else []


class MetricComponent(ReportComponent):
    """Metric component for displaying key performance indicators"""

    def validate_config(self) -> None:
        """Validate metric configuration"""
        if not self.config.data_source:
            raise ValueError("Metric component requires a data source")

    def render_html(self, context: Dict[str, Any] = None) -> str:
        """Render metric as HTML"""
        css_classes = " ".join(self.get_css_classes())
        inline_styles = self.get_inline_styles()

        value = self.config.custom_props.get("value", "0") if self.config.custom_props else "0"
        unit = self.config.custom_props.get("unit", "") if self.config.custom_props else ""
        trend = self.config.custom_props.get("trend", "") if self.config.custom_props else ""

        trend_class = f"trend-{trend}" if trend in ["up", "down", "stable"] else ""
        trend_icon = {"up": "↑", "down": "↓", "stable": "→"}.get(trend, "")

        return f"""
        <div class="{css_classes}" style="{inline_styles}">
            <div class="metric-container">
                <h4 class="metric-title">{self.config.title}</h4>
                <div class="metric-value">
                    <span class="value">{value}</span>
                    <span class="unit">{unit}</span>
                    <span class="trend {trend_class}">{trend_icon}</span>
                </div>
            </div>
        </div>
        """

    def render_json(self) -> Dict[str, Any]:
        """Render metric as JSON"""
        return {
            "type": self.config.type.value,
            "id": self.config.id,
            "title": self.config.title,
            "value": self.config.custom_props.get("value") if self.config.custom_props else None,
            "unit": self.config.custom_props.get("unit") if self.config.custom_props else None,
            "trend": self.config.custom_props.get("trend") if self.config.custom_props else None,
            "data_source": self.config.data_source,
            "styles": self.get_inline_styles(),
            "classes": self.get_css_classes(),
        }

    def get_required_data(self) -> List[str]:
        """Get required data fields"""
        return [self.config.data_source] if self.config.data_source else []


class ComponentLibrary:
    """Library of available report components"""

    def __init__(self):
        self._components = {}
        self._register_default_components()

    def _register_default_components(self):
        """Register default component types"""
        self._components[ComponentType.HEADER] = HeaderComponent
        self._components[ComponentType.TABLE] = TableComponent
        self._components[ComponentType.CHART] = ChartComponent
        self._components[ComponentType.METRIC] = MetricComponent

    def register_component(self, component_type: ComponentType, component_class: type):
        """Register a new component type"""
        if not issubclass(component_class, ReportComponent):
            raise ValueError("Component class must inherit from ReportComponent")

        self._components[component_type] = component_class

    def create_component(self, config: ComponentConfig) -> ReportComponent:
        """Create a component instance from configuration"""
        if config.type not in self._components:
            raise ValueError(f"Unknown component type: {config.type}")

        component_class = self._components[config.type]
        return component_class(config)

    def get_available_components(self) -> List[Dict[str, Any]]:
        """Get list of available component types"""
        components = []

        for component_type, component_class in self._components.items():
            # Create sample config to get component metadata
            sample_config = ComponentConfig(
                id=f"sample-{component_type.value}",
                type=component_type,
                title=f"Sample {component_type.value.title()}",
                data_source="sample_data"
                if component_type in [ComponentType.TABLE, ComponentType.CHART, ComponentType.METRIC]
                else None,
            )

            try:
                sample_component = component_class(sample_config)
                components.append(
                    {
                        "type": component_type.value,
                        "name": component_type.value.replace("_", " ").title(),
                        "description": f"A {component_type.value.replace('_', ' ')} component",
                        "category": self._get_component_category(component_type),
                        "required_data": hasattr(sample_component, "get_required_data")
                        and sample_component.get_required_data() != [],
                        "configurable": True,
                    }
                )
            except Exception:
                # Skip components that can't be instantiated with sample config
                continue

        return components

    def _get_component_category(self, component_type: ComponentType) -> str:
        """Get category for component type"""
        if component_type in [ComponentType.HEADER, ComponentType.FOOTER, ComponentType.SECTION, ComponentType.COLUMN]:
            return "Layout"
        elif component_type in [ComponentType.TABLE, ComponentType.CHART, ComponentType.METRIC, ComponentType.LIST]:
            return "Data"
        elif component_type in [ComponentType.HEADING, ComponentType.PARAGRAPH, ComponentType.FORMATTED_TEXT]:
            return "Text"
        elif component_type in [ComponentType.IMAGE, ComponentType.LOGO, ComponentType.ICON]:
            return "Media"
        elif component_type in [ComponentType.LINK, ComponentType.BUTTON]:
            return "Interactive"
        else:
            return "Other"

    def validate_component_config(self, config: ComponentConfig) -> List[str]:
        """Validate component configuration and return error messages"""
        errors = []

        try:
            component = self.create_component(config)
            component.validate_config()
        except ValueError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Configuration error: {str(e)}")

        return errors


# Global component library instance
component_library = ComponentLibrary()
