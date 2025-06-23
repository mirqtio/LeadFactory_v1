
## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Delta Scope & Success Criteria](#2-delta-scope--success-criteria)
3. [Tech-wide Additions](#3-tech-wide-additions)
4. [D0 Gateway – New Providers & Cost Ledger](#4-d0-gateway—new-providers--cost-ledger)
5. [D1 Targeting – Geo/Vertical Buckets](#5-d1-targeting—geovertical-buckets)
6. [D4 Enrichment – Provider Fan-out Logic](#6-d4-enrichment—provider-fan-out-logic)
7. [D10 Analytics – Cost & Profit Views](#7-d10-analytics—cost--profit-views)
8. [D11 Orchestration – Nightly Jobs & Guard-rail](#8-d11-orchestration—nightly-jobs--guard-rail)
9. [Environment & Config Keys](#9-environment--config-keys)
10. [Testing & CI Updates](#10-testing--ci-updates)
11. [Task Breakdown & Effort](#11-task-breakdown--effort)

---

## 1 Executive Summary

Phase 0.5 closes all functional gaps discovered since the original MVP code-freeze:

* **Email coverage** – add Data Axle “Match” API (+38–45 % hits) and optional Hunter fallback.
* **Cost visibility** – track \$ at API call-level; drive live profit per email.
* **Targeting intelligence** – tag every lead with **geo\_bucket** & **vert\_bucket** for immediate CTR/purchase roll-ups.
* **Spend safety** – Prefect guard-rail kills pipeline if last-24 h variable cost > \$1 000 (configurable).
* **Deploy control** – Windsurf `--set` flags toggle providers, score cut-offs, optional audits.

Go-live gate: **one 7-day exploratory burst completes ≤ \$5 k variable spend and prints profit/day ≥ \$0**.

---

## 2 Delta Scope & Success Criteria

| Theme                    | Success KPI                                                                                                                |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Provider integration** | ≥ 40 % of leads missing an email after Yelp now carry one from Data Axle/Hunter.                                           |
| **Cost tracking**        | `fct_api_cost` rows exist for ≥ 98 % of external calls; Metabase *unit\_economics\_day* shows cost ±2 % vs Stripe revenue. |
| **Bucket tagging**       | 100 % of new leads have non-null `geo_bucket`, `vert_bucket`; `bucket_performance` view returns ≥ 90 buckets.              |
| **Spend guard-rail**     | Prefect flow terminates run when `sum(cost_usd)[24 h] > $1 000`; log shows exit reason.                                    |
| **Deploy flags**         | Docs show one-liner to turn Data Axle on/off; regression tests pass in both modes.                                         |

---

## 3 Tech-wide Additions

* **New domain tables**

  * `fct_api_cost (lead_id, provider, cost_usd, created_at)`
* **New Lead columns**

  * `geo_bucket VARCHAR(80)`, `vert_bucket VARCHAR(80)`
* **CSV lookup seeds** (committed under `/data/seed/`)

  * `geo_features.csv` – ZIP-level affluence, broadband, agency density
  * `vertical_features.csv` – Yelp category job-value, urgency, maturity
* **New Prometheus metrics**

  * `gateway_api_cost_usd_total{provider}`
  * `bucket_profit_per_email`
* **Prefab Jupyter notebook** `/analytics/notebooks/bucket_profit.ipynb`

---

## 4 D0 Gateway – New Providers & Cost Ledger

### 4.1 Data Axle Provider

* **Endpoint** `POST /v2/business/match`
* Retry: `3 attempts`, back-off `2 s`
* Rate limit: `DATA_AXLE_RATE_LIMIT_PER_MIN` (env var)
* **Cost model**: \$0.05 / successful match (trial cost \$0)

### 4.2 Hunter Provider (optional)

* Endpoint `GET /v2/email-finder`
* Rate limit: fixed Free-tier 25/day (guard in client)
* Cost model: \$0.01 / successful email (used only if Data Axle missing)

### 4.3 Cost Ledger Hook

* `emit_cost(lead_id, provider, cost_usd)` inserts into `fct_api_cost`.
* Called **once per successful match** or per paid OpenAI, PageSpeed invocation (retrofit existing providers).

---

## 5 D1 Targeting – Geo/Vertical Buckets

### 5.1 Bucket Definition

| Dimension        | Bucketing rule                                      | Values       |
| ---------------- | --------------------------------------------------- | ------------ |
| `affluence_tier` | ZIP median income terciles                          | low/med/high |
| `agency_density` | z-score > 0.5 = *high*                              | low/high     |
| `broadband_tier` | ≥ 90 % 25 Mbps = *hi* else *lo*                     | hi/lo        |
| `urgency_flag`   | HVAC/Plumbing/Electrical/Roof = 1                   | 0/1          |
| `ticket_band`    | <\$500, \$500-5k, >\$5k                             | low/mid/high |
| `maturity`       | `website_age_bucket` 0-2 -> immature, 3-5 -> mature | low/high     |

* **`geo_bucket`** = `{affluence}-{density}-{broadband}` → 12 combos
* **`vert_bucket`** = `{urgency}-{ticket}-{maturity}` → 8 combos

### 5.2 Lookup & Nightly ETL

* Prefect flow `bucket_enrichment` joins new ZIP & vertical CSV LUTs to every lead & target.
* Missing ZIPs/categories get logged to `etl_missing_dim` table.

---

## 6 D4 Enrichment – Provider Fan-out Logic

1. **Yelp record** arrives →
2. If `PROVIDERS.DATA_AXLE.enabled`

   * call Data Axle; merge `emails[0]`, `phones[0]`, firmographics
   * `emit_cost()` \$0.05
3. If `lead.email is NULL` **AND** `PROVIDERS.HUNTER.enabled`

   * call Hunter; merge first email; `emit_cost()` \$0.01
4. Commit lead; downstream Assessment unchanged.

---

## 7 D10 Analytics – Cost & Profit Views

### 7.1 `unit_economics_day`

```sql
SELECT
  date_trunc('day', e.sent_at) AS day,
  COUNT(*)                                       AS emails_sent,
  SUM(purchased)::int                            AS purchases,
  SUM(price * purchased)                         AS gross_revenue,
  SUM(f.cost_usd)                                AS variable_cost,
  SUM(price * purchased - f.cost_usd)            AS profit
FROM emails e
LEFT JOIN purchases p USING (business_id)
LEFT JOIN fct_api_cost f USING (lead_id)
GROUP BY 1;
```

### 7.2 `bucket_performance`

```sql
SELECT
  geo_bucket, vert_bucket,
  COUNT(*)                       AS emails,
  SUM(purchased)::int            AS buys,
  SUM(price * purchased) / NULLIF(COUNT(*),0) - 0.073 AS profit_per_email
FROM emails e
JOIN businesses b ON b.id = e.business_id
LEFT JOIN purchases p USING (business_id)
LEFT JOIN fct_api_cost c USING (lead_id)
GROUP BY 1,2;
```

---

## 8 D11 Orchestration – Nightly Jobs & Guard-rail

| Flow                | Schedule        | Action                                                                       |
| ------------------- | --------------- | ---------------------------------------------------------------------------- |
| `bucket_enrichment` | 02:00 UTC daily | Refresh buckets for all new leads & targets.                                 |
| `cost_guardrail`    | Hourly          | Abort pipeline if `sum(cost_usd)[24h] > COST_BUDGET_USD` (env default 1000). |
| `profit_snapshot`   | 03:00 UTC daily | Print yesterday’s `profit` from `unit_economics_day` to Slack/CLI.           |

---

## 9 Environment & Config Keys

```dotenv
# Providers
DATA_AXLE_API_KEY=
DATA_AXLE_BASE_URL=https://api.data-axle.com/v2
DATA_AXLE_RATE_LIMIT_PER_MIN=200
HUNTER_API_KEY=
HUNTER_RATE_LIMIT_PER_MIN=30

# Feature flags
PROVIDERS.DATA_AXLE.enabled=true
PROVIDERS.HUNTER.enabled=false
LEAD_FILTER_MIN_SCORE=0          # 0 = wide-open exploratory
ASSESSMENT_OPTIONAL=true         # run screenshot/Lighthouse

# Spend guard-rail
COST_BUDGET_USD=1000
```

---

## 10 Testing & CI Updates

* **Unit tests**

  * Provider client happy-path + 429/back-off.
  * `bucket_enrichment` populates correct bucket strings.
* **Integration**

  * End-to-end flow with stubs for Data Axle & Hunter; asserts email has an address.
* **CI**: Add `tests/providers/` to coverage; Docker test container now installs `pymc` optionally (for notebook—skip if heavy).

---

## 11 Task Breakdown & Effort (≈ 8 h total)

| ID         | Title                                              | Domain             | Est (h)   |
| ---------- | -------------------------------------------------- | ------------------ | --------- |
| **DX-01**  | Add env keys & config blocks                       | core               | 0.3       |
| **GW-02**  | Implement Data Axle client, register factory       | d0\_gateway        | 1.0       |
| **GW-03**  | Implement Hunter client (fallback)                 | d0\_gateway        | 0.7       |
| **GW-04**  | Cost ledger table + helper                         | d0\_gateway / db   | 0.5       |
| **EN-05**  | Modify enrichment flow (fan-out + cost)            | d4\_enrichment     | 0.8       |
| **TG-06**  | Bucket columns migration + CSV seeds               | d1\_targeting / db | 0.7       |
| **ET-07**  | Nightly `bucket_enrichment` Prefect flow           | d11\_orchestration | 0.8       |
| **AN-08**  | Views `unit_economics_day`, `bucket_performance`   | d10\_analytics     | 0.6       |
| **OR-09**  | Prefect `cost_guardrail` & `profit_snapshot` flows | d11\_orchestration | 0.5       |
| **TS-10**  | Unit & integration tests                           | tests              | 1.0       |
| **DOC-11** | README & provider docs                             | docs               | 0.4       |
| **NB-12**  | Jupyter notebook for hierarchical model (template) | analytics          | 0.5       |
| **TOTAL**  | —                                                  | —                  | **7.8 h** |

---

### Deployment one-liner after merge

```bash
windsurf deploy \
  --set PROVIDERS.DATA_AXLE.enabled=true \
  --set PROVIDERS.HUNTER.enabled=false \
  --set LEAD_FILTER_MIN_SCORE=0 \
  --set ASSESSMENT_OPTIONAL=true \
  --set COST_BUDGET_USD=1000
```

---

### End-state assurance
