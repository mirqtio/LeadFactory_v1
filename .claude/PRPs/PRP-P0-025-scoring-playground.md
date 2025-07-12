# P0-025 - Scoring Playground
**Priority**: P0  
**Status**: Not Started  
**Estimated Effort**: 3 days  
**Dependencies**: P0-024

## Goal & Success Criteria

Create a web-based scoring playground that enables safe experimentation with YAML weight vectors using Google Sheets, displays real-time score deltas on a 100-lead sample, and facilitates GitHub PR creation for weight updates.

### Success Criteria:
- [ ] Weights import correctly from config/scoring_rules.yaml to Google Sheets
- [ ] Weight sum validation enforces 1.0 ± 0.005 tolerance with clear error messages
- [ ] Delta table renders in < 1 second using cached 100-lead sample
- [ ] GitHub PR includes proper before/after YAML diff with preserved comments
- [ ] Test coverage ≥ 80% on d5_scoring.playground module
- [ ] All existing scoring tests continue to pass without modification
- [ ] Google Sheets API authentication works with service account credentials
- [ ] UI updates reflect sheet changes within 500ms

## Context & Background

The LeadFactory scoring system currently uses YAML-based weight configuration (`config/scoring_rules.yaml`) with 15 components that must sum to 1.0. Business stakeholders need a familiar interface to experiment with weight adjustments and immediately see the impact on lead scores without developer involvement.

Current implementation:
- `d5_scoring/rules_schema.py` validates weight sums with ± 0.005 tolerance
- Scripts exist for YAML↔Sheet conversion but lack UI and real-time feedback
- Scoring engine supports hot-reloading but requires manual file edits
- No current mechanism for non-technical users to propose weight changes

## Technical Approach

### 1. Architecture Overview
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   FastAPI UI    │────▶│  Google Sheets   │────▶│  Score Engine   │
│  (Playground)   │◀────│      API         │◀────│  (Delta Calc)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                                  │
         │                                                  │
         ▼                                                  ▼
┌─────────────────┐                             ┌─────────────────┐
│   GitHub API    │                             │  Redis Cache    │
│   (PR Create)   │                             │ (100-lead sample)│
└─────────────────┘                             └─────────────────┘
```

### 2. Module Structure
```python
# d5_scoring/playground/__init__.py
from .api import router
from .sheets_client import SheetsClient
from .delta_calculator import DeltaCalculator
from .github_client import GitHubClient

# d5_scoring/playground/api.py
@router.post("/import-weights")
async def import_weights_to_sheet(sheet_id: str = Form(...)):
    """Import current YAML weights to Google Sheet"""
    
@router.get("/sheet-updates")
async def get_sheet_updates(sheet_id: str):
    """Poll for weight changes in sheet"""
    
@router.post("/calculate-deltas")
async def calculate_deltas(weights: Dict[str, float]):
    """Calculate score changes for sample leads"""
    
@router.post("/create-pr")
async def create_weight_pr(weights: Dict[str, float], message: str):
    """Create GitHub PR with updated weights"""
```

### 3. Google Sheets Integration
```python
# d5_scoring/playground/sheets_client.py
class SheetsClient:
    def __init__(self, credentials_json: str):
        self.client = gspread.service_account_from_dict(
            json.loads(credentials_json)
        )
        
    async def import_weights(self, sheet_id: str, config_path: str):
        """Import weights maintaining component structure"""
        yaml_data = load_scoring_config(config_path)
        sheet = self.client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)
        
        # Clear and populate with headers
        worksheet.clear()
        headers = ["Component", "Weight", "Sum Check"]
        rows = [headers]
        
        # Add component weights
        total = 0.0
        for name, component in yaml_data["components"].items():
            weight = component["weight"]
            total += weight
            rows.append([name, weight, ""])
            
        # Add sum validation row
        rows.append(["TOTAL", f"=SUM(B2:B{len(rows)})", 
                    f'=IF(ABS(B{len(rows)+1}-1)<0.005,"✓","✗")'])
        
        worksheet.update("A1", rows)
```

### 4. Weight Validation
```python
# d5_scoring/playground/weight_validator.py
from d5_scoring.constants import WEIGHT_SUM_WARNING_THRESHOLD

def validate_weights(weights: Dict[str, float]) -> ValidationResult:
    """Validate weight sum and individual constraints"""
    total = sum(weights.values())
    tolerance = WEIGHT_SUM_WARNING_THRESHOLD  # 0.005
    
    if abs(total - 1.0) > tolerance:
        return ValidationResult(
            valid=False,
            error=f"Weights sum to {total:.4f}, must be 1.0 ± {tolerance}",
            total=total
        )
    
    # Check individual weights
    for name, weight in weights.items():
        if not 0 <= weight <= 1:
            return ValidationResult(
                valid=False,
                error=f"{name} weight {weight} must be between 0 and 1"
            )
    
    return ValidationResult(valid=True, total=total)
