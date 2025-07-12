# PRP: Scoring Playground

## Task ID: P0-025
## Wave: 2

## Business Logic (Why This Matters)
CPO must tweak YAML weights safely and preview cohort impact before merge. The scoring weights directly control how leads are prioritized and evaluated, making them critical business logic that needs frequent iteration. Without a safe environment to test changes, the CPO risks breaking production scoring or making changes blindly without understanding their impact on lead distribution and prioritization.

## Overview
The Scoring Playground provides a safe, interactive environment for the CPO to experiment with scoring weight configurations. It bridges Google Sheets (for easy editing) with the production YAML format, allowing real-time preview of how weight changes affect lead scoring across a sample cohort. The system imports current weights into a Google Sheet, allows editing, re-scores a sample set of leads with the new weights, shows a delta comparison, and creates a GitHub PR with the updated configuration - all without touching production until the PR is reviewed and merged.

## Dependencies
- P0-023 Lineage Panel (for sample cohort query)
- Google Sheets API creds (read-only)
- Existing `config/scoring_rules.yaml` file
- `scripts/sheet_to_yaml.py` (already exists for Sheet→YAML conversion)
- GitHub API token (for PR creation)

**Note**: Depends on P0-023 Lineage Panel completing successfully to provide sample lead cohorts for testing.

## Outcome-Focused Acceptance Criteria
- "Import weights" copies YAML → Sheet named `weights_preview`
- CPO edits Sheet; "Re-score sample 100" shows delta table
- "Create PR" writes updated YAML and opens GitHub PR
- Coverage ≥ 80% on scoring_playground tests
- No production scoring affected until PR merged
- Tests: pytest tests/cpo_console/scoring_playground -xvs

### Task-Specific Acceptance Criteria
- [ ] "Import weights" button copies current YAML to Google Sheet
- [ ] Sheet preserves all component and factor structures
- [ ] "Re-score sample 100" button triggers rescoring with preview weights
- [ ] Delta table shows: lead_id, old_score, new_score, delta, old_tier, new_tier
- [ ] Weight validation ensures components sum to 1.0 (±0.005)
- [ ] "Create PR" generates valid YAML and opens GitHub PR
- [ ] PR description includes impact summary (leads moved between tiers)
- [ ] Coverage ≥ 80% on scoring_playground tests

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression from current baseline
- [ ] Only modify files within specified integration points (no scope creep)
- [ ] Validate YAML syntax before PR creation
- [ ] Preserve comments from original YAML file

## Integration Points
- src/cpo_console/scoring_playground/
- config/scoring_rules.yaml (read-only until PR)
- scripts/sheet_to_yaml.py (reuse existing converter)
- d5_scoring/scoring_engine.py (for re-scoring logic)
- tests/cpo_console/scoring_playground/

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
- pytest tests/cpo_console/scoring_playground -xvs
- pytest tests/unit/d5_scoring/test_scoring_engine.py (must remain green)
- pytest tests/test_scoring_rules_schema.py (validate YAML structure)

## Example File/Pattern

