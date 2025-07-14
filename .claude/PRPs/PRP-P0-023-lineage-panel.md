# PRP-P0-023 Lineage Panel

> 💡 **Claude Implementation Note**: Consider how task subagents can be used to execute portions of this task in parallel to improve efficiency and reduce overall completion time.

## Goal
Persist and surface the {lead_id, pipeline_run_id, template_version_id} triplet for every PDF, with click-through to raw inputs

## Why
- **Business value**: Enables lightning-fast debugging, compliance audits, and transparent customer support
- **Integration**: Integrates with existing report generation flow to capture complete lineage metadata
- **Problems solved**: Addresses lack of visibility into report generation history, inability to trace data sources, and difficulty debugging report issues

## What
Create a comprehensive report lineage tracking system that:
1. Captures detailed lineage information for every PDF report generated
2. Provides API endpoints to query lineage data
3. Includes a web console panel for viewing lineage information
4. Supports downloading compressed raw input data
5. Implements audit trail for all lineage operations

### Success Criteria
- [ ] Report lineage table created with proper schema and indexes
- [ ] 100% of new PDFs have lineage row captured
- [ ] JSON log viewer loads < 500ms
- [ ] Raw input downloads compressed to ≤2MB with gzip
- [ ] Test coverage ≥80% on lineage_panel module
- [ ] Audit trail captures all lineage data access

## All Needed Context

### Documentation & References
```yaml
- url: https://docs.python.org/3/library/gzip.html
  why: Official Python gzip documentation for compression implementation
  
- url: https://docs.sqlalchemy.org/en/20/orm/session_events.html
  why: SQLAlchemy event system for automatic lineage capture
  
- url: https://fastapi.tiangolo.com/advanced/custom-response/
  why: FastAPI custom response classes for JSON viewer and downloads
  
- file: d6_reports/models.py
  why: Existing report generation models to extend with lineage
  
- file: d6_reports/pdf_converter.py
  why: PDF generation flow where lineage capture needs to be integrated
```

### Current Codebase Tree
```
LeadFactory_v1_Final/
├── d6_reports/
│   ├── models.py          # Report generation models
│   ├── pdf_converter.py   # PDF generation logic
│   └── generator.py       # Report generator
├── api/
│   └── internal_routes.py # Existing API routes
├── alembic/versions/      # Database migrations
└── tests/unit/d6_reports/ # Existing report tests
```

### Desired Codebase Tree
```
LeadFactory_v1_Final/
├── d6_reports/
│   ├── models.py          # Extended with lineage models
│   ├── pdf_converter.py   # Updated with lineage capture
│   ├── generator.py       # Updated with lineage integration
│   └── lineage/           # New lineage module
│       ├── __init__.py
│       ├── models.py      # Lineage-specific models
│       ├── tracker.py     # Lineage tracking logic
│       └── compressor.py  # Data compression utilities
├── api/
│   ├── internal_routes.py # Existing routes
│   └── lineage/           # New lineage API
│       ├── __init__.py
│       ├── routes.py      # Lineage API endpoints
│       └── schemas.py     # Pydantic schemas
├── alembic/versions/
│   └── xxx_add_report_lineage.py # New migration
└── tests/unit/
    ├── d6_reports/        # Existing tests
    └── lineage/           # New lineage tests
        ├── __init__.py
        ├── test_models.py
        ├── test_tracker.py
        ├── test_api.py
        └── test_compressor.py
```

## Technical Implementation

### Integration Points
- `d6_reports/models.py`: Add ReportLineage model with relationships
- `d6_reports/pdf_converter.py`: Hook into PDF generation completion with event listeners
- `d6_reports/generator.py`: Capture pipeline run context and pass to lineage tracker
- `d6_reports/base.py`: Add lineage capture to report generation base flow
- `api/internal_routes.py`: Mount new lineage router
- `alembic/versions/`: Create migration for lineage tables

### Implementation Approach

1. **Database Schema**
   - Create `report_lineage` table with optimized indexes
   - Add foreign key to `d6_report_generations`
   - Include audit columns (created_at, accessed_at, accessed_by)

