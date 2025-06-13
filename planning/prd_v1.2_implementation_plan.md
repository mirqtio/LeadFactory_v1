# PRD v1.2 Implementation Plan

## Overview
Implementation plan for LeadFactory MVP v1.2 "Yelp-Only Week 1 – Full-Stack Assessments"

## Key Changes from Current State
1. **New Assessment Stack**: Add 7 assessors including SEMrush, ScreenshotOne, GPT-4o Vision
2. **Email Enrichment**: Hunter.io primary, Data Axle fallback (trial)
3. **New Database Schema**: Add columns for new assessment data
4. **Production-Only**: Single Docker Compose stack
5. **Smoke Tests**: Live API tests for all providers

## Implementation Tasks

### Phase 1: Environment & Configuration
- [ ] **ENV-01**: Update .env with new API keys
  - Add: SEMRUSH_API_KEY, SCREENSHOTONE_KEY (already added), HUNTER_API_KEY
  - Add: MAX_DAILY_YELP_CALLS=300, MAX_DAILY_EMAILS=100000
  - Verify: DATA_AXLE_API_KEY exists

### Phase 2: Database Migration
- [ ] **DB-01**: Create and apply migration
  ```sql
  ALTER TABLE businesses
    ADD COLUMN domain_hash TEXT,
    ADD COLUMN phone_hash TEXT;

  ALTER TABLE assessment_results
    ADD COLUMN bsoup_json JSONB,
    ADD COLUMN semrush_json JSONB,
    ADD COLUMN yelp_json JSONB,
    ADD COLUMN gbp_profile_json JSONB,
    ADD COLUMN screenshot_url TEXT,
    ADD COLUMN screenshot_thumb_url TEXT,
    ADD COLUMN visual_scores_json JSONB,
    ADD COLUMN visual_warnings JSONB,
    ADD COLUMN visual_quickwins JSONB;
    
  CREATE INDEX idx_business_domain_hash ON businesses(domain_hash);
  ```

### Phase 3: Gateway Providers
- [ ] **GW-01**: Fix Hunter.io client implementation
  - Endpoint: `/v2/domain-search`
  - Cost: $0.003 per search
  - Implement domain_search method

- [ ] **GW-02**: Implement SEMrush client
  - Endpoint: `/domain/overview`
  - Cost: $0.010 per call
  - Daily quota: 1,000

- [ ] **GW-03**: Fix ScreenshotOne implementation
  - Already have API key
  - Cost: $0.010 per screenshot
  - Rate limit: 2/s

- [ ] **GW-04**: Update OpenAI for GPT-4o Vision
  - Model: gpt-4o-mini
  - Cost: $0.0045 per 1k tokens
  - Implement vision analysis

- [ ] **GW-05**: Implement token bucket for Yelp
  - Hard cap: 300 calls/day
  - Implement rate limiting

### Phase 4: Assessment Stack
- [ ] **AS-01**: Implement BeautifulSoup assessor
  - Extract page content as JSON
  - Timeout: 5s
  - No external API

- [ ] **AS-02**: Implement SEMrush assessor
  - Get domain overview
  - Extract organic keywords
  - Timeout: 5s

- [ ] **AS-03**: Implement YelpSearchFields assessor
  - Extract from existing Yelp data (no API call)
  - Fields: rating, review_count, price, categories

- [ ] **AS-04**: Implement GBPProfile assessor
  - Use existing Google Places client
  - Cost: $0.002 per call
  - Timeout: 5s

- [ ] **AS-05**: Integrate ScreenshotOne assessor
  - Full page screenshot
  - Generate thumbnail
  - Timeout: 8s

- [ ] **AS-06**: Implement GPT-4o Vision assessor
  - Use provided prompt
  - Extract visual scores and recommendations
  - Timeout: 12s

### Phase 5: Scoring Updates
- [ ] **SC-01**: Add new scoring rules
  - visual_readability_low (weight: 0.07)
  - visual_outdated (weight: 0.05)
  - seo_low_keywords (weight: 0.15)
  - listing_gap (weight: 0.05)
  - Re-normalize weights

### Phase 6: Email Enrichment
- [ ] **EM-01**: Implement Hunter-first enrichment
  ```python
  if not business.email:
      email, conf = hunter.domain_search(domain)
      if conf >= 0.75: business.email = email
      elif DATA_AXLE_API_KEY:
          data = dataaxle.enrich(domain)
          if data.email: business.email = data.email
  ```

### Phase 7: Personalizer Updates
- [ ] **PR-01**: Update listing quick-win logic
  - Value estimates: $1k-$3k/yr
  - Pick GBP hours or Yelp reviews gap

- [ ] **PR-02**: Update site teaser logic
  - Third-highest business impact issue
  - Include specific metrics

### Phase 8: Smoke Tests
- [ ] **ST-01**: Create smoke test suite
  - test_smoke_yelp.py
  - test_smoke_data_axle.py (skip if no key)
  - test_smoke_hunter.py
  - test_smoke_semrush.py
  - test_smoke_screenshotone.py
  - test_smoke_openai_vision.py
  - test_smoke_gbp.py

### Phase 9: CI/CD Updates
- [ ] **CI-01**: Update GitHub Actions workflow
  - Run unit tests (mocked)
  - Build Docker containers
  - Run smoke tests (live APIs)
  - Fail on any smoke test failure

### Phase 10: Integration & Testing
- [ ] **IT-01**: Full pipeline test
  - Source 50 leads from Yelp
  - Run all assessments
  - Verify scoring
  - Test email generation

## Success Criteria
1. All smoke tests pass in production
2. Per-lead cost ≤ $0.055
3. Yelp quota respected (300/day)
4. CI/CD pipeline green
5. Full assessment stack operational

## Estimated Timeline
- Phase 1-2: 2 hours (config & DB)
- Phase 3: 4 hours (providers)
- Phase 4: 6 hours (assessments)
- Phase 5-7: 3 hours (scoring & personalization)
- Phase 8-9: 3 hours (testing & CI)
- Phase 10: 2 hours (integration)
- **Total: 20 hours**