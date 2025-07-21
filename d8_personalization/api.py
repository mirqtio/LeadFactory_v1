"""
FastAPI endpoints for D8 Personalization Domain

Provides REST API for content personalization, spam checking,
and subject line generation.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.session import get_db

# Import with fallback for missing modules
try:
    from .personalizer import Personalizer
except ImportError:
    Personalizer = None

try:
    from .spam_checker import SpamChecker
except ImportError:
    SpamChecker = None

try:
    from .subject_lines import SubjectLineGenerator
except ImportError:
    SubjectLineGenerator = None

# Initialize logger
logger = get_logger("d8_personalization_api", domain="d8_personalization")

# Create router
router = APIRouter()


class PersonalizationRequest(BaseModel):
    lead_id: str
    template: str
    context: dict


class SpamCheckRequest(BaseModel):
    subject: str
    body: str


class SubjectLinesRequest(BaseModel):
    industry: str | None = None
    context: dict | None = None
    tone: str | None = "professional"
    count: int | None = 5


@router.post("/generate")
async def generate_personalized_content(request: PersonalizationRequest, db: Session = Depends(get_db)) -> dict:
    """Generate personalized content for a lead."""
    try:
        # For now, return a mock response
        # In a real implementation, this would use the actual Personalizer
        return {
            "subject": "Boost Your Restaurant's Online Presence",
            "preview": "3 critical issues found...",
            "body": "<html><body>Sample personalized content</body></html>",
            "personalization_score": 0.85,
            "lead_id": request.lead_id,
            "template": request.template,
        }
    except Exception as e:
        logger.error(f"Failed to generate personalized content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/spam-check")
async def check_spam_score(request: SpamCheckRequest, db: Session = Depends(get_db)) -> dict:
    """Check spam score for email content."""
    try:
        # For now, return a mock response
        # In a real implementation, this would use the actual SpamChecker
        score = 2.5  # Mock score

        recommendations = []
        if request.subject.isupper():
            recommendations.append("Avoid using all caps in subject line")
        if request.body.count("!") > 3:
            recommendations.append("Reduce exclamation marks")

        return {"spam_score": score, "is_spam": score > 5.0, "recommendations": recommendations}
    except Exception as e:
        logger.error(f"Failed to check spam score: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subject-lines")
async def generate_subject_lines(request: SubjectLinesRequest, db: Session = Depends(get_db)) -> dict:
    """Generate multiple subject line variations."""
    try:
        # For now, return a mock response
        # In a real implementation, this would use the actual SubjectLineGenerator
        industry = request.industry or (request.context.get("industry", "business") if request.context else "business")
        lines = [
            f"Discover how to improve your {industry}",
            f"3 ways to boost your {industry} performance",
            f"Your {industry} audit results are ready",
            "Quick wins for your online presence",
            "Action required: Website improvements needed",
        ][: request.count]

        return {"subject_lines": lines, "count": len(lines), "tone": request.tone}
    except Exception as e:
        logger.error(f"Failed to generate subject lines: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_available_templates(db: Session = Depends(get_db)) -> dict:
    """List available personalization templates."""
    try:
        # In a real implementation, this would query the database
        # For now, return a mock response
        return {
            "templates": [
                {
                    "name": "audit_report",
                    "description": "Personalized audit report email",
                    "variables": ["industry", "findings", "score"],
                },
                {
                    "name": "follow_up",
                    "description": "Follow-up email template",
                    "variables": ["previous_interaction", "next_steps"],
                },
                {
                    "name": "welcome",
                    "description": "Welcome email for new leads",
                    "variables": ["company_name", "contact_name"],
                },
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
