"""
Report Designer Core - P2-040 Dynamic Report Designer

Core orchestration for the dynamic report designer system. Manages template creation,
component composition, validation, and rendering workflows.

Features:
- Template creation and management
- Component drag-and-drop coordination
- Real-time preview generation
- Template validation and error handling
- Export to multiple formats
- Integration with existing report generation system
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .component_library import ComponentConfig, ComponentLibrary, ComponentType, component_library
from .template_engine import RenderContext, TemplateConfig, TemplateEngine, TemplateResult, template_engine
from .validation_engine import ValidationEngine, ValidationResult, validation_engine


class DesignerConfig(BaseModel):
    """Configuration for report designer"""

    # Template settings
    default_template: str = Field(default="basic_report", description="Default template to use")
    auto_save: bool = Field(default=True, description="Auto-save templates")
    auto_save_interval: int = Field(default=30, description="Auto-save interval in seconds")

    # Component settings
    allow_custom_components: bool = Field(default=True, description="Allow custom component creation")
    component_validation: bool = Field(default=True, description="Validate components on add")

    # Preview settings
    preview_mode: str = Field(default="html", description="Default preview mode")
    preview_auto_refresh: bool = Field(default=True, description="Auto-refresh preview")
    preview_debounce_ms: int = Field(default=500, description="Preview debounce delay")

    # Export settings
    export_formats: List[str] = Field(default=["html", "pdf", "json"], description="Available export formats")

    # Integration settings
    data_source_validation: bool = Field(default=True, description="Validate data sources")
    batch_generation: bool = Field(default=True, description="Enable batch generation")


class DesignerResult(BaseModel):
    """Result of designer operations"""

    success: bool
    template_id: Optional[str] = None
    operation: str = Field(..., description="Operation performed")
    message: Optional[str] = None
    errors: List[str] = Field(default=[])
    warnings: List[str] = Field(default=[])

    # Operation-specific data
    template_data: Optional[Dict[str, Any]] = None
    component_data: Optional[Dict[str, Any]] = None
    preview_data: Optional[Dict[str, Any]] = None
    validation_data: Optional[Dict[str, Any]] = None

    # Performance metrics
    execution_time_ms: int = 0
    memory_usage_mb: Optional[float] = None


@dataclass
class DesignerSession:
    """Designer session state"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    template_id: Optional[str] = None

    # Session state
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    # Design state
    current_template: Optional[TemplateConfig] = None
    unsaved_changes: bool = False
    change_history: List[Dict[str, Any]] = field(default_factory=list)

    # UI state
    selected_component: Optional[str] = None
    preview_mode: str = "html"
    zoom_level: float = 1.0

    # Configuration
    config: DesignerConfig = field(default_factory=DesignerConfig)