### API Routes (src/cpo_console/scoring_playground/api.py)
```python
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import tempfile
import yaml
import time
from pathlib import Path

from core.auth import get_current_user, require_role
from d5_scoring.scoring_engine import ScoringEngine
from database.models import Lead, ScoringResult
from .sheets_client import SheetsClient
from .github_client import GitHubClient
from .yaml_generator import generate_yaml_with_comments
from .schemas import (
    WeightImportResponse,
    RescoringRequest,
    RescoringResponse,
    PRCreationRequest,
    PRCreationResponse
)

router = APIRouter(prefix="/api/scoring-playground", tags=["scoring-playground"])

@router.post("/import-weights", response_model=WeightImportResponse)
async def import_weights_to_sheet(
    current_user=Depends(get_current_user)
):
    """Import current YAML weights to Google Sheet for editing."""
    require_role(current_user, ["admin", "cpo"])
    
    # Read current weights
    weights_path = Path("config/scoring_rules.yaml")
    with open(weights_path) as f:
        current_weights = yaml.safe_load(f)
    
    # Create/update Google Sheet
    sheets_client = SheetsClient()
    sheet_url = await sheets_client.create_weights_sheet(
        weights_data=current_weights,
        sheet_name="weights_preview"
    )
    
    return WeightImportResponse(
        sheet_url=sheet_url,
        components_count=len(current_weights.get("components", {})),
        version=current_weights.get("version", "1.0")
    )

@router.post("/rescore-sample", response_model=RescoringResponse)
async def rescore_sample_cohort(
    request: RescoringRequest,
    current_user=Depends(get_current_user)
):
    """Re-score sample leads with preview weights from Sheet."""
    require_role(current_user, ["admin", "cpo"])
    
    # Fetch weights from Sheet
    sheets_client = SheetsClient()
    preview_weights = await sheets_client.read_weights_from_sheet(
        sheet_id=request.sheet_id
    )
    
    # Validate weights sum to 1.0
    total_weight = sum(
        comp["weight"] for comp in preview_weights["components"].values()
    )
    if abs(total_weight - 1.0) > 0.005:
        raise HTTPException(
            status_code=400,
            detail=f"Component weights must sum to 1.0 (current: {total_weight})"
        )
    
    # Get sample cohort (last 100 scored leads by default)
    sample_leads = await Lead.get_sample_cohort(
        limit=request.sample_size or 100,
        filter_criteria=request.filter_criteria
    )
    
    # Score with current weights
    current_engine = ScoringEngine()
    current_scores = [
        current_engine.score_lead(lead) for lead in sample_leads
    ]
    
    # Score with preview weights
    preview_engine = ScoringEngine(weights_override=preview_weights)
    preview_scores = [
        preview_engine.score_lead(lead) for lead in sample_leads
    ]
    
    # Calculate deltas
    deltas = []
    tier_movements = {"up": 0, "down": 0, "same": 0}
    
    for lead, current, preview in zip(sample_leads, current_scores, preview_scores):
        delta = preview.total_score - current.total_score
        
        # Determine tier movement
        current_tier = current_engine.get_tier(current.total_score)
        preview_tier = preview_engine.get_tier(preview.total_score)
        
        if preview_tier < current_tier:  # A < B < C < D
            tier_movements["up"] += 1
        elif preview_tier > current_tier:
            tier_movements["down"] += 1
        else:
            tier_movements["same"] += 1
        
        deltas.append({
            "lead_id": lead.id,
            "business_name": lead.business_name,
            "old_score": round(current.total_score, 2),
            "new_score": round(preview.total_score, 2),
            "delta": round(delta, 2),
            "old_tier": current_tier,
            "new_tier": preview_tier
        })
    
    return RescoringResponse(
        sample_size=len(sample_leads),
        deltas=deltas,
        tier_movements=tier_movements,
        preview_weights_valid=True
    )

@router.post("/create-pr", response_model=PRCreationResponse)
async def create_weights_pr(
    request: PRCreationRequest,
    current_user=Depends(get_current_user)
):
    """Create GitHub PR with updated weights from Sheet."""
    require_role(current_user, ["admin", "cpo"])
    
    # Fetch weights from Sheet
    sheets_client = SheetsClient()
    new_weights = await sheets_client.read_weights_from_sheet(
        sheet_id=request.sheet_id
    )
    
    # Validate weights
    total_weight = sum(
        comp["weight"] for comp in new_weights["components"].values()
    )
    if abs(total_weight - 1.0) > 0.005:
        raise HTTPException(
            status_code=400,
            detail=f"Component weights must sum to 1.0 (current: {total_weight})"
        )
    
    # Generate YAML with preserved comments
    yaml_content = generate_yaml_with_comments(new_weights)
    
    # Create PR
    github_client = GitHubClient()
    pr_url = await github_client.create_weights_pr(
        yaml_content=yaml_content,
        description=request.pr_description or "Update scoring weights",
        impact_summary=request.impact_summary
    )
    
    return PRCreationResponse(
        pr_url=pr_url,
        branch_name=f"scoring-weights-{current_user.id}-{int(time.time())}",
        yaml_valid=True
    )
```