```

### 5. Delta Calculation with Caching
```python
# d5_scoring/playground/delta_calculator.py
class DeltaCalculator:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.engine = ScoringEngine()
        
    async def get_sample_leads(self) -> List[Lead]:
        """Get cached 100-lead sample or generate new"""
        cached = await self.redis.get("scoring_sample_leads")
        if cached:
            return json.loads(cached)
            
        # Generate diverse sample
        async with get_session() as session:
            leads = await session.execute(
                select(Lead)
                .join(Assessment)
                .where(Assessment.data.isnot(None))
                .order_by(func.random())
                .limit(100)
            )
            sample = [lead.to_dict() for lead in leads.scalars()]
            
        # Cache for 1 hour
        await self.redis.setex(
            "scoring_sample_leads", 
            3600, 
            json.dumps(sample)
        )
        return sample
```

## Acceptance Criteria

1. **Import Functionality**
   - Current weights load from YAML to Google Sheet
   - Component names and weights display correctly
   - Sum validation formula shows in sheet
   - Import completes in < 500ms

2. **Real-time Updates**
   - Sheet changes reflect in UI within 500ms
   - Weight sum validation shows clear pass/fail
   - Invalid weights highlight with error message
   - Concurrent users see consistent state

3. **Delta Calculation**
   - Score changes calculate for all 100 sample leads
   - Delta table shows: Lead ID, Old Score, New Score, Change
   - Calculation completes in < 1 second
   - Results sort by largest change magnitude

4. **GitHub PR Creation**
   - YAML file preserves comments and structure
   - PR description includes weight comparison table
   - Commit message follows conventional format
   - PR links back to scoring playground session

5. **Testing Requirements**
   - Unit tests cover all validation edge cases
   - Integration tests verify Google Sheets API
   - Mock GitHub API for PR creation tests
   - Performance tests ensure < 1s delta calculation

## Dependencies

### External Services
- Google Sheets API v4 with service account authentication
- GitHub API v3 for PR creation
- Redis for caching (existing infrastructure)

### Python Packages
```txt
gspread>=6.1.2              # Google Sheets client
google-auth>=2.23.0         # Authentication
google-auth-oauthlib>=1.1.0 # OAuth support
PyGithub>=2.1.1            # GitHub API client
ruamel.yaml>=0.18.0        # YAML with comment preservation
```

### Internal Dependencies
- `d5_scoring/scoring_engine.py` - Score calculation
- `d5_scoring/rules_schema.py` - Weight validation constants
- `config/scoring_rules.yaml` - Current weight configuration
- `core/database.py` - Database session management
- `core/redis.py` - Redis client configuration

## Testing Strategy

### Unit Tests (tests/unit/d5_scoring/playground/)
1. **test_weight_validator.py**
   - Test sum validation with various tolerances
   - Test individual weight constraints
   - Test empty and null weight handling

2. **test_sheets_client.py**
   - Mock gspread calls
   - Test import formatting
   - Test error handling for API limits

3. **test_delta_calculator.py**
   - Test with deterministic sample data
   - Verify calculation accuracy
   - Test caching behavior

4. **test_github_client.py**
   - Mock PyGithub API calls
   - Test PR creation payload
   - Test YAML diff generation

### Integration Tests
```python
# tests/integration/test_scoring_playground.py
@pytest.mark.integration
async def test_full_weight_update_flow():
    """Test complete flow from import to PR"""
    # 1. Import weights to sheet
    # 2. Modify weights
    # 3. Calculate deltas
    # 4. Create PR
    # 5. Verify all steps succeed
```

### Performance Tests
- Measure delta calculation time with 100 leads
- Test concurrent user load on sheet updates
- Verify Redis cache effectiveness

## Rollback Plan

### Immediate Rollback (< 5 minutes)
1. Set feature flag `ENABLE_SCORING_PLAYGROUND=false`
2. Remove `/scoring-playground` routes from API
3. No database changes to revert

### Full Rollback Procedure
1. Remove `d5_scoring/playground/` module
2. Remove playground tests
3. Clean up Redis cache keys: `scoring_sample_*`
4. Document manual cleanup of test Google Sheets
5. Close any open PRs created by playground

### Rollback Triggers
- Google Sheets API quota exhaustion
- Performance degradation in scoring engine
- Security vulnerability discovered
- Weight validation bypassed

## Validation Framework

### Required Validation (Backend/API Task)
- [X] **Pre-commit hooks configured**
  - ruff format check on Python files
  - mypy type checking for playground module
  - pytest unit tests before commit

- [X] **Branch protection rules**
  - Require PR reviews for weight changes
  - Status checks must pass
  - No direct commits to main

- [X] **Security scanning**
  - No hardcoded credentials (use env vars)
  - Validate all user inputs
  - Rate limit API endpoints
  - Audit log all weight changes

- [X] **API performance budgets**
  - Import weights: < 500ms
  - Calculate deltas: < 1000ms
  - Sheet polling: < 200ms
  - PR creation: < 2000ms

### Additional Validation
- [X] **Input validation**
  - Weight values must be numeric 0.0-1.0
  - Component names must match YAML schema
  - Sheet ID format validation
  - GitHub token permission check

- [X] **Error handling**
  - Graceful Google Sheets API failures
  - Clear messages for validation errors
  - Retry logic for transient failures
  - User-friendly error display

- [X] **Monitoring**
  - Track API usage vs quotas
  - Alert on repeated failures
  - Log performance metrics
  - Monitor cache hit rates