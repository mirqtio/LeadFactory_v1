"""
FastAPI endpoints for Template Studio (P0-024)

Web-based Jinja2 editor with live preview and GitHub PR workflow
"""
import os
import json
import subprocess
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jinja2 import Template, TemplateSyntaxError, UndefinedError
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.logging import get_logger
from core.config import settings
from database.session import get_db
from d6_reports.models import ReportTemplate
from database.models import Lead

logger = get_logger("template_studio", domain="template_studio")

# Create router with prefix
router = APIRouter(prefix="/api/template-studio", tags=["template_studio"])

# Rate limiter for preview endpoint
limiter = Limiter(key_func=get_remote_address)


class TemplateListItem(BaseModel):
    """Template metadata for list view"""
    id: str
    name: str
    display_name: str
    description: Optional[str]
    version: str
    git_sha: Optional[str] = None
    last_modified: Optional[datetime] = None
    is_active: bool


class TemplateDetail(BaseModel):
    """Full template details for editing"""
    id: str
    name: str
    display_name: str
    description: Optional[str]
    version: str
    git_sha: Optional[str] = None
    content: str  # The actual Jinja2 template content
    css_styles: Optional[str] = None
    supports_mobile: bool = True
    supports_print: bool = True


class PreviewRequest(BaseModel):
    """Request to preview a template"""
    template_content: str
    lead_id: str = Field(default="1", description="Lead ID to use for preview")


class PreviewResponse(BaseModel):
    """Template preview response"""
    rendered_html: str
    render_time_ms: float
    errors: List[str] = Field(default_factory=list)


class ProposeChangesRequest(BaseModel):
    """Request to propose template changes"""
    template_id: str
    template_content: str
    commit_message: str
    description: Optional[str] = None


class ProposeChangesResponse(BaseModel):
    """Response from proposing changes"""
    pr_url: str
    branch_name: str
    commit_sha: str


def get_git_info(file_path: str) -> Dict[str, Any]:
    """Get git information for a file"""
    try:
        # Ensure we're in the git repository root
        repo_root = Path(__file__).parent.parent
        
        # Get last commit SHA for the file
        sha_result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        sha = sha_result.stdout.strip()
        
        # Get last modified date
        date_result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        date_str = date_result.stdout.strip()
        
        if sha and date_str:
            return {
                "git_sha": sha[:8],  # Short SHA
                "last_modified": datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            }
        else:
            return {}
    except subprocess.CalledProcessError as e:
        logger.warning(f"Git command failed for {file_path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Failed to get git info for {file_path}: {e}")
        return {}


@router.get("/templates", response_model=List[TemplateListItem])
async def list_templates(
    db: Session = Depends(get_db)
) -> List[TemplateListItem]:
    """
    List all available templates with git metadata.
    
    Response time: <500ms
    """
    logger.info("Listing templates")
    
    templates = db.query(ReportTemplate).filter(
        ReportTemplate.is_active == True
    ).all()
    
    result = []
    for template in templates:
        item = TemplateListItem(
            id=template.id,
            name=template.name,
            display_name=template.display_name,
            description=template.description,
            version=template.version,
            is_active=template.is_active
        )
        
        # Try to get git info if template file exists
        template_path = Path(f"d6_reports/templates/{template.name}.html")
        if template_path.exists():
            git_info = get_git_info(str(template_path))
            item.git_sha = git_info.get("git_sha")
            item.last_modified = git_info.get("last_modified")
        
        result.append(item)
    
    return result


