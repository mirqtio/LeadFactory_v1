# P0-022 - Batch Report Runner
**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 5 days
**Dependencies**: P0-021

## Goal & Success Criteria

### Goal
Enable the CPO to pick any set of leads, preview cost, and launch a bulk report run with real-time progress tracking via WebSocket updates.

### Success Criteria
1. Lead multi-select interface with filtering capabilities
2. Cost preview calculation accurate within ±5% of actual spend
3. WebSocket progress updates delivered every 2 seconds during processing
4. Individual lead failures logged without stopping batch execution
5. Test coverage ≥80% on batch_runner module
6. Batch status API endpoints respond in <500ms
7. Progress updates properly throttled (≥1 msg/2s, ≤1 msg/s)
8. Comprehensive error reporting for failed leads

## Context & Background

### Business Context
Bulk processing is the CPO's core "job-to-be-done" - they need to efficiently generate reports for multiple leads while maintaining cost visibility and control. Current one-by-one processing is inefficient and provides no batch cost estimates.

### Technical Context
- Builds on P0-021 Lead Explorer for lead selection
- Integrates with existing Prefect pipeline for report generation
- Requires WebSocket support for real-time progress tracking
- Must respect cost guardrails from P1-060
- Failed individual leads should not halt entire batch

### Research Findings
- FastAPI WebSockets with ConnectionManager pattern for multi-client support
- Batch processing at HTTP layer using aiohttp for better performance
- Cost calculation should use configurable blended rates with caching
- WebSocket connections need authentication and compression for production
- Progress throttling prevents client overwhelm while maintaining responsiveness

## Technical Approach

### Architecture Overview
1. **API Layer**: New batch runner endpoints with WebSocket support
2. **Processing Layer**: Resilient batch processor with error isolation
3. **Cost Layer**: Configurable cost calculator with provider rates
4. **WebSocket Layer**: Connection manager with throttled broadcasts
5. **Database Layer**: Batch tracking tables for state persistence

### Component Design

