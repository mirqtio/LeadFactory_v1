"""
Unit tests for P2-040 Dynamic Report Designer System

Tests the complete designer system including component library, template engine,
preview engine, validation engine, and designer core functionality.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d6_reports.designer.component_library import (
    ChartComponent,
    ComponentConfig,
    ComponentLibrary,
    ComponentType,
    HeaderComponent,
    MetricComponent,
    TableComponent,
    component_library,
)
from d6_reports.designer.designer_core import (
    DesignerConfig,
    DesignerResult,
    DesignerSession,
    ReportDesigner,
    report_designer,
)
from d6_reports.designer.preview_engine import PreviewEngine, PreviewOptions, PreviewResult, preview_engine
from d6_reports.designer.template_engine import (
    RenderContext,
    TemplateConfig,
    TemplateEngine,
    TemplateResult,
    template_engine,
)
from d6_reports.designer.validation_engine import (
    ValidationCategory,
    ValidationEngine,
    ValidationLevel,
    ValidationResult,
    validation_engine,
)


class TestComponentLibrary:
    """Test component library functionality"""

    def test_component_config_creation(self):
        """Test creating component configuration"""
        config = ComponentConfig(
            id="test-header",
            type=ComponentType.HEADER,
            title="Test Header",
            description="A test header component",
            width="100%",
            height="auto",
            custom_props={"subtitle": "Test Subtitle"},
        )

        assert config.id == "test-header"
        assert config.type == ComponentType.HEADER
        assert config.title == "Test Header"
        assert config.description == "A test header component"
        assert config.width == "100%"
        assert config.height == "auto"
        assert config.custom_props["subtitle"] == "Test Subtitle"

    def test_header_component_creation(self):
        """Test creating header component"""
        config = ComponentConfig(
            id="header-1", type=ComponentType.HEADER, title="Test Header", custom_props={"subtitle": "Test Subtitle"}
        )

        header = HeaderComponent(config)

        assert header.config.id == "header-1"
        assert header.config.type == ComponentType.HEADER
        assert header.config.title == "Test Header"

    def test_header_component_render_html(self):
        """Test header component HTML rendering"""
        config = ComponentConfig(
            id="header-1", type=ComponentType.HEADER, title="Test Header", custom_props={"subtitle": "Test Subtitle"}
        )

        header = HeaderComponent(config)
        html = header.render_html()

        assert "Test Header" in html
        assert "Test Subtitle" in html
        assert "header-title" in html
        assert "header-subtitle" in html

    def test_header_component_render_json(self):
        """Test header component JSON rendering"""
        config = ComponentConfig(
            id="header-1", type=ComponentType.HEADER, title="Test Header", custom_props={"subtitle": "Test Subtitle"}
        )

        header = HeaderComponent(config)
        json_data = header.render_json()

        assert json_data["type"] == "header"
        assert json_data["id"] == "header-1"
        assert json_data["title"] == "Test Header"
        assert json_data["subtitle"] == "Test Subtitle"

    def test_table_component_creation(self):
        """Test creating table component"""
        config = ComponentConfig(
            id="table-1",
            type=ComponentType.TABLE,
            title="Test Table",
            data_source="test_data",
            custom_props={"columns": ["Name", "Value", "Status"]},
        )

        table = TableComponent(config)

        assert table.config.id == "table-1"
        assert table.config.type == ComponentType.TABLE
        assert table.config.data_source == "test_data"

    def test_table_component_validation(self):
        """Test table component validation"""
        config = ComponentConfig(
            id="table-1",
            type=ComponentType.TABLE,
            title="Test Table",
            # Missing data_source
        )

        with pytest.raises(ValueError, match="Table component requires a data source"):
            TableComponent(config)

    def test_component_library_creation(self):
        """Test creating component from library"""
        config = ComponentConfig(id="test-header", type=ComponentType.HEADER, title="Test Header")

        component = component_library.create_component(config)

        assert isinstance(component, HeaderComponent)
        assert component.config.id == "test-header"

    def test_component_library_available_components(self):
        """Test getting available components"""
        components = component_library.get_available_components()

        assert len(components) > 0
        assert any(comp["type"] == "header" for comp in components)
        assert any(comp["type"] == "table" for comp in components)
        assert any(comp["type"] == "chart" for comp in components)
        assert any(comp["type"] == "metric" for comp in components)

    def test_component_library_validation(self):
        """Test component configuration validation"""
        # Valid configuration
        valid_config = ComponentConfig(id="valid-header", type=ComponentType.HEADER, title="Valid Header")

        errors = component_library.validate_component_config(valid_config)
        assert len(errors) == 0

        # Invalid configuration
        invalid_config = ComponentConfig(
            id="invalid-table",
            type=ComponentType.TABLE,
            title="Invalid Table",
            # Missing data_source
        )

        errors = component_library.validate_component_config(invalid_config)
        assert len(errors) > 0
        assert "requires a data source" in errors[0]


class TestTemplateEngine:
    """Test template engine functionality"""

    def test_template_config_creation(self):
        """Test creating template configuration"""
        config = TemplateConfig(
            id="test-template",
            name="Test Template",
            description="A test template",
            components=[ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Test Header")],
            data_sources=["test_data"],
        )

        assert config.id == "test-template"
        assert config.name == "Test Template"
        assert len(config.components) == 1
        assert len(config.data_sources) == 1

    def test_template_engine_creation(self):
        """Test creating template in engine"""
        engine = TemplateEngine()

        config = TemplateConfig(
            id="new-template", name="New Template", description="A new template", components=[], data_sources=[]
        )

        template_id = engine.create_template(config)

        assert template_id == "new-template"
        assert engine.get_template(template_id) is not None

    def test_template_engine_list_templates(self):
        """Test listing templates"""
        engine = TemplateEngine()
        templates = engine.list_templates()

        assert len(templates) >= 2  # Should have default templates
        assert any(t["id"] == "basic_report" for t in templates)
        assert any(t["id"] == "executive_summary" for t in templates)

    def test_template_engine_validation(self):
        """Test template validation"""
        engine = TemplateEngine()

        # Valid template
        valid_config = TemplateConfig(
            id="valid-template",
            name="Valid Template",
            components=[ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Valid Header")],
            data_sources=[],
        )

        errors = engine.validate_template(valid_config)
        assert len(errors) == 0

        # Invalid template
        invalid_config = TemplateConfig(
            id="invalid-template",
            name="Invalid Template",
            components=[
                ComponentConfig(
                    id="table-1", type=ComponentType.TABLE, title="Invalid Table", data_source="missing_data"
                )
            ],
            data_sources=[],  # Missing data source
        )

        errors = engine.validate_template(invalid_config)
        assert len(errors) > 0

    def test_template_engine_render_html(self):
        """Test template HTML rendering"""
        engine = TemplateEngine()

        config = TemplateConfig(
            id="render-template",
            name="Render Template",
            components=[ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Test Header")],
            data_sources=[],
        )

        engine.create_template(config)

        context = RenderContext(data={}, render_mode="html")

        result = engine.render_template("render-template", context)

        assert result.success
        assert result.html_content is not None
        assert "Test Header" in result.html_content
        assert result.css_content is not None

    def test_template_engine_render_json(self):
        """Test template JSON rendering"""
        engine = TemplateEngine()

        config = TemplateConfig(
            id="json-template",
            name="JSON Template",
            components=[ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Test Header")],
            data_sources=[],
        )

        engine.create_template(config)

        context = RenderContext(data={}, render_mode="json")

        result = engine.render_template("json-template", context)

        assert result.success
        assert result.json_structure is not None
        assert result.json_structure["template"]["id"] == "json-template"
        assert len(result.json_structure["components"]) == 1

    def test_template_engine_clone(self):
        """Test template cloning"""
        engine = TemplateEngine()

        # Clone existing template
        cloned_id = engine.clone_template("basic_report", "Cloned Basic Report")

        assert cloned_id != "basic_report"

        cloned_template = engine.get_template(cloned_id)
        assert cloned_template is not None
        assert cloned_template.name == "Cloned Basic Report"
        assert "Copy of" in cloned_template.description


class TestPreviewEngine:
    """Test preview engine functionality"""

    @pytest.mark.asyncio
    async def test_preview_engine_creation(self):
        """Test creating preview engine"""
        engine = PreviewEngine()

        assert engine.template_engine is not None
        assert len(engine.device_presets) > 0
        assert "desktop" in engine.device_presets
        assert "mobile" in engine.device_presets

    @pytest.mark.asyncio
    async def test_preview_generation(self):
        """Test preview generation"""
        engine = PreviewEngine()

        options = PreviewOptions(
            viewport_width=1200, viewport_height=800, device_type="desktop", format="html", enable_edit_mode=True
        )

        result = await engine.generate_preview("basic_report", options)

        assert result.success
        assert result.html_content is not None
        assert result.css_content is not None
        assert result.viewport_width == 1200
        assert result.viewport_height == 800
        assert result.device_type == "desktop"

    @pytest.mark.asyncio
    async def test_preview_caching(self):
        """Test preview caching"""
        engine = PreviewEngine()

        options = PreviewOptions(
            viewport_width=1200, viewport_height=800, cache_enabled=True, cache_duration_seconds=60
        )

        # First generation
        result1 = await engine.generate_preview("basic_report", options)
        assert result1.success
        assert not result1.cache_hit

        # Second generation should hit cache
        result2 = await engine.generate_preview("basic_report", options)
        assert result2.success
        assert result2.cache_hit

    @pytest.mark.asyncio
    async def test_preview_mobile_generation(self):
        """Test mobile preview generation"""
        engine = PreviewEngine()

        options = PreviewOptions(device_type="mobile", format="html", enable_edit_mode=False)

        result = await engine.generate_preview("basic_report", options)

        assert result.success
        assert result.device_type == "mobile"
        assert result.viewport_width == 375  # Mobile width
        assert "preview-mobile" in result.html_content

    def test_preview_device_presets(self):
        """Test device presets"""
        engine = PreviewEngine()
        presets = engine.get_device_presets()

        assert "desktop" in presets
        assert "mobile" in presets
        assert "tablet" in presets
        assert presets["desktop"]["width"] == 1200
        assert presets["mobile"]["width"] == 375

    def test_preview_cache_stats(self):
        """Test cache statistics"""
        engine = PreviewEngine()
        stats = engine.get_cache_stats()

        assert "total_entries" in stats
        assert "active_entries" in stats
        assert "total_hits" in stats
        assert "hit_rate" in stats


class TestValidationEngine:
    """Test validation engine functionality"""

    def test_validation_engine_creation(self):
        """Test creating validation engine"""
        engine = ValidationEngine()

        assert len(engine.rules) > 0
        assert any(rule.name == "required_fields" for rule in engine.rules)
        assert any(rule.name == "data_source_validation" for rule in engine.rules)

    def test_template_validation_success(self):
        """Test successful template validation"""
        engine = ValidationEngine()

        config = TemplateConfig(
            id="valid-template",
            name="Valid Template",
            description="A valid template",
            components=[ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Valid Header")],
            data_sources=[],
        )

        result = engine.validate_template(config)

        assert result.is_valid
        assert result.score > 80
        assert len(result.errors) == 0

    def test_template_validation_errors(self):
        """Test template validation with errors"""
        engine = ValidationEngine()

        config = TemplateConfig(
            id="invalid-template",
            name="Invalid Template",
            components=[ComponentConfig(id="", type=ComponentType.HEADER, title="")],  # Missing ID  # Missing title
            data_sources=[],
        )

        result = engine.validate_template(config)

        assert not result.is_valid
        assert result.score < 100
        assert len(result.errors) > 0

    def test_component_validation(self):
        """Test component validation"""
        engine = ValidationEngine()

        # Valid component
        valid_config = ComponentConfig(id="valid-header", type=ComponentType.HEADER, title="Valid Header")

        result = engine.validate_component(valid_config)

        assert result.is_valid
        assert result.score > 80

        # Invalid component
        invalid_config = ComponentConfig(id="", type=ComponentType.HEADER, title="")  # Missing ID  # Missing title

        result = engine.validate_component(invalid_config)

        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validation_report(self):
        """Test validation report generation"""
        engine = ValidationEngine()

        config = TemplateConfig(
            id="report-template",
            name="Report Template",
            components=[ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Test Header")],
            data_sources=[],
        )

        report = engine.get_validation_report(config)

        assert "summary" in report
        assert "category_scores" in report
        assert "issues_by_category" in report
        assert "recommendations" in report
        assert isinstance(report["summary"]["is_valid"], bool)
        assert isinstance(report["summary"]["overall_score"], float)


class TestDesignerCore:
    """Test designer core functionality"""

    def test_designer_creation(self):
        """Test creating designer"""
        config = DesignerConfig(auto_save=False, component_validation=True)  # Disable for testing

        designer = ReportDesigner(config)

        assert designer.config.component_validation
        assert not designer.config.auto_save

    def test_designer_session_creation(self):
        """Test creating designer session"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user", template_id="basic_report")

        assert session.user_id == "test-user"
        assert session.template_id == "basic_report"
        assert session.is_active
        assert not session.unsaved_changes
        assert session.current_template is not None

    def test_designer_template_creation(self):
        """Test creating template through designer"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")

        result = designer.create_template(session_id=session.id, template_name="New Template")

        assert result.success
        assert result.template_id is not None
        assert "New Template" in result.message

    def test_designer_add_component(self):
        """Test adding component through designer"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Test Template")

        component_config = ComponentConfig(id="test-header", type=ComponentType.HEADER, title="Test Header")

        result = designer.add_component(session_id=session.id, component_config=component_config)

        assert result.success
        assert "Test Header" in result.message

    def test_designer_update_component(self):
        """Test updating component through designer"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Test Template")

        component_config = ComponentConfig(id="test-header", type=ComponentType.HEADER, title="Test Header")

        designer.add_component(session_id=session.id, component_config=component_config)

        result = designer.update_component(
            session_id=session.id, component_id="test-header", updates={"title": "Updated Header"}
        )

        assert result.success
        assert "Updated Header" in result.message

    def test_designer_remove_component(self):
        """Test removing component through designer"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Test Template")

        component_config = ComponentConfig(id="test-header", type=ComponentType.HEADER, title="Test Header")

        designer.add_component(session_id=session.id, component_config=component_config)

        result = designer.remove_component(session_id=session.id, component_id="test-header")

        assert result.success
        assert "removed successfully" in result.message

    def test_designer_validation(self):
        """Test template validation through designer"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Test Template")

        result = designer.validate_template(session_id=session.id)

        assert result.success
        assert result.validation_data is not None

    def test_designer_save_template(self):
        """Test saving template through designer"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Test Template")

        result = designer.save_template(session_id=session.id)

        assert result.success
        assert "saved successfully" in result.message

    def test_designer_history(self):
        """Test template history tracking"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Test Template")

        history = designer.get_template_history(session_id=session.id)

        assert len(history) >= 1
        assert history[0]["action"] == "create_template"

    def test_designer_session_management(self):
        """Test session management"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        session = designer.create_session(user_id="test-user")
        session_id = session.id

        # Session should exist
        retrieved_session = designer.get_session(session_id)
        assert retrieved_session is not None
        assert retrieved_session.id == session_id

        # Close session
        success = designer.close_session(session_id)
        assert success

        # Session should no longer exist
        retrieved_session = designer.get_session(session_id)
        assert retrieved_session is None