2. **Lineage Capture Integration**
   - Hook into `PDFConverter.convert()` method to capture lineage after successful PDF generation
   - Add `capture_lineage` parameter to `ReportGenerator.generate()` method
   - Use SQLAlchemy event listeners on ReportGeneration model:
     ```python
     @event.listens_for(ReportGeneration, 'after_insert')
     def capture_report_lineage(mapper, connection, target):
         if settings.ENABLE_REPORT_LINEAGE:
             lineage_tracker.capture(target)
     ```
   - Capture full pipeline context during PDF generation:
     - Extract lead_id, pipeline_run_id, template_version_id from ReportGeneration
     - Get pipeline logs from Prefect context or execution metadata
     - Capture raw inputs from assessment and enrichment data
   - Store raw inputs in compressed format using gzip

3. **API Implementation**
   - GET /api/lineage/{report_id} - Retrieve lineage data
   - GET /api/lineage/search - Search lineage by criteria
   - GET /api/lineage/{lineage_id}/logs - View JSON logs
   - GET /api/lineage/{lineage_id}/download - Download raw inputs

4. **Compression Strategy**
   - Use gzip level 6 for balance of speed/size
   - Stream large data to avoid memory issues
   - Implement size checks before storage

5. **Error Handling**
   - Graceful degradation if lineage capture fails
   - Log but don't block report generation
   - Handle compression errors with fallback

6. **Testing Strategy**
   - Unit tests for each component
   - Integration tests for full flow
   - Performance tests for viewer and downloads
   - Mock compression for deterministic tests

## Integration Flow Details

### Step-by-Step PDF Generation Integration

1. **ReportGeneration Creation**
   - When a report is requested, `ReportGenerator.generate()` creates a `ReportGeneration` record
   - This record includes: lead_id, pipeline_run_id, template_version_id
   - Status is set to "in_progress"

2. **HTML Generation**
   - Report HTML is generated using the Jinja2 template
   - Assessment and enrichment data is collected for the lead
   - This raw data will be captured for lineage

3. **PDF Conversion with Lineage Capture**
   - `PDFConverter.convert()` is called with HTML and ReportGeneration instance
   - PDF is generated from HTML
   - **CRITICAL**: After successful PDF generation, lineage is captured:
     ```python
     if settings.ENABLE_REPORT_LINEAGE:
         await lineage_tracker.capture_from_report_generation(report_gen)
     ```

4. **Lineage Data Collection**
   - LineageTracker extracts all metadata from ReportGeneration
   - Pipeline logs are retrieved from execution context
   - Raw inputs (assessment + enrichment data) are collected
   - All data is compressed using gzip

5. **Lineage Storage**
   - Compressed data is stored in report_lineage table
   - Foreign key links to d6_report_generations
   - Audit fields are populated (created_at, etc.)

### Ensuring 100% Capture Rate

To guarantee every PDF has lineage captured:

1. **Atomic Transaction**: Lineage capture happens within the same database transaction as PDF generation
2. **Rollback on Failure**: If lineage capture fails, the entire report generation is rolled back
3. **Monitoring**: Add metrics to track lineage capture success rate
4. **Validation**: Integration tests verify lineage exists for every generated PDF

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
ruff check d6_reports/lineage api/lineage --fix
mypy d6_reports/lineage api/lineage

# Unit Tests
pytest tests/unit/lineage -v
pytest tests/unit/d6_reports/test_lineage_integration.py -v

# Integration Tests
pytest tests/integration/test_lineage_api.py -v
pytest tests/integration/test_pdf_lineage_capture.py -v

# Performance Tests
pytest tests/unit/lineage/test_performance.py -v -k "viewer_load_time"
pytest tests/unit/lineage/test_performance.py -v -k "download_size"

