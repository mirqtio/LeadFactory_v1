You're absolutely right! Let me create a comprehensive master PRD that incorporates all the detailed specifications from your 30+ domain and feature PRDs. This will be the definitive implementation guide.

# LeadFactory MVP - Comprehensive Master PRD

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Technical Architecture & Constraints](#2-technical-architecture--constraints)
3. [D0: External Data Gateway - Complete Specification](#3-d0-external-data-gateway)
4. [D1: Targeting - Complete Specification](#4-d1-targeting)
5. [D2: Lead Sourcing - Complete Specification](#5-d2-lead-sourcing)
6. [D3: Assessment - Complete Specification](#6-d3-assessment)
7. [D4: Enrichment - Complete Specification](#7-d4-enrichment)
8. [D5: Scoring & Filtering - Complete Specification](#8-d5-scoring--filtering)
9. [D6: Audit Report Builder - Complete Specification](#9-d6-audit-report-builder)
10. [D7: Storefront & Purchase Flow - Complete Specification](#10-d7-storefront--purchase-flow)
11. [D8: Personalization - Complete Specification](#11-d8-personalization)
12. [D9: Delivery & Compliance - Complete Specification](#12-d9-delivery--compliance)
13. [D10: Analytics & Reporting - Complete Specification](#13-d10-analytics--reporting)
14. [D11: Orchestration & Experimentation - Complete Specification](#14-d11-orchestration--experimentation)
15. [Testing Strategy & CI-First Development](#15-testing-strategy--ci-first-development)
16. [Task Execution Plan](#16-task-execution-plan)

---

## 1. Executive Summary

### 1.1 Vision & Goals
**Vision**: Build an AI-powered website audit platform that generates revenue through automated audit report sales, starting with $25k MRR within 6 weeks.

**Phase 0 Goals (This Build)**:
- Process businesses daily from various data sources
- Score and filter to top 10% (500 qualified leads)
- Send personalized emails with audit teasers
- Sell detailed reports at $199 (launch price)
- Achieve 0.25-0.6% conversion rate
- Generate first revenue within 48-72 hours

**Note**: Yelp provider was removed in July 2025; see CHANGELOG.

### 1.2 Development Approach
- **Single developer** using autonomous AI (Claude Code in Windsurf)
- **TaskMaster MCP** for task breakdown and management
- **Context7 MCP** for current documentation
- **CI-First Development** - all tests run in Docker matching production
- **48-72 hour timeline** for revenue-generating MVP

### 1.3 Critical Success Metrics
- Pipeline processes: Yelp → Assessment → Scoring → Email → Payment → Report
- All tests pass in Docker (zero local/CI discrepancies)
- System sends 100+ emails daily
- Stripe payments functional in test mode
- PDF reports generate in <30 seconds
- First revenue within 72 hours

---

## 2. Technical Architecture & Constraints

### 2.1 System Architecture Overview
```
LeadFactory/
├── core/                   # Shared utilities, config, error handling
├── database/               # SQLAlchemy models, migrations
├── d0_gateway/            # External API facade (all third-party calls)
├── d1_targeting/          # Geo × vertical campaign management  
├── d2_sourcing/           # Yelp data acquisition
├── d3_assessment/         # Website analysis (PageSpeed, tech, LLM)
├── d4_enrichment/         # Google Business Profile data
├── d5_scoring/            # Lead qualification engine
├── d6_reports/            # PDF/HTML report generation
├── d7_storefront/         # Stripe checkout flow
├── d8_personalization/    # Email content generation
├── d9_delivery/           # SendGrid integration
├── d10_analytics/         # Metrics and reporting
├── d11_orchestration/     # Prefect workflows
├── stubs/                 # Mock external services
├── tests/                 # All tests (CI-first)
├── planning/              # TaskMaster files
└── scripts/               # Deployment, utilities
```

### 2.2 Technology Stack
```yaml
Core:
  Language: Python 3.11.0 (exact version for CI)
  Framework: FastAPI 0.104.1
  ORM: SQLAlchemy 2.0.23
  Database: SQLite (MVP), PostgreSQL 15 (production)

External Services:
  Yelp: Fusion API v3 (5,000 calls/day free tier)
  SendGrid: v3 API (shared IPs)
  Stripe: Checkout API (test mode)
  Google: PageSpeed Insights API v5
  OpenAI: GPT-4o-mini for analysis

Infrastructure:
  Development: Mac Mini M4 (10 cores, 24GB RAM)
  Testing: Docker containers matching CI
  CI/CD: GitHub Actions
  Monitoring: Prometheus + Grafana (basic)
```

### 2.3 Constraints
- **API Limits**: Yelp 5k/day, PageSpeed 25k/day
- **Budget**: <$0.02 per lead analyzed
- **Performance**: Process 250k businesses from 5k API calls in 4 hours
- **Email**: Max 100/day initially (deliverability)
- **Single-threaded**: One AI task at a time

---

## 3. D0: External Data Gateway

### 3.1 Purpose
Unified facade for all external APIs with caching, rate limiting, circuit breakers, and cost tracking. No other domain makes direct external calls.

### 3.2 Detailed Components

#### 3.2.1 Gateway Architecture
```python
# d0_gateway/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class BaseAPIClient(ABC):
    """Base class for all external API clients"""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    @abstractmethod
    def get_rate_limit(self) -> Dict[str, int]:
        """Return rate limits for this API"""
        pass
        
    @abstractmethod
    def calculate_cost(self, operation: str) -> float:
        """Calculate cost in USD for an operation"""
        pass
```

#### 3.2.2 Rate Limiter
```python
# d0_gateway/rate_limiter.py
import asyncio
from datetime import datetime, timedelta
from typing import Dict
import redis.asyncio as redis

class TokenBucketRateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        
    async def check_and_consume(
        self,
        provider: str,
        tokens_requested: int = 1
    ) -> bool:
        """Check if tokens available and consume if so"""
        key = f"rate_limit:{provider}"
        
        # Lua script for atomic check-and-consume
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local tokens = tonumber(ARGV[2])
        local refill_rate = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        local current = redis.call('HGETALL', key)
        -- Implementation details...
        """
        # Returns True if tokens consumed, False if limit exceeded
```

#### 3.2.3 Circuit Breaker
```python
# d0_gateway/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
```

#### 3.2.4 Response Cache
```python
# d0_gateway/cache.py
import hashlib
import json
from typing import Optional, Dict, Any
import redis.asyncio as redis

class ResponseCache:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        
    def _generate_key(
        self,
        provider: str,
        endpoint: str,
        params: Dict[str, Any]
    ) -> str:
        """Generate cache key from request parameters"""
        content = f"{provider}:{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()
        
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response"""
        data = await self.redis.get(f"cache:{key}")
        return json.loads(data) if data else None
```

### 3.3 Provider Implementations

#### 3.3.1 Yelp Client
```python
# d0_gateway/providers/yelp.py
class YelpClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            api_key=settings.YELP_API_KEY,
            base_url="https://api.yelp.com/v3"
        )
        self.daily_limit = 5000
        self.burst_limit = 10  # calls per second
        
    async def search_businesses(
        self,
        location: str,
        categories: str,
        offset: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Search businesses with automatic pagination"""
        # Implementation with rate limiting, caching, circuit breaker
```

### 3.4 Metrics & Monitoring
```python
# d0_gateway/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
api_calls_total = Counter(
    'gateway_api_calls_total',
    'Total API calls',
    ['provider', 'endpoint', 'status']
)

api_latency_seconds = Histogram(
    'gateway_api_latency_seconds',
    'API call latency',
    ['provider', 'endpoint']
)

api_cost_usd_total = Counter(
    'gateway_api_cost_usd_total',
    'Total API costs in USD',
    ['provider', 'endpoint']
)

circuit_breaker_state = Gauge(
    'gateway_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['provider']
)
```

### 3.5 Database Schema
```sql
-- API usage tracking
CREATE TABLE gateway_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    cost_usd DECIMAL(10, 6),
    cache_hit BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER,
    status_code INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rate limit tracking
CREATE TABLE gateway_rate_limits (
    provider VARCHAR(50) PRIMARY KEY,
    daily_limit INTEGER NOT NULL,
    daily_used INTEGER DEFAULT 0,
    burst_limit INTEGER NOT NULL,
    reset_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.6 Testing Requirements
```python
# tests/d0_gateway/test_circuit_breaker.py
@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    """Circuit breaker should open after failure threshold"""
    breaker = CircuitBreaker(failure_threshold=3)
    
    # Simulate failures
    for _ in range(3):
        with pytest.raises(Exception):
            async with breaker:
                raise Exception("Service unavailable")
    
    assert breaker.state == CircuitState.OPEN
    
    # Should reject calls when open
    with pytest.raises(CircuitBreakerError):
        async with breaker:
            pass  # This should not execute
```

---

## 4. D1: Targeting

### 4.1 Purpose
Manage geo × vertical target batches, track freshness, and allocate API quotas across campaigns.

### 4.2 Detailed Components

#### 4.2.1 Target Universe Manager
```python
# d1_targeting/target_universe.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
import asyncio

class TargetUniverseManager:
    def __init__(self, db_session):
        self.db = db_session
        
    async def create_target(
        self,
        geo_type: str,  # "zip", "city", "metro"
        geo_value: str,
        vertical: str,
        estimated_businesses: Optional[int] = None
    ) -> Target:
        """Create a new geo × vertical target"""
        # Validate geo hierarchy conflicts
        conflicts = await self._check_geo_conflicts(geo_type, geo_value)
        if conflicts:
            raise ValueError(f"Geo conflicts detected: {conflicts}")
            
    async def _check_geo_conflicts(
        self,
        geo_type: str,
        geo_value: str
    ) -> List[str]:
        """Check for overlapping geo definitions"""
        # ZIP ⊂ City ⊂ Metro ⊂ State hierarchy validation
```

#### 4.2.2 Batch Scheduler
```python
# d1_targeting/batch_scheduler.py
class BatchScheduler:
    def __init__(self, quota_tracker):
        self.quota_tracker = quota_tracker
        
    async def create_daily_batches(self) -> List[Batch]:
        """Create batches for today respecting quotas"""
        targets = await self._get_active_targets()
        prioritized = await self._prioritize_targets(targets)
        
        batches = []
        remaining_quota = await self.quota_tracker.get_remaining_daily()
        
        for target in prioritized:
            if remaining_quota <= 0:
                break
                
            batch_size = min(
                target.estimated_businesses,
                remaining_quota,
                self.MAX_BATCH_SIZE
            )
            
            batch = await self._create_batch(target, batch_size)
            batches.append(batch)
            remaining_quota -= batch_size
            
        return batches
```

### 4.3 Database Schema
```sql
-- Target definitions
CREATE TABLE targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    geo_type VARCHAR(20) CHECK (geo_type IN ('zip', 'city', 'metro', 'state')),
    geo_value VARCHAR(100) NOT NULL,
    vertical VARCHAR(50) NOT NULL,
    estimated_businesses INTEGER,
    priority_score DECIMAL(3, 2) DEFAULT 0.5,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(geo_type, geo_value, vertical)
);

-- Daily batches
CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id UUID REFERENCES targets(id),
    batch_date DATE NOT NULL,
    planned_size INTEGER NOT NULL,
    actual_size INTEGER,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    UNIQUE(target_id, batch_date)
);
```

---

## 5. D2: Lead Sourcing

### 5.1 Purpose
Fetch business data from Yelp within strict quota limits, handle pagination, and deduplicate results.

### 5.2 Detailed Components

#### 5.2.1 Yelp Scraper
```python
# d2_sourcing/yelp_scraper.py
class YelpScraper:
    def __init__(self, gateway_client):
        self.gateway = gateway_client
        self.MAX_OFFSET = 1000  # Yelp hard limit
        
    async def scrape_batch(self, batch: Batch) -> List[Business]:
        """Scrape all businesses for a batch"""
        businesses = []
        offset = 0
        
        while offset < self.MAX_OFFSET:
            response = await self.gateway.yelp.search_businesses(
                location=batch.target.geo_value,
                categories=batch.target.vertical,
                offset=offset,
                limit=50  # Max per request
            )
            
            if not response['businesses']:
                break
                
            for biz_data in response['businesses']:
                business = await self._process_business(biz_data)
                businesses.append(business)
                
            offset += 50
            
            # Stop if we've hit our batch quota
            if len(businesses) >= batch.planned_size:
                break
                
        return businesses[:batch.planned_size]
```

#### 5.2.2 Business Deduplicator
```python
# d2_sourcing/deduplicator.py
class BusinessDeduplicator:
    def __init__(self, db_session):
        self.db = db_session
        
    async def find_existing(self, yelp_id: str) -> Optional[Business]:
        """Check if business already exists"""
        return await self.db.query(Business).filter(
            Business.yelp_id == yelp_id
        ).first()
        
    async def merge_or_create(
        self,
        yelp_data: Dict[str, Any]
    ) -> Business:
        """Create new or update existing business"""
        existing = await self.find_existing(yelp_data['id'])
        
        if existing:
            # Update with fresh data
            existing.updated_at = datetime.utcnow()
            existing.raw_data = yelp_data
            return existing
        else:
            # Create new
            return Business(
                yelp_id=yelp_data['id'],
                name=yelp_data['name'],
                url=yelp_data.get('url'),
                phone=yelp_data.get('phone'),
                raw_data=yelp_data
            )
```

### 5.3 Testing Requirements
```python
# tests/d2_sourcing/test_scraper.py
@pytest.mark.asyncio
async def test_scraper_respects_quota():
    """Scraper should stop at batch quota even if more results available"""
    mock_gateway = Mock()
    mock_gateway.yelp.search_businesses.return_value = {
        'businesses': [{'id': f'biz_{i}'} for i in range(50)],
        'total': 200
    }
    
    scraper = YelpScraper(mock_gateway)
    batch = Batch(planned_size=75)  # Less than available
    
    businesses = await scraper.scrape_batch(batch)
    
    assert len(businesses) == 75
    assert mock_gateway.yelp.search_businesses.call_count == 2
```

---

## 6. D3: Assessment

### 6.1 Purpose
Analyze each business website to identify issues and opportunities, combining PageSpeed data, technical analysis, and AI insights.

### 6.2 Detailed Components

#### 6.2.1 Assessment Coordinator
```python
# d3_assessment/coordinator.py
class AssessmentCoordinator:
    def __init__(self, gateway_client):
        self.gateway = gateway_client
        self.assessors = {
            'pagespeed': PageSpeedAssessor(gateway_client),
            'techstack': TechStackDetector(),
            'llm': LLMInsightGenerator(gateway_client)
        }
        
    async def assess_business(
        self,
        business: Business,
        assessment_types: List[str] = None
    ) -> AssessmentResult:
        """Run all assessments with timeout and error handling"""
        if assessment_types is None:
            assessment_types = ['pagespeed', 'techstack', 'llm']
            
        results = {}
        errors = []
        
        # Run assessments in parallel with timeout
        tasks = []
        for assessment_type in assessment_types:
            if assessment_type in self.assessors:
                task = asyncio.create_task(
                    self._run_with_timeout(
                        self.assessors[assessment_type].assess(business),
                        timeout=30
                    )
                )
                tasks.append((assessment_type, task))
                
        # Gather results
        for assessment_type, task in tasks:
            try:
                result = await task
                results[assessment_type] = result
            except asyncio.TimeoutError:
                errors.append(f"{assessment_type} timed out")
            except Exception as e:
                errors.append(f"{assessment_type} failed: {e}")
                
        return AssessmentResult(
            business_id=business.id,
            results=results,
            errors=errors
        )
```

#### 6.2.2 PageSpeed Assessor
```python
# d3_assessment/pagespeed.py
class PageSpeedAssessor:
    def __init__(self, gateway_client):
        self.gateway = gateway_client
        
    async def assess(self, business: Business) -> PageSpeedResult:
        """Analyze Core Web Vitals and performance"""
        if not business.url:
            return PageSpeedResult(error="No URL available")
            
        try:
            # Fetch PageSpeed data
            psi_data = await self.gateway.pagespeed.analyze(
                url=business.url,
                strategy='mobile'  # Mobile-first
            )
            
            # Extract key metrics
            lighthouse = psi_data['lighthouseResult']
            
            return PageSpeedResult(
                performance_score=int(lighthouse['categories']['performance']['score'] * 100),
                seo_score=int(lighthouse['categories']['seo']['score'] * 100),
                accessibility_score=int(lighthouse['categories']['accessibility']['score'] * 100),
                best_practices_score=int(lighthouse['categories']['best-practices']['score'] * 100),
                
                # Core Web Vitals
                lcp_ms=self._extract_numeric_value(lighthouse['audits']['largest-contentful-paint']),
                fid_ms=self._extract_numeric_value(lighthouse['audits']['max-potential-fid']),
                cls=self._extract_numeric_value(lighthouse['audits']['cumulative-layout-shift']),
                
                # Key issues
                issues=self._extract_issues(lighthouse['audits'])
            )
        except Exception as e:
            return PageSpeedResult(error=str(e))
```

#### 6.2.3 LLM Insight Generator
```python
# d3_assessment/llm_insights.py
class LLMInsightGenerator:
    def __init__(self, gateway_client):
        self.gateway = gateway_client
        self.max_cost_per_assessment = 0.01
        
    async def assess(self, business: Business) -> LLMInsights:
        """Generate AI-powered insights and recommendations"""
        # Build context from other assessments
        context = await self._build_context(business)
        
        prompt = f"""
        Analyze this {business.vertical} business website and provide exactly 3 actionable recommendations.
        
        Business: {business.name}
        URL: {business.url}
        Performance Score: {context.get('performance_score', 'Unknown')}
        Key Issues: {context.get('issues', [])}
        
        For each recommendation provide:
        1. Specific issue identified
        2. Business impact (how it affects customers/revenue)
        3. Effort estimate (easy/medium/hard)
        4. Expected improvement
        
        Focus on issues that directly impact conversions and user experience.
        Keep recommendations specific to their industry.
        """
        
        response = await self.gateway.openai.complete(
            prompt=prompt,
            model="gpt-4o-mini",
            max_tokens=500,
            temperature=0.3
        )
        
        return self._parse_recommendations(response)
```

### 6.3 Database Schema
```sql
-- Assessment results
CREATE TABLE assessment_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id),
    assessment_type VARCHAR(50) NOT NULL,
    
    -- PageSpeed metrics
    performance_score INTEGER,
    seo_score INTEGER,
    accessibility_score INTEGER,
    best_practices_score INTEGER,
    lcp_ms INTEGER,
    fid_ms INTEGER,
    cls DECIMAL(5, 3),
    
    -- Analysis results
    issues_json JSONB,
    recommendations_json JSONB,
    
    -- Metadata
    cost_usd DECIMAL(10, 6),
    duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_assessment_business_type 
    ON assessment_results(business_id, assessment_type);
```

---

## 7. D4: Enrichment

### 7.1 Purpose
Enhance business data with Google Business Profile information (hours, ratings, reviews) using fuzzy matching.

### 7.2 Detailed Components

#### 7.2.1 GBP Enricher
```python
# d4_enrichment/gbp_enricher.py
class GBPEnricher:
    def __init__(self, gateway_client):
        self.gateway = gateway_client
        self.matchers = [
            PhoneMatcher(weight=0.3),
            NameZipMatcher(weight=0.25),
            AddressMatcher(weight=0.25),
            WebsiteMatcher(weight=0.15),
            CategoryMatcher(weight=0.05)
        ]
        
    async def enrich(self, business: Business) -> EnrichmentResult:
        """Find and merge GBP data"""
        # Try to find GBP match
        place = await self._find_best_match(business)
        
        if not place:
            return EnrichmentResult(
                business_id=business.id,
                source='gbp',
                match_confidence=0.0,
                enriched=False
            )
            
        # Extract valuable data
        enrichment_data = {
            'place_id': place['place_id'],
            'rating': place.get('rating'),
            'user_ratings_total': place.get('user_ratings_total'),
            'price_level': place.get('price_level'),
            'opening_hours': place.get('opening_hours'),
            'website': place.get('website'),
            'formatted_phone_number': place.get('formatted_phone_number'),
            'business_status': place.get('business_status', 'OPERATIONAL')
        }
        
        # Update business record
        await self._update_business(business, enrichment_data)
        
        return EnrichmentResult(
            business_id=business.id,
            source='gbp',
            match_confidence=place['match_confidence'],
            enriched=True,
            data=enrichment_data
        )
```

---

## 8. D5: Scoring & Filtering

### 8.1 Purpose
Calculate lead quality scores (0-100) and assign tiers (A/B/C/D) using weighted rules.

### 8.2 Detailed Components

#### 8.2.1 Scoring Engine
```python
# d5_scoring/engine.py
import yaml
from typing import Dict, Any, List
import numpy as np

class ScoringEngine:
    def __init__(self, rules_path: str = "scoring_rules.yaml"):
        self.rules = self._load_rules(rules_path)
        self.version = self.rules['version']
        
    def calculate_score(
        self,
        business: Business,
        assessment: AssessmentResult,
        enrichment: Optional[EnrichmentResult] = None
    ) -> ScoringResult:
        """Calculate weighted score and tier"""
        # Get rules for this vertical
        vertical_rules = self._get_vertical_rules(business.vertical)
        
        # Calculate each component
        scores = {}
        total_weight = 0
        weighted_sum = 0
        
        for rule_name, rule_config in vertical_rules.items():
            try:
                score = self._evaluate_rule(
                    rule_config['rule'],
                    business,
                    assessment,
                    enrichment
                )
                weight = rule_config['weight']
                
                scores[rule_name] = {
                    'score': score,
                    'weight': weight,
                    'contribution': score * weight
                }
                
                weighted_sum += score * weight
                total_weight += weight
                
            except Exception as e:
                # Use fallback value if rule fails
                fallback = rule_config.get('fallback_value', 0.5)
                scores[rule_name] = {
                    'score': fallback,
                    'weight': rule_config['weight'],
                    'contribution': fallback * rule_config['weight'],
                    'error': str(e)
                }
                
        # Calculate final score
        final_score = weighted_sum / total_weight if total_weight > 0 else 0
        score_pct = int(final_score * 100)
        
        # Assign tier
        tier = self._calculate_tier(score_pct)
        
        # Calculate confidence
        confidence = self._calculate_confidence(scores, assessment)
        
        return ScoringResult(
            business_id=business.id,
            score_raw=final_score,
            score_pct=score_pct,
            tier=tier,
            confidence=confidence,
            scoring_version=self.version,
            score_breakdown=scores,
            passed_gate=(tier in ['A', 'B'])
        )
```

#### 8.2.2 Scoring Rules YAML
```yaml
# scoring_rules.yaml
version: 1
base_rules:
  performance:
    weight: 0.3
    rule: "assessment.pagespeed.performance_score < 50"
    fallback_value: 0.5
    
  mobile_friendly:
    weight: 0.2
    rule: "assessment.pagespeed.mobile_issues > 3"
    
  has_reviews:
    weight: 0.2
    rule: "enrichment.rating is not None and enrichment.user_ratings_total > 10"
    
  seo_issues:
    weight: 0.2
    rule: "assessment.pagespeed.seo_score < 70"
    
  technical_issues:
    weight: 0.1
    rule: "len(assessment.techstack.issues) > 5"

vertical_overrides:
  restaurant:
    has_reviews:
      weight: 0.3  # More important for restaurants
      rule: "enrichment.rating < 4.0 and enrichment.user_ratings_total > 50"
      
    has_hours:
      weight: 0.1
      rule: "enrichment.opening_hours is None"
      
  medical:
    performance:
      weight: 0.4  # Critical for medical sites
      
tier_boundaries:
  A: 80  # >= 80
  B: 60  # >= 60
  C: 40  # >= 40
  D: 0   # < 40
```

### 8.3 Testing Requirements
```python
# tests/d5_scoring/test_engine.py
def test_scoring_respects_weights():
    """Scoring should properly weight rules"""
    engine = ScoringEngine("test_rules.yaml")
    
    # Create test data with known values
    business = Business(vertical="restaurant")
    assessment = AssessmentResult(
        pagespeed=PageSpeedResult(performance_score=30),  # Bad
        techstack=TechStackResult(issues=[])  # Good
    )
    
    result = engine.calculate_score(business, assessment, None)
    
    # With test weights, performance (0.3) should hurt score more
    assert result.score_pct < 50
    assert result.tier == 'C'
```

---

## 9. D6: Audit Report Builder

### 9.1 Purpose
Generate conversion-optimized audit reports (HTML + PDF) after successful payment.

### 9.2 Detailed Components

#### 9.2.1 Report Generator
```python
# d6_reports/generator.py
class ReportGenerator:
    def __init__(self, template_engine, pdf_converter):
        self.templates = template_engine
        self.pdf_converter = pdf_converter
        
    async def generate_report(
        self,
        purchase: Purchase,
        timeout: int = 30
    ) -> ReportResult:
        """Generate both HTML and PDF versions"""
        # Load all data
        business = await self._load_business(purchase.business_id)
        assessment = await self._load_assessment(business.id)
        scoring = await self._load_scoring(business.id)
        
        # Prioritize findings
        findings = self._prioritize_findings(assessment, scoring)
        
        # Generate HTML
        html_content = await self.templates.render(
            'audit_report.html',
            {
                'business': business,
                'assessment': assessment,
                'scoring': scoring,
                'findings': findings,
                'generated_at': datetime.utcnow(),
                'report_id': purchase.id
            }
        )
        
        # Generate PDF
        pdf_bytes = await self.pdf_converter.convert(
            html_content,
            options={
                'format': 'A4',
                'margin': '10mm',
                'printBackground': True,
                'preferCSSPageSize': True
            }
        )
        
        # Upload to S3
        urls = await self._upload_reports(
            purchase.id,
            html_content,
            pdf_bytes
        )
        
        return ReportResult(
            purchase_id=purchase.id,
            html_url=urls['html'],
            pdf_url=urls['pdf'],
            generated_at=datetime.utcnow()
        )
```

#### 9.2.2 Finding Prioritizer
```python
# d6_reports/prioritizer.py
class FindingPrioritizer:
    def prioritize_findings(
        self,
        assessment: AssessmentResult,
        max_issues: int = 3,
        max_quick_wins: int = 5
    ) -> Dict[str, List[Finding]]:
        """Select most impactful findings for report"""
        all_findings = []
        
        # Extract findings from all assessment types
        for assessment_type, result in assessment.results.items():
            if 'issues' in result:
                for issue in result['issues']:
                    finding = Finding(
                        source=assessment_type,
                        title=issue.get('title'),
                        description=issue.get('description'),
                        impact=issue.get('impact', 'medium'),
                        effort=issue.get('effort', 'medium'),
                        category=issue.get('category', 'performance')
                    )
                    all_findings.append(finding)
                    
        # Score findings by conversion impact
        for finding in all_findings:
            finding.priority_score = self._calculate_priority(finding)
            
        # Sort by priority
        all_findings.sort(key=lambda f: f.priority_score, reverse=True)
        
        # Separate into issues and quick wins
        quick_wins = [f for f in all_findings if f.effort == 'easy'][:max_quick_wins]
        top_issues = [f for f in all_findings if f.effort != 'easy'][:max_issues]
        
        return {
            'top_issues': top_issues,
            'quick_wins': quick_wins,
            'all_findings': all_findings
        }
```

#### 9.2.3 PDF Converter
```python
# d6_reports/pdf_converter.py
from playwright.async_api import async_playwright
import asyncio

class PDFConverter:
    def __init__(self):
        self.browser = None
        self.semaphore = asyncio.Semaphore(3)  # Max concurrent PDFs
        
    async def convert(
        self,
        html_content: str,
        options: Dict[str, Any]
    ) -> bytes:
        """Convert HTML to PDF using Playwright"""
        async with self.semaphore:
            if not self.browser:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(
                    headless=True,
                    args=['--disable-dev-shm-usage']
                )
                
            context = await self.browser.new_context()
            page = await context.new_page()
            
            try:
                # Load HTML
                await page.set_content(html_content)
                
                # Wait for content to render
                await page.wait_for_load_state('networkidle')
                
                # Generate PDF
                pdf_bytes = await page.pdf(**options)
                
                # Compress if too large
                if len(pdf_bytes) > 2 * 1024 * 1024:  # 2MB
                    pdf_bytes = await self._compress_pdf(pdf_bytes)
                    
                return pdf_bytes
                
            finally:
                await context.close()
```

### 9.3 Report Template Structure
```html
<!-- templates/audit_report.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        /* Mobile-first, print-optimized CSS */
        @media print {
            .no-print { display: none; }
        }
    </style>
</head>
<body>
    <!-- Hero Section -->
    <section class="hero">
        <h1>Website Audit Report</h1>
        <h2>{{ business.name }}</h2>
        <div class="score-badge">
            <span class="score">{{ scoring.score_pct }}</span>
            <span class="tier">Grade: {{ scoring.tier }}</span>
        </div>
    </section>
    
    <!-- Executive Summary -->
    <section class="summary">
        <h3>Key Findings</h3>
        <p>Your website scored {{ scoring.score_pct }} out of 100, 
           indicating {{ 'significant' if scoring.score_pct < 50 else 'moderate' }} 
           room for improvement.</p>
    </section>
    
    <!-- Top Issues -->
    <section class="issues">
        <h3>Priority Issues</h3>
        {% for issue in findings.top_issues %}
        <div class="issue">
            <h4>{{ issue.title }}</h4>
            <p>{{ issue.description }}</p>
            <div class="impact">Impact: {{ issue.impact }}</div>
            <div class="solution">{{ issue.recommendation }}</div>
        </div>
        {% endfor %}
    </section>
    
    <!-- Quick Wins -->
    <section class="quick-wins">
        <h3>Quick Wins</h3>
        <ul>
        {% for win in findings.quick_wins %}
            <li>{{ win.title }} - {{ win.description }}</li>
        {% endfor %}
        </ul>
    </section>
    
    <!-- CTA -->
    <section class="cta">
        <h3>Ready to Improve Your Website?</h3>
        <p>Our team can implement these improvements for you.</p>
        <a href="{{ cta_url }}" class="button">Get Started</a>
    </section>
</body>
</html>
```

---

## 10. D7: Storefront & Purchase Flow

### 10.1 Purpose
Handle the complete purchase flow from landing page through Stripe payment to report delivery.

### 10.2 Detailed Components

#### 10.2.1 Checkout Manager
```python
# d7_storefront/checkout.py
import stripe
from typing import Dict, Any
import secrets

class CheckoutManager:
    def __init__(self, stripe_client):
        self.stripe = stripe_client
        self.success_url = f"{settings.BASE_URL}/purchase/success"
        self.cancel_url = f"{settings.BASE_URL}/purchase/cancel"
        
    async def create_checkout_session(
        self,
        business_id: str,
        email: str,
        metadata: Dict[str, Any]
    ) -> stripe.checkout.Session:
        """Create Stripe Checkout session"""
        # Generate unique client reference
        client_reference_id = f"biz_{business_id}_{secrets.token_urlsafe(8)}"
        
        session = await self.stripe.checkout.Session.create_async(
            payment_method_types=['card'],
            line_items=[{
                'price': settings.STRIPE_PRICE_ID,  # Pre-created price
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{self.success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=self.cancel_url,
            client_reference_id=client_reference_id,
            customer_email=email,
            metadata={
                'business_id': business_id,
                'source': metadata.get('source', 'direct'),
                'campaign': metadata.get('campaign'),
                **metadata
            },
            payment_intent_data={
                'metadata': {
                    'business_id': business_id
                }
            }
        )
        
        return session
```

#### 10.2.2 Webhook Processor
```python
# d7_storefront/webhooks.py
import stripe
from typing import Dict, Any
import hmac
import hashlib

class StripeWebhookProcessor:
    def __init__(self, db_session, report_generator):
        self.db = db_session
        self.report_generator = report_generator
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        
    async def process_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        # Verify signature
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret
            )
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid signature")
            
        # Handle event
        if event['type'] == 'checkout.session.completed':
            await self._handle_checkout_completed(event['data']['object'])
        elif event['type'] == 'payment_intent.succeeded':
            await self._handle_payment_succeeded(event['data']['object'])
            
        return {"status": "processed", "event_id": event['id']}
        
    async def _handle_checkout_completed(
        self,
        session: Dict[str, Any]
    ) -> None:
        """Handle successful checkout"""
        # Check if already processed (idempotency)
        existing = await self.db.query(Purchase).filter(
            Purchase.stripe_session_id == session['id']
        ).first()
        
        if existing:
            return  # Already processed
            
        # Create purchase record
        purchase = Purchase(
            business_id=session['metadata']['business_id'],
            stripe_session_id=session['id'],
            stripe_payment_intent_id=session['payment_intent'],
            amount_cents=session['amount_total'],
            customer_email=session['customer_email'],
            metadata=session['metadata'],
            status='completed'
        )
        
        self.db.add(purchase)
        await self.db.commit()
        
        # Queue report generation
        await self.report_generator.generate_report_async(purchase.id)
```

### 10.3 Database Schema
```sql
-- Purchase records
CREATE TABLE purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id),
    stripe_session_id VARCHAR(255) UNIQUE,
    stripe_payment_intent_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    customer_email VARCHAR(255) NOT NULL,
    
    -- Attribution
    source VARCHAR(50),
    campaign VARCHAR(100),
    metadata JSONB,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',
    completed_at TIMESTAMP,
    refunded_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Webhook events (for idempotency)
CREATE TABLE webhook_events (
    id VARCHAR(255) PRIMARY KEY,  -- Stripe event ID
    type VARCHAR(50) NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload JSONB
);
```

---

## 11. D8: Personalization

### 11.1 Purpose
Generate personalized email content that converts, with subject lines, body copy, and optional mockups.

### 11.2 Detailed Components

#### 11.2.1 Email Personalizer
```python
# d8_personalization/personalizer.py
class EmailPersonalizer:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.subject_patterns = [
            'urgency',
            'question',
            'specific_issue',
            'competitor_comparison',
            'score_reveal'
        ]
        
    async def generate_email(
        self,
        business: Business,
        scoring: ScoringResult,
        assessment: AssessmentResult
    ) -> PersonalizedEmail:
        """Generate complete personalized email"""
        # Extract top issues for personalization
        top_issues = self._extract_top_issues(assessment)
        
        # Generate subject lines
        subject_lines = await self._generate_subject_lines(
            business,
            scoring,
            top_issues
        )
        
        # Generate body
        body = await self._generate_body(
            business,
            scoring,
            top_issues
        )
        
        # Check spam score
        spam_score = await self._check_spam_score(
            subject_lines[0],
            body
        )
        
        # Apply fixes if spammy
        if spam_score > 5:
            subject_lines[0], body = await self._reduce_spam_score(
                subject_lines[0],
                body
            )
            
        return PersonalizedEmail(
            business_id=business.id,
            subject_lines=subject_lines,
            preview_text=self._generate_preview_text(top_issues),
            html_body=self._format_html(body),
            text_body=self._format_text(body),
            personalization_tokens={
                'business_name': business.name,
                'score': scoring.score_pct,
                'top_issue': top_issues[0]['title'] if top_issues else None,
                'location': business.city
            },
            spam_score=spam_score
        )
```

#### 11.2.2 Subject Line Generator
```python
# d8_personalization/subject_lines.py
class SubjectLineGenerator:
    def __init__(self):
        self.templates = {
            'urgency': [
                "{business_name}: {top_issue} is costing you customers",
                "Warning: Your {location} competitors are {ahead_by}% faster"
            ],
            'question': [
                "Is {top_issue} hurting your {vertical} business?",
                "Why are {competitor_count} {location} {vertical}s faster than you?"
            ],
            'specific_issue': [
                "{business_name}'s mobile site loads in {load_time}s (industry avg: {avg_time}s)",
                "Your website scored {score}/100 - here's what to fix"
            ],
            'score_reveal': [
                "{business_name} Website Audit: Grade {tier} ({score}/100)",
                "Your {vertical} website report is ready - Score: {score}"
            ]
        }
        
    def generate(
        self,
        pattern: str,
        tokens: Dict[str, Any],
        max_length: int = 60
    ) -> str:
        """Generate subject line from pattern and tokens"""
        templates = self.templates.get(pattern, [])
        if not templates:
            return "Your Website Audit Report is Ready"
            
        # Select template
        template = templates[hash(str(tokens)) % len(templates)]
        
        # Fill tokens
        subject = template.format(**tokens)
        
        # Truncate if needed
        if len(subject) > max_length:
            subject = subject[:max_length-3] + "..."
            
        return subject
```

### 11.3 Email Templates
```html
<!-- templates/email/audit_teaser.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* Mobile-first responsive email CSS */
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .score-card { 
            background: #f8f9fa; 
            border-radius: 8px; 
            padding: 20px; 
            text-align: center;
            margin: 20px 0;
        }
        .score-number { 
            font-size: 48px; 
            font-weight: bold; 
            color: {{ score_color }};
        }
        .cta-button {
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hi {{ business_name }},</h1>
        
        <p>I analyzed your website and found some issues that are likely costing you customers.</p>
        
        <div class="score-card">
            <div class="score-number">{{ score }}/100</div>
            <div>Website Performance Score</div>
        </div>
        
        <h2>Top 3 Issues Found:</h2>
        <ol>
        {% for issue in top_issues %}
            <li><strong>{{ issue.title }}</strong> - {{ issue.impact }}</li>
        {% endfor %}
        </ol>
        
        <p>The good news? These are all fixable. I've prepared a detailed report showing exactly what to fix and how.</p>
        
        <div style="text-align: center;">
            <a href="{{ report_url }}" class="cta-button">
                Get Your Full Report (${{ price }} ${{ original_price }})
            </a>
        </div>
        
        <p>This report includes:</p>
        <ul>
            <li>Detailed analysis of all issues</li>
            <li>Step-by-step fixes you can implement</li>
            <li>Priority order to maximize impact</li>
            <li>Competitor comparison</li>
        </ul>
        
        <p>Best regards,<br>
        The Anthrasite Team</p>
        
        <hr>
        <p style="font-size: 12px; color: #666;">
            <a href="{{ unsubscribe_url }}">Unsubscribe</a> | 
            123 Business St, New York, NY 10001
        </p>
    </div>
</body>
</html>
```

---

## 12. D9: Delivery & Compliance

### 12.1 Purpose
Send emails compliantly via SendGrid, handle bounces/complaints, and maintain sender reputation.

### 12.2 Detailed Components

#### 12.2.1 Email Delivery Manager
```python
# d9_delivery/delivery_manager.py
import sendgrid
from sendgrid.helpers.mail import Mail, From, To, Content
import hashlib
import secrets

class EmailDeliveryManager:
    def __init__(self, sendgrid_client, db_session):
        self.sg = sendgrid_client
        self.db = db_session
        self.from_email = From(
            email=settings.FROM_EMAIL,
            name=settings.FROM_NAME
        )
        
    async def send_email(
        self,
        email: PersonalizedEmail,
        business: Business
    ) -> DeliveryResult:
        """Send email with compliance headers"""
        # Check suppression list
        if await self._is_suppressed(business.email):
            return DeliveryResult(
                status='suppressed',
                message='Email on suppression list'
            )
            
        # Generate unsubscribe token
        unsub_token = self._generate_unsubscribe_token(business.email)
        
        # Build message
        message = Mail(
            from_email=self.from_email,
            to_emails=To(business.email),
            subject=email.subject_lines[0],
            html_content=Content("text/html", email.html_body)
        )
        
        # Add compliance headers
        message.add_header("List-Unsubscribe", 
            f"<{settings.BASE_URL}/unsubscribe/{unsub_token}>")
        message.add_header("List-Unsubscribe-Post", 
            "List-Unsubscribe=One-Click")
        
        # Add tracking
        message.add_category("leadfactory")
        message.add_category(f"tier_{email.tier}")
        message.add_category(f"vertical_{business.vertical}")
        
        # Custom args for webhook
        message.add_custom_arg("business_id", str(business.id))
        message.add_custom_arg("email_id", str(email.id))
        
        try:
            # Send via SendGrid
            response = await self.sg.send(message)
            
            # Record send
            await self._record_send(email, business, response)
            
            return DeliveryResult(
                status='sent',
                message_id=response.headers.get('X-Message-Id'),
                status_code=response.status_code
            )
            
        except Exception as e:
            return DeliveryResult(
                status='failed',
                error=str(e)
            )
```

#### 12.2.2 Webhook Handler
```python
# d9_delivery/webhook_handler.py
class SendGridWebhookHandler:
    def __init__(self, db_session):
        self.db = db_session
        self.event_handlers = {
            'delivered': self._handle_delivered,
            'open': self._handle_open,
            'click': self._handle_click,
            'bounce': self._handle_bounce,
            'spamreport': self._handle_spam_report,
            'unsubscribe': self._handle_unsubscribe
        }
        
    async def process_events(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Process batch of SendGrid events"""
        results = {'processed': 0, 'errors': 0}
        
        for event in events:
            try:
                event_type = event.get('event')
                if event_type in self.event_handlers:
                    await self.event_handlers[event_type](event)
                    results['processed'] += 1
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                results['errors'] += 1
                
        return results
        
    async def _handle_bounce(self, event: Dict[str, Any]) -> None:
        """Handle bounce events"""
        email = event.get('email')
        reason = event.get('reason', 'unknown')
        
        # Add to suppression list
        suppression = EmailSuppression(
            email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
            reason=f"bounce: {reason}",
            source='sendgrid_webhook'
        )
        
        self.db.add(suppression)
        
        # Update email record
        business_id = event.get('business_id')
        if business_id:
            await self.db.query(Email).filter(
                Email.business_id == business_id
            ).update({
                'bounced_at': datetime.utcnow(),
                'bounce_reason': reason
            })
```

### 12.3 Database Schema
```sql
-- Email sends
CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id),
    
    -- Content
    subject VARCHAR(500) NOT NULL,
    preview_text VARCHAR(200),
    html_body TEXT NOT NULL,
    text_body TEXT,
    
    -- Tracking
    sendgrid_message_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    
    -- Timestamps
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    bounced_at TIMESTAMP,
    unsubscribed_at TIMESTAMP,
    complained_at TIMESTAMP,
    
    -- Additional data
    bounce_reason TEXT,
    spam_score DECIMAL(3, 1),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suppression list
CREATE TABLE email_suppressions (
    email_hash VARCHAR(64) PRIMARY KEY,  -- SHA-256 of lowercase email
    reason VARCHAR(100) NOT NULL,
    source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Click tracking
CREATE TABLE email_clicks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES emails(id),
    url TEXT NOT NULL,
    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);
```

---

## 13. D10: Analytics & Reporting

### 13.1 Purpose
Track all metrics, generate insights, and provide dashboards for monitoring performance.

### 13.2 Detailed Components

#### 13.2.1 Metrics Warehouse
```python
# d10_analytics/warehouse.py
from sqlalchemy import create_engine
from typing import Dict, Any
import pandas as pd

class MetricsWarehouse:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        
    async def build_daily_metrics(self, date: date) -> Dict[str, Any]:
        """Build comprehensive daily metrics"""
        metrics = {}
        
        # Funnel metrics
        metrics['funnel'] = {
            'businesses_sourced': await self._count_businesses_sourced(date),
            'assessments_completed': await self._count_assessments(date),
            'leads_scored': await self._count_scored(date),
            'emails_sent': await self._count_emails_sent(date),
            'emails_opened': await self._count_emails_opened(date),
            'emails_clicked': await self._count_emails_clicked(date),
            'purchases': await self._count_purchases(date),
            'revenue': await self._sum_revenue(date)
        }
        
        # Conversion rates
        metrics['conversions'] = {
            'assessment_to_email': self._safe_divide(
                metrics['funnel']['emails_sent'],
                metrics['funnel']['assessments_completed']
            ),
            'email_to_open': self._safe_divide(
                metrics['funnel']['emails_opened'],
                metrics['funnel']['emails_sent']
            ),
            'open_to_click': self._safe_divide(
                metrics['funnel']['emails_clicked'],
                metrics['funnel']['emails_opened']
            ),
            'click_to_purchase': self._safe_divide(
                metrics['funnel']['purchases'],
                metrics['funnel']['emails_clicked']
            ),
            'overall': self._safe_divide(
                metrics['funnel']['purchases'],
                metrics['funnel']['emails_sent']
            )
        }
        
        # Cost analysis
        metrics['costs'] = {
            'api_costs': await self._sum_api_costs(date),
            'per_lead': await self._calculate_cost_per_lead(date),
            'per_purchase': await self._calculate_cac(date)
        }
        
        # Performance by segment
        metrics['segments'] = {
            'by_vertical': await self._metrics_by_vertical(date),
            'by_tier': await self._metrics_by_tier(date),
            'by_location': await self._metrics_by_location(date)
        }
        
        return metrics
```

#### 13.2.2 Dashboard Queries
```sql
-- Daily funnel view
CREATE MATERIALIZED VIEW mv_daily_funnel AS
SELECT 
    DATE(created_at) as date,
    COUNT(DISTINCT CASE WHEN step >= 1 THEN business_id END) as sourced,
    COUNT(DISTINCT CASE WHEN step >= 2 THEN business_id END) as assessed,
    COUNT(DISTINCT CASE WHEN step >= 3 THEN business_id END) as scored,
    COUNT(DISTINCT CASE WHEN step >= 4 THEN business_id END) as emailed,
    COUNT(DISTINCT CASE WHEN step >= 5 THEN business_id END) as opened,
    COUNT(DISTINCT CASE WHEN step >= 6 THEN business_id END) as clicked,
    COUNT(DISTINCT CASE WHEN step >= 7 THEN business_id END) as purchased,
    SUM(CASE WHEN step >= 7 THEN revenue ELSE 0 END) as revenue
FROM business_funnel_events
GROUP BY DATE(created_at);

-- Cohort retention
CREATE MATERIALIZED VIEW mv_cohort_retention AS
SELECT 
    DATE_TRUNC('week', first_email_sent) as cohort_week,
    EXTRACT(DAY FROM (purchased_at - first_email_sent)) as days_to_purchase,
    COUNT(DISTINCT business_id) as purchases
FROM (
    SELECT 
        b.id as business_id,
        MIN(e.sent_at) as first_email_sent,
        MIN(p.created_at) as purchased_at
    FROM businesses b
    JOIN emails e ON b.id = e.business_id
    LEFT JOIN purchases p ON b.id = p.business_id
    GROUP BY b.id
) cohort_data
WHERE purchased_at IS NOT NULL
GROUP BY cohort_week, days_to_purchase;
```

### 13.3 Testing Requirements
```python
# tests/d10_analytics/test_metrics.py
@pytest.mark.asyncio
async def test_funnel_metrics_consistency():
    """Funnel metrics should decrease monotonically"""
    warehouse = MetricsWarehouse(test_db_url)
    
    metrics = await warehouse.build_daily_metrics(date.today())
    funnel = metrics['funnel']
    
    # Each step should have fewer or equal to previous
    assert funnel['businesses_sourced'] >= funnel['assessments_completed']
    assert funnel['assessments_completed'] >= funnel['leads_scored']
    assert funnel['leads_scored'] >= funnel['emails_sent']
    assert funnel['emails_sent'] >= funnel['emails_opened']
    assert funnel['emails_opened'] >= funnel['emails_clicked']
    assert funnel['emails_clicked'] >= funnel['purchases']
```

---

## 14. D11: Orchestration & Experimentation

### 14.1 Purpose
Coordinate the entire pipeline with Prefect, manage A/B experiments, and ensure reliable execution.

### 14.2 Detailed Components

#### 14.2.1 Pipeline Orchestrator
```python
# d11_orchestration/pipeline.py
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner
import asyncio

@flow(
    name="leadfactory-daily",
    task_runner=ConcurrentTaskRunner(max_workers=10)
)
async def daily_pipeline(date: date = None):
    """Main daily pipeline flow"""
    if date is None:
        date = date.today()
        
    # Get today's batches
    batches = await get_daily_batches(date)
    
    # Process each batch
    results = []
    for batch in batches:
        result = await process_batch(batch)
        results.append(result)
        
    # Generate summary
    summary = await generate_daily_summary(results)
    
    # Send notifications
    await send_completion_notification(summary)
    
    return summary

@task(retries=2, retry_delay_seconds=300)
async def process_batch(batch: Batch):
    """Process a single geo × vertical batch"""
    logger.info(f"Processing batch: {batch.id}")
    
    # Source businesses
    businesses = await source_businesses(batch)
    
    # Assess each business
    assessments = await assess_businesses(businesses)
    
    # Score and filter
    scored = await score_businesses(businesses, assessments)
    
    # Filter to top tier
    qualified = [b for b in scored if b.tier in ['A', 'B']]
    
    # Generate and send emails
    if qualified:
        emails = await generate_emails(qualified)
        await send_emails(emails)
        
    return {
        'batch_id': batch.id,
        'sourced': len(businesses),
        'assessed': len(assessments),
        'qualified': len(qualified),
        'emails_sent': len(emails)
    }
```

#### 14.2.2 Experiment Manager
```python
# d11_orchestration/experiments.py
import hashlib
from typing import Dict, Any, Optional

class ExperimentManager:
    def __init__(self, db_session):
        self.db = db_session
        self.active_experiments = {}
        
    async def get_variant(
        self,
        experiment_name: str,
        business_id: str
    ) -> str:
        """Get variant assignment for business"""
        # Check if experiment exists and is active
        experiment = await self._get_experiment(experiment_name)
        if not experiment or experiment.status != 'active':
            return 'control'
            
        # Check for existing assignment
        assignment = await self.db.query(ExperimentAssignment).filter(
            ExperimentAssignment.experiment_id == experiment.id,
            ExperimentAssignment.business_id == business_id
        ).first()
        
        if assignment:
            return assignment.variant
            
        # Create new assignment
        variant = self._assign_variant(business_id, experiment)
        
        assignment = ExperimentAssignment(
            experiment_id=experiment.id,
            business_id=business_id,
            variant=variant
        )
        
        self.db.add(assignment)
        await self.db.commit()
        
        return variant
        
    def _assign_variant(
        self,
        business_id: str,
        experiment: Experiment
    ) -> str:
        """Deterministically assign variant"""
        # Hash business ID for consistent assignment
        hash_input = f"{business_id}:{experiment.id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        
        # Map to variant based on weights
        bucket = hash_value % 100
        cumulative = 0
        
        for variant in experiment.variants:
            cumulative += variant['weight']
            if bucket < cumulative:
                return variant['name']
                
        return 'control'  # Fallback
```

### 14.3 Database Schema
```sql
-- Pipeline runs
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_name VARCHAR(100) NOT NULL,
    flow_run_id VARCHAR(100) UNIQUE,
    
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT,
    
    -- Metrics
    total_businesses INTEGER,
    total_assessed INTEGER,
    total_qualified INTEGER,
    total_emails_sent INTEGER,
    total_purchases INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Experiments
CREATE TABLE experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    
    status VARCHAR(20) DEFAULT 'draft',
    hypothesis TEXT,
    success_metrics JSONB,
    
    variants JSONB NOT NULL,  -- [{name, weight, config}]
    
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Experiment assignments
CREATE TABLE experiment_assignments (
    experiment_id UUID REFERENCES experiments(id),
    business_id UUID REFERENCES businesses(id),
    variant VARCHAR(50) NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (experiment_id, business_id)
);
```

---

## 15. Testing Strategy & CI-First Development

### 15.1 Test Environment Setup

#### 15.1.1 Docker Test Container
```dockerfile
# Dockerfile.test
FROM python:3.11-slim

# Install system dependencies exactly like production
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Copy code
COPY . .

# Set test environment
ENV ENVIRONMENT=test
ENV DATABASE_URL=sqlite:///tmp/test.db
ENV USE_STUBS=true
ENV PYTHONPATH=/app

# Default test command
CMD ["pytest", "-xvs", "--tb=short", "--cov=.", "--cov-report=term-missing"]
```

#### 15.1.2 Test Configuration
```python
# tests/conftest.py
import pytest
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
from database.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="function")
def test_db():
    """Create fresh test database for each test"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def mock_gateway():
    """Mock external gateway for testing"""
    from unittest.mock import Mock, AsyncMock
    
    gateway = Mock()
    
    # Mock Yelp client
    gateway.yelp = AsyncMock()
    gateway.yelp.search_businesses.return_value = {
        'businesses': [
            {
                'id': 'test-biz-1',
                'name': 'Test Business 1',
                'url': 'https://example.com',
                'phone': '+1234567890'
            }
        ],
        'total': 1
    }
    
    # Mock PageSpeed client
    gateway.pagespeed = AsyncMock()
    gateway.pagespeed.analyze.return_value = {
        'lighthouseResult': {
            'categories': {
                'performance': {'score': 0.45},
                'seo': {'score': 0.80}
            }
        }
    }
    
    return gateway

@pytest.fixture(scope="session")
def stub_server():
    """Start stub server for integration tests"""
    import subprocess
    import time
    
    # Start stub server
    process = subprocess.Popen(
        ["uvicorn", "stubs.server:app", "--port", "5010"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for startup
    time.sleep(2)
    
    yield "http://localhost:5010"
    
    # Cleanup
    process.terminate()
    process.wait()
```

### 15.2 CI Pipeline

#### 15.2.1 GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

env:
  PYTHON_VERSION: "3.11"
  DATABASE_URL: "sqlite:///test.db"
  USE_STUBS: "true"

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run linting
      run: |
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 . --count --max-complexity=10 --max-line-length=100 --statistics
    
    - name: Run type checking
      run: |
        mypy --ignore-missing-imports .
    
    - name: Run tests in Docker
      run: |
        docker build -f Dockerfile.test -t leadfactory-test .
        docker run --rm \
          -e DATABASE_URL=$DATABASE_URL \
          -e USE_STUBS=$USE_STUBS \
          leadfactory-test
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

### 15.3 Testing Best Practices

#### 15.3.1 Test Organization
```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_models.py
│   ├── test_scoring.py
│   └── test_utils.py
├── integration/            # Component integration tests
│   ├── test_pipeline.py
│   ├── test_payment_flow.py
│   └── test_email_flow.py
├── e2e/                    # End-to-end tests
│   └── test_full_flow.py
└── fixtures/               # Test data
    ├── sample_business.json
    └── sample_assessment.json
```

#### 15.3.2 Sample Unit Test
```python
# tests/unit/test_scoring.py
import pytest
from d5_scoring.engine import ScoringEngine
from tests.factories import BusinessFactory, AssessmentFactory

class TestScoringEngine:
    def test_calculates_score_correctly(self):
        """Score calculation should follow weighted rules"""
        # Arrange
        engine = ScoringEngine("tests/fixtures/test_rules.yaml")
        business = BusinessFactory(vertical="restaurant")
        assessment = AssessmentFactory(
            performance_score=30,  # Poor
            seo_score=85,          # Good
            mobile_issues=5        # Bad
        )
        
        # Act
        result = engine.calculate_score(business, assessment)
        
        # Assert
        assert 0 <= result.score_pct <= 100
        assert result.tier in ['A', 'B', 'C', 'D']
        assert len(result.score_breakdown) > 0
        
    def test_handles_missing_data(self):
        """Should use fallback values for missing data"""
        engine = ScoringEngine("tests/fixtures/test_rules.yaml")
        business = BusinessFactory()
        assessment = AssessmentFactory(performance_score=None)
        
        result = engine.calculate_score(business, assessment)
        
        assert result.confidence < 1.0  # Lower confidence
        assert result.score_pct > 0      # Still produces score
```

#### 15.3.3 Sample Integration Test
```python
# tests/integration/test_pipeline.py
import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_full_pipeline_flow(test_db, mock_gateway):
    """Complete pipeline should process business to email"""
    # Arrange
    from d2_sourcing.scraper import YelpScraper
    from d3_assessment.coordinator import AssessmentCoordinator
    from d5_scoring.engine import ScoringEngine
    from d8_personalization.personalizer import EmailPersonalizer
    
    # Create components
    scraper = YelpScraper(mock_gateway)
    assessor = AssessmentCoordinator(mock_gateway)
    scorer = ScoringEngine()
    personalizer = EmailPersonalizer(mock_gateway)
    
    # Act - Run pipeline
    businesses = await scraper.scrape_batch(Mock(planned_size=1))
    assessment = await assessor.assess_business(businesses[0])
    score = scorer.calculate_score(businesses[0], assessment)
    email = await personalizer.generate_email(businesses[0], score, assessment)
    
    # Assert
    assert len(businesses) == 1
    assert assessment.results['pagespeed'] is not None
    assert score.tier in ['A', 'B', 'C', 'D']
    assert email.subject_lines[0] is not None
    assert email.spam_score < 5
```

---

## 16. Task Execution Plan

### 16.1 Task Generation Instructions

When generating tasks with TaskMaster, use this structure:

```json
{
  "project": "leadfactory-mvp",
  "version": "1.0",
  "total_tasks": 100,
  "phases": [
    {
      "phase": 1,
      "name": "Foundation",
      "tasks": [
        {
          "id": "001",
          "title": "Setup project structure and dependencies",
          "domain": "core",
          "complexity": 2,
          "dependencies": [],
          "estimated_hours": 1,
          "test_requirements": {
            "docker_test": true,
            "files": ["tests/test_setup.py"],
            "commands": ["docker run --rm leadfactory-test pytest tests/test_setup.py"]
          },
          "files_to_create": [
            "requirements.txt",
            "requirements-dev.txt",
            "Dockerfile.test",
            ".gitignore",
            "setup.py"
          ],
          "acceptance_criteria": [
            "All dependencies installable",
            "Docker test container builds",
            "Basic pytest runs successfully"
          ]
        },
        {
          "id": "002",
          "title": "Create database models and migrations",
          "domain": "database",
          "complexity": 3,
          "dependencies": ["001"],
          "estimated_hours": 2,
          "context_technologies": ["sqlalchemy", "alembic"],
          "test_requirements": {
            "docker_test": true,
            "files": ["tests/test_models.py"],
            "commands": [
              "docker run --rm leadfactory-test pytest tests/test_models.py",
              "docker run --rm leadfactory-test alembic upgrade head"
            ]
          }
        }
      ]
    }
  ]
}
```

### 16.2 Execution Protocol

For each task:

1. **Start fresh Docker environment**
   ```bash
   docker build -f Dockerfile.test -t leadfactory-test .
   ```

2. **Use Context7 for all libraries**
   ```
   "Implement task 002. Use context7 for SQLAlchemy and Alembic documentation."
   ```

3. **Run tests in Docker**
   ```bash
   docker run --rm leadfactory-test pytest tests/domain/test_file.py
   ```

4. **Verify CI compatibility**
   ```bash
   python scripts/ci_check.py
   ```

5. **Commit if passing**
   ```bash
   git add -A
   git commit -m "Complete task 002: Database models"
   git push
   ```

### 16.3 Critical Path Tasks

These must be completed in order:

1. **Project setup** (Task 001)
2. **Database schema** (Task 002)
3. **Stub server** (Task 003)
4. **D0 Gateway base** (Task 010-015)
5. **D2 Sourcing** (Task 020-025)
6. **D3 Assessment** (Task 030-035)
7. **D5 Scoring** (Task 040-045)
8. **D7 Payments** (Task 050-055)
9. **D9 Delivery** (Task 060-065)
10. **Integration tests** (Task 090-095)

---

## Appendices

### A. Environment Variables

```bash
# .env.test (commit this file)
# Database
DATABASE_URL=sqlite:///tmp/test.db

# External APIs (stubbed for testing)
USE_STUBS=true
STRIPE_TEST_SECRET_KEY=sk_test_dummy
STRIPE_TEST_PUBLISHABLE_KEY=pk_test_dummy
SENDGRID_API_KEY=SG.dummy
YELP_API_KEY=yelp_dummy
GOOGLE_PLACES_API_KEY=places_dummy
OPENAI_API_KEY=openai_dummy

# Application
ENVIRONMENT=test
LOG_LEVEL=INFO
SECRET_KEY=test-secret-key-change-in-production
BASE_URL=http://localhost:8000

# Email
FROM_EMAIL=test@leadfactory.com
FROM_NAME=LeadFactory Test

# Limits
MAX_DAILY_EMAILS=100
MAX_DAILY_YELP_CALLS=5000
```

### B. Quick Start Commands

```bash
# Initial setup
mkdir leadfactory && cd leadfactory
git init

# Copy this PRD
cp /path/to/this/PRD.md .

# Initialize TaskMaster
taskmaster init
taskmaster parse prd PRD.md
taskmaster analyze complexity
taskmaster complexity report

# Start development
python planning/get_next_task.py
```

### C. Monitoring Metrics

Key metrics to track from day 1:

```python
# Prometheus metrics to implement
# d0_gateway
gateway_api_calls_total
gateway_api_latency_seconds
gateway_api_cost_dollars
gateway_circuit_breaker_state

# d2_sourcing
businesses_sourced_total
sourcing_duration_seconds

# d3_assessment
assessments_completed_total
assessment_duration_seconds
assessment_cost_dollars

# d5_scoring
leads_scored_total
scoring_tiers_total

# d9_delivery
emails_sent_total
emails_bounced_total
emails_opened_total
emails_clicked_total

# d7_payments
purchases_total
revenue_dollars_total
```