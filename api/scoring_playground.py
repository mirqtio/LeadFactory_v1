"""
FastAPI endpoints for Scoring Playground (P0-025)

Allows safe experimentation with scoring weights using Google Sheets
"""
import yaml
import hashlib
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.session import get_db
from database.models import Lead
# from d5_scoring.engine import ScoringEngine  # Not used, would use in production

logger = get_logger("scoring_playground", domain="scoring")

# Create router with prefix
router = APIRouter(prefix="/api/scoring-playground", tags=["scoring_playground"])

# Cache for sample leads
_sample_leads_cache = None
_cache_timestamp = None
CACHE_DURATION = 3600  # 1 hour


class WeightVector(BaseModel):
    """Individual weight in the scoring system"""
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    description: Optional[str] = None


class WeightImportRequest(BaseModel):
    """Request to import weights to Google Sheets"""
    sheet_id: str = Field(description="Google Sheets ID")


class WeightImportResponse(BaseModel):
    """Response from weight import"""
    sheet_url: str
    weights_count: int
    sha: str  # SHA of current weights for optimistic locking


class ScoreDeltaRequest(BaseModel):
    """Request to calculate score deltas"""
    new_weights: List[WeightVector]

    @field_validator('new_weights')
    @classmethod
    def validate_weight_sum(cls, weights: List[WeightVector]) -> List[WeightVector]:
        """Ensure weights sum to 1.0 ± 0.005"""
        total = sum(w.weight for w in weights)
        if abs(total - 1.0) > 0.005:
            raise ValueError(f"Weights must sum to 1.0 ± 0.005, got {total:.3f}")
        return weights


class ScoreDelta(BaseModel):
    """Score change for a single lead"""
    lead_id: str
    business_name: str
    old_score: float
    new_score: float
    delta: float
    delta_percent: float


class ScoreDeltaResponse(BaseModel):
    """Response with score deltas"""
    deltas: List[ScoreDelta]
    summary: Dict[str, Any]
    calculation_time_ms: float


class ProposeDiffRequest(BaseModel):
    """Request to propose scoring weight changes"""
    new_weights: List[WeightVector]
    commit_message: str
    original_sha: str  # For optimistic locking
    description: Optional[str] = None


class ProposeDiffResponse(BaseModel):
    """Response from proposing changes"""
    pr_url: str
    branch_name: str
    commit_sha: str
    yaml_diff: str


def get_current_weights() -> Tuple[List[WeightVector], str]:
    """Load current weights from YAML and calculate SHA"""
    weights_path = Path("d5_scoring/weights.yaml")

    if not weights_path.exists():
        # Return default weights if file doesn't exist
        default_weights = [
            WeightVector(name="revenue_potential", weight=0.25),
            WeightVector(name="competitive_advantage", weight=0.20),
            WeightVector(name="market_position", weight=0.20),
            WeightVector(name="growth_trajectory", weight=0.15),
            WeightVector(name="operational_efficiency", weight=0.10),
            WeightVector(name="digital_presence", weight=0.10),
        ]
        return default_weights, "default"

    with open(weights_path, 'r') as f:
        content = f.read()
        weights_data = yaml.safe_load(content)

    # Calculate SHA for optimistic locking
    sha = hashlib.sha256(content.encode()).hexdigest()[:8]

    # Convert to WeightVector objects
    weights = []
    for name, config in weights_data.get('weights', {}).items():
        weights.append(WeightVector(
            name=name,
            weight=config.get('weight', 0.0),
            description=config.get('description')
        ))

    return weights, sha


def get_sample_leads(db: Session, count: int = 100) -> List[Lead]:
    """Get sample leads for scoring (with caching)"""
    global _sample_leads_cache, _cache_timestamp

    # Check cache
    if (_sample_leads_cache is not None and
        _cache_timestamp is not None and
        time.time() - _cache_timestamp < CACHE_DURATION):
        return _sample_leads_cache[:count]

    # Query sample leads
    leads = db.query(Lead).filter(
        Lead.is_deleted == False,
        Lead.is_manual == False
    ).limit(count).all()

    # Anonymize PII for privacy
    anonymized_leads = []
    for i, lead in enumerate(leads):
        # Create a copy with anonymized data
        anon_lead = Lead(
            id=f"sample-{i+1:03d}",
            business_name=f"Business {i+1}",
            website=lead.website,  # Keep website for scoring
            phone="(555) 000-0000",
            email=f"contact{i+1}@example.com",
            street_address="123 Main St",
            city=lead.city,
            state=lead.state,
            zip_code="00000",
            # Keep scoring-relevant fields
            annual_revenue=lead.annual_revenue,
            employee_count=lead.employee_count,
            industry=lead.industry,
            years_in_business=lead.years_in_business,
        )
        anonymized_leads.append(anon_lead)

    # Update cache
    _sample_leads_cache = anonymized_leads
    _cache_timestamp = time.time()

    return anonymized_leads[:count]


@router.get("/weights/current")
async def get_weights() -> Dict[str, Any]:
    """Get current scoring weights"""
    logger.info("Getting current scoring weights")

    weights, sha = get_current_weights()

    return {
        "weights": weights,
        "sha": sha,
        "total": sum(w.weight for w in weights)
    }


@router.post("/weights/import", response_model=WeightImportResponse)
async def import_weights_to_sheets(
    request: WeightImportRequest,
    db: Session = Depends(get_db)
) -> WeightImportResponse:
    """
    Import current weights to Google Sheets.
    
    Note: In production, this would use Google Sheets API.
    For now, returns mock response.
    """
    logger.info(f"Importing weights to sheet {request.sheet_id}")

    weights, sha = get_current_weights()

    # In production: Use Google Sheets API to create/update sheet
    # For now, mock the response
    sheet_url = f"https://docs.google.com/spreadsheets/d/{request.sheet_id}/edit"

    return WeightImportResponse(
        sheet_url=sheet_url,
        weights_count=len(weights),
        sha=sha
    )