class ReportDesigner:
    """Main report designer orchestration class"""

    def __init__(self, config: DesignerConfig = None):
        self.config = config or DesignerConfig()
        self.template_engine = template_engine
        self.component_library = component_library
        self.validation_engine = validation_engine

        # Active sessions
        self.sessions: Dict[str, DesignerSession] = {}

        # Auto-save task
        self._auto_save_task: Optional[asyncio.Task] = None
        # Note: Auto-save will be started when first session is created

    def _start_auto_save(self):
        """Start auto-save background task"""
        if self.config.auto_save and (self._auto_save_task is None or self._auto_save_task.done()):
            try:
                self._auto_save_task = asyncio.create_task(self._auto_save_loop())
            except RuntimeError:
                # No event loop running, will start when needed
                pass

    async def _auto_save_loop(self):
        """Auto-save loop for active sessions"""
        while True:
            try:
                await asyncio.sleep(self.config.auto_save_interval)

                for session in self.sessions.values():
                    if session.is_active and session.unsaved_changes:
                        await self._auto_save_session(session)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                print(f"Auto-save error: {e}")

    async def _auto_save_session(self, session: DesignerSession):
        """Auto-save a session"""
        if session.current_template:
            try:
                # Save template
                self.template_engine.templates[session.current_template.id] = session.current_template
                session.unsaved_changes = False

                # Add to change history
                session.change_history.append(
                    {
                        "action": "auto_save",
                        "timestamp": datetime.utcnow().isoformat(),
                        "template_id": session.current_template.id,
                    }
                )

            except Exception as e:
                print(f"Auto-save failed for session {session.id}: {e}")

    def create_session(self, user_id: str = None, template_id: str = None) -> DesignerSession:
        """Create a new designer session"""
        session = DesignerSession(user_id=user_id, template_id=template_id, config=self.config)

        # Load template if specified
        if template_id:
            template = self.template_engine.get_template(template_id)
            if template:
                session.current_template = template
                session.template_id = template_id

        # Store session
        self.sessions[session.id] = session

        # Start auto-save if this is the first session
        if len(self.sessions) == 1:
            self._start_auto_save()

        return session

    def get_session(self, session_id: str) -> Optional[DesignerSession]:
        """Get designer session by ID"""
        return self.sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close a designer session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.is_active = False

            # Save if needed
            if session.unsaved_changes and session.current_template:
                self.template_engine.templates[session.current_template.id] = session.current_template

            del self.sessions[session_id]
            return True

        return False

    def create_template(self, session_id: str, template_name: str, template_id: str = None) -> DesignerResult:
        """Create a new template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="create_template", errors=["Session not found"])

        try:
            # Generate template ID if not provided
            if not template_id:
                template_id = f"template_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"

            # Create template config
            template_config = TemplateConfig(
                id=template_id,
                name=template_name,
                description=f"Template created on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                created_by=session.user_id,
                components=[],
                data_sources=[],
            )

            # Validate template
            validation_errors = self.template_engine.validate_template(template_config)
            if validation_errors:
                return DesignerResult(success=False, operation="create_template", errors=validation_errors)

            # Create template
            created_id = self.template_engine.create_template(template_config)

            # Update session
            session.current_template = template_config
            session.template_id = created_id
            session.unsaved_changes = False
            session.last_activity = datetime.utcnow()

            # Add to change history
            session.change_history.append(
                {
                    "action": "create_template",
                    "timestamp": datetime.utcnow().isoformat(),
                    "template_id": created_id,
                    "template_name": template_name,
                }
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=True,
                template_id=created_id,
                operation="create_template",
                message=f"Template '{template_name}' created successfully",
                template_data=template_config.dict(),
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="create_template", errors=[f"Failed to create template: {str(e)}"]
            )

    def add_component(self, session_id: str, component_config: ComponentConfig, position: int = -1) -> DesignerResult:
        """Add a component to the current template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="add_component", errors=["Session not found"])

        if not session.current_template:
            return DesignerResult(success=False, operation="add_component", errors=["No active template"])

        try:
            # Validate component if enabled
            if self.config.component_validation:
                validation_errors = self.component_library.validate_component_config(component_config)
                if validation_errors:
                    return DesignerResult(success=False, operation="add_component", errors=validation_errors)

            # Add component to template
            if position == -1:
                session.current_template.components.append(component_config)
            else:
                session.current_template.components.insert(position, component_config)

            # Update data sources
            if (
                component_config.data_source
                and component_config.data_source not in session.current_template.data_sources
            ):
                session.current_template.data_sources.append(component_config.data_source)

            # Update session
            session.unsaved_changes = True
            session.last_activity = datetime.utcnow()

            # Add to change history
            session.change_history.append(
                {
                    "action": "add_component",
                    "timestamp": datetime.utcnow().isoformat(),
                    "component_id": component_config.id,
                    "component_type": component_config.type.value,
                    "position": position,
                }
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=True,
                template_id=session.template_id,
                operation="add_component",
                message=f"Component '{component_config.title}' added successfully",
                component_data=component_config.dict(),
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="add_component", errors=[f"Failed to add component: {str(e)}"]
            )

    def remove_component(self, session_id: str, component_id: str) -> DesignerResult:
        """Remove a component from the current template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="remove_component", errors=["Session not found"])

        if not session.current_template:
            return DesignerResult(success=False, operation="remove_component", errors=["No active template"])

        try:
            # Find and remove component
            component_removed = None
            for i, component in enumerate(session.current_template.components):
                if component.id == component_id:
                    component_removed = session.current_template.components.pop(i)
                    break

            if not component_removed:
                return DesignerResult(
                    success=False, operation="remove_component", errors=[f"Component not found: {component_id}"]
                )

            # Update session
            session.unsaved_changes = True
            session.last_activity = datetime.utcnow()

            # Add to change history
            session.change_history.append(
                {
                    "action": "remove_component",
                    "timestamp": datetime.utcnow().isoformat(),
                    "component_id": component_id,
                    "component_type": component_removed.type.value,
                }
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=True,
                template_id=session.template_id,
                operation="remove_component",
                message=f"Component '{component_removed.title}' removed successfully",
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="remove_component", errors=[f"Failed to remove component: {str(e)}"]
            )

    def update_component(self, session_id: str, component_id: str, updates: Dict[str, Any]) -> DesignerResult:
        """Update a component in the current template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="update_component", errors=["Session not found"])

        if not session.current_template:
            return DesignerResult(success=False, operation="update_component", errors=["No active template"])

        try:
            # Find component
            component = None
            for comp in session.current_template.components:
                if comp.id == component_id:
                    component = comp
                    break

            if not component:
                return DesignerResult(
                    success=False, operation="update_component", errors=[f"Component not found: {component_id}"]
                )

            # Apply updates
            for key, value in updates.items():
                if hasattr(component, key):
                    setattr(component, key, value)
                elif key == "custom_props":
                    if component.custom_props:
                        component.custom_props.update(value)
                    else:
                        component.custom_props = value

            # Validate component if enabled
            if self.config.component_validation:
                validation_errors = self.component_library.validate_component_config(component)
                if validation_errors:
                    return DesignerResult(success=False, operation="update_component", errors=validation_errors)

            # Update session
            session.unsaved_changes = True
            session.last_activity = datetime.utcnow()

            # Add to change history
            session.change_history.append(
                {
                    "action": "update_component",
                    "timestamp": datetime.utcnow().isoformat(),
                    "component_id": component_id,
                    "updates": updates,
                }
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=True,
                template_id=session.template_id,
                operation="update_component",
                message=f"Component '{component.title}' updated successfully",
                component_data=component.dict(),
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="update_component", errors=[f"Failed to update component: {str(e)}"]
            )

    def generate_preview(self, session_id: str, preview_data: Dict[str, Any] = None) -> DesignerResult:
        """Generate preview of current template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="generate_preview", errors=["Session not found"])

        if not session.current_template:
            return DesignerResult(success=False, operation="generate_preview", errors=["No active template"])

        try:
            # Create render context
            render_context = RenderContext(
                data=preview_data or {}, render_mode=session.preview_mode, include_debug=True
            )

            # Render template
            result = self.template_engine.render_template(session.current_template.id, render_context)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=result.success,
                template_id=session.template_id,
                operation="generate_preview",
                message="Preview generated successfully" if result.success else "Preview generation failed",
                errors=[result.error_message] if result.error_message else [],
                warnings=result.warnings,
                preview_data={
                    "html_content": result.html_content,
                    "css_content": result.css_content,
                    "json_structure": result.json_structure,
                    "render_time_ms": result.render_time_ms,
                    "component_count": result.component_count,
                },
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="generate_preview", errors=[f"Failed to generate preview: {str(e)}"]
            )

    def validate_template(self, session_id: str) -> DesignerResult:
        """Validate current template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="validate_template", errors=["Session not found"])

        if not session.current_template:
            return DesignerResult(success=False, operation="validate_template", errors=["No active template"])

        try:
            # Validate template
            validation_result = self.validation_engine.validate_template(session.current_template)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=validation_result.is_valid,
                template_id=session.template_id,
                operation="validate_template",
                message="Template validation completed",
                errors=validation_result.errors,
                warnings=validation_result.warnings,
                validation_data=validation_result.dict(),
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="validate_template", errors=[f"Failed to validate template: {str(e)}"]
            )

    def save_template(self, session_id: str) -> DesignerResult:
        """Save current template"""
        start_time = datetime.utcnow()

        session = self.get_session(session_id)
        if not session:
            return DesignerResult(success=False, operation="save_template", errors=["Session not found"])

        if not session.current_template:
            return DesignerResult(success=False, operation="save_template", errors=["No active template"])

        try:
            # Update template metadata
            session.current_template.updated_at = datetime.utcnow()

            # Save template
            self.template_engine.templates[session.current_template.id] = session.current_template

            # Update session
            session.unsaved_changes = False
            session.last_activity = datetime.utcnow()

            # Add to change history
            session.change_history.append(
                {
                    "action": "save_template",
                    "timestamp": datetime.utcnow().isoformat(),
                    "template_id": session.current_template.id,
                }
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DesignerResult(
                success=True,
                template_id=session.template_id,
                operation="save_template",
                message="Template saved successfully",
                execution_time_ms=int(execution_time),
            )

        except Exception as e:
            return DesignerResult(
                success=False, operation="save_template", errors=[f"Failed to save template: {str(e)}"]
            )

    def list_available_components(self) -> List[Dict[str, Any]]:
        """List available components for the designer"""
        return self.component_library.get_available_components()

    def get_template_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get template change history"""
        session = self.get_session(session_id)
        if not session:
            return []

        return session.change_history.copy()

    def shutdown(self):
        """Shutdown the designer"""
        if self._auto_save_task:
            self._auto_save_task.cancel()

        # Save all active sessions
        for session in self.sessions.values():
            if session.unsaved_changes and session.current_template:
                self.template_engine.templates[session.current_template.id] = session.current_template


# Global designer instance
report_designer = ReportDesigner()
