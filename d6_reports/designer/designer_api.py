"""
Designer API - P2-040 Dynamic Report Designer

REST API endpoints for the dynamic report designer. Provides comprehensive
API for template management, component operations, real-time preview, and
export functionality.

Features:
- Template CRUD operations
- Component management
- Real-time preview generation
- Validation and error handling
- Export capabilities
- Session management
"""

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from account_management.models import AccountUser
from core.auth import get_current_user_dependency, require_organization_access
from core.logging import get_logger

from .component_library import ComponentConfig, ComponentType, component_library
from .designer_core import DesignerResult, DesignerSession, report_designer
from .preview_engine import PreviewOptions, preview_engine
from .template_engine import template_engine

logger = get_logger("designer_api", domain="d6_reports")

# Create router
router = APIRouter()


# Pydantic models for API


class CreateTemplateRequest(BaseModel):
    """Request to create a new template"""

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: str | None = Field(None, max_length=500, description="Template description")
    template_id: str | None = Field(None, description="Custom template ID")
    base_template: str | None = Field(None, description="Base template to clone from")


class AddComponentRequest(BaseModel):
    """Request to add a component to template"""

    component_type: ComponentType = Field(..., description="Component type")
    title: str = Field(..., min_length=1, max_length=100, description="Component title")
    description: str | None = Field(None, max_length=200, description="Component description")
    position: int = Field(default=-1, description="Position in template (-1 for end)")

    # Layout properties
    width: int | str | None = Field("100%", description="Component width")
    height: int | str | None = Field("auto", description="Component height")
    margin: str | None = Field("0", description="Component margin")
    padding: str | None = Field("0", description="Component padding")

    # Data properties
    data_source: str | None = Field(None, description="Data source identifier")
    data_filters: dict[str, Any] | None = Field(None, description="Data filters")

    # Custom properties
    custom_props: dict[str, Any] | None = Field(None, description="Custom properties")


class UpdateComponentRequest(BaseModel):
    """Request to update a component"""

    title: str | None = Field(None, min_length=1, max_length=100, description="Component title")
    description: str | None = Field(None, max_length=200, description="Component description")

    # Layout properties
    width: int | str | None = Field(None, description="Component width")
    height: int | str | None = Field(None, description="Component height")
    margin: str | None = Field(None, description="Component margin")
    padding: str | None = Field(None, description="Component padding")

    # Styling properties
    background_color: str | None = Field(None, description="Background color")
    border: str | None = Field(None, description="Border style")
    border_radius: str | None = Field(None, description="Border radius")

    # Data properties
    data_source: str | None = Field(None, description="Data source identifier")
    data_filters: dict[str, Any] | None = Field(None, description="Data filters")

    # Custom properties
    custom_props: dict[str, Any] | None = Field(None, description="Custom properties")


class PreviewRequest(BaseModel):
    """Request to generate preview"""

    # Viewport settings
    viewport_width: int | None = Field(None, ge=320, le=3840, description="Viewport width")
    viewport_height: int | None = Field(None, ge=240, le=2160, description="Viewport height")
    device_type: str | None = Field(None, description="Device type")

    # Content settings
    sample_data: dict[str, Any] | None = Field(None, description="Sample data")
    format: str | None = Field(None, description="Preview format")

    # Edit mode settings
    enable_edit_mode: bool | None = Field(None, description="Enable edit mode")
    show_component_bounds: bool | None = Field(None, description="Show component bounds")
    show_grid: bool | None = Field(None, description="Show grid")


class TemplateResponse(BaseModel):
    """Response containing template data"""

    id: str
    name: str
    description: str | None = None
    version: str
    component_count: int
    data_sources: list[str]
    created_at: str | None = None
    updated_at: str | None = None
    created_by: str | None = None
    tags: list[str]


class ComponentResponse(BaseModel):
    """Response containing component data"""

    id: str
    type: str
    title: str
    description: str | None = None
    width: int | str | None = None
    height: int | str | None = None
    data_source: str | None = None
    custom_props: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    """Response containing session data"""

    session_id: str
    user_id: str | None = None
    template_id: str | None = None
    started_at: str
    last_activity: str
    is_active: bool
    unsaved_changes: bool
    template_name: str | None = None


# Helper functions


def get_designer_session(session_id: str, user_id: str = None) -> DesignerSession:
    """Get designer session with validation"""
    session = report_designer.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if user_id and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Session access denied")

    return session


