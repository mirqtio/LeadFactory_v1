"""
Template Studio API endpoints
"""

import asyncio
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from d6_reports.template_manager import TemplateManager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/template-studio", tags=["template-studio"])


# Pydantic models
class TemplateInfo(BaseModel):
    """Template information model"""
    name: str
    path: str
    size: int
    modified: str
    git: Dict[str, str]
    checksum: str


class TemplateContent(BaseModel):
    """Template content model"""
    name: str
    content: str


class ValidationResult(BaseModel):
    """Template validation result"""
    valid: bool
    variables: List[str]
    errors: List[str]


class PreviewRequest(BaseModel):
    """Preview request model"""
    template_name: str
    sample_data: Optional[Dict[str, Any]] = None


class PreviewResponse(BaseModel):
    """Preview response model"""
    success: bool
    content: Optional[str]
    error: Optional[str]


class PRRequest(BaseModel):
    """Pull request creation request"""
    changes: Dict[str, str] = Field(..., description="Template name to content mapping")
    user: str = Field(..., description="Username making changes")
    commit_message: str = Field(..., description="Commit message")


class PRResponse(BaseModel):
    """Pull request creation response"""
    success: bool
    error: Optional[str]
    pr_url: Optional[str]
    pr_number: Optional[int] = None


# Dependencies
def get_template_manager() -> TemplateManager:
    """Get template manager instance"""
    return TemplateManager()


def check_admin_access(user_role: Optional[str] = None) -> bool:
    """
    Check if user has admin access
    
    For now, returns True. In production, implement proper auth.
    """
    # TODO: Implement proper role-based access control
    return True


def check_viewer_access(user_role: Optional[str] = None) -> bool:
    """
    Check if user has at least viewer access
    
    For now, returns True. In production, implement proper auth.
    """
    # TODO: Implement proper role-based access control
    return True


# API Endpoints
@router.get("/templates", response_model=List[TemplateInfo])
async def list_templates(
    has_access: bool = Depends(check_viewer_access),
    manager: TemplateManager = Depends(get_template_manager),
):
    """
    List all templates with git metadata
    
    Returns list of templates with SHA, last modified, and author info.
    """
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        templates = manager.list_templates()
        return templates
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/templates/{template_name:path}", response_model=TemplateContent)
async def get_template(
    template_name: str,
    has_access: bool = Depends(check_viewer_access),
    manager: TemplateManager = Depends(get_template_manager),
):
    """
    Get template content
    
    Returns the content of a specific template.
    """
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    content = manager.get_template_content(template_name)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return TemplateContent(name=template_name, content=content)


@router.post("/validate", response_model=ValidationResult)
async def validate_template(
    content: str,
    has_access: bool = Depends(check_viewer_access),
    manager: TemplateManager = Depends(get_template_manager),
):
    """
    Validate a Jinja2 template
    
    Returns validation result with variables and any errors.
    """
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = manager.validate_template(content)
    return ValidationResult(**result)


@router.post("/preview", response_model=PreviewResponse)
async def preview_template(
    request: PreviewRequest,
    has_access: bool = Depends(check_viewer_access),
    manager: TemplateManager = Depends(get_template_manager),
):
    """
    Preview a template with sample data
    
    Renders template with lead_id=1 sample data by default.
    Must complete in < 500ms.
    """
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Use provided sample data or default
    sample_data = request.sample_data or manager.get_sample_lead_data(lead_id=1)
    
    # Render with timeout
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                manager.render_preview,
                request.template_name,
                sample_data
            ),
            timeout=0.5  # 500ms timeout
        )
        return PreviewResponse(**result)
    except asyncio.TimeoutError:
        return PreviewResponse(
            success=False,
            content=None,
            error="Preview rendering timed out (>500ms)"
        )


@router.post("/create-pr", response_model=PRResponse)
async def create_pull_request(
    request: PRRequest,
    has_admin: bool = Depends(check_admin_access),
    manager: TemplateManager = Depends(get_template_manager),
):
    """
    Create a GitHub PR with template changes
    
    Only admins can propose changes. Creates a PR with semantic commit message.
    """
    if not has_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate all templates first
    for template_name, content in request.changes.items():
        validation = manager.validate_template(content)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid template {template_name}: {validation['errors']}"
            )
    
    # Create PR
    result = manager.create_template_pr(
        changes=request.changes,
        user=request.user,
        commit_message=request.commit_message
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return PRResponse(**result)


@router.get("/sample-data/{lead_id}")
async def get_sample_data(
    lead_id: int = 1,
    has_access: bool = Depends(check_viewer_access),
    manager: TemplateManager = Depends(get_template_manager),
):
    """
    Get sample lead data for preview
    
    Returns sample data for the specified lead ID.
    """
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return manager.get_sample_lead_data(lead_id)


# WebSocket for real-time preview
@router.websocket("/ws/preview")
async def websocket_preview(websocket: WebSocket):
    """
    WebSocket endpoint for real-time template preview
    
    Receives template content and returns rendered preview.
    """
    await websocket.accept()
    manager = TemplateManager()
    
    try:
        while True:
            # Receive data
            data = await websocket.receive_json()
            
            template_name = data.get("template_name")
            content = data.get("content")
            sample_data = data.get("sample_data")
            
            if not template_name or not content:
                await websocket.send_json({
                    "error": "Missing template_name or content"
                })
                continue
            
            # Validate template
            validation = manager.validate_template(content)
            if not validation["valid"]:
                await websocket.send_json({
                    "error": f"Invalid template: {validation['errors']}"
                })
                continue
            
            # Create temporary template for preview
            env = manager.create_safe_environment()
            
            try:
                # Render preview
                template = env.from_string(content)
                sample_data = sample_data or manager.get_sample_lead_data(lead_id=1)
                rendered = template.render(**sample_data)
                
                await websocket.send_json({
                    "success": True,
                    "content": rendered,
                    "variables": validation["variables"],
                })
            except Exception as e:
                await websocket.send_json({
                    "error": f"Render error: {str(e)}"
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


# Serve Template Studio UI
@router.get("/", response_class=HTMLResponse)
async def template_studio_ui():
    """
    Serve the Template Studio web interface
    """
    # In production, this would serve the actual UI
    # For now, return a placeholder
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LeadFactory Template Studio</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Template Studio</h1>
            <p>Web-based Jinja2 template editor with live preview</p>
            <p>Full UI implementation would go here with Monaco editor integration.</p>
        </div>
    </body>
    </html>
    """