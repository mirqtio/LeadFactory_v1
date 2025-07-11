# LeadFactory Reference Map

Below is a **feature-by-feature lookup sheet** that provides **one concrete example** and **one authoritative reference** for every task in INITIAL.md.

## Legend

* **Example** = a *small, self-contained snippet or test* already in your repo that illustrates the pattern to follow.
  *If none exists, point to an analogous file or a quick "toy" snippet you can copy into `examples/`.*
* **Reference** = the spec, schema, or external doc that defines "correct" behaviour.

## Wave A - Stabilize (Priority P0)

| Wave / Priority | Feature slug                  | Example to show CC                                                                              | Reference to cite                                                                                                                                 |
| --------------- | ----------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P0-000**      | Prerequisites check           | `examples/prereq_check.md` *(checklist template)*                                               | Setup documentation in README.md                                                                                                                   |
| **P0-001**      | D4 Coordinator fix            | `tests/unit/d4_enrichment/test_matchers.py` illustrates merge logic that already passes         | Your original PRD section "D4 Enrichment Coordinator – merge strategy" (PDF p 4)                                                                  |
| **P0-002**      | Prefect full-pipeline flow    | `examples/min_flow.py` *(create a 20-line toy flow that calls two dummy tasks and logs JSON)*   | Prefect docs: [https://docs.prefect.io/latest/concepts/flows/](https://docs.prefect.io/latest/concepts/flows/)                                    |
| **P0-003**      | Dockerize CI                  | Existing `tests/test_docker_compose.py` shows container status check                            | GitHub Actions "Docker build push" example [https://docs.github.com/actions/publishing-images](https://docs.github.com/actions/publishing-images) |
| **P0-004**      | Alembic migrations up-to-date | `migrations/01dbf243d224_drop_yelp_id_column.py` shows proper upgrade/downgrade                 | Alembic docs: "autogenerate" section                                                                                                              |
| **P0-005**      | Stub-server wiring            | `tests/integration/test_stub_server.py` demonstrates starting stubs in fixtures                 | README § "Running stub server locally"                                                                                                            |
| **P0-006**      | KEEP test gating              | `pytest.ini` KEEP list & `phase_future` marker example                                          | CLAUDE.md "Test policy" block                                                                                                                     |
| **P0-007**      | `/health` endpoint            | `tests/integration/test_metrics_endpoint.py` has simple status route test                       | FastAPI docs: health check patterns                                                                                                               |
| **P0-008**      | Test infrastructure cleanup   | `examples/slow_test.py` *(demonstrate @pytest.mark.slow)*                                       | pytest documentation on markers                                                                                                                    |
| **P0-009**      | Remove Yelp remnants          | `git grep -i yelp` command example                                                              | Git grep documentation                                                                                                                             |
| **P0-010**      | Fix missing dependencies      | `requirements.txt` with version pins                                                             | pip-tools documentation for dependency management                                                                                                  |
| **P0-011**      | Deploy to VPS                 | `examples/deploy_workflow.yml` *(SSH + docker-run workflow from Actions marketplace)*            | VPS hardening checklist from "Move LeadFactory to VPS" thread                                                                                      |
| **P0-012**      | Postgres on VPS Container     | `examples/docker_postgres_deploy.yml` *(postgres with named volume)*                             | Docker Compose networking documentation                                                                                                            |

## Wave B - Expand (Priority P1-P2)

| Pri.       | Feature                             | Example                                                                                         | Reference                                                                 |
| ---------- | ----------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **P1-010** | **SEMrush client & metrics**        | `tests/unit/d0_gateway/test_pagespeed_client.py` shows a provider wrapper + stub                | SEMrush "Domain Overview API" doc PDF (**docs/api/semrush_domain.pdf**)  |
| **P1-020** | **Lighthouse headless audit**       | `examples/playwright_stub.py` *(10-line Playwright script loading example.com & printing JSON)* | Google Lighthouse CLI JSON schema (**docs/schemas/lighthouse_v10.json**) |
| **P1-030** | **Visual rubric analyzer**          | `tests/unit/d3_assessment/test_rubric.py` – scoring pattern on deterministic inputs             | Design brief "Visual Rubric Definitions" (Notion doc link)                |
| **P1-040** | **LLM heuristic audit**             | `tests/unit/d8_personalization/test_subject_lines.py` – deterministic OpenAI stub & parser      | Prompt template draft in `/docs/prompts/heuristic_audit.md`               |
| **P1-050** | **Gateway cost ledger**             | `tests/unit/d9_delivery/test_compliance.py` – example of new table + fixture                    | Cost model table spec in `/docs/schemas/cost_ledger.sql`                  |
| **P1-060** | **Cost guardrails**                 | `tests/unit/d11_orchestration/test_cost_guardrails.py` (currently xfail)                        | Phase 0.5 Orchestration PRD § "Budget Enforcement"                        |
| **P1-070** | **Data provider client (DataAxle)** | `tests/smoke/test_smoke_data_axle.py` skip-if-key pattern                                       | DataAxle API doc excerpt (**docs/api/dataaxle.pdf**)                      |
| **P1-080** | **Bucket enrichment flow**          | `tests/integration/test_targeting_integration_simple.py` small bucket example                   | D1 Targeting PRD § "Nightly bucket enrichment"                            |
| **P2-010** | **Unit-economics views & API**      | `tests/unit/d5_scoring/test_d5_scoring_models.py` – models + simple calc                        | Analytics spec `/docs/schemas/unit_econ_views.sql`                        |
| **P2-020** | **Unit-economics PDF section**      | `tests/unit/d6_reports/test_pdf_converter.py` – PDF writer pattern                              | Figma mockup PDF **docs/design/pdf_unit_econ_mock.pdf**                   |
| **P2-030** | **Email personalisation V2**        | `tests/unit/d9_delivery/test_email_builder.py` – templating + stub LLM                          | Marketing copy prompt bank `/docs/prompts/email_personalization.md`       |
| **P2-040** | **Orchestration budget-stop**       | `tests/unit/d11_orchestration/test_bucket_enrichment.py` shows Prefect stop condition (xfail)   | Prefect recipe "Fail flow on budget" (**docs/prefect_budget_stop.md**)    |

*(Add file placeholders under `examples/` or `docs/` if they don't exist yet — Claude will generate their content when executing the PRP.)*

---

## How to use this table

1. For each feature heading in `INITIAL.md`, look up the corresponding row
2. The PRP generator will embed these example paths and reference URLs
3. During `/execute-prp`, Claude will automatically open the example & reference files

This gives Claude explicit, minimal context snippets to imitate and authoritative docs to honor — the heart of effective context engineering.

---

## Test Inventory

Below is the **revised feature inventory** that includes all the extra stabilization items, with explicit test targets for each task.

### Wave A – Stabilize (Priority P0)

| Ref        | Feature (slug)                    | Acceptance tests that must pass                                                                                    | Notes / Example files                               |
| ---------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| **P0-000** | **Prerequisites & Setup**         | *No code tests* – PRP passes if `pytest --collect-only` exits 0 inside Docker.                                     | Example checklist in `examples/prereq_check.md`     |
| **P0-001** | **Fix D4 Coordinator**            | `tests/unit/d4_enrichment/test_d4_coordinator.py`                                                                  | Broken merge/cache logic.                           |
| **P0-002** | **Prefect full-pipeline flow**    | `tests/smoke/test_full_pipeline_flow.py` *(new)* — asserts JSON contains `"score"` and a PDF path.                 | Provide toy flow example in `examples/min_flow.py`. |
| **P0-003** | **Dockerised CI**                 | Entire KEEP suite must pass **inside** the Docker image.                                                           | Use `tests/test_docker_compose.py` as pattern.      |
| **P0-004** | **Alembic migrations up-to-date** | `tests/unit/test_migrations.py` *(new)* — runs `alembic upgrade head` and asserts autogenerate diff is empty.      |                                                     |
| **P0-005** | **Stub-server wiring**            | `tests/integration/test_stub_server.py` passes with `USE_STUBS=true`.                                              |                                                     |
| **P0-006** | **KEEP / phase_future gating**    | `tests/test_marker_policy.py` *(new)* — collects tests and asserts no un-marked reds.                              | Confirms `conftest.py` auto-marker.                 |
| **P0-007** | **/health endpoint**              | `tests/unit/test_health_endpoint.py` and smoke test in `tests/smoke/test_health.py` *(new)*.                       |                                                     |
| **P0-008** | **Test infrastructure cleanup**   | `pytest -m "slow" -q` runs **zero** slow tests in CI; import errors in ignored files are gone.                     | Example slow marker in `examples/slow_test.py`.     |
| **P0-009** | **Remove Yelp remnants**          | `git grep -i yelp` returns 0 active-code hits inside `tests/test_yelp_purge.py` *(new)*.                           |                                                     |
| **P0-010** | **Fix missing dependencies**      | CI green on a fresh Docker build; `requirements.txt` contains all imports (checked by `pip-check` step in CI).     |                                                     |
| **P0-011** | **Automated VPS deploy**          | `deploy_vps.yml` workflow completes & `/health` endpoint test returns 200.                                          |                                                     |
| **P0-012** | **Postgres on VPS Container**     | Database container runs with volume; `alembic upgrade head` completes in deployment.                                | Docker networking and volumes.                      |

> **Tip:** place the three tiny *new* test stubs (health, migrations, marker policy) in `tests/smoke/` so they run quickly.

### Wave B – Expand (Priorities P1 & P2)

| Ref        | Feature                             | Key tests                                                 |
| ---------- | ----------------------------------- | --------------------------------------------------------- |
| **P1-010** | SEMrush client & metrics            | `tests/unit/d0_gateway/test_semrush_client.py` (stub)     |
| **P1-020** | Lighthouse headless audit           | `tests/unit/d4_enrichment/test_lighthouse_runner.py`      |
| **P1-030** | Visual rubric analyser              | `tests/unit/d3_assessment/test_visual_rubric.py`          |
| **P1-040** | LLM heuristic audit                 | `tests/unit/d3_assessment/test_llm_heuristic.py`          |
| **P1-050** | Gateway cost ledger                 | `tests/unit/d0_gateway/test_cost_ledger.py`               |
| **P1-060** | Cost guardrails                     | `tests/unit/d11_orchestration/test_cost_guardrails.py`    |
| **P1-070** | Data provider client (DataAxle/TBD) | `tests/unit/d0_gateway/test_dataaxle_client.py`           |
| **P1-080** | Bucket enrichment flow              | `tests/integration/test_bucket_enrichment_flow.py`        |
| **P2-010** | Unit-economics views & API          | `tests/unit/d10_analytics/test_unit_econ_views.py`        |
| **P2-020** | Unit-economics PDF section          | `tests/unit/d6_reports/test_pdf_unit_econ_section.py`     |
| **P2-030** | Email personalisation V2            | `tests/unit/d9_delivery/test_email_personalisation_v2.py` |
| **P2-040** | Orchestration budget-stop           | `tests/integration/test_budget_stop.py`                   |