# Coverage Check
pytest tests/unit/lineage --cov=d6_reports.lineage --cov=api.lineage --cov-report=term-missing --cov-fail-under=80
```

### Missing-Checks Validation
**Required for Backend/API tasks:**
- [x] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [x] Branch protection & required status checks
- [x] Security scanning (no sensitive data in lineage)
- [x] API performance budgets (<500ms response time)

**Recommended:**
- [x] Database query performance monitoring
- [x] Storage usage alerts for lineage data
- [x] Automated cleanup for old lineage records
- [x] Backup strategy for lineage data

## Dependencies
```python
# Existing dependencies (already in requirements.txt)
sqlalchemy>=2.0.0
fastapi>=0.104.0
pydantic>=2.0.0
pytest>=7.4.0
pytest-cov>=4.1.0

# No new dependencies needed - using Python stdlib gzip
```

## Rollback Strategy
1. Remove lineage API endpoints from router
2. Run migration downgrade: `alembic downgrade -1`
3. Remove lineage module directories
4. Revert changes to report generation files
5. Drop report_lineage table if migration fails

## Feature Flag Requirements
```python
# In core/config.py
ENABLE_REPORT_LINEAGE = env.bool("ENABLE_REPORT_LINEAGE", default=True)

# Usage in code:
if settings.ENABLE_REPORT_LINEAGE:
    await capture_lineage(report_generation)
```

## Migration Script
```sql
-- Create report_lineage table
CREATE TABLE report_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_generation_id UUID NOT NULL REFERENCES d6_report_generations(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL,
    pipeline_run_id UUID NOT NULL,
    template_version_id VARCHAR(255) NOT NULL,
    
    -- Lineage data
    pipeline_start_time TIMESTAMP NOT NULL,
    pipeline_end_time TIMESTAMP NOT NULL,
    pipeline_logs JSONB,
    raw_inputs_compressed BYTEA,
    raw_inputs_size_bytes INTEGER,
    compression_ratio DECIMAL(5,2),
    
    -- Audit fields
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    
    -- Indexes for performance
    CONSTRAINT fk_report_generation FOREIGN KEY (report_generation_id) 
        REFERENCES d6_report_generations(id) ON DELETE CASCADE
);

CREATE INDEX idx_lineage_report_id ON report_lineage(report_generation_id);
CREATE INDEX idx_lineage_lead_id ON report_lineage(lead_id);
CREATE INDEX idx_lineage_pipeline_run ON report_lineage(pipeline_run_id);
CREATE INDEX idx_lineage_created_at ON report_lineage(created_at);

-- Audit log for lineage access
CREATE TABLE report_lineage_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lineage_id UUID NOT NULL REFERENCES report_lineage(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    user_id VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    accessed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_lineage FOREIGN KEY (lineage_id) 
        REFERENCES report_lineage(id) ON DELETE CASCADE
);

CREATE INDEX idx_lineage_audit_lineage_id ON report_lineage_audit(lineage_id);
CREATE INDEX idx_lineage_audit_user_id ON report_lineage_audit(user_id);
CREATE INDEX idx_lineage_audit_accessed_at ON report_lineage_audit(accessed_at);
```

## Implementation Notes

### Lineage Data Structure
```python
@dataclass
class LineageData:
    lead_id: str
    pipeline_run_id: str
    template_version_id: str
    pipeline_start_time: datetime
    pipeline_end_time: datetime
    pipeline_logs: Dict[str, Any]
    raw_inputs: Dict[str, Any]
    report_generation_id: str  # Foreign key to d6_report_generations

# Integration in PDF generation flow
class PDFConverter:
    async def convert(self, html_content: str, report_generation: ReportGeneration) -> bytes:
        """Convert HTML to PDF and capture lineage."""
        pdf_bytes = await self._generate_pdf(html_content)
        
        if settings.ENABLE_REPORT_LINEAGE:
            # Capture lineage after successful PDF generation
            await self._capture_lineage(report_generation)
        
        return pdf_bytes
    
    async def _capture_lineage(self, report_generation: ReportGeneration):
        """Capture and store report lineage."""
        from d6_reports.lineage.tracker import LineageTracker
        
        tracker = LineageTracker()
        await tracker.capture_from_report_generation(report_generation)
