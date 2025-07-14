# PRP-P3-006 Replace Mock Integrations

## Goal
Replace mock GitHub and Google Sheets APIs with real implementations in Template Studio and Scoring Playground to enable production functionality.

## Why  
- **Business value**: Enables Template Studio and Scoring Playground to function with real external services, supporting production workflows for template editing and scoring experimentation
- **Integration**: Completes the implementation of P0-024 (Template Studio) and P0-025 (Scoring Playground) by replacing placeholder mock integrations
- **Problems solved**: Removes development-only mock responses that prevent real GitHub PR creation and Google Sheets integration in production environments

## What
Replace the mock GitHub and Google Sheets integrations with real API implementations:

### Template Studio GitHub Integration
- Replace mock PR creation with real GitHub API calls using PyGithub
- Implement GitHub App authentication for secure, production-ready access
- Add proper rate limiting and error handling for GitHub API calls
- Support real branch creation, commit creation, and pull request workflow

### Scoring Playground Google Sheets Integration  
- Replace mock Google Sheets responses with real gspread integration
- Implement Service Account authentication for automated access
- Add proper rate limiting and quota management for Google Sheets API
- Support real sheet creation, data import, and change polling

### Success Criteria
- [ ] PyGithub creates real pull requests in Template Studio
- [ ] gspread integrates with actual Google Sheets in Scoring Playground
- [ ] GitHub App authentication working with proper token management
- [ ] Google Service Account authentication properly configured
- [ ] Rate limits respected for both APIs with exponential backoff
- [ ] Integration tests pass with real API calls (using test accounts)
- [ ] Error recovery handles transient failures gracefully
- [ ] Feature flags allow fallback to mock implementations
- [ ] Coverage ≥ 80% on new integration code
- [ ] Production deployment successful with real integrations

## All Needed Context

### Documentation & References
```yaml
- url: https://pygithub.readthedocs.io/en/latest/
  why: Official PyGithub documentation for GitHub API integration
  
- url: https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request
  why: GitHub REST API specification for creating pull requests
  
- url: https://docs.gspread.org/en/latest/oauth2.html
  why: gspread authentication documentation for Google Sheets integration
  
- url: https://developers.google.com/sheets/api/quickstart/python
  why: Google Sheets API Python quickstart guide
  
- url: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github
  why: GitHub authentication best practices comparison
  
- file: api/template_studio.py
  why: Current mock implementation pattern to replace
  
- file: api/scoring_playground.py
  why: Current mock implementation pattern to replace
  
- file: core/config.py
  why: Configuration pattern for API keys and feature flags
```

### Current Codebase Tree
```
api/
├── template_studio.py          # Mock GitHub integration (lines 395-398, 382-383)
├── scoring_playground.py       # Mock Google Sheets (lines 213-221, 382-383)
core/
├── config.py                   # Feature flags and API key configuration
tests/
├── unit/api/
│   ├── test_template_studio.py
│   └── test_scoring_playground.py
```

### Desired Codebase Tree  
```
api/
├── template_studio.py          # Real GitHub integration with PyGithub
├── scoring_playground.py       # Real Google Sheets with gspread
core/
├── config.py                   # New GitHub/Google Sheets credentials
├── github_client.py            # GitHub API client wrapper
├── sheets_client.py            # Google Sheets API client wrapper
requirements.txt                # Add PyGithub, gspread, google-auth
tests/
├── unit/api/
│   ├── test_template_studio.py # Updated with real API mocks
│   └── test_scoring_playground.py # Updated with real API mocks
├── integration/
│   ├── test_github_integration.py  # Integration tests with real APIs
│   └── test_sheets_integration.py  # Integration tests with real APIs
```

## Technical Implementation

### Integration Points
- `api/template_studio.py`: Replace mock PR creation (lines 395-398, 382-383)
- `api/scoring_playground.py`: Replace mock Sheets responses (lines 213-221, 382-383)
- `core/config.py`: Add GitHub token and Google Sheets credentials configuration
- `requirements.txt`: Add PyGithub, gspread, google-auth dependencies