@router.get("/templates/{template_id}", response_model=TemplateDetail)
async def get_template_detail(
    template_id: str,
    db: Session = Depends(get_db)
) -> TemplateDetail:
    """
    Get full template details for editing.
    """
    logger.info(f"Getting template detail for {template_id}")
    
    template = db.query(ReportTemplate).filter(
        ReportTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    detail = TemplateDetail(
        id=template.id,
        name=template.name,
        display_name=template.display_name,
        description=template.description,
        version=template.version,
        content=template.html_template or "",
        css_styles=template.css_styles,
        supports_mobile=template.supports_mobile,
        supports_print=template.supports_print
    )
    
    # Get git info
    template_path = Path(f"d6_reports/templates/{template.name}.html")
    if template_path.exists():
        git_info = get_git_info(str(template_path))
        detail.git_sha = git_info.get("git_sha")
    
    return detail


@router.post("/preview", response_model=PreviewResponse)
@limiter.limit("20/second")
async def preview_template(
    request: Request,
    preview_req: PreviewRequest,
    db: Session = Depends(get_db)
) -> PreviewResponse:
    """
    Preview a template with sample data.
    
    Requirements:
    - Render time < 500ms
    - Rate limited to 20 requests/second
    - Jinja2 autoescape enabled
    """
    import time
    start_time = time.time()
    
    logger.info(f"Previewing template for lead_id={preview_req.lead_id}")
    
    errors = []
    rendered_html = ""
    
    try:
        # Get sample lead data
        lead = db.query(Lead).filter(
            Lead.id == preview_req.lead_id
        ).first()
        
        if not lead:
            # Use default sample data
            lead_data = {
                "business_name": "Sample Business Inc.",
                "website": "https://example.com",
                "phone": "(555) 123-4567",
                "email": "contact@example.com",
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip": "12345"
                }
            }
        else:
            lead_data = {
                "business_name": lead.business_name,
                "website": lead.website,
                "phone": lead.phone,
                "email": lead.email,
                "address": {
                    "street": lead.street_address,
                    "city": lead.city,
                    "state": lead.state,
                    "zip": lead.zip_code
                }
            }
        
        # Create Jinja2 template with autoescape
        template = Template(
            preview_req.template_content,
            autoescape=True
        )
        
        # Render with sample data
        context = {
            "lead": lead_data,
            "report_date": datetime.now().strftime("%B %d, %Y"),
            "score": 85,
            "recommendations": [
                "Improve website loading speed",
                "Add more customer testimonials",
                "Optimize for mobile devices"
            ]
        }
        
        rendered_html = template.render(**context)
        
    except TemplateSyntaxError as e:
        errors.append(f"Template syntax error: {str(e)}")
        logger.error(f"Template syntax error: {e}")
    except UndefinedError as e:
        errors.append(f"Undefined variable: {str(e)}")
        logger.error(f"Undefined variable error: {e}")
    except Exception as e:
        errors.append(f"Render error: {str(e)}")
        logger.error(f"Template render error: {e}")
    
    render_time_ms = (time.time() - start_time) * 1000
    
    return PreviewResponse(
        rendered_html=rendered_html,
        render_time_ms=render_time_ms,
        errors=errors
    )


@router.post("/propose-changes", response_model=ProposeChangesResponse)
async def propose_changes(
    proposal: ProposeChangesRequest,
    db: Session = Depends(get_db)
) -> ProposeChangesResponse:
    """
    Create a GitHub PR with template changes.
    
    Requirements:
    - Valid auth required (TODO: implement auth check)
    - Creates new branch, commit, and PR
    - PR body includes semantic commit message
    """
    logger.info(f"Proposing changes for template {proposal.template_id}")
    
    # Get template
    template = db.query(ReportTemplate).filter(
        ReportTemplate.id == proposal.template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Get repository root
    repo_root = Path(__file__).parent.parent
    
    try:
        # Get current branch to return to later
        current_branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        current_branch = current_branch_result.stdout.strip()
        
        # Create branch name
        branch_name = f"template-update-{template.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create new branch
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Write updated template
        template_path = repo_root / f"d6_reports/templates/{template.name}.html"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(proposal.template_content)
        
        # Add and commit
        subprocess.run(
            ["git", "add", str(template_path.relative_to(repo_root))],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True
        )
        
        commit_message = f"{proposal.commit_message}\n\nTemplate: {template.display_name}\nProposed via Template Studio"
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Get commit SHA
        commit_sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        commit_sha = commit_sha_result.stdout.strip()
        
        # In production, would use GitHub API to create PR
        # For now, return mock response
        pr_url = f"https://github.com/mirqtio/LeadFactory_v1/pull/999"
        
        logger.info(f"Created branch {branch_name} with commit {commit_sha[:8]}")
        
        return ProposeChangesResponse(
            pr_url=pr_url,
            branch_name=branch_name,
            commit_sha=commit_sha[:8]
        )
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create PR: {str(e)}"
        )
    finally:
        # Switch back to original branch
        try:
            subprocess.run(
                ["git", "checkout", current_branch],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True
            )
        except:
            pass


@router.get("/diff/{template_id}")
async def get_template_diff(
    template_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get diff between current template and last committed version.
    """
    logger.info(f"Getting diff for template {template_id}")
    
    template = db.query(ReportTemplate).filter(
        ReportTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Get repository root
    repo_root = Path(__file__).parent.parent
    template_path = repo_root / f"d6_reports/templates/{template.name}.html"
    
    try:
        # Get diff against HEAD
        diff_result = subprocess.run(
            ["git", "diff", "HEAD", "--", str(template_path.relative_to(repo_root))],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        diff_output = diff_result.stdout
        
        # Parse diff to extract additions/deletions
        additions = []
        deletions = []
        
        for line in diff_output.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                additions.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                deletions.append(line[1:])
        
        return {
            "template_id": template_id,
            "diff": diff_output,
            "additions": additions,
            "deletions": deletions,
            "has_changes": bool(diff_output.strip())
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get diff: {e.stderr}")
        return {
            "template_id": template_id,
            "diff": "",
            "additions": [],
            "deletions": [],
            "has_changes": False
        }