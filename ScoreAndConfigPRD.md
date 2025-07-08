## LeadFactory – Phase-0 “Config-as-Data & Prompt-Ops” PRD

**Version 1.1 – Final for Claude Code**
*(incorporates PO answers 2025-07-08)*

---

### 0 Key Updates Since v1.0

| Topic                           | Decision                                                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Sheet ID & tab**              | *Placeholder* values (`{{SHEET_ID}}`, `{{TAB_NAME}}`) until Sheet is created. Claude Code must parameterise these in Actions & Apps Script.      |
| **Sync cadence**                | **Button-only**. No cron job for Sheet→YAML.                                                                                                     |
| **Complex formulas**            | Use the existing “\$ impact” Excel formulas in repo (see `lead_value.xlsx`, sheet *ImpactCalcs*) as reference fixtures for xlcalculator tests.   |
| **Humanloop project IDs**       | Placeholders (`{{HUMANLOOP_PROJECT_DEV}}`, `{{HUMANLOOP_PROJECT_PROD}}`)—to be replaced when projects spun up. Vision support is required.       |
| **Alerting**                    | Target Slack channel `#alerts`, but **no direct Slack integration yet**. Emit Prom/Loki logs; Slack webhook integration is flagged as TODO.      |
| **Reload failure policy**       | On YAML validation/reload error, **retain previous rules**, log error, increment `scoring_rules_reload_total{status="failure"}`.                 |
| **Tier splits & scoring model** | Initial thresholds 80/60/40 accepted **for analytics only**. Scoring coverage gaps will be revisited after data collection (see Task S-7 below). |

---

### 1 Goals & Success Criteria

*(unchanged from v1.0 except G-2 description)*

| ID  | Goal                                                              | Success Metric                                            |
| --- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| G-1 | CPO edits scoring in Google Sheets; change live ≤ 5 min.          | PR merges; new weight visible in API.                     |
| G-2 | \*\*Tiers calculated, but have **zero gating effect** in Phase 0. | Pipeline treats every lead the same; `tier` only in logs. |
| G-3 | 100 % of prompts via Humanloop; prompts in repo.                  | No direct OpenAI calls; prompt slug in Humanloop dash.    |
| G-4 | Hot-reload without restart.                                       | Reload ≤ 5 s; failures leave previous rules active.       |

---

### 2 Functional Requirements (Final)

#### 2.1 `scoring_rules.yaml` (canonical)

* **Schema** identical to v1.0.
* **Comment**:

  ```yaml
  # Tier used for analytics only until Phase 0.5. Do not branch on tier.
  ```
* **Validation Adds**: if a component listed in `components` has no matching field in sample assessment fixture, raise warning (but do not block).

#### 2.2 Tier Logic

* No branching. Ensure any previous `if lead.tier …` code is deleted or commented `TODO Phase 0.5`.

#### 2.3 Sheet ⇆ YAML Sync

* **Apps Script** (in Sheet):

  ```javascript
  function submitToCI() {
    const body = {sheetId: "{{SHEET_ID}}", tab: "{{TAB_NAME}}", sha: getSha()};
    UrlFetchApp.fetch("https://api.github.com/repos/anthrasite/LeadFactory_v1/actions/workflows/sheet_pull.yml/dispatches", {
      method: "POST",
      headers: {"Authorization": "token {{GH_PAT}}"},
      payload: JSON.stringify({ref:"main", inputs:body})
    });
  }
  ```
* **Sync-Pull Action (`.github/workflows/sheet_pull.yml`)** – uses `{{SHEET_ID}}`.
* **Sync-Push Action** – updates the same tab; verifies SHA cell.

#### 2.4 xlcalculator

* Use `$ impact` formulas from `/assets/lead_value.xlsx` sheet *ImpactCalcs* as unit-test truth set.
* Unsupported functions get caught during validation; PR fails.

#### 2.5 Prompt Directory & Humanloop