### Sheets Client (src/cpo_console/scoring_playground/sheets_client.py)
```python
import os
import json
from typing import Dict, Any, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi import HTTPException

class SheetsClient:
    """Client for Google Sheets operations."""
    
    def __init__(self):
        """Initialize with service account credentials."""
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS not set")
        
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=creds)
    
    async def create_weights_sheet(
        self,
        weights_data: Dict[str, Any],
        sheet_name: str
    ) -> str:
        """Create or update Google Sheet with weights data.
        
        Args:
            weights_data: Dictionary containing scoring weights configuration
            sheet_name: Name for the Google Sheet
            
        Returns:
            str: URL of the created/updated sheet
        """
        try:
            # Create new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': f'{sheet_name} - {weights_data.get("version", "1.0")}'
                }
            }
            spreadsheet = self.service.spreadsheets().create(
                body=spreadsheet, 
                fields='spreadsheetId'
            ).execute()
            sheet_id = spreadsheet.get('spreadsheetId')
            
            # Prepare data for sheet
            values = [
                ['Component', 'Weight', 'Description'],
                ['', '', ''],  # Empty row for clarity
            ]
            
            # Add component weights
            for comp_name, comp_data in weights_data.get('components', {}).items():
                values.append([
                    comp_name,
                    comp_data.get('weight', 0.0),
                    comp_data.get('description', '')
                ])
            
            # Add factor details in separate section
            values.extend([
                ['', '', ''],  # Empty row
                ['Factor Details', '', ''],
                ['Component', 'Factor', 'Weight', 'Max Score'],
            ])
            
            for comp_name, comp_data in weights_data.get('components', {}).items():
                for factor_name, factor_data in comp_data.get('factors', {}).items():
                    values.append([
                        comp_name,
                        factor_name,
                        factor_data.get('weight', 0.0),
                        factor_data.get('max_score', 100)
                    ])
            
            # Write to sheet
            body = {'values': values}
            self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Format sheet
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': 0,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                                'textFormat': {'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}, 'bold': True}
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body=body
            ).execute()
            
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            
        except HttpError as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create sheet: {error}"
            )
    
    async def read_weights_from_sheet(
        self,
        sheet_id: str
    ) -> Dict[str, Any]:
        """Read weights configuration from Google Sheet.
        
        Args:
            sheet_id: Google Sheet ID to read from
            
        Returns:
            Dict containing parsed weights configuration
        """
        try:
            # Read all values from sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range='A1:D100'  # Read sufficient rows
            ).execute()
            
            values = result.get('values', [])
            if not values:
                raise ValueError("Sheet is empty")
            
            # Parse component weights
            weights_config = {
                'version': '1.0',
                'components': {}
            }
            
            # Find component section
            in_components = False
            in_factors = False
            
            for row in values:
                if not row:
                    continue
                    
                if row[0] == 'Component' and len(row) >= 3 and row[1] == 'Weight':
                    in_components = True
                    in_factors = False
                    continue
                elif row[0] == 'Factor Details':
                    in_components = False
                    in_factors = False
                    continue
                elif row[0] == 'Component' and len(row) >= 4 and row[1] == 'Factor':
                    in_components = False
                    in_factors = True
                    continue
                
                if in_components and row[0] and row[0] != '':
                    # Parse component weight
                    comp_name = row[0]
                    weight = float(row[1]) if len(row) > 1 and row[1] else 0.0
                    description = row[2] if len(row) > 2 else ''
                    
                    weights_config['components'][comp_name] = {
                        'weight': weight,
                        'description': description,
                        'factors': {}
                    }
                
                elif in_factors and len(row) >= 4 and row[0] and row[1]:
                    # Parse factor details
                    comp_name = row[0]
                    factor_name = row[1]
                    factor_weight = float(row[2]) if row[2] else 0.0
                    max_score = int(row[3]) if row[3] else 100
                    
                    if comp_name in weights_config['components']:
                        weights_config['components'][comp_name]['factors'][factor_name] = {
                            'weight': factor_weight,
                            'max_score': max_score
                        }
            
            return weights_config
            
        except HttpError as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read sheet: {error}"
            )
        except (ValueError, IndexError) as error:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sheet format: {error}"
            )
```

