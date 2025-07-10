# Phase 0 Gap‑Closure PRD

**Version 0.2 • 10 Jul 2025**  (previous v0.1 superseded)

## 1 Purpose

Close every Phase 0 blocker gap so LeadFactory ships all promised metrics: HTTPS security check, full visual rubric assessment, ScreenshotOne capture, and SEMrush Site Audit metrics—all wired into scoring (D5).

---

## 2 Scope & Feature Slugs

| Gap ID  | Area                       | Feature‑Slug(s)           |
| ------- | -------------------------- | ------------------------- |
| **G‑1** | Security metric            | `techscrape-https-check`  |
| **G‑2** | Screenshot capture         | `audit-screenshotone`     |
| **G‑3** | Visual rubric + warnings   | `audit-visual-rubric`     |
| **G‑4** | SEMrush Site Audit metrics | `audit-semrush-siteaudit` |

---

## 3 Functional Requirements

### 3.1 G‑1 HTTPS Enforced Check (`techscrape-https-check`)

* **FR‑1.1** Follow up to three redirects from origin URL; flag if final hop is non‑HTTPS.
* **FR‑1.2** Validate TLS certificate expiry & chain (Python `ssl`); populate `tls_version` string (e.g. “TLS 1.3”).
* **FR‑1.3** Persist `https_enforced` BOOL + `tls_version` TEXT in `assessment_techscrape`.
* **FR‑1.4** If `https_enforced` is **false** create `AuditFinding(severity='high', category='security', issue_id='HTTPS_MISSING')`.

### 3.2 G‑2 Full‑Page Screenshot Capture (`audit-screenshotone`)

* **FR‑2.1** Enable feature‑flag `ENABLE_SCREENSHOT_ONE` **default true**.
* **FR‑2.2** Request ScreenshotOne full‑page PNG (1440 px wide, 75 % quality).
* **FR‑2.3** Store result in S3 → `screenshot_url` presigned 24 h; cache key `sshot:{hash(url)}`.
* **FR‑2.4** Expose Prom counter `screenshotone_calls_total` and cost gauge `screenshotone_cost_usd_total`.

### 3.3 G‑3 Visual Rubric & Warnings (`audit-visual-rubric`)

* **FR‑3.1** Pass captured screenshot to **GPT‑4o Vision** with system prompt *“Grade homepage per Rubric v1 JSON schema”*.
* **FR‑3.2** Rubric JSON schema:

  ```json
  {
    "rubric_scores": {"r1":0-2,"r2":0-2,"r3":0-2,"r4":0-2,"r5":0-2,
                       "r6":0-2,"r7":0-2,"r8":0-2,"r9":0-2},
    "warnings": ["string"],
    "overall_pass": true/false
  }
  ```
* **FR‑3.3 Rubric Criteria Table**
  \| Code | Criterion | 0 | 1 | 2 |
  \|------|-----------|---|---|---|
  \| **r1** | Above‑fold CTA visibility | none | visible but secondary | primary CTA prominent |
  \| **r2** | CTA prominence (colour/size) | blends in | somewhat stands out | highly salient |
  \| **r3** | Trust signals present | none | 1 signal | ≥2 signals (SSL lock, reviews, badges) |
  \| **r4** | Visual hierarchy / contrast | poor contrast | adequate | excellent hierarchy |
  \| **r5** | Text readability | font < 14 px or low contrast | readable | very readable |
  \| **r6** | Brand colour cohesion | mismatched palette | partial match | cohesive brand palette |
  \| **r7** | Image quality | blurry/low‑res | acceptable | crisp/pro quality |
  \| **r8** | Mobile responsiveness hint | text cuts off | slight overflow | fully responsive layout |
  \| **r9** | Clutter vs white‑space | very cluttered | average | ample breathing room |
* **FR‑3.4** Persist scores in `visual_rubric` table (`r1`‑`r9` SMALLINT, `overall_pass` BOOL, `warnings` JSONB).
* **FR‑3.5** Generate `AuditFinding` for any score < 1 (severity ‘medium’) or if `overall_pass` false (severity ‘high’).
* **FR‑3.6 Fallback** If GPT‑4o Vision errors > 1 or service unavailable:

  * a. Apply heuristic fallback: simple OpenCV checks → estimate `r1` (CTA bounding‑box above 600 px) and `r5` (contrast check); all other scores set `NULL`.
  * b. Mark `visual_rubric.fallback_used=true` and still deliver report.

### 3.4 G‑4 SEMrush Site Audit Metrics (`audit-semrush-siteaudit`)