* Directory: `prompts/`
* File example with front-matter remains.
* Wrapper config placeholders:

  ```env
  HUMANLOOP_API_KEY     = ${{ secrets.HUMANLOOP_API_KEY }}
  HUMANLOOP_PROJECT_ID  = {{HUMANLOOP_PROJECT_PROD}}
  HUMANLOOP_ENV         = prod
  ```
* Vision prompts pass `images=[{url:...}]` to Humanloop SDK.

#### 2.6 Hot-Reload

* File-watcher plus `POST /internal/reload_rules`.
* On validation error:

  * keep old config,
  * log `"reload_failed"` + message,
  * metric `scoring_rules_reload_total{status="failure"}`++.

#### 2.7 Observability

* Metrics unchanged; slack integration left as **future task S-8**.

---

### 3 Milestone Plan

| Sprint  | Deliverable                                                                                                                       | Owner          |
| ------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| **S-1** | • Remove hard-coded weights/tiers.<br>• Introduce YAML schema & validator.                                                        | Backend        |
| **S-2** | • Create Google Sheet template with protected tab & Apps Script (placeholders).<br>• `sheet_pull.yml` workflow (Button → PR).     | DevOps         |
| **S-3** | • `sheet_push.yml` workflow (on merge → Sheet).<br>• YAML watcher + `/internal/reload_rules`.                                     | DevOps         |
| **S-4** | • xlcalculator integration + unit tests using `$ impact` formulas.                                                                | Backend        |
| **S-5** | • Prompt directory, Humanloop wrapper with placeholders; migrate existing prompts.<br>• Replace direct OpenAI calls.              | ML/Backend     |
| **S-6** | • Prom/Loki metrics; reload failure handling.<br>• Documentation & sample scripts.                                                | DevOps         |
| **S-7** | **(Future) Assess scoring coverage** – After 3 k leads processed, analyze tier-to-purchase correlation; iterate scoring formulas. | Product + Data |
| **S-8** | **(Future) Slack alert webhook** – Send metrics failures to `#alerts`.                                                            | DevOps         |

---

### 4 Open Items Resolved / Outstanding

| ID                           | Status                                                 |
| ---------------------------- | ------------------------------------------------------ |
| **Q1** Sheet ID / Tab        | **Placeholder** `{{SHEET_ID}}`, `{{TAB_NAME}}`.        |
| **Q2** Sync cadence          | Button-only ✅                                          |
| **Q3** Formula examples      | Use `$ impact` formulas in `/assets/lead_value.xlsx` ✅ |
| **Q4** Humanloop IDs         | Placeholders. Vision support confirmed ✅               |
| **Q5** Slack channel         | `#alerts` – integration deferred (S-8)                 |
| **Q6** Reload failure policy | Keep previous rules ✅                                  |
| **Q7** Tier splits adequacy  | 80/60/40 OK; coverage revisit scheduled (S-7) ✅        |

---

### 5 Acceptance Criteria (Final)

1. **Sheet Edit Test** – Change weight in Sheet → press *Submit* → PR merges → `GET /score/test` returns updated score in < 5 min; log shows `rules_reload_success`.
2. **Tier Neutrality Test** – For two dummy leads (score = 35 & 95) verify both pass through full mockup + email steps; `tier` differs but pipeline branch count == 1.
3. **Prompt Path Test** – Call insight generator; Humanloop dashboard shows prompt slug `insight_v1`, environment `dev` in dev test.
4. **Reload Failure Test** – Commit YAML with bad formula; unit tests fail in CI; runtime reload never attempted (old config persists).
5. **Formula Parity Test** – Unit test validates `$ impact` calculation matches Excel sample to ±0.01.

---

### 6 Handoff Notes for Claude Code

* **Repository root**: `/workspace/LeadFactory_v1/` (Windsurf mounts).
* **Placeholders** must be TODO-commented for easy grep (`TODO: inject SHEET_ID`).
* Use **feature branches** (`feat/sheets-sync`, `feat/prompt-humanloop`, etc.) and open PRs per sprint item.
* Provide a short **README-changes.md** summarising setup steps for Sheet credentials and Humanloop keys.
* Keep PRs small; CI must stay green.

---

**End of PRD — ready for implementation.**