### GitHub Client (src/cpo_console/scoring_playground/github_client.py)
```python
import os
import base64
import time
from typing import Optional, Dict, Any
from github import Github, GithubException
from fastapi import HTTPException

class GitHubClient:
    """Client for GitHub operations."""
    
    def __init__(self):
        """Initialize with GitHub token."""
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GITHUB_TOKEN not set")
        
        self.github = Github(token)
        self.repo_name = os.getenv('GITHUB_REPO', 'your-org/your-repo')
        self.repo = self.github.get_repo(self.repo_name)
    
    async def create_weights_pr(
        self,
        yaml_content: str,
        description: str,
        impact_summary: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create GitHub PR with updated weights.
        
        Args:
            yaml_content: YAML content for the new scoring rules
            description: PR description
            impact_summary: Summary of scoring impact
            
        Returns:
            str: URL of the created PR
        """
        try:
            # Create new branch
            branch_name = f"update-scoring-weights-{int(time.time())}"
            main_branch = self.repo.get_branch("main")
            
            # Create new branch from main
            self.repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=main_branch.commit.sha
            )
            
            # Get current file to preserve SHA
            file_path = "config/scoring_rules.yaml"
            try:
                file_contents = self.repo.get_contents(file_path, ref="main")
                file_sha = file_contents.sha
            except GithubException:
                file_sha = None  # File doesn't exist, will create new
            
            # Update file in new branch
            commit_message = "Update scoring weights via playground"
            if file_sha:
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=yaml_content,
                    sha=file_sha,
                    branch=branch_name
                )
            else:
                self.repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=yaml_content,
                    branch=branch_name
                )
            
            # Build PR body
            pr_body = f"""## Description
{description}

## Impact Summary
"""
            if impact_summary:
                pr_body += f"""
- Leads moving up tiers: {impact_summary.get('tier_movements', {}).get('up', 0)}
- Leads moving down tiers: {impact_summary.get('tier_movements', {}).get('down', 0)}
- Leads staying in same tier: {impact_summary.get('tier_movements', {}).get('same', 0)}

### Sample Lead Score Changes
| Lead ID | Business Name | Old Score | New Score | Delta | Tier Change |
|---------|---------------|-----------|-----------|-------|-------------|
"""
                # Add first 5 deltas as examples
                for delta in impact_summary.get('deltas', [])[:5]:
                    tier_change = "↑" if delta['new_tier'] < delta['old_tier'] else (
                        "↓" if delta['new_tier'] > delta['old_tier'] else "→"
                    )
                    pr_body += f"| {delta['lead_id']} | {delta['business_name']} | {delta['old_score']} | {delta['new_score']} | {delta['delta']:+.2f} | {delta['old_tier']} {tier_change} {delta['new_tier']} |\n"
            
            pr_body += """
## Testing
- [ ] YAML syntax validated
- [ ] Component weights sum to 1.0
- [ ] Sample cohort re-scored successfully
- [ ] No errors in scoring engine

## Review Checklist
- [ ] Weight changes align with business goals
- [ ] No component weight exceeds reasonable bounds (0.1-0.5)
- [ ] Factor weights within components sum appropriately
- [ ] Changes won't cause dramatic tier shifts
"""
            
            # Create PR
            pr = self.repo.create_pull(
                title=f"Update scoring weights - {time.strftime('%Y-%m-%d')}",
                body=pr_body,
                head=branch_name,
                base="main"
            )
            
            # Add labels if available
            try:
                pr.add_to_labels("scoring", "config-change")
            except GithubException:
                # Labels might not exist, log but don't fail
                print(f"Warning: Could not add labels to PR {pr.number}")
            
            return pr.html_url
            
        except GithubException as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create PR: {error}"
            )
```