class TestDesignerIntegration:
    """Test integration between designer components"""

    def test_full_workflow(self):
        """Test complete designer workflow"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))

        # Create session
        session = designer.create_session(user_id="test-user")

        # Create template
        template_result = designer.create_template(session_id=session.id, template_name="Integration Test Template")
        assert template_result.success

        # Add header component
        header_config = ComponentConfig(
            id="header-1",
            type=ComponentType.HEADER,
            title="Integration Test Header",
            custom_props={"subtitle": "Test Subtitle"},
        )

        add_result = designer.add_component(session_id=session.id, component_config=header_config)
        assert add_result.success

        # Add table component
        table_config = ComponentConfig(
            id="table-1",
            type=ComponentType.TABLE,
            title="Integration Test Table",
            data_source="test_data",
            custom_props={"columns": ["Name", "Value", "Status"]},
        )

        add_result = designer.add_component(session_id=session.id, component_config=table_config)
        assert add_result.success

        # Validate template
        validation_result = designer.validate_template(session_id=session.id)
        assert validation_result.success

        # Generate preview
        preview_result = designer.generate_preview(session_id=session.id)
        assert preview_result.success
        assert preview_result.preview_data is not None

        # Save template
        save_result = designer.save_template(session_id=session.id)
        assert save_result.success

        # Check history
        history = designer.get_template_history(session_id=session.id)
        assert len(history) >= 4  # create, add, add, save

    @pytest.mark.asyncio
    async def test_preview_integration(self):
        """Test preview integration with template engine"""
        designer = ReportDesigner(DesignerConfig(auto_save=False))
        preview_engine_instance = PreviewEngine()

        # Create session with template
        session = designer.create_session(user_id="test-user")
        designer.create_template(session_id=session.id, template_name="Preview Test")

        # Add components
        header_config = ComponentConfig(id="header-1", type=ComponentType.HEADER, title="Preview Test Header")
        designer.add_component(session_id=session.id, component_config=header_config)

        # Generate preview through engine
        options = PreviewOptions(device_type="desktop", enable_edit_mode=True)

        result = await preview_engine_instance.generate_preview(session.current_template.id, options)

        assert result.success
        assert result.html_content is not None
        assert "Preview Test Header" in result.html_content
        assert result.edit_mode_data is not None
        assert result.component_metadata is not None


if __name__ == "__main__":
    pytest.main([__file__])