* **FR‑4.1** Call SEMrush *Site Audit → Overview* endpoint for domain with `strategy=quick`. Required fields:

  * `site_health_score` (0–100), `backlink_toxicity_score`, `authority_score`.
* **FR‑4.2 Issue Categorisation Logic**

  * Map SEMrush issue `category` strings into LeadFactory categories:

    | SEMrush Issue Group           | LeadFactory Category |
    | ----------------------------- | -------------------- |
    | Performance / Core Web Vitals | **performance**      |
    | Crawlability / Internal Links | **seo**              |
    | HTTPS / Security              | **security**         |
    | Markup / Structured Data      | **seo**              |
    | Content / Duplicates          | **ux**               |
  * Aggregate count of *high‑severity* issues per category; return top 3.
* **FR‑4.3** Persist metrics in `assessment_semrush` table (columns above + `top_issue_categories` JSONB).
* **FR‑4.4** Budget guardrail: skip SEMrush call if `daily_semrush_cost_usd` exceeds \$10 or `remaining_quota` < 20 %.
* **FR‑4.5** Generate `AuditFinding` when `site_health_score` < 80 or `backlink_toxicity_score` > 30.

---

## 4 Non‑Functional Requirements

| Aspect         | Target                                                                                                                            |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Latency budget | +≤ 3 s/business (Visual LLM dominates)                                                                                            |
| Cost budget    | +≤ \$0.015/lead (ScreenshotOne 0.003 + GPT‑4o 0.01 + SEMrush 0.002)                                                               |
| Reliability    | ≥ 98 % successful metric harvest per node                                                                                         |
| Observability  | Prom metrics: `https_checks_total`, `sshot_calls_total`, `visual_llm_latency_ms`, `semrush_calls_total`, `semrush_cost_usd_total` |

---

## 5 Data Contracts & Scoring Integration

### 5.1 New Tables / Columns

* **visual\_rubric**  (PK `business_id`, `created_at` TIMESTAMP)

  * `r1`‑`r9` SMALLINT, `overall_pass` BOOL, `warnings` JSONB, `fallback_used` BOOL.
* **assessment\_semrush**  (extends existing)

  * `site_health_score` INT, `backlink_toxicity_score` FLOAT, `authority_score` INT,
    `top_issue_categories` JSONB.
* **assessment\_techscrape**

  * add `https_enforced` BOOL, `tls_version` TEXT.

### 5.2 Scoring Engine (D5) Hooks

| New Field                    | Rule Key           | Default Weight |
| ---------------------------- | ------------------ | -------------- |
| `https_enforced`             | `security_https`   | 0.10           |
| `visual_rubric.overall_pass` | `visual_pass`      | 0.10           |
| `site_health_score`          | `semrush_health`   | 0.15           |
| `backlink_toxicity_score`    | `semrush_toxicity` | 0.05           |

* **Hot‑Reload YAML**—update sample config with new keys above; validator to ensure weights still sum 1.0.

---

## 6 Acceptance Criteria (BDD)

* **AC‑1** Given a site that forces HTTP → HTTPS When tech‑scrape runs Then `https_enforced=true`.
* **AC‑2** Given expired cert When tech‑scrape runs Then `https_enforced=false` and AuditFinding severity high.
* **AC‑3** Given Tier A lead When screenshot node runs Then `screenshot_url` is non‑null.
* **AC‑4** Given no CTA above fold When visual rubric runs Then `r1=0`.
* **AC‑5** When GPT‑4o unavailable Then `fallback_used=true` and at least `r1` + `r5` populated.
* **AC‑6** Given domain example.com with SEMrush Site Health 92 Then DB row stores `site_health_score=92`.

---

## 7 Timeline & Owners

| Week | Owner         | Milestone                                       |
| ---- | ------------- | ----------------------------------------------- |
| W‑0  | Sec Eng       | HTTPS check merged & CI green                   |
| W‑1  | Front‑end Eng | ScreenshotOne flag enabled, S3 upload verified  |
| W‑2  | AI Eng        | GPT‑4o Vision rubric pipeline MVP + fallbacks   |
| W‑3  | Data Eng      | SEMrush Site Audit integration & cost guardrail |
| W‑4  | QA            | All BDD tests pass; prod cut‑over               |

---

## 8 Open Questions

1. GPT‑4o Vision cost—finance sign‑off required for \$10/day pilot cap.
2. Are rubric weights (0.10 each) acceptable in scoring YAML?
3. SEMrush quota scaling—need paid plan confirmation.

*Document history*: v0.2 adds rubric criteria table, fallback handling, SEMrush issue mapping, and scoring integration per reviewer feedback.
