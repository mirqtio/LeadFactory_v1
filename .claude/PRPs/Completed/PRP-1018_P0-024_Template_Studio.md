# PRP-P0-024 Template Studio

> 💡 **Claude Implementation Note**: Consider how task subagents can be used to execute portions of this task in parallel to improve efficiency and reduce overall completion time.

## Goal
Create a web-based Jinja2 template editor with live preview and GitHub PR workflow, enabling non-developers to safely modify report templates without deployment friction.

## Why  
- **Business value**: Empowers marketing and sales teams to iterate on report copy without engineering bottlenecks
- **Integration**: Leverages existing Jinja2 template system and GitHub-based version control
- **Problems solved**: Eliminates 2-3 day turnaround for simple copy changes, reduces developer interruptions

## What
Build a secure template editing interface featuring:
- Template listing with git metadata (SHA, last modified, author)
- Monaco editor with Jinja2 syntax highlighting
- Live preview pane rendering templates with sample lead data
- GitHub PR creation workflow for proposing changes
- Diff viewer showing before/after changes
- Role-based access control (viewers read-only, admins can propose changes)

### Success Criteria
- [ ] Template list displays git SHA and version metadata
- [ ] Monaco editor renders with Jinja2 syntax highlighting
- [ ] Preview renders in < 500ms with lead_id=1 sample data
- [ ] GitHub PR created with semantic commit message and diff using REAL GitHub API
- [ ] Viewers get read-only access, admins can propose changes
- [ ] Coverage ≥ 80% on template_studio module
- [ ] All existing tests remain green
- [ ] Integration tests demonstrate real GitHub PR creation and branch management
- [ ] Test repository configured and operational for CI/CD validation

## All Needed Context

### Documentation & References
```yaml
- url: https://microsoft.github.io/monaco-editor/api/index.html
  why: Official Monaco Editor API documentation for integration

- url: https://pygithub.readthedocs.io/en/latest/introduction.html
  why: PyGithub library for GitHub API integration
  
- url: https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request
  why: GitHub REST API documentation for PR creation

- url: https://jinja.palletsprojects.com/en/3.1.x/sandbox/
  why: Jinja2 sandboxed environment for secure template rendering

- file: d6_reports/generator.py
  why: Existing template rendering implementation to follow

- file: api/auth.py
  why: Authentication patterns for role-based access
```

### Current Codebase Tree
```
LeadFactory_v1_Final/
├── api/
│   ├── __init__.py
│   ├── auth.py           # Authentication utilities
│   └── main.py           # FastAPI app instance
├── d6_reports/
│   ├── generator.py      # Template rendering logic
│   └── templates/        # Jinja2 templates directory
├── core/
│   ├── config.py         # Settings and configuration
│   └── dependencies.py   # Shared dependencies
└── tests/
    └── unit/
        └── d6_reports/
            └── test_generator.py
```

### Desired Codebase Tree  
```
LeadFactory_v1_Final/
├── api/
│   ├── template_studio.py     # New API endpoints
│   └── main.py                # Register new router
├── d6_reports/
│   ├── template_manager.py    # New git/template utilities
│   └── templates/
├── static/                    # New directory
│   └── template_studio/
│       ├── index.html         # Studio UI
│       ├── editor.js          # Monaco integration
│       └── style.css          # Studio styles
├── tests/
│   └── unit/
│       ├── api/
│       │   └── test_template_studio.py
│       └── d6_reports/
│           └── test_template_manager.py
└── requirements.txt           # Add PyGithub, GitPython
```

## Technical Implementation

### Integration Points
- `api/main.py` - Register template_studio router
- `api/template_studio.py` - New endpoints for template operations
- `d6_reports/template_manager.py` - Git operations and template utilities
- `core/dependencies.py` - Add role-based auth dependency
- `static/template_studio/` - Frontend assets for the editor UI

### Implementation Approach
1. **Backend Setup**:
   - Install PyGithub and GitPython dependencies
   - Create template_manager.py for git operations
   - Implement API endpoints for listing, previewing, and proposing changes
   - Add WebSocket endpoint for real-time preview updates