```

### Compression Implementation
```python
async def compress_lineage_data(data: Dict[str, Any], max_size_mb: float = 2.0) -> bytes:
    """Compress lineage data with size limit"""
    json_str = json.dumps(data, default=str)
    compressed = gzip.compress(json_str.encode('utf-8'), compresslevel=6)
    
    size_mb = len(compressed) / (1024 * 1024)
    if size_mb > max_size_mb:
        # Truncate least important data and retry
        data = truncate_lineage_data(data)
        return await compress_lineage_data(data, max_size_mb)
    
    return compressed

# Integration with Report Generation
class LineageTracker:
    """Tracks and stores report generation lineage."""
    
    async def capture_from_report_generation(self, report_gen: ReportGeneration):
        """Capture lineage from a ReportGeneration instance."""
        # Extract metadata from report generation
        lineage_data = LineageData(
            lead_id=str(report_gen.lead_id),
            pipeline_run_id=str(report_gen.pipeline_run_id or uuid.uuid4()),
            template_version_id=report_gen.template_version or "v1.0.0",
            pipeline_start_time=report_gen.created_at,
            pipeline_end_time=report_gen.updated_at or datetime.utcnow(),
            pipeline_logs=await self._extract_pipeline_logs(report_gen),
            raw_inputs=await self._extract_raw_inputs(report_gen),
            report_generation_id=str(report_gen.id)
        )
        
        # Compress and store
        compressed_data = await compress_lineage_data(asdict(lineage_data))
        await self._store_lineage(lineage_data, compressed_data)
```

### API Response Format
```json
{
    "lineage_id": "uuid",
    "report_generation_id": "uuid",
    "lead_id": "uuid",
    "pipeline_run_id": "uuid",
    "template_version_id": "v1.0.0",
    "pipeline_duration_seconds": 45.2,
    "raw_inputs_size_bytes": 524288,
    "compression_ratio": 0.75,
    "created_at": "2024-01-10T10:00:00Z",
    "access_count": 3,
    "last_accessed_at": "2024-01-10T11:30:00Z"
}
```

### PDF Generation Integration Example
```python
# In d6_reports/generator.py
class ReportGenerator:
    async def generate(self, lead_id: str, template_version: str = None) -> ReportGeneration:
        """Generate report with automatic lineage capture."""
        # Create ReportGeneration record
        report_gen = ReportGeneration(
            lead_id=lead_id,
            template_version=template_version or self.get_latest_template_version(),
            pipeline_run_id=self.get_current_pipeline_run_id(),
            status="in_progress"
        )
        self.db.add(report_gen)
        await self.db.commit()
        
        try:
            # Generate report HTML
            html_content = await self._generate_html(lead_id)
            
            # Convert to PDF (lineage captured automatically in PDFConverter)
            pdf_converter = PDFConverter()
            pdf_bytes = await pdf_converter.convert(html_content, report_gen)
            
            # Update status
            report_gen.status = "completed"
            report_gen.pdf_url = await self._store_pdf(pdf_bytes)
            await self.db.commit()
            
        except Exception as e:
            report_gen.status = "failed"
            report_gen.error_message = str(e)
            await self.db.commit()
            raise
        
        return report_gen
```

### Integration Test Example
```python
# tests/integration/test_pdf_lineage_capture.py
async def test_pdf_generation_creates_lineage_record():
    """Verify that every PDF generation creates a corresponding lineage record."""
    # Generate a report
    generator = ReportGenerator(db)
    report_gen = await generator.generate(lead_id="test-lead-123")
    
    # Verify lineage was captured
    lineage = await db.query(ReportLineage).filter_by(
        report_generation_id=report_gen.id
    ).first()
    
    assert lineage is not None
    assert lineage.lead_id == "test-lead-123"
    assert lineage.pipeline_run_id is not None
    assert lineage.raw_inputs_compressed is not None
    assert lineage.compression_ratio > 0
    
    # Verify raw inputs can be decompressed
    decompressed = gzip.decompress(lineage.raw_inputs_compressed)
    raw_data = json.loads(decompressed.decode('utf-8'))
    assert 'assessment_data' in raw_data
    assert 'enrichment_data' in raw_data
```