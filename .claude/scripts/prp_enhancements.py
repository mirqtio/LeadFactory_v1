#!/usr/bin/env python3
"""PRP Enhancement Data.

Contains business logic and outcome-focused acceptance criteria for all tasks.
"""

BUSINESS_LOGIC = {
    "P0-000": "Ensure any new contributor or CI runner has the minimum tool-chain before code executes.",
    "P0-001": "Accurate enrichment merge prevents stale or duplicate provider data in assessments.",
    "P0-002": "One orchestrated flow proves the entire MVP works end-to-end.",
    "P0-003": '"Works on my machine" disparities disappear when tests always run in the same image.',
    "P0-004": "Schema drift breaks runtime and Alembic autogenerate.",
    "P0-005": "Tests must never hit paid APIs; prod must never run with stubs.",
    "P0-006": "A green baseline proves core logic is stable for further work.",
    "P0-007": "External uptime monitors need a single, fast status route.",
    "P0-008": "Slow or mis-marked tests waste CI minutes and confuse signal.",
    "P0-009": "Stray Yelp code causes dead imports and schema noise.",
    "P0-010": "Fresh clone + install must succeed for new devs and CI.",
    "P0-011": "Automated prod deploy removes human error and provides rollback point.",
    "P0-012": "Local DB on VPS avoids external dependency while you evaluate Supabase.",
    "P1-010": "SEO snapshot is a client-value driver and upsell hook.",
    "P1-020": "Core Web Vitals & accessibility scores are industry benchmarks demanded by prospects.",
    "P1-030": "Visual trust cues correlate with conversion; automated scoring yields scalable insights.",
    "P1-040": "Narrative feedback differentiates the report and feeds email personalisation.",
    "P1-050": "Without per-call cost tracking you cannot manage profit or guardrails.",
    "P1-060": "Prevent invoice shock and keep unit economics predictable.",
    "P1-070": "Purchased enrichment fills firmographic gaps essential for lead resale.",
    "P1-080": "Processing by vertical maximises ROI under budget caps.",
    "P2-010": "Transparency on CPL/CAC drives pricing and spend decisions.",
    "P2-020": "Buyers want a visually digestible cost story.",
    "P2-030": "Higher personalisation lifts open & click rates.",
    "P2-040": "Monthly burn must not exceed planned spend.",
    "P2-050": "Managed Postgres reduces ops burden and enables auth/analytics features.",
}

OUTCOME_CRITERIA = {
    "P0-000": ("`pytest --collect-only` exits 0 inside Docker **and** a checklist in README lists required "
               "versions (Python 3.11, Docker ≥ 20, Compose ≥ 2)."),
    "P0-001": ("`test_d4_coordinator.py` passes **and** coordinator returns freshest, deduped fields; "
               "cache key collisions across businesses impossible (property-based test)."),
    "P0-002": ("`smoke/test_full_pipeline_flow.py` generates PDF + email + DB rows for a sample URL "
               "within 90 s runtime."),
    "P0-003": "GitHub Actions logs show image build, KEEP suite green, coverage ≥ 80%, image pushed to GHCR.",
    "P0-004": ("`alembic upgrade head` + autogen diff both return no changes on CI; downgrade path tested "
               "for latest revision."),
    "P0-005": ("Running tests with `USE_STUBS=true` yields 0 external calls (network mocked); "
               "prod env rejects `USE_STUBS=true` at startup."),
    "P0-006": '`pytest -m "not phase_future and not slow"` exits 0 in < 5 min on CI.',
    "P0-007": '`/health` returns JSON `{status:"ok"}` plus DB connectivity ≤ 100 ms; monitored in deploy workflow.',
    "P0-008": ("Collect phase shows correct counts; `pytest -m slow` runs 0 tests in CI; import errors in "
               "ignored files eliminated."),
    "P0-009": ("`git grep -i yelp` finds only comments/docs; migration drops last Yelp columns; "
               "stub server has no `/yelp/*` routes."),
    "P0-010": ("`pip install -r requirements.txt` succeeds in clean venv; `pip check` green; version pins "
               "documented."),
    "P0-011": ("GH Actions deploy job completes; container responds 200 on `/health`; restart policy is "
               "`always`; SSH key auth works."),
    "P0-012": ("Postgres service starts with named volume; app connects; `alembic upgrade head` runs during "
               "deploy; data survives container restart."),
    "P1-010": ('Stubbed unit tests pass; live smoke test fetches all six metrics; metrics appear in PDF '
               'section "SEO Snapshot".'),
    "P1-020": ("Headless run completes ≤ 30 s; returns 5 scores; cached 7 days; results populate assessment "
               "row and PDF."),
    "P1-030": ("Screenshot captured; 9 rubric scores (0-100) persisted; PDF shows coloured bar chart "
               "per dimension."),
    "P1-040": "For a given URL stub, audit returns 7 structured fields; JSON matches schema; costs logged in ledger.",
    "P1-050": ("Every external API request inserts a ledger row with `cost_usd`; daily aggregation view "
               "returns non-NULL totals."),
    "P1-060": "Flow halts when simulated spend > cap; Slack (or log) warning emitted; admin override flag tested.",
    "P1-070": "Stub test passes; live smoke returns ≥ 10 firmographic fields; enrichment merged into business record.",
    "P1-080": "Prefect schedule runs; summary email lists processed counts per bucket; respects guardrails.",
    "P2-010": "`/analytics/unit_econ?date=…` returns CPL, CAC, ROI; SQL view tested; response cached 24 h.",
    "P2-020": "New 2-page section renders pie, bar, gauge charts; PDF snapshot test diff < 2%.",
    "P2-030": ("For sample lead, builder returns 5 subjects / 3 bodies with placeholders filled; "
               "deterministic stub for tests; live emails sent in SendGrid sandbox."),
    "P2-040": ("When ledger total > monthly cap, all flows transition to `Failed` with custom message; "
               "auto-resume next month verified."),
    "P2-050": ("CI pipeline spins up Supabase shadow DB, runs migrations; deploy workflow switches "
               "`DATABASE_URL`; app health remains 200; old VPS Postgres container stopped."),
}