2. **Frontend Development**:
   - Create static HTML/JS/CSS for template studio UI
   - Integrate Monaco editor via CDN with Jinja2 language support
   - Implement preview pane with debounced rendering
   - Build PR creation form with commit message input

3. **Security & Performance**:
   - Sandbox Jinja2 environment for safe rendering
   - Implement preview caching and debouncing
   - Add rate limiting for preview requests
   - Validate templates before rendering

4. **Error Handling Strategy**:
   - Graceful fallback for git operations failures
   - Clear error messages for invalid templates
   - GitHub API rate limit handling
   - Preview timeout handling

5. **Testing Strategy**:
   - Use real GitHub API integration with test repository
   - Create dedicated test repository for Template Studio CI/CD testing
   - Test template rendering with various Jinja2 constructs
   - Verify role-based access control
   - Test preview performance under load
   - Integration tests must use actual GitHub API calls
   - Unit tests can mock only for edge cases and error scenarios

## Validation Gates


### CI Validation (MANDATORY)
**CI Validation = Code merged to main + GitHub Actions logs verified + All errors resolved + Solid green CI run**

This means:
1. Code must be merged to the main branch (not just pushed)
2. GitHub Actions logs must be checked to confirm successful workflow completion
3. Any errors that appear during CI must be resolved
4. The final CI run must show all green checkmarks with no failures
5. This verification must be done by reviewing the actual GitHub Actions logs, not just assumed

**This is a mandatory requirement for PRP completion.**

### Executable Tests
```bash
# Syntax/Style
ruff check --fix && mypy .

# Unit Tests  
pytest tests/unit/api/test_template_studio.py -v
pytest tests/unit/d6_reports/test_template_manager.py -v

# Integration Tests (requires GITHUB_TOKEN and test repository)
GITHUB_TEST_REPO="leadfactory/template-studio-test" pytest tests/integration/test_template_studio_integration.py -v

# Performance Tests
pytest tests/performance/test_template_preview_speed.py -v
```

### Missing-Checks Validation
**Required for UI/Frontend tasks:**
- [ ] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [ ] Branch protection & required status checks
- [ ] Visual regression & accessibility testing
- [ ] Style-guide enforcement
- [ ] CSP headers for Monaco editor CDN
- [ ] XSS prevention in template preview

**Recommended:**
- [ ] Performance regression budgets (< 500ms preview)
- [ ] Automated CI failure handling
- [ ] Browser compatibility testing
- [ ] Memory leak detection for Monaco instances

## Dependencies
```txt
PyGithub==2.1.1        # GitHub API integration
GitPython==3.1.40      # Local git operations
python-multipart==0.0.6 # File upload support
websockets==12.0       # Real-time preview updates
```

## Environment Variables Required
```bash
# Required for GitHub API integration
GITHUB_TOKEN=<personal_access_token_with_repo_scope>
GITHUB_TEST_REPO=leadfactory/template-studio-test  # For integration tests
ENABLE_TEMPLATE_STUDIO=true  # Feature flag

# Optional
GITHUB_API_TIMEOUT=30  # Seconds
GITHUB_RATE_LIMIT_BUFFER=100  # Preserve this many API calls
```

## Rollback Strategy
1. Remove template_studio router from api/main.py
2. Delete api/template_studio.py and d6_reports/template_manager.py
3. Remove static/template_studio directory
4. Uninstall PyGithub and GitPython if not used elsewhere
5. Remove template_studio tests

## Feature Flag Requirements  
```python
# In core/config.py
ENABLE_TEMPLATE_STUDIO = env.bool("ENABLE_TEMPLATE_STUDIO", default=False)

# In api/main.py
if settings.ENABLE_TEMPLATE_STUDIO:
    from api.template_studio import router as template_studio_router
    app.include_router(template_studio_router, prefix="/api/template-studio")
```

## Real GitHub API Integration Requirements