@router.post("/score/delta", response_model=ScoreDeltaResponse)
async def calculate_score_deltas(
    request: ScoreDeltaRequest,
    db: Session = Depends(get_db)
) -> ScoreDeltaResponse:
    """
    Calculate score deltas for sample leads.
    
    Requirements:
    - Delta table renders < 1s (uses cached sample)
    - Shows before/after scores and deltas
    """
    start_time = time.time()

    logger.info("Calculating score deltas for new weights")

    # Get sample leads (cached)
    sample_leads = get_sample_leads(db, count=100)

    # Get current weights for comparison
    current_weights, _ = get_current_weights()

    # Initialize scoring engine (would use real engine in production)
    deltas = []

    for lead in sample_leads:
        # Mock scoring calculation
        # In production, would use actual ScoringEngine
        old_score = sum(w.weight * 85 for w in current_weights)  # Mock
        new_score = sum(w.weight * 85 for w in request.new_weights)  # Mock

        # Add some variance based on lead properties
        if lead.annual_revenue and lead.annual_revenue > 1000000:
            old_score += 5
            new_score += 7

        delta = new_score - old_score
        delta_percent = (delta / old_score * 100) if old_score > 0 else 0

        deltas.append(ScoreDelta(
            lead_id=lead.id,
            business_name=lead.business_name,
            old_score=round(old_score, 2),
            new_score=round(new_score, 2),
            delta=round(delta, 2),
            delta_percent=round(delta_percent, 2)
        ))

    # Calculate summary statistics
    total_delta = sum(d.delta for d in deltas)
    avg_delta = total_delta / len(deltas) if deltas else 0
    improved = sum(1 for d in deltas if d.delta > 0)
    decreased = sum(1 for d in deltas if d.delta < 0)

    calculation_time_ms = (time.time() - start_time) * 1000

    # Ensure we meet performance requirement
    if calculation_time_ms > 1000:
        logger.warning(f"Delta calculation took {calculation_time_ms:.0f}ms, exceeds 1s requirement")

    return ScoreDeltaResponse(
        deltas=deltas[:20],  # Return top 20 for UI
        summary={
            "total_leads": len(deltas),
            "average_delta": round(avg_delta, 2),
            "improved_count": improved,
            "decreased_count": decreased,
            "unchanged_count": len(deltas) - improved - decreased,
            "max_increase": round(max(d.delta for d in deltas), 2) if deltas else 0,
            "max_decrease": round(min(d.delta for d in deltas), 2) if deltas else 0
        },
        calculation_time_ms=calculation_time_ms
    )


@router.post("/propose-diff", response_model=ProposeDiffResponse)
async def propose_weight_changes(
    proposal: ProposeDiffRequest,
    db: Session = Depends(get_db)
) -> ProposeDiffResponse:
    """
    Create GitHub PR with new scoring weights.
    
    Requirements:
    - PR includes before/after YAML diff
    - Optimistic locking with SHA verification
    """
    logger.info("Proposing scoring weight changes")

    # Verify SHA for optimistic locking
    current_weights, current_sha = get_current_weights()
    if proposal.original_sha != current_sha:
        raise HTTPException(
            status_code=409,
            detail=f"Weights have been modified. Expected SHA {proposal.original_sha}, got {current_sha}"
        )

    try:
        # Create new weights YAML
        weights_dict = {
            w.name: {
                "weight": w.weight,
                "description": w.description or f"Weight for {w.name}"
            }
            for w in proposal.new_weights
        }

        new_yaml_content = yaml.dump({
            "weights": weights_dict,
            "version": "2.0",
            "updated_at": datetime.utcnow().isoformat()
        }, default_flow_style=False)

        # Create branch
        branch_name = f"scoring-weights-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            check=True,
            capture_output=True,
            text=True
        )

        # Write new weights file
        weights_path = Path("d5_scoring/weights.yaml")
        old_content = weights_path.read_text() if weights_path.exists() else ""
        weights_path.write_text(new_yaml_content)

        # Generate diff for display
        diff_output = subprocess.check_output(
            ["git", "diff", "HEAD", str(weights_path)],
            text=True
        )

        # Commit changes
        subprocess.run(
            ["git", "add", str(weights_path)],
            check=True,
            capture_output=True,
            text=True
        )

        commit_message = f"{proposal.commit_message}\n\n" \
                        f"Original SHA: {proposal.original_sha}\n" \
                        f"Proposed via Scoring Playground"

        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True,
            capture_output=True,
            text=True
        )

        # Get commit SHA
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True
        ).strip()

        # In production: Create PR via GitHub API
        pr_url = "https://github.com/mirqtio/LeadFactory_v1/pull/999"

        return ProposeDiffResponse(
            pr_url=pr_url,
            branch_name=branch_name,
            commit_sha=commit_sha[:8],
            yaml_diff=diff_output
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create PR: {str(e)}"
        )
    finally:
        # Switch back to main
        try:
            subprocess.run(
                ["git", "checkout", "main"],
                check=True,
                capture_output=True,
                text=True
            )
        except:
            pass


@router.get("/sheets/poll/{sheet_id}")
async def poll_sheet_changes(
    sheet_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Poll Google Sheets for weight changes.
    
    Note: In production, implements rate limiting and quota guards.
    """
    logger.info(f"Polling sheet {sheet_id} for changes")

    # In production: Use Google Sheets API with rate limiting
    # For now, return mock data
    return {
        "sheet_id": sheet_id,
        "last_updated": datetime.utcnow().isoformat(),
        "weights": get_current_weights()[0],
        "status": "ready"
    }