### YAML Generator (src/cpo_console/scoring_playground/yaml_generator.py)
```python
from typing import Dict, Any
from ruamel.yaml import YAML
from io import StringIO
import time

def generate_yaml_with_comments(weights_data: Dict[str, Any]) -> str:
    """Generate YAML content with preserved comments and formatting.
    
    Args:
        weights_data: Dictionary containing scoring weights
        
    Returns:
        str: Formatted YAML content with comments
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 120
    
    # Build YAML structure with comments
    output = StringIO()
    
    # Write header comment
    output.write("# Scoring Rules Configuration\n")
    output.write("# This file defines the weights and factors used for lead scoring\n")
    output.write("# Generated by Scoring Playground\n\n")
    
    # Write version
    output.write(f"version: \"{weights_data.get('version', '1.0')}\"\n\n")
    
    # Write components section
    output.write("# Component weights must sum to 1.0\n")
    output.write("components:\n")
    
    for comp_name, comp_data in weights_data.get('components', {}).items():
        output.write(f"  {comp_name}:\n")
        output.write(f"    weight: {comp_data.get('weight', 0.0)}\n")
        if comp_data.get('description'):
            output.write(f"    description: \"{comp_data['description']}\"\n")
        
        # Write factors
        if comp_data.get('factors'):
            output.write("    factors:\n")
            for factor_name, factor_data in comp_data['factors'].items():
                output.write(f"      {factor_name}:\n")
                output.write(f"        weight: {factor_data.get('weight', 0.0)}\n")
                output.write(f"        max_score: {factor_data.get('max_score', 100)}\n")
                if factor_data.get('description'):
                    output.write(f"        description: \"{factor_data['description']}\"\n")
        output.write("\n")
    
    # Write tier thresholds if present
    if weights_data.get('tier_thresholds'):
        output.write("# Score thresholds for tier assignment\n")
        output.write("tier_thresholds:\n")
        for tier, threshold in weights_data['tier_thresholds'].items():
            output.write(f"  {tier}: {threshold}\n")
        output.write("\n")
    
    # Write metadata
    output.write("# Metadata\n")
    output.write("metadata:\n")
    output.write(f"  last_updated: \"{time.strftime('%Y-%m-%d %H:%M:%S')}\"\n")
    output.write(f"  updated_by: \"scoring_playground\"\n")
    
    return output.getvalue()
```