#### WebSocket Connection Manager
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.throttle = AsyncThrottle(rate_limit=1, period=2.0)
    
    async def connect(self, batch_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[batch_id] = websocket
    
    async def broadcast_progress(self, batch_id: str, progress: dict):
        async with self.throttle:
            if batch_id in self.active_connections:
                await self.active_connections[batch_id].send_json(progress)
```

#### Cost Calculator
```python
class CostCalculator:
    def __init__(self, config_path: str = "config/costs.json"):
        self.rates = self._load_rates(config_path)
        self.cache_ttl = 300  # 5 minutes
    
    def calculate_batch_cost(self, lead_count: int, template_version: str) -> Decimal:
        blended_rate = self.rates.get("default_blended_rate", 0.45)
        base_cost = self.rates.get("report_generation_base_cost", 0.05)
        return Decimal(lead_count * (blended_rate + base_cost))
```

#### Batch Processor
```python
class BatchProcessor:
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.max_concurrent = settings.BATCH_MAX_CONCURRENT_LEADS
    
    async def process_batch(self, batch_id: str, lead_ids: List[str]):
        semaphore = asyncio.Semaphore(self.max_concurrent)
        tasks = [self._process_lead(lead_id, semaphore) for lead_id in lead_ids]
        
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            progress = {
                "processed": i + 1,
                "total": len(lead_ids),
                "percentage": ((i + 1) / len(lead_ids)) * 100
            }
            await self.connection_manager.broadcast_progress(batch_id, progress)
```

### API Endpoints

1. **POST /api/batch/preview**
   - Input: List of lead IDs, template version
   - Output: Cost estimate, lead count, estimated duration
   - Response time: <200ms

2. **POST /api/batch/start**
   - Input: Lead IDs, template version, cost acceptance
   - Output: Batch ID, WebSocket URL
   - Creates batch_reports record

3. **GET /api/batch/{batch_id}/status**
   - Output: Current status, progress, errors
   - Response time: <500ms

4. **WS /api/batch/{batch_id}/progress**
   - WebSocket endpoint for real-time updates
   - Throttled to 1 message per 2 seconds
   - Includes progress percentage, current lead, errors

## Acceptance Criteria

1. **Lead Selection**
   - Multi-select interface with checkbox support
   - Filter by status, date range, score tier
   - Select all/none functionality
   - Visual indication of selection count

2. **Cost Preview**
   - Display total estimated cost before processing
   - Breakdown by provider if available
   - Warning if exceeds daily budget
   - Accuracy within ±5% of actual

3. **Batch Processing**
   - Process up to 1000 leads per batch
   - Concurrent processing with configurable limit
   - Individual failures don't stop batch
   - Detailed error logging per lead

4. **Progress Tracking**
   - WebSocket updates every 2 seconds
   - Show current lead being processed
   - Display success/failure counts
   - Estimated time remaining

5. **Error Handling**
   - Retry failed leads up to 3 times
   - Log detailed error messages
   - Provide downloadable error report
   - Email notification on completion

## Dependencies

### Codebase Dependencies
- P0-021: Lead Explorer for lead selection UI
- D11 Orchestration: Pipeline execution
- D10 Analytics: Cost tracking integration

### External Dependencies
```python
# requirements.txt additions
websockets==12.0          # WebSocket server support
aiofiles==23.2.1         # Async file operations
asyncio-throttle==1.0.2  # Rate limiting for broadcasts

# requirements-dev.txt additions
pytest-asyncio==0.21.1   # Async test support
httpx==0.25.2           # WebSocket testing
```

## Testing Strategy

### Unit Tests (80% coverage)
1. **test_cost_calculator.py**
   - Test rate loading and caching
   - Verify calculation accuracy
   - Test edge cases (0 leads, missing rates)

2. **test_websocket_manager.py**
   - Connection/disconnection handling
   - Broadcast throttling verification
   - Multiple client support

3. **test_batch_processor.py**
   - Concurrent processing limits
   - Error isolation verification
   - Progress calculation accuracy

### Integration Tests
1. **test_batch_runner_integration.py**
   - End-to-end batch processing
   - WebSocket connection lifecycle
   - Cost preview to actual comparison
   - Database state verification

### Load Tests
1. Verify 500ms response time under load
2. Test WebSocket with 100 concurrent connections
3. Process 1000-lead batch within SLA

### Chaos Tests
1. Random lead failures during batch
2. WebSocket disconnection handling
3. Database connection failures

## Rollback Plan

### Immediate Rollback (< 5 minutes)
1. Disable feature flag `ENABLE_BATCH_PROCESSING`
2. Remove batch runner routes from API
3. Stop any running batch processes

### Full Rollback (< 30 minutes)
1. Execute immediate rollback steps
2. Run migration rollback:
   ```sql
   DROP TABLE batch_report_leads;
   DROP TABLE batch_reports;
   ```
3. Remove batch_runner module and tests
4. Revert requirements.txt changes
5. Clear Redis keys with pattern `batch:*`

### Rollback Triggers
- Critical errors affecting lead processing
- Cost calculations significantly incorrect (>10% deviation)
- WebSocket connections causing memory leaks
- Database performance degradation

## Validation Framework


### CI Validation (MANDATORY)
**CI Validation = Code merged to main + GitHub Actions logs verified + All errors resolved + Solid green CI run**

This means:
1. Code must be merged to the main branch (not just pushed)
2. GitHub Actions logs must be checked to confirm successful workflow completion
3. Any errors that appear during CI must be resolved
4. The final CI run must show all green checkmarks with no failures
5. This verification must be done by reviewing the actual GitHub Actions logs, not just assumed

**This is a mandatory requirement for PRP completion.**

### Pre-Deployment Validation
1. **Code Quality**
   ```bash
   ruff check --fix api/batch_runner.py d11_orchestration/batch_*.py
   mypy api/batch_runner.py d11_orchestration/batch_*.py --strict
   ```

2. **Test Coverage**
   ```bash
   pytest tests/unit/d11_orchestration/test_batch_*.py \
          tests/integration/test_batch_runner_integration.py \
          --cov=d11_orchestration.batch_processor \
          --cov=d11_orchestration.cost_calculator \
          --cov=d11_orchestration.websocket_manager \
          --cov=api.batch_runner \
          --cov-report=term-missing \
          --cov-fail-under=80
   ```

3. **Security Checks**
   - WebSocket authentication required
   - Rate limiting on connections
   - Input validation on lead IDs
   - SQL injection prevention

### Post-Deployment Validation
1. **Smoke Tests**
   - Create small batch (5 leads)
   - Verify cost preview accuracy
   - Check WebSocket updates
   - Confirm database records

2. **Performance Tests**
   - API response times <500ms
   - WebSocket message delivery <2s
   - Memory usage stable
   - Database query performance

3. **Business Validation**
   - Cost calculations match finance team expectations
   - Progress updates clear to CPO users
   - Error messages actionable
   - Batch completion notifications working

### Missing-Checks Framework
**Required for Backend/API tasks:**
- [x] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [x] Branch protection with required status checks
- [x] Security scanning for WebSocket vulnerabilities
- [x] API performance budgets (<500ms)
- [x] Rate limiting on WebSocket connections
- [x] Cost guardrail integration

**Recommended additions:**
- [ ] WebSocket connection monitoring (Prometheus)
- [ ] Automated load testing in CI
- [ ] Batch processing performance regression tests
- [ ] Cost calculation accuracy tests with production data