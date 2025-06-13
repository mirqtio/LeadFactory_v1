
# Anthrasite  –  LeadFactory MVP

### PRD v 1.2 (2025-06-13) “Yelp-Only Week 1 – Full-Stack Assessments”

---

## 0 Ground Rules

| Rule                      | Detail                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **Prod-only**             | One Docker-Compose stack (`app`, `db`, `prometheus`, `grafana`), no “dev” split.                    |
| **Live smoke tests**      | Every external API hit once in `tests/smoke/…`; CI fails if any smoke test fails.                   |
| **Yelp quota**            | Hard-cap 300 calls / day (≈ 15 000 leads).                                                          |
| **Data Axle trial**       | Used *only* for enrichment (email & firmographics) while trial credits last; **not** a lead source. |
| **Per-lead cost ceiling** | ≤ \$0.055, including new assessors.                                                                 |

---

## 1 Environment (.env)

```
ENVIRONMENT=production
BASE_URL=https://anthrasite.io
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/app

YELP_API_KEY=
DATA_AXLE_API_KEY=        # 14-day trial token, optional
SEMRUSH_API_KEY=
SCREENSHOTONE_KEY=
HUNTER_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

MAX_DAILY_YELP_CALLS=300
MAX_DAILY_EMAILS=100000
```

---

## 2 Lead Flow (Week 1)

```
Yelp 300/d  ──┐
              │  (Hunter & optional DataAxle trial fill missing emails)
              └─  Assessment Stack  ──  Scoring  ──  Personaliser
                                               │
                                         SendGrid email
                                               │
                                         Stripe purchase
                                               │
                                         PDF Report
```

*Only one true lead source, so deduplication is **disabled for now**, but the code path exists for later.*

---

## 3 Gateway Providers (production endpoints & smoke tests)

| Provider                       | Endpoint(s)                         | Day Quota     | Unit cost    | Smoke test                                       |
| ------------------------------ | ----------------------------------- | ------------- | ------------ | ------------------------------------------------ |
| **yelp**                       | `/businesses/search` + `?limit=50`  | 300           | \$0          | `test_smoke_yelp.py`                             |
| **data\_axle\_api** (optional) | `GET /v1/companies/enrich?domain=`  | trial—credit  | free (trial) | `test_smoke_data_axle.py` (skipped if key empty) |
| **hunter**                     | `/v2/domain-search`                 | pay-as-you-go | \$0.003      | `test_smoke_hunter.py`                           |
| **semrush**                    | `/domain/overview`                  | 1 000         | \$0.010      | `test_smoke_semrush.py`                          |
| **screenshotone**              | `POST /take`                        | 2/s           | \$0.010      | `test_smoke_screenshotone.py`                    |
| **openai\_vision**             | `/chat/completions`                 | 60 k tok/min  | \$0.0045/k   | `test_smoke_openai_vision.py`                    |
| **google\_places**             | `place/findplace` + `place/details` | 5 000         | \$0.002      | `test_smoke_gbp.py`                              |

Smoke tests cost ≈ \$0.04/run.

---

## 4 Lead Sourcing

### 4.1 YelpScraper

*300 calls × 50 results → ≈ 15 000 leads/day.*
Use search parameters `(term="", location=ZIP or city, sort_by=best_match)`.

### 4.2 Email enrichment

```python
if not business.email:
    # Try Hunter first
    email, conf = hunter.domain_search(domain)
    if conf >= 0.75: business.email = email
    elif DATA_AXLE_API_KEY:
        data = dataaxle.enrich(domain)   # trial call
        if data.email: business.email = data.email
```

---

## 5 Assessment Stack (all leads)