### Test Suite (tests/cpo_console/scoring_playground/test_scoring_playground.py)
```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

from src.cpo_console.scoring_playground.api import router
from src.cpo_console.scoring_playground.sheets_client import SheetsClient
from src.cpo_console.scoring_playground.github_client import GitHubClient
from core.auth import get_current_user

@pytest.fixture
def client():
    """Test client with mocked auth."""
    app = FastAPI()
    app.include_router(router)
    
    # Mock auth dependency
    def mock_get_current_user():
        return Mock(id="test-user", roles=["admin"])
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    return TestClient(app)

@pytest.fixture
def mock_sheets_client():
    """Mock Google Sheets client."""
    with patch('src.cpo_console.scoring_playground.api.SheetsClient') as mock:
        instance = mock.return_value
        instance.create_weights_sheet = AsyncMock()
        instance.read_weights_from_sheet = AsyncMock()
        yield instance

@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    with patch('src.cpo_console.scoring_playground.api.GitHubClient') as mock:
        instance = mock.return_value
        instance.create_weights_pr = AsyncMock()
        yield instance

def test_import_weights_success(client, mock_sheets_client):
    """Test successful import of weights to Sheet."""
    mock_sheets_client.create_weights_sheet.return_value = "https://sheets.google.com/test-sheet"
    
    response = client.post("/api/scoring-playground/import-weights")
    
    assert response.status_code == 200
    data = response.json()
    assert data["sheet_url"] == "https://sheets.google.com/test-sheet"
    assert data["components_count"] > 0
    assert "version" in data

def test_rescore_sample_with_validation(client, mock_sheets_client):
    """Test re-scoring with weight validation."""
    # Mock sheet data with invalid weights (sum != 1.0)
    mock_sheets_client.read_weights_from_sheet.return_value = {
        "components": {
            "company_info": {"weight": 0.5, "factors": {}},
            "contact_info": {"weight": 0.6, "factors": {}}  # Sum = 1.1
        }
    }
    
    response = client.post("/api/scoring-playground/rescore-sample", json={
        "sheet_id": "test-sheet-id"
    })
    
    assert response.status_code == 400
    assert "must sum to 1.0" in response.json()["detail"]

def test_rescore_sample_success(client, mock_sheets_client):
    """Test successful re-scoring with valid weights."""
    # Mock valid weights
    mock_sheets_client.read_weights_from_sheet.return_value = {
        "version": "1.0",
        "components": {
            "company_info": {"weight": 0.5, "factors": {"size": {"weight": 0.5, "max_score": 100}}},
            "contact_info": {"weight": 0.5, "factors": {"quality": {"weight": 1.0, "max_score": 100}}}
        }
    }
    
    # Mock lead data
    with patch('src.cpo_console.scoring_playground.api.Lead') as mock_lead:
        mock_leads = [
            Mock(id=1, business_name="Test Co 1"),
            Mock(id=2, business_name="Test Co 2")
        ]
        mock_lead.get_sample_cohort = AsyncMock(return_value=mock_leads)
        
        # Mock scoring engine
        with patch('src.cpo_console.scoring_playground.api.ScoringEngine') as mock_engine:
            mock_engine.return_value.score_lead.return_value = Mock(total_score=75.0)
            mock_engine.return_value.get_tier.return_value = "B"
            
            response = client.post("/api/scoring-playground/rescore-sample", json={
                "sheet_id": "test-sheet-id",
                "sample_size": 2
            })
    
    assert response.status_code == 200
    data = response.json()
    assert data["sample_size"] == 2
    assert len(data["deltas"]) == 2
    assert data["preview_weights_valid"] is True
    assert "tier_movements" in data

def test_create_pr_success(client, mock_sheets_client, mock_github_client):
    """Test successful PR creation."""
    mock_sheets_client.read_weights_from_sheet.return_value = {
        "version": "1.0",
        "components": {
            "company_info": {"weight": 0.5, "factors": {}},
            "contact_info": {"weight": 0.5, "factors": {}}
        }
    }
    mock_github_client.create_weights_pr.return_value = "https://github.com/org/repo/pull/123"
    
    response = client.post("/api/scoring-playground/create-pr", json={
        "sheet_id": "test-sheet-id",
        "pr_description": "Test weight update",
        "impact_summary": {
            "tier_movements": {"up": 5, "down": 3, "same": 92},
            "deltas": []
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["pr_url"] == "https://github.com/org/repo/pull/123"
    assert data["yaml_valid"] is True
    assert "branch_name" in data

def test_create_pr_invalid_weights(client, mock_sheets_client):
    """Test PR creation fails with invalid weights."""
    mock_sheets_client.read_weights_from_sheet.return_value = {
        "components": {
            "company_info": {"weight": 0.3},
            "contact_info": {"weight": 0.3}  # Sum = 0.6
        }
    }
    
    response = client.post("/api/scoring-playground/create-pr", json={
        "sheet_id": "test-sheet-id"
    })
    
    assert response.status_code == 400
    assert "must sum to 1.0" in response.json()["detail"]

def test_yaml_generation():
    """Test YAML generation with comments."""
    from src.cpo_console.scoring_playground.yaml_generator import generate_yaml_with_comments
    
    weights = {
        "version": "1.0",
        "components": {
            "company_info": {
                "weight": 0.5,
                "description": "Company information scoring",
                "factors": {
                    "size": {"weight": 0.5, "max_score": 100}
                }
            }
        }
    }
    
    yaml_content = generate_yaml_with_comments(weights)
    
    assert "# Scoring Rules Configuration" in yaml_content
    assert "version: \"1.0\"" in yaml_content
    assert "company_info:" in yaml_content
    assert "weight: 0.5" in yaml_content
    assert "# Component weights must sum to 1.0" in yaml_content
```