# Example code snippets for specific tasks
CODE_EXAMPLES = {
    "P0-001": """
## Example: D4 Coordinator Merge Fix

**Before (broken):**
```python
def merge_enrichment_data(self, existing_data, new_data):
    # Naive merge that causes duplicates
    return {**existing_data, **new_data}
```

**After (fixed):**
```python
def merge_enrichment_data(self, existing_data, new_data):
    # Merge by (field, provider) with freshest collected_at
    merged = {}
    for field, value in chain(existing_data.items(), new_data.items()):
        key = (field, value['provider'])
        if key not in merged or value['collected_at'] > merged[key]['collected_at']:
            merged[key] = value
    return merged
```
""",
    "P0-002": """
## Example: Prefect Pipeline Flow

```python
from prefect import flow, task

@flow(name="full_pipeline")
def full_pipeline_flow(url: str):
    business = target_business(url)
    assessment = assess_website(business)
    score = calculate_score(assessment)
    report = generate_report(score)
    send_email(report)
    return {"status": "complete", "report_id": report.id}
```
""",
    "P0-009": """
## Example: Yelp Removal Check

```bash
# Before: Yelp references found
$ git grep -i yelp | wc -l
47

# After: Only docs/comments remain
$ git grep -i yelp
CHANGELOG.md:- Removed Yelp provider (July 2025)
docs/history.md:Original design included Yelp integration
```
""",
    "P0-003": """
## Example: Dockerfile.test for CI

```dockerfile
# Multi-stage build for test environment
FROM python:3.11.0-slim as test

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .

# Run tests as default command
CMD ["pytest", "-m", "not slow and not phase_future", "--tb=short"]
```
""",
    "P0-004": """
## Example: Migration Validation Test

```python
def test_migrations_current():
    \"\"\"Ensure no pending migrations\"\"\"
    # Run upgrade to head
    alembic_cfg = Config("alembic.ini")
    upgrade(alembic_cfg, "head")

    # Check for model changes
    context = MigrationContext.configure(connection)
    diff = compare_metadata(context, target_metadata)

    assert len(diff) == 0, f"Uncommitted changes: {diff}"
```
""",
    "P0-005": """
## Example: Stub Detection in Tests

```python
# In conftest.py
@pytest.fixture(autouse=True)
def enforce_stubs(monkeypatch):
    \"\"\"Ensure tests never hit real APIs\"\"\"
    if os.getenv("USE_STUBS") == "true":
        monkeypatch.setattr("requests.get", mock_requests_get)
        monkeypatch.setattr("requests.post", mock_requests_post)
```
""",
    "P0-007": """
## Example: Health Endpoint Implementation

```python
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        # Check DB connectivity
        db.execute("SELECT 1")
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.VERSION,
            "database": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )
```
""",
    "P1-050": """
## Example: Cost Ledger Implementation

```python
class GatewayCostLedger(Base):
    __tablename__ = "gateway_cost_ledger"

    id = Column(UUID, primary_key=True, default=uuid4)
    provider = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    cost_usd = Column(Numeric(10, 4), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    business_id = Column(UUID, ForeignKey("businesses.id"))
    response_time_ms = Column(Integer)

    __table_args__ = (
        Index("idx_cost_ledger_daily", "provider", "timestamp"),
    )
```
""",
}

# Rollback strategies for each task
ROLLBACK_STRATEGIES = {
    "P0-000": "Delete setup.sh if created",
    "P0-001": "`git revert` to restore previous coordinator logic",
    "P0-002": "Delete flows/full_pipeline_flow.py",
    "P0-003": "Remove Dockerfile.test and revert CI workflow",
    "P0-004": "Use `alembic downgrade` to previous revision",
    "P0-005": "Revert config.py changes",
    "P0-006": "Re-add xfail markers to unblock CI",
    "P0-007": "Remove /health route from API",
    "P0-008": "Revert conftest.py and pytest.ini changes",
    "P0-009": "Not applicable - Yelp already removed",
    "P0-010": "Restore previous requirements.txt",
    "P0-011": "Delete deploy.yml workflow",
    "P0-012": "Stop postgres container, keep volume for data recovery",
    "P1-010": "Feature flag ENABLE_SEMRUSH=false",
    "P1-020": "Remove lighthouse.py and uninstall Playwright",
    "P1-030": "Feature flag ENABLE_VISUAL_ANALYSIS=false",
    "P1-040": "Feature flag ENABLE_LLM_AUDIT=false",
    "P1-050": "Drop gateway_cost_ledger table",
    "P1-060": "Set all guardrail limits to None",
    "P1-070": "Feature flag ENABLE_DATAAXLE=false",
    "P1-080": "Disable Prefect schedule",
    "P2-010": "Drop unit economics views",
    "P2-020": "Remove economics section from PDF template",
    "P2-030": "Revert to V1 email templates",
    "P2-040": "Remove budget stop decorator from flows",
    "P2-050": "Revert DATABASE_URL to VPS Postgres",
}