| Assessor           | Timeout | Cost/lead | Outputs (columns)                                                             |
| ------------------ | ------- | --------- | ----------------------------------------------------------------------------- |
| PageSpeed          | 15 s    | free      | performance\_score, seo\_score, …                                             |
| BeautifulSoup      | 5 s     | free      | bsoup\_json                                                                   |
| SEMrush            | 5 s     | \$0.010   | semrush\_json                                                                 |
| YelpSearchFields ✱ | 0 s     | free      | yelp\_json (rating, review\_count, price, categories) – **no extra API call** |
| GBPProfile         | 5 s     | \$0.002   | gbp\_profile\_json                                                            |
| ScreenshotOne      | 8 s     | \$0.010   | screenshot\_url, screenshot\_thumb\_url                                       |
| GPT-4o Vision      | 12 s    | \$0.003   | visual\_scores\_json, visual\_warnings, visual\_quickwins                     |

### 5.1 GPT-4o Vision full prompt

```
You are a senior web-design auditor.
Given this full-page screenshot, return STRICT JSON:

{
 "scores":{         // 0-5 ints
   "visual_appeal":0,
   "readability":0,
   "modernity":0,
   "brand_consistency":0,
   "accessibility":0
 },
 "style_warnings":[ "…", "…" ],  // max 3
 "quick_wins":[ "…", "…" ]       // max 3
}

Scoring rubric:
visual_appeal = aesthetics / imagery
readability   = typography & contrast
modernity     = feels current vs outdated
brand_consistency = colours/images align w/ name
accessibility = obvious a11y issues (alt-text, contrast)

Give short bullet phrases only.  Return JSON ONLY.
```

---

## 6 Scoring Rules (additions only)

```yaml
visual_readability_low:
  weight: 0.07
  rule: "assessment.visual.scores.readability < 3"

visual_outdated:
  weight: 0.05
  rule: "assessment.visual.scores.modernity < 3"

seo_low_keywords:
  weight: 0.15
  rule: "assessment.semrush.organic_keywords < 10"

listing_gap:
  weight: 0.05
  rule: "assessment.gbp.hours_missing == true or assessment.yelp_json.review_count < 5"
```

Weights re-normalised so total = 1.0.

---

## 7 Personaliser Content Logic

1. **Listing quick-win**
   *Pick one gap* (missing hours on GBP OR review\_count<5 on Yelp).
   *Value estimate*: use `$1 k – $3 k / yr` heuristics (not \$300) to make impact credible.

2. **Site teaser**
   Third-highest `$business_impact` issue after excluding the quick-win.
   Example line:
   *“Your mobile pages shift on load (CLS 0.62) – our data shows stores like yours lose ≈ \$2.1 k / yr from this.”*

---

## 8 Database Migration (Postgres)

```sql
ALTER TABLE businesses
  ADD COLUMN domain_hash TEXT,
  ADD COLUMN phone_hash  TEXT;

ALTER TABLE assessment_results
  ADD COLUMN bsoup_json JSONB,
  ADD COLUMN semrush_json JSONB,
  ADD COLUMN yelp_json   JSONB,
  ADD COLUMN gbp_profile_json JSONB,
  ADD COLUMN screenshot_url TEXT,
  ADD COLUMN screenshot_thumb_url TEXT,
  ADD COLUMN visual_scores_json JSONB,
  ADD COLUMN visual_warnings JSONB,
  ADD COLUMN visual_quickwins JSONB;
CREATE INDEX idx_business_domain_hash ON businesses(domain_hash);
```

*No data\_axle\_id field for now.*

---

## 9 Prefect Flows

| Flow                   | Schedule (UTC) | Notes                                                |
| ---------------------- | -------------- | ---------------------------------------------------- |
| **leadfactory\_daily** | `0 5 * * *`    | Sourcing (Yelp) → enrichment → assessments → emails. |

*(No Data Axle diff flow in this version.)*

---

## 10 CI Workflow

```
pytest -m "not smoke_production"        # unit + integration (mocked)
docker compose up -d --build
pytest -m smoke_production --maxfail=1  # live tests, cost ≈ $0.04
```

---

## 11 Acceptance for Claude

Claude must:

1. Apply migration to the `db` container.
2. Implement YelpSearchFields assessor (no extra API call), new providers, enrichment, scoring, personaliser logic, smoke tests.
3. Respect `MAX_DAILY_YELP_CALLS=300` token bucket.
4. CI green