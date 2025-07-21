# PRP-P3-002 Complete Lineage Integration

## Goal
Integrate lineage capture into actual PDF generation flow to achieve 100% capture rate

## Why
- **Business value**: Enables complete audit trail for every generated PDF, supporting compliance requirements and customer support
- **Integration**: Completes the lineage system implementation by connecting it to the actual report generation flow
- **Problems solved**: Currently lineage capture is not integrated with actual PDF generation, resulting in 0% capture rate

## What
Integrate the existing lineage tracking system into the ReportGenerator class to automatically capture lineage data for every PDF generation. This involves:
- Adding SQLAlchemy event listeners to capture report generation completion
- Integrating LineageCapture service into the PDF generation flow
- Ensuring 100% of PDFs have associated lineage records
- Performance optimization to keep overhead under 100ms

### Success Criteria
- [ ] 100% of new PDFs have lineage row captured
- [ ] LineageCapture integrated into ReportGenerator
- [ ] SQLAlchemy event listeners properly implemented
- [ ] Migration applied to create lineage tables
- [ ] Feature flag ENABLE_REPORT_LINEAGE working
- [ ] Performance overhead < 100ms
- [ ] Integration test verifying every PDF generation creates lineage record
- [ ] No breaking changes to existing report generation API
- [ ] Coverage ≥ 80% on modified code

## All Needed Context

### Documentation & References
```yaml
- url: https://docs.sqlalchemy.org/en/20/orm/events.html
  why: SQLAlchemy 2.0 event system documentation for implementing after_flush_postexec listeners
  
- url: https://docs.sqlalchemy.org/en/20/orm/session_events.html
  why: Session-level events for capturing post-flush operations
  
- file: d6_reports/generator.py
  why: Main report generator that needs lineage integration
  
- file: d6_reports/lineage/tracker.py
  why: Existing lineage tracking implementation to integrate
  
- file: d6_reports/lineage_integration.py
  why: Existing integration module with LineageCapture service
```

### Current Codebase Tree
```
d6_reports/
├── generator.py                 # ReportGenerator class (main integration point)
├── pdf_converter.py            # PDFConverter class
├── models.py                   # ReportGeneration model
├── lineage/
│   ├── __init__.py
│   ├── models.py              # ReportLineage model  
│   ├── tracker.py             # LineageTracker implementation
│   └── compressor.py          # Data compression utilities
└── lineage_integration.py     # LineageCapture service (exists but not integrated)

tests/
├── integration/
│   └── test_lineage_integration.py  # Integration tests
└── unit/
    └── lineage/
        └── test_tracker.py          # Unit tests
```

### Desired Codebase Tree
```
d6_reports/
├── generator.py                 # Modified: Integrated with LineageCapture
├── pdf_converter.py            # No changes
├── models.py                   # Modified: Event listeners added
├── lineage/
│   ├── __init__.py
│   ├── models.py              # No changes
│   ├── tracker.py             # No changes
│   └── compressor.py          # No changes
├── lineage_integration.py     # Modified: Enhanced integration
└── event_listeners.py         # New: SQLAlchemy event listeners

tests/
├── integration/
│   └── test_lineage_integration.py  # Modified: Enhanced tests
└── unit/
    ├── d6_reports/
    │   └── test_generator_lineage.py  # New: Test lineage in generator
    └── lineage/
        └── test_event_listeners.py    # New: Test event listeners
```

## Technical Implementation

### Integration Points
- `d6_reports/generator.py`: ReportGenerator.generate_report() method
- `d6_reports/models.py`: ReportGeneration model for event listeners
- `d6_reports/lineage_integration.py`: LineageCapture service
- `database/base.py`: Session configuration for event listeners

### Implementation Approach

1. **Create Event Listeners Module**
   - Implement after_flush_postexec listener for ReportGeneration
   - Use session.info to coordinate lineage capture
   - Handle both success and failure cases

2. **Integrate LineageCapture into ReportGenerator**
   - Initialize LineageCapture in ReportGenerator.__init__()
   - Start pipeline tracking at beginning of generate_report()
   - Capture lineage data throughout generation process
   - Complete lineage capture after PDF generation