### Test Repository Setup
1. Create dedicated test repository: `leadfactory/template-studio-test`
2. Configure GitHub App or Personal Access Token with repo permissions
3. Set up branch protection rules for testing PR workflow
4. Populate with sample templates for testing

### Integration Test Configuration
```python
# tests/integration/conftest.py
import pytest
from github import Github
import os

@pytest.fixture
def github_test_repo():
    """Fixture for real GitHub API testing."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set for integration tests")
    
    g = Github(token)
    repo = g.get_repo("leadfactory/template-studio-test")
    
    # Clean up any test branches before test
    for branch in repo.get_branches():
        if branch.name.startswith("test-"):
            repo.get_git_ref(f"heads/{branch.name}").delete()
    
    return repo
```

### Real API Testing Strategy
1. **Unit Tests**: Mock only for error scenarios and edge cases
2. **Integration Tests**: Always use real GitHub API with test repository
3. **CI/CD Tests**: Run integration tests with GitHub secrets
4. **Local Development**: Developers must set GITHUB_TOKEN for full testing

## Additional Considerations

### Monaco Editor Setup
```javascript
// Jinja2 language definition
monaco.languages.register({ id: 'jinja2' });
monaco.languages.setMonarchTokensProvider('jinja2', {
    tokenizer: {
        root: [
            [/\{\{/, { token: 'delimiter.jinja2', next: '@expression' }],
            [/\{%/, { token: 'delimiter.jinja2', next: '@statement' }],
            [/\{#/, { token: 'comment.jinja2', next: '@comment' }],
        ],
        expression: [
            [/\}\}/, { token: 'delimiter.jinja2', next: '@pop' }],
            [/[^}]+/, 'variable.jinja2']
        ],
        statement: [
            [/%\}/, { token: 'delimiter.jinja2', next: '@pop' }],
            [/(if|for|endif|endfor|else|elif|set|include|extends|block|endblock)/, 'keyword.jinja2'],
            [/[^%]+/, 'string.jinja2']
        ],
        comment: [
            [/#\}/, { token: 'comment.jinja2', next: '@pop' }],
            [/[^#]+/, 'comment.jinja2']
        ]
    }
});
```

### GitHub PR Creation (Real API Integration)
```python
# Real GitHub API integration - NO MOCKS in production code
def create_template_pr(repo_name: str, changes: dict, user: str):
    """Create a real GitHub PR using the actual GitHub API.
    
    This function MUST use real GitHub API calls in production.
    Test environment should use a dedicated test repository.
    """
    g = Github(auth=Auth.Token(settings.GITHUB_TOKEN))
    repo = g.get_repo(repo_name)
    
    # Create new branch
    base_branch = repo.get_branch("main")
    new_branch = f"template-update-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    repo.create_git_ref(f"refs/heads/{new_branch}", base_branch.commit.sha)
    
    # Update files
    for file_path, content in changes.items():
        file = repo.get_contents(file_path, ref="main")
        repo.update_file(
            file_path,
            f"Update template: {file_path}",
            content,
            file.sha,
            branch=new_branch
        )
    
    # Create PR
    pr = repo.create_pull(
        title=f"Template Update by {user}",
        body=f"""## Template Studio Update
        
        Updated by: {user}
        Timestamp: {datetime.now().isoformat()}
        
        ### Changes
        - Modified templates via Template Studio
        
        🤖 Generated with [LeadFactory Template Studio](https://leadfactory.com/template-studio)
        """,
        base="main",
        head=new_branch
    )
    
    return pr.html_url
```

### Preview Security
```python
# Sandboxed Jinja2 environment
from jinja2.sandbox import SandboxedEnvironment

def create_safe_environment():
    env = SandboxedEnvironment(
        autoescape=True,
        loader=FileSystemLoader('d6_reports/templates')
    )
    # Restrict dangerous operations
    env.globals = {
        'range': range,
        'len': len,
        'str': str,
        'int': int,
        'float': float,
    }
    return env
```