### Schemas (src/cpo_console/scoring_playground/schemas.py)
```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class WeightImportResponse(BaseModel):
    """Response for weight import to Sheet."""
    sheet_url: str = Field(..., description="URL of the created Google Sheet")
    components_count: int = Field(..., description="Number of components imported")
    version: str = Field(..., description="Version of the weights configuration")

class RescoringRequest(BaseModel):
    """Request for re-scoring sample cohort."""
    sheet_id: str = Field(..., description="Google Sheet ID containing preview weights")
    sample_size: Optional[int] = Field(100, description="Number of leads to rescore", ge=1, le=1000)
    filter_criteria: Optional[Dict[str, Any]] = Field(None, description="Optional filter for sample selection")

class LeadDelta(BaseModel):
    """Score change information for a single lead."""
    lead_id: int = Field(..., description="Lead ID")
    business_name: str = Field(..., description="Business name for display")
    old_score: float = Field(..., description="Score with current weights")
    new_score: float = Field(..., description="Score with preview weights")
    delta: float = Field(..., description="Score difference (new - old)")
    old_tier: str = Field(..., description="Current tier assignment")
    new_tier: str = Field(..., description="New tier assignment")

class TierMovements(BaseModel):
    """Summary of tier movements."""
    up: int = Field(..., description="Number of leads moving to better tier")
    down: int = Field(..., description="Number of leads moving to worse tier")
    same: int = Field(..., description="Number of leads staying in same tier")

class RescoringResponse(BaseModel):
    """Response for re-scoring operation."""
    sample_size: int = Field(..., description="Number of leads rescored")
    deltas: List[LeadDelta] = Field(..., description="Individual lead score changes")
    tier_movements: TierMovements = Field(..., description="Summary of tier changes")
    preview_weights_valid: bool = Field(..., description="Whether preview weights passed validation")

class PRCreationRequest(BaseModel):
    """Request for creating GitHub PR."""
    sheet_id: str = Field(..., description="Google Sheet ID containing final weights")
    pr_description: Optional[str] = Field(None, description="Custom PR description")
    impact_summary: Optional[Dict[str, Any]] = Field(None, description="Impact data from rescoring")

class PRCreationResponse(BaseModel):
    """Response for PR creation."""
    pr_url: str = Field(..., description="URL of the created GitHub PR")
    branch_name: str = Field(..., description="Name of the created branch")
    yaml_valid: bool = Field(..., description="Whether generated YAML is valid")
```

## Reference Documentation
- Google Sheets API Python: https://developers.google.com/sheets/api/quickstart/python
- Google Sheets API Reference: https://developers.google.com/sheets/api/reference/rest
- GitHub API PR Creation: https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request
- FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
- YAML Processing with ruamel: https://yaml.readthedocs.io/en/latest/overview.html
- Existing sheet_to_yaml.py: scripts/sheet_to_yaml.py (reuse patterns)
- Scoring engine: d5_scoring/scoring_engine.py
- Current weights schema: config/scoring_rules.yaml

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure P0-023 shows "completed"
- Verify Google Sheets API credentials are available in environment
- Confirm GitHub token has repo write access
- Verify CI is green before starting

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Install Google API dependencies: `pip install google-api-python-client google-auth`
- Install GitHub client: `pip install PyGithub`
- Install YAML processor: `pip install ruamel.yaml`
- Set environment variables:
  - `GOOGLE_SHEETS_CREDENTIALS`: Service account JSON
  - `GITHUB_TOKEN`: Personal access token with repo scope
  - `GITHUB_REPO`: Repository name (e.g., "your-org/your-repo")