### Implementation Approach

#### Phase 1: GitHub Integration
1. **Install and configure PyGithub**
   - Add `PyGithub>=2.1.0` to requirements.txt
   - Create `core/github_client.py` wrapper with rate limiting and error handling
   - Add GitHub App credentials to config.py

2. **Replace mock PR creation**
   - Update `propose_changes` endpoint to use real GitHub API
   - Implement branch creation, commit creation, and PR creation workflow
   - Add comprehensive error handling for API failures

3. **Add rate limiting and retry logic**
   - Implement exponential backoff with jitter for rate-limited requests
   - Add proper logging for GitHub API interactions
   - Handle GitHub API quota limits gracefully

#### Phase 2: Google Sheets Integration
1. **Install and configure gspread**
   - Add `gspread>=6.1.0` and `google-auth>=2.0.0` to requirements.txt
   - Create `core/sheets_client.py` wrapper with Service Account authentication
   - Add Google Service Account credentials to config.py

2. **Replace mock Sheets responses**
   - Update `import_weights_to_sheets` to create real Google Sheets
   - Implement `poll_sheet_changes` with actual Sheets API polling
   - Add quota management and rate limiting

3. **Add authentication and security**
   - Implement Service Account authentication flow
   - Add proper credential management with environment variables
   - Handle authentication errors and token refresh

#### Phase 3: Error Handling and Testing
1. **Comprehensive error handling**
   - Implement transient vs permanent error differentiation
   - Add circuit breaker pattern for repeated failures
   - Ensure graceful degradation when APIs are unavailable

2. **Integration testing**
   - Create test accounts for GitHub and Google Sheets
   - Implement integration tests that use real APIs
   - Add test cleanup procedures

3. **Feature flag implementation**
   - Add `ENABLE_REAL_GITHUB` and `ENABLE_REAL_SHEETS` feature flags
   - Ensure smooth fallback to mock implementations
   - Support gradual rollout in production

## Validation Gates

### Executable Tests
```bash
# Syntax/Style
ruff check --fix && mypy .

# Unit Tests  
pytest tests/unit/api/test_template_studio.py tests/unit/api/test_scoring_playground.py -v

# Integration Tests
pytest tests/integration/test_github_integration.py tests/integration/test_sheets_integration.py -v

# End-to-End Tests
pytest tests/e2e/test_real_integrations.py -v --slow
```

### Missing-Checks Validation
**Required for Backend/API tasks:**
- [ ] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [ ] Branch protection & required status checks
- [ ] Security scanning (Dependabot, Trivy, audit tools)
- [ ] API performance budgets (GitHub API <2s, Sheets API <1s)
- [ ] Rate limiting compliance tests
- [ ] Authentication security audit
- [ ] Environment variable security validation

**Recommended:**
- [ ] Performance regression budgets
- [ ] Automated CI failure handling
- [ ] External API monitoring and alerting
- [ ] Cost tracking for API usage
- [ ] Automated credential rotation procedures

## Dependencies
- PyGithub>=2.1.0 - GitHub API client library
- gspread>=6.1.0 - Google Sheets API client
- google-auth>=2.0.0 - Google authentication library
- tenacity>=8.0.0 - Retry and backoff library

## Rollback Strategy
- Feature flags `ENABLE_REAL_GITHUB=false` and `ENABLE_REAL_SHEETS=false` to revert to mock implementations
- Environment variables can be removed to disable real integrations
- Database changes: None required, pure API integration changes
- Git revert of all changes will restore mock implementations

## Feature Flag Requirements  
- `ENABLE_REAL_GITHUB`: Enable real GitHub API integration (default: false)
- `ENABLE_REAL_SHEETS`: Enable real Google Sheets integration (default: false)
- `GITHUB_TOKEN`: GitHub App token for API authentication
- `GOOGLE_SHEETS_CREDENTIALS`: Service Account credentials JSON for Google Sheets
- `GITHUB_REPO_OWNER`: GitHub repository owner for PR creation
- `GITHUB_REPO_NAME`: GitHub repository name for PR creation