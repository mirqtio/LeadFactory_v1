# LeadFactory Testing Guide

Comprehensive testing guide for the LeadFactory MVP system covering all domains, testing strategies, and quality assurance practices.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Architecture](#test-architecture)
3. [Testing Framework](#testing-framework)
4. [Test Types](#test-types)
5. [Coverage Requirements](#coverage-requirements)
6. [Running Tests](#running-tests)
7. [Test Data Generation](#test-data-generation)
8. [Domain-Specific Testing](#domain-specific-testing)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

## Testing Philosophy

LeadFactory follows a comprehensive testing strategy ensuring:

- **Quality First**: Every feature must have tests before deployment
- **Docker-First**: All tests must pass in Docker environment
- **Real-World Scenarios**: Tests simulate actual business conditions
- **Performance Validation**: Load testing for all critical paths
- **Security Assurance**: Comprehensive security and compliance testing

## Test Architecture

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── d0_gateway/         # Gateway layer tests
│   ├── d1_targeting/       # Targeting system tests
│   ├── d2_sourcing/        # Data sourcing tests
│   ├── d3_assessment/      # Website assessment tests
│   ├── d4_enrichment/      # Data enrichment tests
│   ├── d5_scoring/         # Lead scoring tests
│   ├── d6_reports/         # Report generation tests
│   ├── d7_storefront/      # Payment and storefront tests
│   ├── d8_personalization/ # Email personalization tests
│   ├── d9_delivery/        # Email delivery tests
│   ├── d10_analytics/      # Analytics and metrics tests
│   └── d11_orchestration/  # Pipeline orchestration tests
├── integration/            # Integration tests between domains
├── e2e/                   # End-to-end workflow tests
├── performance/           # Load and performance tests
├── security/              # Security and compliance tests
└── generators/            # Test data generators
```

## Testing Framework

### Core Tools

- **pytest**: Primary testing framework
- **pytest-asyncio**: Async testing support
- **pytest-mock**: Mocking and patching
- **factory-boy**: Test data factories
- **coverage**: Code coverage measurement
- **Docker**: Containerized test execution

### Configuration

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=.
    --cov-report=html
    --cov-report=xml
    --cov-report=term-missing
```

## Test Types

### 1. Unit Tests

**Purpose**: Test individual components in isolation

**Coverage**: >95% for all modules

**Examples**:
```python
def test_rate_limiter_respects_limits():
    """Test rate limiter enforces API limits"""
    limiter = RateLimiter(limit=5, window=60)
    # Test implementation...

def test_scoring_engine_calculates_correctly():
    """Test lead scoring calculations"""
    engine = ScoringEngine()
    # Test implementation...
```

### 2. Integration Tests

**Purpose**: Test interactions between domains

**Coverage**: All critical integration points

**Examples**:
```python
def test_sourcing_to_assessment_flow():
    """Test complete sourcing → assessment flow"""
    # Test implementation...

def test_payment_to_delivery_integration():
    """Test payment success triggers report delivery"""
    # Test implementation...
```

### 3. End-to-End Tests

**Purpose**: Test complete business workflows

**Coverage**: All user journeys

**Examples**:
```python
def test_complete_lead_generation_pipeline():
    """Test full pipeline from targeting to delivery"""
    # Test implementation...

def test_customer_purchase_and_report_delivery():
    """Test complete customer experience"""
    # Test implementation...
```

### 4. Performance Tests

**Purpose**: Validate system performance under load

**Coverage**: All critical paths

**Tools**: Locust, pytest-benchmark

```python
def test_5k_business_processing_performance():
    """Test processing 5000 businesses within SLA"""
    # Test implementation...
```

### 5. Security Tests

**Purpose**: Validate security and compliance

**Coverage**: All API endpoints and data flows

```python
def test_api_authentication_required():
    """Test all APIs require proper authentication"""
    # Test implementation...
```

## Coverage Requirements

### Overall Coverage

- **Minimum**: 80% overall coverage
- **Target**: 90% overall coverage
- **Critical Paths**: 100% coverage

### Critical Paths (100% Required)

1. **Configuration Management** (`core/config.py`)
2. **Error Handling** (`core/exceptions.py`)
3. **Database Models** (`database/models.py`)
4. **Gateway Base** (`d0_gateway/base.py`)
5. **Circuit Breaker** (`d0_gateway/circuit_breaker.py`)
6. **Rate Limiter** (`d0_gateway/rate_limiter.py`)
7. **Payment Processing** (`d7_storefront/checkout.py`)
8. **Webhook Handling** (`d7_storefront/webhooks.py`)
9. **Email Compliance** (`d9_delivery/compliance.py`)

### Domain-Specific Requirements

| Domain | Min Coverage | Critical Components |
|--------|-------------|-------------------|
| D0 Gateway | 90% | Rate limiting, circuit breakers |
| D1 Targeting | 85% | Geo validation, quota tracking |
| D2 Sourcing | 85% | Deduplication, error handling |
| D3 Assessment | 90% | PageSpeed integration, AI insights |
| D4 Enrichment | 85% | Fuzzy matching, data quality |
| D5 Scoring | 90% | Scoring engine, tier assignment |
| D6 Reports | 85% | PDF generation, template engine |
| D7 Storefront | 95% | Payment processing, webhooks |
| D8 Personalization | 85% | Content generation, spam checking |
| D9 Delivery | 95% | Email delivery, compliance |
| D10 Analytics | 85% | Metrics calculation, aggregation |
| D11 Orchestration | 90% | Pipeline execution, experiments |

## Running Tests

### Local Development

```bash
# Run all tests
pytest

# Run specific domain tests
pytest tests/unit/d0_gateway/

# Run with coverage
pytest --cov=. --cov-report=html

# Run integration tests only
pytest tests/integration/

# Run end-to-end tests
pytest tests/e2e/
```

### Docker Environment

```bash
# Build test container
docker build -f Dockerfile.test -t leadfactory-test .

# Run all tests in Docker
docker run --rm leadfactory-test

# Run specific test suite
docker run --rm leadfactory-test pytest tests/unit/d0_gateway/ -v

# Run with coverage report
docker run --rm leadfactory-test python3 scripts/coverage_report.py
```

### CI/CD Pipeline

```bash
# Generate coverage report for CI
python3 scripts/coverage_report.py --ci-check --xml --html

# Performance testing
pytest tests/performance/ --benchmark-only

# Security testing
pytest tests/security/
```

## Test Data Generation

### Business Data Generator

```python
from tests.generators import BusinessGenerator, BusinessScenario

# Generate deterministic test data
generator = BusinessGenerator(seed=42)

# Generate restaurants
restaurants = generator.generate_scenario_dataset(
    BusinessScenario.RESTAURANTS, count=50
)

# Generate performance dataset
large_dataset = generator.generate_performance_dataset("large")  # 5000 businesses
```

### Assessment Data Generator

```python
from tests.generators import AssessmentGenerator, AssessmentScenario

generator = AssessmentGenerator(seed=42)

# Generate high-performance assessments
assessments = generator.generate_assessments(
    businesses, [AssessmentScenario.HIGH_PERFORMANCE]
)

# Generate mixed performance dataset
mixed_assessments = generator.generate_performance_dataset(
    businesses, "medium"
)
```

### Scenario Coverage

| Scenario | Business Types | Assessment Types |
|----------|---------------|-----------------|
| Restaurants | Pizza, Fine Dining, Fast Food | Mixed Performance |
| Healthcare | Clinics, Hospitals, Dental | High Compliance |
| Retail | Clothing, Electronics, Books | E-commerce Focus |
| Professional | Legal, Accounting, Consulting | Desktop Optimization |
| Automotive | Repair, Sales, Parts | Local Business |

## Domain-Specific Testing

### D0 Gateway Testing

**Focus Areas**:
- Rate limiting accuracy
- Circuit breaker states
- Cache hit/miss ratios
- API response times

**Key Tests**:
```python
def test_rate_limiter_token_bucket():
    """Test token bucket algorithm accuracy"""

def test_circuit_breaker_state_transitions():
    """Test circuit breaker state machine"""

def test_cache_ttl_expiration():
    """Test cache TTL handling"""
```

### D1 Targeting Testing

**Focus Areas**:
- Geo validation accuracy
- Quota allocation fairness
- Batch scheduling logic

**Key Tests**:
```python
def test_geo_conflict_detection():
    """Test geographic overlap detection"""

def test_quota_allocation_algorithm():
    """Test quota distribution fairness"""
```

### D2 Sourcing Testing

**Focus Areas**:
- Deduplication accuracy
- Yelp API integration
- Error recovery

**Key Tests**:
```python
def test_business_deduplication():
    """Test duplicate business detection"""

def test_yelp_pagination_handling():
    """Test pagination edge cases"""
```

### D3 Assessment Testing

**Focus Areas**:
- PageSpeed API integration
- Technology detection accuracy
- AI insight quality

**Key Tests**:
```python
def test_pagespeed_score_extraction():
    """Test PageSpeed data parsing"""

def test_tech_stack_detection():
    """Test technology pattern matching"""

def test_ai_insight_generation():
    """Test LLM insight quality"""
```

### D7 Storefront Testing

**Focus Areas**:
- Payment processing security
- Webhook signature validation
- Idempotency handling

**Key Tests**:
```python
def test_stripe_webhook_signature():
    """Test webhook signature validation"""

def test_payment_idempotency():
    """Test duplicate payment handling"""
```

### D9 Delivery Testing

**Focus Areas**:
- Email compliance
- Suppression list management
- SendGrid integration

**Key Tests**:
```python
def test_email_compliance_headers():
    """Test required compliance headers"""

def test_suppression_list_checking():
    """Test bounce/complaint handling"""
```

## CI/CD Integration

### Local Validation with BPCI

**IMPORTANT**: Always validate locally before pushing to prevent CI failures:

```bash
# Run Bulletproof CI - exactly mirrors GitHub Actions
make bpci

# Quick validation for small changes
make quick-check
```

The BPCI (Bulletproof CI) system at `scripts/bpci.sh`:
- Creates the same Docker Compose environment as GitHub CI
- Starts PostgreSQL and stub server containers
- Runs the complete test suite with coverage
- Provides colored output and clear pass/fail status
- Cleans up containers automatically on exit

### GitHub Actions

The GitHub Actions workflow uses the same Docker Compose setup that BPCI validates locally:

```yaml
# .github/workflows/main.yml
name: CI Pipeline
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests with Docker Compose
        run: |
          docker compose -f docker-compose.test.yml up \
            --abort-on-container-exit \
            --exit-code-from test
```

### Coverage Gates

**PR Requirements**:
- Overall coverage ≥ 80%
- Critical paths = 100%
- No new uncovered lines in modified files

**Quality Gates**:
```bash
# Pre-commit hook
python3 scripts/coverage_report.py --ci-check
if [ $? -ne 0 ]; then
    echo "❌ Coverage requirements not met"
    exit 1
fi
```

## Troubleshooting

### Common Issues

#### 1. Docker Test Failures

**Problem**: Tests pass locally but fail in Docker
**Solution**: 
```bash
# Check environment differences
docker run --rm -it leadfactory-test bash
pytest tests/failing_test.py -vvv
```

#### 2. Coverage Calculation Issues

**Problem**: Coverage not calculating correctly
**Solution**:
```bash
# Clear coverage data
rm -rf .coverage htmlcov/
python3 scripts/coverage_report.py --skip-tests
```

#### 3. Test Data Conflicts

**Problem**: Tests interfering with each other
**Solution**:
```python
# Use proper test isolation
@pytest.fixture(autouse=True)
def clean_database():
    # Clean state before each test
    yield
    # Clean state after each test
```

#### 4. Performance Test Variability

**Problem**: Performance tests inconsistent results
**Solution**:
```python
# Use relative performance thresholds
@pytest.mark.benchmark(
    min_rounds=5,
    max_time=30,
    disable_gc=True
)
def test_performance():
    # Test implementation
```

### Debug Commands

```bash
# Verbose test output
pytest -vvv --tb=long

# Run single test with debugging
pytest tests/unit/d0_gateway/test_rate_limiter.py::test_token_bucket -vvv

# Coverage debug
coverage debug data
coverage debug sys

# Performance profiling
pytest --profile tests/performance/

# Memory usage analysis
pytest --memory-profiler tests/
```

### Test Environment Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Initialize test database
python3 scripts/db_setup.py --test

# Generate test data
python3 -c "
from tests.generators import BusinessGenerator
gen = BusinessGenerator()
businesses = gen.generate_performance_dataset('small')
print(f'Generated {len(businesses)} test businesses')
"
```

## Best Practices

### 1. Test Structure

```python
# Good test structure
class TestRateLimiter:
    """Test rate limiter functionality"""
    
    def test_allows_requests_within_limit(self):
        """Test normal operation within limits"""
        # Arrange
        limiter = RateLimiter(limit=5, window=60)
        
        # Act
        results = [limiter.allow_request("user1") for _ in range(5)]
        
        # Assert
        assert all(results)
    
    def test_blocks_requests_over_limit(self):
        """Test blocking when limit exceeded"""
        # Test implementation...
```

### 2. Test Data Management

```python
# Use factories for consistent test data
@pytest.fixture
def sample_business():
    return BusinessFactory(
        name="Test Restaurant",
        vertical="restaurants",
        rating=Decimal("4.5")
    )

# Use generators for large datasets
@pytest.fixture
def business_dataset():
    generator = BusinessGenerator(seed=42)
    return generator.generate_performance_dataset("small")
```

### 3. Mocking External APIs

```python
# Mock external API calls
@pytest.fixture
def mock_yelp_api():
    with patch('d0_gateway.providers.yelp.YelpClient') as mock:
        mock.return_value.search_businesses.return_value = {
            "businesses": [...]
        }
        yield mock

def test_business_search(mock_yelp_api):
    """Test business search with mocked API"""
    # Test implementation...
```

### 4. Async Testing

```python
@pytest.mark.asyncio
async def test_async_assessment():
    """Test asynchronous assessment processing"""
    coordinator = AssessmentCoordinator()
    result = await coordinator.process_assessment(business)
    assert result.status == AssessmentStatus.COMPLETED
```

## Maintenance

### Regular Tasks

1. **Weekly**: Review coverage reports
2. **Monthly**: Update test data generators
3. **Quarterly**: Performance baseline updates
4. **Release**: Full test suite validation

### Metrics Monitoring

- Test execution time trends
- Coverage percentage over time
- Test failure rates by domain
- Performance benchmark tracking

---

This testing guide ensures comprehensive quality assurance for the LeadFactory system. For questions or improvements, please update this documentation and submit a pull request.