# P0-025 - Scoring Playground
**Priority**: P0  
**Status**: Not Started  
**Estimated Effort**: 3 days  
**Dependencies**: P0-024

> 💡 **Claude Implementation Note**: Consider how task subagents can be used to execute portions of this task in parallel to improve efficiency and reduce overall completion time.

## Goal & Success Criteria

Create a web-based scoring playground that enables safe experimentation with YAML weight vectors using Google Sheets, displays real-time score deltas on a 100-lead sample, and facilitates GitHub PR creation for weight updates.

### Success Criteria:
- [ ] Weights import correctly from config/scoring_rules.yaml to REAL Google Sheets (not mocked)
- [ ] Weight sum validation enforces 1.0 ± 0.005 tolerance with clear error messages
- [ ] Delta table renders in < 1 second using cached 100-lead sample
- [ ] GitHub PR creates REAL pull request in actual repository (not mocked)
- [ ] Test coverage ≥ 80% on d5_scoring.playground module
- [ ] All existing scoring tests continue to pass without modification
- [ ] Google Sheets API authentication works with REAL service account credentials
- [ ] UI updates reflect REAL sheet changes within 500ms
- [ ] Integration tests verify REAL API calls to Google Sheets and GitHub
- [ ] No mock implementations used for external service integrations

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

1. **Import Functionality (REAL API)**
   - Current weights load from YAML to REAL Google Sheet via API
   - Component names and weights display correctly in actual spreadsheet
   - Sum validation formula shows in real sheet cells
   - Import completes in < 500ms including real API latency
   - Service account authentication works with actual credentials

2. **Real-time Updates (REAL API)**
   - Sheet changes from REAL Google Sheets reflect in UI within 500ms
   - Weight sum validation shows clear pass/fail in actual sheet
   - Invalid weights highlight with error message via Sheets API
   - Concurrent users see consistent state from real spreadsheet
   - Handle Google Sheets API rate limits gracefully

3. **Delta Calculation**
   - Score changes calculate for all 100 sample leads
   - Delta table shows: Lead ID, Old Score, New Score, Change
   - Calculation completes in < 1 second
   - Results sort by largest change magnitude

4. **GitHub PR Creation (REAL API)**
   - YAML file preserves comments and structure
   - PR creates REAL pull request in actual GitHub repository
   - Commit message follows conventional format
   - PR links back to scoring playground session
   - Real branch created and file updated via GitHub API

5. **Testing Requirements**
   - Unit tests cover all validation edge cases (can use mocks)
   - Integration tests verify REAL Google Sheets API (NO MOCKS)
   - Integration tests create REAL GitHub PRs to test repository
   - Performance tests ensure < 1s delta calculation
   - CI runs integration tests with real service account credentials

## Dependencies

### External Services
- Google Sheets API v4 with REAL service account authentication (NOT MOCKED)
  - Requires active Google Cloud project
  - Service account with Sheets API enabled
  - Credentials stored in GOOGLE_SHEETS_CREDENTIALS env var
- GitHub API v3 for REAL PR creation (NOT MOCKED)
  - Uses actual GitHub token from environment
  - Creates real PRs to configured test repository
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

## Real API Integration Requirements

### Google Sheets Setup
1. **Service Account Creation**
   ```bash
   # Required: Google Cloud project with Sheets API enabled
   # 1. Create service account in GCP Console
   # 2. Download JSON credentials
   # 3. Share target sheet with service account email
   # 4. Set GOOGLE_SHEETS_CREDENTIALS env var with JSON content
   ```

2. **Test Sheet Configuration**
   - Create dedicated test spreadsheet
   - Share with service account email
   - Set TEST_SHEET_ID env var
   - Sheet must have edit permissions

3. **Real API Authentication**
   ```python
   # d5_scoring/playground/sheets_client.py
   def get_authenticated_client():
       """Get real authenticated Google Sheets client"""
       creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
       if not creds_json:
           raise ValueError("GOOGLE_SHEETS_CREDENTIALS not set")
       
       # Parse and validate service account JSON
       try:
           creds_dict = json.loads(creds_json)
           return gspread.service_account_from_dict(creds_dict)
       except Exception as e:
           raise ValueError(f"Invalid service account credentials: {e}")
   ```

### GitHub Integration
1. **Real PR Creation**
   ```python
   # d5_scoring/playground/github_client.py
   def create_real_pr(weights: Dict[str, float], message: str):
       """Create actual GitHub PR - NOT MOCKED"""
       token = os.environ.get("GITHUB_TOKEN")
       if not token:
           raise ValueError("GITHUB_TOKEN not set")
       
       g = Github(token)
       repo = g.get_repo(os.environ.get("GITHUB_REPO", "user/test-repo"))
       
       # Create real branch
       base = repo.get_branch("main")
       branch_name = f"scoring-update-{datetime.now():%Y%m%d-%H%M%S}"
       repo.create_git_ref(f"refs/heads/{branch_name}", base.commit.sha)
       
       # Update real file
       file = repo.get_contents("config/scoring_rules.yaml", ref=branch_name)
       updated_yaml = update_weights_preserving_comments(file.decoded_content, weights)
       repo.update_file(
           file.path,
           f"Update scoring weights via playground\n\n{message}",
           updated_yaml,
           file.sha,
           branch=branch_name
       )
       
       # Create real PR
       pr = repo.create_pull(
           title=f"Update scoring weights: {message[:50]}",
           body=generate_pr_description(weights),
           head=branch_name,
           base="main"
       )
       return pr.html_url
   ```

