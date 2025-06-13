# PRD v1.2 Action Plan

## Executive Summary
Implement "Yelp-Only Week 1 – Full-Stack Assessments" MVP with new assessment stack, email enrichment, and production deployment.

## Current State Analysis
- ✅ Basic Yelp sourcing exists
- ✅ Google Places API working
- ✅ ScreenshotOne API key added
- ❌ Missing: SEMrush, Hunter, Data Axle integrations
- ❌ Missing: New assessors (BeautifulSoup, SEMrush, YelpSearchFields, Vision)
- ❌ Missing: Database columns for new assessment data
- ❌ Missing: Smoke tests for all providers
- ❌ Missing: Yelp rate limiting (300/day)

## Implementation Phases

### Phase 1: Database Migration (1 hour)
**Priority: CRITICAL - Must do first**

1. Create migration `005_prd_v1_2_assessment_columns.py`
   - Add domain_hash, phone_hash to businesses
   - Add 9 new JSONB/TEXT columns to assessment_results
   - Create index on domain_hash

### Phase 2: Environment Configuration (30 min)
1. Update `.env.example` with new keys
2. Update `core/config.py` with new settings
3. Add MAX_DAILY_YELP_CALLS=300, MAX_DAILY_EMAILS=100000

### Phase 3: Gateway Provider Implementation (4 hours)

#### 3.1 Hunter.io Client
- Endpoint: `/v2/domain-search`
- Cost tracking: $0.003 per search
- Confidence threshold: 0.75
- File: `d0_gateway/providers/hunter.py`

#### 3.2 SEMrush Client  
- Endpoint: `/domain/overview`
- Cost tracking: $0.010 per call
- Daily quota: 1,000
- File: `d0_gateway/providers/semrush.py`

#### 3.3 Data Axle Client (Enhancement)
- Endpoint: `GET /v1/companies/enrich?domain=`
- Trial mode only
- File: Update existing `d0_gateway/providers/dataaxle.py`

#### 3.4 Yelp Rate Limiter
- Token bucket: 300 calls/day
- File: Update `d0_gateway/providers/yelp.py`

### Phase 4: Assessment Stack Implementation (6 hours)

#### 4.1 BeautifulSoup Assessor
- Extract page structure as JSON
- No external API
- Timeout: 5s
- File: `d3_assessment/assessors/beautifulsoup_assessor.py`

#### 4.2 SEMrush Assessor
- Get domain metrics
- Extract organic_keywords count
- Timeout: 5s
- File: `d3_assessment/assessors/semrush_assessor.py`

#### 4.3 YelpSearchFields Assessor
- Extract from existing Yelp data (NO API CALL)
- Fields: rating, review_count, price, categories
- File: `d3_assessment/assessors/yelp_fields_assessor.py`

#### 4.4 GBPProfile Assessor
- Use existing Google Places client
- Check for missing hours
- File: `d3_assessment/assessors/gbp_profile_assessor.py`

#### 4.5 ScreenshotOne Integration
- Full page screenshot
- Generate thumbnail
- Timeout: 8s
- File: Update existing screenshot assessor

#### 4.6 GPT-4o Vision Assessor
- Use exact prompt from PRD
- Model: gpt-4o-mini
- Extract scores and recommendations
- File: `d3_assessment/assessors/vision_assessor.py`

### Phase 5: Email Enrichment Logic (2 hours)

1. Update `d4_enrichment/coordinator.py`:
```python
if not business.email:
    # Try Hunter first
    email, conf = await hunter.domain_search(domain)
    if conf >= 0.75: 
        business.email = email
    elif self.config.DATA_AXLE_API_KEY:
        data = await dataaxle.enrich(domain)
        if data and data.get('email'):
            business.email = data['email']
```

### Phase 6: Scoring Updates (1 hour)

1. Add new rules to `d9_scoring/rules.yaml`:
   - visual_readability_low (0.07)
   - visual_outdated (0.05)
   - seo_low_keywords (0.15)
   - listing_gap (0.05)

2. Update score calculator to re-normalize weights

### Phase 7: Personalizer Updates (1 hour)

1. Update value estimates: $1k-$3k/yr (not $300)
2. Listing quick-win: GBP hours OR Yelp reviews < 5
3. Site teaser: Third-highest business impact

### Phase 8: Smoke Tests (3 hours)

Create `tests/smoke/` directory with:
- `test_smoke_yelp.py`
- `test_smoke_hunter.py`
- `test_smoke_semrush.py`
- `test_smoke_screenshotone.py`
- `test_smoke_openai_vision.py`
- `test_smoke_gbp.py`
- `test_smoke_data_axle.py` (skip if no key)

### Phase 9: CI/CD Updates (1 hour)

1. Update GitHub Actions workflow
2. Add smoke test stage after Docker build
3. Fail on any smoke test failure

### Phase 10: Integration Testing (2 hours)

1. Run full pipeline with 50 Yelp leads
2. Verify all assessments complete
3. Check total cost per lead ≤ $0.055
4. Verify email enrichment works

## Success Metrics

- [ ] All smoke tests pass
- [ ] Per-lead cost ≤ $0.055
- [ ] Yelp respects 300/day limit
- [ ] All 7 assessors functional
- [ ] Email enrichment > 75% coverage
- [ ] CI pipeline green

## Risk Mitigation

1. **API Keys**: Verify all keys in .env before starting
2. **Rate Limits**: Implement backoff for all providers
3. **Cost Control**: Add cost tracking to all paid APIs
4. **Timeouts**: Strict timeout enforcement on assessors
5. **Smoke Tests**: Run locally before CI to save costs

## Execution Order

1. Database migration (blocks everything)
2. Environment config
3. Provider implementations (can parallelize)
4. Assessor implementations (can parallelize)
5. Email enrichment
6. Scoring/Personalizer updates
7. Smoke tests
8. CI/CD
9. Full integration test

**Total Estimated Time: 20 hours**