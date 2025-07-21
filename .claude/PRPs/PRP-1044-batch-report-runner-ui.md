# P1-044 - Batch Report Runner UI
**Priority**: P1
**Status**: Not Started
**Estimated Effort**: 4 days
**Dependencies**: P1-037, P1-016

## Goal & Success Criteria
Create a comprehensive operational dashboard UI for the Batch Report Runner that provides real-time monitoring, control, and analytics for bulk lead processing operations with intuitive user experience and production-ready reliability.

## Context & Background
The Batch Report Runner is a critical operational component that processes bulk lead assessments for clients. Currently, the system has a basic static HTML interface that lacks real-time monitoring capabilities, requiring operators to use SSH access and log files to monitor batch processing status.

**Business value**: Enables operational staff to efficiently manage batch processing at scale, reducing manual oversight and improving system reliability through proper monitoring and control interfaces

**Integration**: Builds upon existing Batch Runner API (PRP-1016) and integrates with global navigation shell (PRP-1037) to provide seamless operational workflows

**Problems solved**: 
- Manual batch monitoring requiring SSH/log access
- Lack of real-time visibility into processing status and errors
- No standardized interface for batch operations (start, pause, cancel, retry)
- Missing analytics for capacity planning and cost optimization
- Inconsistent UI patterns across operational tools

## Technical Approach

### Architecture Strategy
Develop a modern, responsive operational dashboard using progressive enhancement:

1. **Progressive Enhancement Strategy**
   - Start with server-side rendered HTML for baseline functionality
   - Add JavaScript components for enhanced interactivity
   - Implement WebSocket connections for real-time updates
   - Ensure graceful degradation when JavaScript is disabled

2. **Component Architecture**
   - Modular JavaScript components using ES6 modules
   - Event-driven communication between components
   - Centralized state management for UI consistency
   - Reactive data binding for real-time updates

3. **Real-time Communication**
   - WebSocket client with automatic reconnection
   - Message queuing during connection interruptions
   - Optimistic UI updates with server reconciliation
   - Rate limiting to prevent UI overwhelming (1 update per 2 seconds)

### Core Features
1. **Real-time Batch Monitoring Dashboard**
   - Live progress tracking with WebSocket updates
   - Visual status indicators and progress bars
   - Queue depth and processing velocity metrics
   - Error rate monitoring and alerting

2. **Batch Control Interface**
   - Start new batch processing with cost preview
   - Pause, resume, and cancel running batches
   - Retry failed batches with selective lead reprocessing
   - Bulk operations for queue management

3. **Analytics and Reporting**
   - Historical batch performance metrics
   - Cost tracking and budget utilization
   - Processing time trends and capacity planning
   - Error pattern analysis and resolution guidance

4. **Operational Tools**
   - Lead selection and batch composition tools
   - Template version selection and configuration
   - Cost estimation with provider breakdown
   - Health monitoring and system status

## Acceptance Criteria
1. [ ] Real-time dashboard displays batch status with <2s update latency
2. [ ] Progressive web app functionality for mobile monitoring
3. [ ] Accessibility compliance (WCAG 2.1 AA) with keyboard navigation
4. [ ] Single-screen layout optimized for 1920x1080 displays
5. [ ] Error handling with graceful degradation for API failures
6. [ ] Coverage ≥ 80% on UI component tests
7. [ ] Performance: Initial load <3s, interactions <200ms
8. [ ] WebSocket reconnection and state recovery on network issues

## Dependencies
- **P1-037**: Global Navigation Shell (for navigation integration)
- **P1-016**: Batch Runner API (provides backend functionality)
- **Existing**: FastAPI application with WebSocket support
- **Existing**: Design system CSS tokens and component patterns
- **Existing**: Bootstrap 5.2.3 and Bootstrap Icons for base styling
- **New**: ES6 module support for component architecture
- **New**: WebSocket client library for real-time communication

## Testing Strategy

### Unit Testing
- JavaScript component tests using Jest or similar framework
- Data formatting and validation utility tests
- WebSocket client connection and message handling tests
- API client wrapper functionality tests

### Integration Testing  
- End-to-end UI workflow testing with Playwright
- WebSocket real-time communication testing
- API integration with batch runner endpoints
- Cross-browser compatibility testing (Chrome, Firefox, Safari, Edge)

### Accessibility Testing
- WCAG 2.1 AA compliance testing with axe-core
- Keyboard navigation testing
- Screen reader compatibility testing
- Color contrast and visual accessibility validation