def handle_designer_result(result: DesignerResult) -> dict[str, Any]:
    """Handle designer operation result"""
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={"message": "Operation failed", "errors": result.errors, "warnings": result.warnings},
        )

    return {
        "success": True,
        "message": result.message,
        "data": result.template_data or result.component_data or result.preview_data or {},
        "warnings": result.warnings,
        "execution_time_ms": result.execution_time_ms,
    }


# API Endpoints


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    template_id: str | None = Query(None, description="Template ID to load"),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """Create a new designer session"""
    logger.info(f"Creating designer session for user {current_user.email}")

    try:
        session = report_designer.create_session(user_id=current_user.id, template_id=template_id)

        return SessionResponse(
            session_id=session.id,
            user_id=session.user_id,
            template_id=session.template_id,
            started_at=session.started_at.isoformat(),
            last_activity=session.last_activity.isoformat(),
            is_active=session.is_active,
            unsaved_changes=session.unsaved_changes,
            template_name=session.current_template.name if session.current_template else None,
        )

    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Get designer session"""
    session = get_designer_session(session_id, current_user.id)

    return SessionResponse(
        session_id=session.id,
        user_id=session.user_id,
        template_id=session.template_id,
        started_at=session.started_at.isoformat(),
        last_activity=session.last_activity.isoformat(),
        is_active=session.is_active,
        unsaved_changes=session.unsaved_changes,
        template_name=session.current_template.name if session.current_template else None,
    )


@router.delete("/sessions/{session_id}")
async def close_session(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Close designer session"""
    session = get_designer_session(session_id, current_user.id)

    success = report_designer.close_session(session_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to close session")

    return {"message": "Session closed successfully"}


@router.post("/sessions/{session_id}/templates")
async def create_template(
    request: CreateTemplateRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Create a new template"""
    session = get_designer_session(session_id, current_user.id)

    result = report_designer.create_template(
        session_id=session_id, template_name=request.name, template_id=request.template_id
    )

    return handle_designer_result(result)


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(current_user: AccountUser = Depends(get_current_user_dependency)):
    """List available templates"""
    templates = template_engine.list_templates()

    return [
        TemplateResponse(
            id=template["id"],
            name=template["name"],
            description=template["description"],
            version=template["version"],
            component_count=template["component_count"],
            data_sources=template["data_sources"],
            created_at=template["created_at"],
            updated_at=template["updated_at"],
            tags=template["tags"],
        )
        for template in templates
    ]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str = Path(..., description="Template ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Get template details"""
    template = template_engine.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        version=template.version,
        component_count=len(template.components),
        data_sources=template.data_sources,
        created_at=template.created_at.isoformat() if template.created_at else None,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
        created_by=template.created_by,
        tags=template.tags,
    )


@router.post("/sessions/{session_id}/components")
async def add_component(
    request: AddComponentRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Add component to template"""
    session = get_designer_session(session_id, current_user.id)

    # Create component configuration
    component_config = ComponentConfig(
        id=f"comp_{uuid.uuid4().hex[:8]}",
        type=request.component_type,
        title=request.title,
        description=request.description,
        width=request.width,
        height=request.height,
        margin=request.margin,
        padding=request.padding,
        data_source=request.data_source,
        data_filters=request.data_filters,
        custom_props=request.custom_props,
    )

    result = report_designer.add_component(
        session_id=session_id, component_config=component_config, position=request.position
    )

    return handle_designer_result(result)


@router.put("/sessions/{session_id}/components/{component_id}")
async def update_component(
    request: UpdateComponentRequest,
    session_id: str = Path(..., description="Session ID"),
    component_id: str = Path(..., description="Component ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Update component in template"""
    session = get_designer_session(session_id, current_user.id)

    # Build updates dictionary
    updates = {}
    for field, value in request.dict(exclude_none=True).items():
        updates[field] = value

    result = report_designer.update_component(session_id=session_id, component_id=component_id, updates=updates)

    return handle_designer_result(result)


@router.delete("/sessions/{session_id}/components/{component_id}")
async def remove_component(
    session_id: str = Path(..., description="Session ID"),
    component_id: str = Path(..., description="Component ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Remove component from template"""
    session = get_designer_session(session_id, current_user.id)

    result = report_designer.remove_component(session_id=session_id, component_id=component_id)

    return handle_designer_result(result)


@router.get("/sessions/{session_id}/components", response_model=list[ComponentResponse])
async def list_components(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """List components in template"""
    session = get_designer_session(session_id, current_user.id)

    if not session.current_template:
        return []

    components = []
    for component in session.current_template.components:
        components.append(
            ComponentResponse(
                id=component.id,
                type=component.type.value,
                title=component.title,
                description=component.description,
                width=component.width,
                height=component.height,
                data_source=component.data_source,
                custom_props=component.custom_props,
            )
        )

    return components


@router.get("/component-library")
async def get_component_library(current_user: AccountUser = Depends(get_current_user_dependency)):
    """Get available component types"""
    return {"components": component_library.get_available_components()}


@router.post("/sessions/{session_id}/preview")
async def generate_preview(
    request: PreviewRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Generate template preview"""
    session = get_designer_session(session_id, current_user.id)

    if not session.current_template:
        raise HTTPException(status_code=400, detail="No template loaded")

    # Create preview options
    preview_options = PreviewOptions()

    # Update with request values
    if request.viewport_width is not None:
        preview_options.viewport_width = request.viewport_width
    if request.viewport_height is not None:
        preview_options.viewport_height = request.viewport_height
    if request.device_type is not None:
        preview_options.device_type = request.device_type
    if request.format is not None:
        preview_options.format = request.format
    if request.enable_edit_mode is not None:
        preview_options.enable_edit_mode = request.enable_edit_mode
    if request.show_component_bounds is not None:
        preview_options.show_component_bounds = request.show_component_bounds
    if request.show_grid is not None:
        preview_options.show_grid = request.show_grid
    if request.sample_data is not None:
        preview_options.sample_data = request.sample_data

    try:
        result = await preview_engine.generate_preview(session.current_template.id, preview_options)

        return {
            "success": result.success,
            "preview_id": result.preview_id,
            "html_content": result.html_content,
            "css_content": result.css_content,
            "javascript_content": result.javascript_content,
            "render_time_ms": result.render_time_ms,
            "cache_hit": result.cache_hit,
            "viewport_width": result.viewport_width,
            "viewport_height": result.viewport_height,
            "device_type": result.device_type,
            "edit_mode_data": result.edit_mode_data,
            "component_metadata": result.component_metadata,
            "errors": [result.error_message] if result.error_message else [],
            "warnings": result.warnings,
        }

    except Exception as e:
        logger.error(f"Preview generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")


@router.post("/sessions/{session_id}/validate")
async def validate_template(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Validate template"""
    session = get_designer_session(session_id, current_user.id)

    result = report_designer.validate_template(session_id)

    return handle_designer_result(result)


@router.post("/sessions/{session_id}/save")
async def save_template(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Save template"""
    session = get_designer_session(session_id, current_user.id)

    result = report_designer.save_template(session_id)

    return handle_designer_result(result)


@router.get("/sessions/{session_id}/history")
async def get_template_history(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Get template change history"""
    session = get_designer_session(session_id, current_user.id)

    history = report_designer.get_template_history(session_id)

    return {"history": history}


@router.post("/templates/{template_id}/clone")
async def clone_template(
    template_id: str = Path(..., description="Template ID"),
    new_name: str = Query(..., description="New template name"),
    new_id: str | None = Query(None, description="New template ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Clone a template"""
    try:
        cloned_id = template_engine.clone_template(template_id, new_name, new_id)

        return {"success": True, "message": "Template cloned successfully", "template_id": cloned_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Template cloning failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Template cloning failed: {str(e)}")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str = Path(..., description="Template ID"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Delete a template"""
    success = template_engine.delete_template(template_id)

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"message": "Template deleted successfully"}


@router.get("/devices")
async def get_device_presets(current_user: AccountUser = Depends(get_current_user_dependency)):
    """Get device presets for preview"""
    return {"devices": preview_engine.get_device_presets()}


@router.post("/sessions/{session_id}/export")
async def export_template(
    session_id: str = Path(..., description="Session ID"),
    format: str = Query(..., description="Export format (html, pdf, json)"),
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """Export template"""
    session = get_designer_session(session_id, current_user.id)

    if not session.current_template:
        raise HTTPException(status_code=400, detail="No template loaded")

    # Generate export content
    result = report_designer.generate_preview(session_id)

    if not result.success:
        raise HTTPException(status_code=400, detail="Export generation failed")

    # Return appropriate response based on format
    if format == "html":
        return Response(
            content=result.preview_data["html_content"],
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{session.current_template.name}.html"'},
        )
    if format == "json":
        return Response(
            content=json.dumps(result.preview_data["json_structure"], indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{session.current_template.name}.json"'},
        )
    raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(report_designer.sessions),
        "cache_stats": preview_engine.get_cache_stats(),
    }
