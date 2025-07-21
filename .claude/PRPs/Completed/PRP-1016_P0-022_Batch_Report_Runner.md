# PRP-P3-004 Create Batch Runner UI

## Goal
Create web UI for Batch Report Runner with lead selection and progress tracking

## Why  
- **Business value**: Provides user-friendly interface for batch report generation, replacing direct API calls
- **Integration**: Complements existing batch_runner API module with visual interface
- **Problems solved**: Enables non-technical users to manage batch reports, monitor progress in real-time, and preview costs

## What
Build a React-based web UI for the Batch Report Runner that provides:
- Lead multi-select interface with filters
- Template/version picker with default to latest
- Cost preview showing estimated spend before execution
- Real-time progress tracking via WebSocket
- Batch history and management capabilities

### Success Criteria
- [ ] Lead table displays with multi-select checkboxes and filters
- [ ] Cost preview shows within ±5% accuracy of actual spend
- [ ] WebSocket connection provides updates every 2 seconds during processing
- [ ] UI responsive on mobile devices (320px+)
- [ ] Cancel batch functionality works correctly
- [ ] Coverage ≥ 80% on UI tests
- [ ] Performance: Initial load < 2s, WebSocket latency < 100ms
- [ ] Accessibility: WCAG 2.1 AA compliant
- [ ] Edge cases handled:
  - [ ] WebSocket connection loss during batch processing
  - [ ] Browser refresh/navigation during active batch
  - [ ] Concurrent batch attempts by same user
  - [ ] Empty lead selection validation
  - [ ] Template version no longer available

## All Needed Context

### Documentation & References
```yaml
- url: https://fastapi.tiangolo.com/advanced/websockets/
  why: WebSocket implementation pattern for real-time updates
  
- url: https://ably.com/blog/websockets-react-tutorial
  why: React WebSocket integration best practices

- url: https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3
  why: Performance optimization for WebSocket UI
  
- file: batch_runner/api.py
  why: API endpoints and WebSocket handler to integrate with

- file: static/template_studio/index.html
  why: Pattern for standalone UI integration in LeadFactory

- file: static/governance/index.html  
  why: Reference for similar UI with WebSocket updates
```

### Current Codebase Tree
```
batch_runner/
├── __init__.py
├── api.py              # REST endpoints + WebSocket handler
├── cost_calculator.py  # Cost estimation logic
├── models.py          # SQLAlchemy models
├── processor.py       # Batch processing logic
├── schemas.py         # Pydantic schemas
└── websocket_manager.py # WebSocket connection management

static/
├── template_studio/   # Reference UI implementation
├── scoring-playground/
├── governance/
└── lineage/
```

### Desired Codebase Tree  
```
batch_runner/
└── [existing files]

static/
├── batch_runner/      # NEW
│   ├── index.html     # Main UI entry point
│   ├── app.js         # React application
│   ├── styles.css     # UI styling
│   └── components/    # React components
│       ├── LeadSelector.js
│       ├── CostPreview.js
│       ├── ProgressTracker.js
│       └── BatchHistory.js
└── [existing folders]

main.py                # Mount new static directory
```

## Technical Implementation

### Integration Points
- `main.py`: Add static mount for `/static/batch_runner`
- `batch_runner/api.py`: Connect to existing WebSocket endpoint at `/api/batch/ws`
- `batch_runner/schemas.py`: Use existing schemas for API requests
- Design tokens from `design/design_tokens.json` for consistent styling

### Implementation Approach
1. **UI Structure**:
   - Single-page React application with component-based architecture
   - Use react-use-websocket hook for WebSocket management
   - Implement useMemo for performance optimization
   - Add proper cleanup in useEffect for WebSocket connections

2. **Component Design**:
   - LeadSelector: Table with filters, pagination, multi-select
   - CostPreview: Real-time cost calculation with template selection
   - ProgressTracker: WebSocket-powered progress bar with cancel button
   - BatchHistory: List of past batches with status and rerun options

3. **WebSocket Strategy**:
   - Single multiplexed connection for all updates
   - Automatic reconnection with exponential backoff
   - Message throttling to prevent UI overload
   - Heartbeat/ping-pong for connection health

4. **Error Handling**:
   - Graceful degradation if WebSocket fails
   - User-friendly error messages with specific codes:
     - 429 Rate Limit: Exponential backoff starting at 1s
     - 503 Service Unavailable: Retry 3x with 2s delay
     - WebSocket disconnect: Reconnect with backoff (1s, 2s, 4s, 8s, max 16s)
   - Clear feedback for rate limiting with countdown timer

5. **Testing Strategy**:
   - Jest + React Testing Library for component tests
   - Mock WebSocket for deterministic testing
   - Cypress/Playwright for E2E WebSocket flow
   - Visual regression tests for UI components

## Validation Gates

### Executable Tests
```bash
# Syntax/Style
npm run lint --prefix static/batch_runner
npm run format:check --prefix static/batch_runner

# Unit Tests  
npm test --prefix static/batch_runner -- --coverage

# Integration Tests
pytest tests/integration/test_batch_runner_ui.py -v

# E2E Tests
npm run test:e2e --prefix static/batch_runner
```

### Missing-Checks Validation
**Required for UI tasks:**
- [ ] Pre-commit hooks configuration:
  ```yaml
  # .pre-commit-config.yaml
  repos:
    - repo: https://github.com/pre-commit/pre-commit-hooks
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
    - repo: https://github.com/pre-commit/mirrors-eslint
      hooks:
        - id: eslint
          files: \.(js|jsx)$
          args: ['--fix']
    - repo: https://github.com/pre-commit/mirrors-prettier
      hooks:
        - id: prettier
          files: \.(js|jsx|css|json)$
  ```
- [ ] Accessibility testing (axe-core in CI)
- [ ] Bundle size monitoring (<250KB gzipped)
- [ ] Visual regression testing via Chromatic
- [ ] Browser compatibility testing (Chrome, Firefox, Safari)
- [ ] Mobile responsive testing (320px - 1920px)
- [ ] WebSocket connection resilience testing
- [ ] Branch protection with required status checks

**Recommended:**
- [ ] Performance budgets (FCP < 1.5s, TTI < 3.5s)
- [ ] Lighthouse CI integration (scores > 90)
- [ ] Error tracking integration (Sentry)
- [ ] Real User Monitoring (RUM)

## Dependencies
- React 18.2.0 (for concurrent features)
- react-use-websocket 4.5.0 (WebSocket hook)
- axios 1.6.2 (HTTP client)
- tailwindcss 3.4.0 (styling framework)
- @testing-library/react 14.0.0 (testing)
- jest 29.7.0 (test runner)
- Design tokens from P0-020

## Rollback Strategy
1. Remove static mount from `main.py`
2. Delete `static/batch_runner` directory
3. No database changes required
4. Feature flag: `ENABLE_BATCH_RUNNER_UI=false`

## Feature Flag Requirements  
- `ENABLE_BATCH_RUNNER_UI`: Controls UI mount in main.py
- `BATCH_RUNNER_MOCK_MODE`: Enable mock data for development
- `BATCH_RUNNER_WS_DEBUG`: Enable WebSocket debug logging