### Performance Testing
- Page load performance benchmarking (target: <3s initial load)
- WebSocket message handling performance testing
- Mobile responsiveness testing
- Progressive web app functionality validation

### Coverage Requirements
- Unit test coverage ≥ 80%
- Integration test coverage for all critical user workflows
- Cross-browser testing on latest stable versions
- Mobile device testing on iOS Safari and Chrome Mobile

## Rollback Plan

### Immediate Rollback (< 5 minutes)
1. **Revert File Replacement**: Replace enhanced static/batch_runner/index.html with previous version
2. **Feature Flag Toggle**: Disable batch_runner_enhanced_ui flag to fall back to basic interface
3. **CDN Cache Invalidation**: Clear any cached assets to ensure immediate rollback

### Gradual Rollback (Progressive)
1. **Component-Level Rollback**: Disable specific features via feature flags while maintaining core functionality
2. **WebSocket Graceful Degradation**: Fall back to polling-based updates if WebSocket connections fail
3. **JavaScript Failure Handling**: Ensure server-rendered HTML remains functional without JavaScript

### Rollback Triggers
- Critical JavaScript errors affecting >10% of users
- WebSocket connection failures preventing real-time updates
- Accessibility compliance failures
- Performance degradation >50% compared to baseline
- Any security vulnerabilities identified in new UI components

### Rollback Validation
- Verify basic batch monitoring functionality works
- Confirm API endpoints remain accessible
- Test core batch operations (start, stop, cancel)
- Validate error handling and user feedback mechanisms

## Validation Framework

### Executable Validation Tests
```bash
# Syntax/Style
ruff check --fix static/batch_runner/ && \
eslint static/batch_runner/components/ static/batch_runner/services/

# Unit Tests  
pytest tests/integration/test_batch_runner_ui.py -v

# Integration Tests
pytest tests/e2e/test_batch_dashboard_workflows.py -v

# Accessibility Tests
axe-core static/batch_runner/index.html
```

### Missing-Checks Framework
**Required for UI/Frontend tasks:**
- [ ] Pre-commit hooks (ruff, mypy, eslint, stylelint)
- [ ] Branch protection & required status checks
- [ ] Visual regression testing with screenshot comparison
- [ ] Style-guide enforcement using design system tokens
- [ ] Cross-browser compatibility testing (Chrome, Firefox, Safari, Edge)
- [ ] Mobile responsiveness validation
- [ ] WCAG 2.1 AA accessibility compliance testing

**Recommended:**
- [ ] Performance regression budgets (Lighthouse scores)
- [ ] WebSocket connection resilience testing
- [ ] Progressive web app manifest and service worker
- [ ] Analytics integration for usage tracking

### Documentation References
```yaml
- url: https://fastapi.tiangolo.com/tutorial/background-tasks/
  why: Official FastAPI background task patterns for WebSocket integration

- url: https://www.uxpin.com/studio/blog/dashboard-design-principles/
  why: 2025 dashboard design principles for operational monitoring

- url: https://github.com/romanzipp/Laravel-Queue-Monitor
  why: Reference implementation for queue monitoring dashboard patterns

- file: batch_runner/api.py
  why: Existing API endpoints and WebSocket patterns to integrate with

- file: batch_runner/models.py
  why: Data models and status enums to display in UI

- file: static/design_system/design_system.css
  why: Design system tokens and component patterns to maintain consistency

- file: static/batch_runner/index.html
  why: Current batch runner UI to enhance and replace
```

### Implementation Context
**Current Codebase Structure:**
```
static/batch_runner/index.html                 # Basic static HTML template
batch_runner/api.py                            # FastAPI endpoints with WebSocket
batch_runner/models.py                         # Database models and enums
static/design_system/design_system.css         # Design tokens and CSS variables
```

**Desired Codebase Structure:**
```
static/batch_runner/
├── index.html                                 # Enhanced operational dashboard
├── components/batch-monitor.js                # Real-time monitoring component
├── services/websocket-client.js              # WebSocket connection manager
├── styles/dashboard.css                       # Dashboard-specific styles
└── utils/formatters.js                       # Data formatting utilities

tests/integration/test_batch_runner_ui.py      # End-to-end UI tests
```

### Integration Requirements
- **WebSocket Integration**: Connect to `/api/v1/batch/{batch_id}/progress` for real-time updates
- **REST API Endpoints**: Integrate with all batch_runner/api.py endpoints for CRUD operations
- **Navigation Shell**: Embed within global navigation framework from PRP-1037
- **Design System**: Use design tokens from static/design_system/design_system.css
- **Authentication**: Integrate with existing auth middleware for user context