## Testing Strategy

### Unit Tests (tests/unit/d5_scoring/playground/)
1. **test_weight_validator.py**
   - Test sum validation with various tolerances
   - Test individual weight constraints
   - Test empty and null weight handling

2. **test_sheets_client.py**
   - Unit tests use mocks for basic logic
   - Integration tests use REAL Google Sheets API
   - Test actual API rate limits and quotas
   - Verify real authentication flow

3. **test_delta_calculator.py**
   - Test with deterministic sample data
   - Verify calculation accuracy
   - Test caching behavior

4. **test_github_client.py**
   - Unit tests mock for logic validation
   - Integration tests create REAL PRs to test repository
   - Test actual GitHub API authentication
   - Verify PR appears in GitHub UI

### Integration Tests
```python
# tests/integration/test_scoring_playground.py
@pytest.mark.integration
@pytest.mark.requires_google_sheets
async def test_real_google_sheets_integration():
    """Test with real Google Sheets API - NOT MOCKED"""
    # Requires GOOGLE_SHEETS_CREDENTIALS env var with service account JSON
    creds = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    if not creds:
        pytest.skip("No Google Sheets credentials available")
    
    client = SheetsClient(creds)
    test_sheet_id = os.getenv("TEST_SHEET_ID")
    
    # Test real API operations
    await client.import_weights(test_sheet_id, "config/scoring_rules.yaml")
    weights = await client.read_weights(test_sheet_id)
    assert sum(weights.values()) == pytest.approx(1.0, abs=0.005)

@pytest.mark.integration
async def test_full_weight_update_flow():
    """Test complete flow from import to PR with real APIs"""
    # 1. Import weights to real Google Sheet
    # 2. Modify weights via Sheets API
    # 3. Calculate deltas with real data
    # 4. Create PR with real GitHub API (to test repo)
    # 5. Verify all steps succeed with actual API calls
```

### Performance Tests
- Measure delta calculation time with 100 leads
- Test concurrent user load on sheet updates
- Verify Redis cache effectiveness
- Test real Google Sheets API quota limits:
  - 100 requests per 100 seconds per user
  - 500 requests per 100 seconds per project
- Implement exponential backoff for rate limiting

## Environment Variables

### Required for Real API Integration
```bash
# Google Sheets API (REQUIRED - NOT OPTIONAL)
GOOGLE_SHEETS_CREDENTIALS='{"type": "service_account", ...}'  # Full service account JSON
TEST_SHEET_ID='1abc...'  # ID of test spreadsheet shared with service account

# GitHub API (uses existing token)
GITHUB_TOKEN='ghp_...'  # Already in .env
GITHUB_REPO='owner/repo'  # Target repo for PRs

# Feature Flag
ENABLE_SCORING_PLAYGROUND=true  # Enable the feature
```

### Service Account Setup Steps
1. Go to Google Cloud Console
2. Create new project or select existing
3. Enable Google Sheets API
4. Create service account with "Editor" role
5. Generate JSON key
6. Share test spreadsheet with service account email
7. Add JSON to GOOGLE_SHEETS_CREDENTIALS env var

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


### CI Validation (MANDATORY)
**CI Validation = Code merged to main + GitHub Actions logs verified + All errors resolved + Solid green CI run**

This means:
1. Code must be merged to the main branch (not just pushed)
2. GitHub Actions logs must be checked to confirm successful workflow completion
3. Any errors that appear during CI must be resolved
4. The final CI run must show all green checkmarks with no failures
5. This verification must be done by reviewing the actual GitHub Actions logs, not just assumed
6. **CRITICAL**: Integration tests with REAL APIs must pass in CI:
   - Set up GitHub Secrets for GOOGLE_SHEETS_CREDENTIALS
   - Set up TEST_SHEET_ID for CI test spreadsheet
   - Verify real API calls succeed in CI logs
   - No mocked external services in integration tests

**This is a mandatory requirement for PRP completion.**

### Real API CI Configuration
```yaml
# .github/workflows/test.yml addition
jobs:
  test:
    env:
      GOOGLE_SHEETS_CREDENTIALS: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS }}
      TEST_SHEET_ID: ${{ secrets.TEST_SHEET_ID }}
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - name: Run integration tests with real APIs
        run: |
          pytest tests/integration/test_scoring_playground.py \
            -m "requires_google_sheets" \
            --no-cov \
            -v
```

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
  - Track REAL API usage vs quotas (Google: 100 req/100s/user)
  - Alert on repeated failures from actual API calls
  - Log performance metrics from real service interactions
  - Monitor cache hit rates to minimize API calls
  - Implement circuit breaker for API failures

- [X] **Real API Error Handling**
  - Handle Google Sheets quota exceeded (429 errors)
  - Retry with exponential backoff
  - Handle GitHub API rate limits
  - Graceful degradation when APIs unavailable
  - User-friendly messages for API failures