3. **Modify Database Session Configuration**
   - Register event listeners at session factory level
   - Ensure listeners work with async sessions
   - Add feature flag checking in listeners

4. **Performance Optimization**
   - Use lightweight event listeners (no DB queries)
   - Batch lineage data collection in memory
   - Compress data asynchronously
   - Monitor performance impact

5. **Error Handling Strategy**
   - Lineage failures should not block report generation
   - Log errors but continue with report delivery
   - Use try/except blocks in all lineage operations
   - Provide fallback for disabled feature flag

6. **Testing Strategy**
   - Integration test with real PDF generation
   - Performance benchmarks for overhead measurement
   - Test with feature flag enabled/disabled
   - Verify 100% capture rate across multiple reports

## Validation Gates

### Executable Tests
```bash
# Syntax/Style
ruff check --fix d6_reports/ tests/
mypy d6_reports/

# Unit Tests
pytest tests/unit/d6_reports/test_generator_lineage.py -v
pytest tests/unit/lineage/test_event_listeners.py -v

# Integration Tests  
pytest tests/integration/test_lineage_integration.py::test_100_percent_capture_requirement -v
pytest tests/integration/test_lineage_integration.py::test_lineage_with_report_generator -v

# Performance Tests
pytest tests/integration/test_lineage_integration.py::test_performance_overhead -v -s

# Coverage Check
pytest tests/ -k "lineage" --cov=d6_reports --cov-report=term-missing
```

### Missing-Checks Validation
**Required for backend tasks:**
- [x] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [x] Branch protection & required status checks
- [x] Security scanning (Dependabot, Trivy, audit tools)
- [ ] API performance budgets (< 100ms overhead requirement)
- [ ] SQLAlchemy event listener registration verification
- [ ] Feature flag testing in CI

**Recommended:**
- [ ] Performance regression budgets (track lineage overhead)
- [ ] Automated CI failure handling
- [ ] Database migration rollback testing
- [ ] Event listener memory leak detection

## Dependencies
- SQLAlchemy >= 2.0 (for modern event system)
- pytest-asyncio >= 0.21.0 (for async test support)
- No new external dependencies required

## Rollback Strategy
1. Set ENABLE_REPORT_LINEAGE=false to disable all lineage capture
2. Remove event listeners from session factory if needed
3. Lineage tables remain but no new data is written
4. Existing report generation continues unaffected
5. Can re-enable without data loss

## Feature Flag Requirements
- **ENABLE_REPORT_LINEAGE**: Controls all lineage capture functionality
  - Default: true
  - When false: No lineage data captured, no performance impact
  - Checked in: LineageTracker, event listeners, ReportGenerator

## Implementation Notes

### Event Listener Pattern
```python
from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(Session, 'after_flush_postexec')
def capture_report_lineage(session, flush_context):
    """Capture lineage for any completed report generations"""
    if not settings.ENABLE_REPORT_LINEAGE:
        return
        
    # Check for ReportGeneration instances in session
    for obj in session.identity_map.values():
        if isinstance(obj, ReportGeneration) and obj in session.new:
            # Store lineage info in session.info for later processing
            if 'pending_lineage' not in session.info:
                session.info['pending_lineage'] = []
            session.info['pending_lineage'].append(obj.id)
```

### Integration in ReportGenerator
```python
async def generate_report(self, business_id: str, options: Optional[GenerationOptions] = None) -> GenerationResult:
    # Start lineage tracking
    if hasattr(self, 'lineage_capture') and settings.ENABLE_REPORT_LINEAGE:
        pipeline_run_id = await self.lineage_capture.start_pipeline(
            lead_id=business_id,
            template_version=options.template_name,
            initial_data={'business_id': business_id}
        )
    
    # ... existing generation logic ...
    
    # Complete lineage capture
    if hasattr(self, 'lineage_capture') and settings.ENABLE_REPORT_LINEAGE:
        await self.lineage_capture.capture_on_completion(
            report_generation_id=report.id,
            pipeline_run_id=pipeline_run_id,
            success=result.success
        )
```

### Performance Monitoring
- Add timing measurements around lineage operations
- Log warnings if overhead exceeds 50ms
- Use asyncio.create_task() for non-critical lineage operations
- Consider background task queue for heavy compression