- Activate virtual environment: `source venv/bin/activate`

### Step 3: Implementation Order
1. Create directory structure: `src/cpo_console/scoring_playground/`
2. Implement schemas.py with Pydantic models
3. Create yaml_generator.py for YAML generation with comments
4. Create sheets_client.py with full implementation
5. Create github_client.py with full implementation
6. Implement api.py with three endpoints
7. Add routes to main FastAPI app
8. Create comprehensive test suite

### Step 4: Testing
- Unit tests for each component (sheets_client, github_client, yaml_generator)
- Integration tests for API endpoints
- End-to-end test with mock services
- Manual test with real Google Sheet (dev environment)
- Verify scoring engine compatibility

### Step 5: Validation
- Import current weights and verify Sheet structure
- Make test weight changes and preview impact
- Create test PR and verify YAML validity
- Run full validation command suite
- Ensure no impact on production scoring

## Validation Commands
```bash
# Run specific tests
pytest tests/cpo_console/scoring_playground -xvs

# Verify YAML validity
python -c "import yaml; yaml.safe_load(open('config/scoring_rules.yaml'))"

# Check scoring engine still works
pytest tests/unit/d5_scoring/test_scoring_engine.py

# Validate overall coverage
pytest --cov=src/cpo_console/scoring_playground --cov-report=term-missing

# Manual API test
curl -X POST http://localhost:8000/api/scoring-playground/import-weights \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json"
```

## Post-Execution Validation
- [ ] All three API endpoints return successful responses
- [ ] Google Sheet correctly displays all components and weights
- [ ] Re-scoring shows accurate deltas and tier movements
- [ ] Created PR has valid YAML that passes CI checks
- [ ] No changes to production scoring until PR merged
- [ ] Test coverage ≥ 80% for new module

## External Research Context
The scoring playground addresses a critical operational need: safe experimentation with business logic that directly impacts lead prioritization. By using Google Sheets as the editing interface, we leverage familiar tools while maintaining code-based version control through PRs. The pattern of Sheet → Preview → PR creates a safety net preventing accidental production changes while enabling rapid iteration.

## Rollback Strategy
1. **API Level**: Feature flag `ENABLE_SCORING_PLAYGROUND=false` disables all endpoints
2. **Sheet Level**: Delete or archive the `weights_preview` Sheet
3. **PR Level**: Close any open PRs without merging
4. **Code Level**: `git revert` the commit adding scoring_playground module
5. **Verification**: Run `pytest tests/unit/d5_scoring/` to ensure scoring unaffected

## Feature Flag Requirements
- Add `ENABLE_SCORING_PLAYGROUND` to config/settings.py
- Default to `false` in production until fully tested
- Wrap all API routes with feature flag check
- Document flag in deployment guide

## Success Criteria
- [ ] CPO can modify weights without engineering help
- [ ] Preview shows accurate impact before committing changes
- [ ] PR creation automates the Git workflow
- [ ] No production impact until PR reviewed and merged
- [ ] System prevents invalid weight configurations
- [ ] Full audit trail via Git history

## Time and Compute Budget
- Implementation: 2-3 days
- Testing: 1 day
- Google Sheets API: Free tier sufficient (< 100 requests/day)
- GitHub API: Well within rate limits
- Compute: Minimal (re-scoring 100 leads takes < 1 second)

## Error Handling Requirements
- Invalid credentials: Return 401 with setup instructions
- Sheet API errors: Retry with exponential backoff
- Invalid weights: Return 400 with specific validation errors
- GitHub API failures: Return 503 with manual PR instructions
- Database errors: Log and return 500 with correlation ID
- All errors logged with context for debugging