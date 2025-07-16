# Cost Enforcement Middleware

The cost enforcement middleware provides comprehensive cost control for API operations with pre-flight cost estimation, rate limiting, and priority-based enforcement.

## Features

- **Pre-flight Cost Estimation**: Estimate costs before making API calls
- **Token Bucket Rate Limiting**: Smooth rate limiting with burst capacity
- **Cost-based Rate Limiting**: Limit spending rate, not just request count
- **Operation Priorities**: Different enforcement levels for critical vs non-critical operations
- **Circuit Breaker Integration**: Automatic circuit breaking on repeated failures
- **Sliding Window Cost Tracking**: Track costs over various time windows

## Usage

### Basic Usage in API Clients

```python
from d0_gateway.base import BaseAPIClient
from d0_gateway.middleware.cost_enforcement import OperationPriority

class MyAPIClient(BaseAPIClient):
    async def critical_operation(self):
        # Critical operations bypass most limits
        return await self.make_critical_request("POST", "/payment")
    
    async def normal_operation(self):
        # Normal priority (default)
        return await self.make_request("GET", "/data")
    
    async def low_priority_operation(self):
        # Can be aggressively rate limited
        return await self.make_low_priority_request("GET", "/analytics")
```

### Using Decorators

```python
from d0_gateway.middleware.cost_enforcement import (
    enforce_cost_limits,
    critical_operation,
    non_critical_operation,
    OperationPriority
)

class MyService:
    provider = "openai"
    
    @critical_operation
    async def process_payment(self):
        """This will never be blocked by cost limits"""
        pass
    
    @enforce_cost_limits(priority=OperationPriority.HIGH)
    async def important_analysis(self, operation="analyze"):
        """High priority - rarely blocked"""
        pass
    
    @non_critical_operation
    async def background_task(self):
        """Can be aggressively limited"""
        pass
```

### Setting Operation Priorities

```python
from d0_gateway import cost_enforcement, OperationPriority

# Set priorities for specific operations
cost_enforcement.set_operation_priority("stripe", "charge", OperationPriority.CRITICAL)
cost_enforcement.set_operation_priority("openai", "embedding", OperationPriority.LOW)
```

### Pre-flight Cost Estimation

```python
from d0_gateway import PreflightCostEstimator

estimator = PreflightCostEstimator()

# Estimate OpenAI costs
estimate = estimator.estimate(
    "openai",
    "chat_completion",
    model="gpt-4",
    estimated_tokens=1000
)
print(f"Estimated cost: ${estimate.estimated_cost}")

# Check if budget is available
from d0_gateway.guardrail_middleware import check_budget_available

if check_budget_available("openai", "analyze", estimate.estimated_cost):
    # Proceed with operation
    pass
```

### Monitoring Usage

```python
from d0_gateway import cost_enforcement

# Get current usage statistics
usage = cost_enforcement.get_current_usage("openai")
print(f"OpenAI hourly spend: ${usage['openai']['hourly']}")
print(f"OpenAI daily spend: ${usage['openai']['daily']}")

# Get all provider usage
all_usage = cost_enforcement.get_current_usage()
```

## Configuration

### Rate Limits

Rate limits are configured through the GuardrailManager:

```python
from d0_gateway.guardrails import RateLimitConfig, guardrail_manager

guardrail_manager.add_rate_limit(RateLimitConfig(
    provider="openai",
    operation="analyze",
    requests_per_minute=60,
    burst_size=10,
    cost_per_minute=Decimal("1.00"),
    cost_burst_size=Decimal("0.20")
))
```

### Cost Limits

Cost limits are also managed through GuardrailManager:

```python
from d0_gateway.guardrails import CostLimit, LimitScope, LimitPeriod

guardrail_manager.add_limit(CostLimit(
    name="openai_hourly",
    scope=LimitScope.PROVIDER,
    period=LimitPeriod.HOURLY,
    provider="openai",
    limit_usd=Decimal("10.00"),
    warning_threshold=0.8,
    critical_threshold=0.95,
    circuit_breaker_enabled=True
))
```

## Priority Levels

- **CRITICAL**: Never blocked, no delays
- **HIGH**: Rarely blocked, minimal delays when throttled
- **NORMAL**: Standard enforcement (default)
- **LOW**: Aggressive rate limiting and throttling

## Error Handling

```python
from core.exceptions import ExternalAPIError
from d0_gateway.guardrail_middleware import GuardrailBlocked, RateLimitExceeded

try:
    result = await client.make_request("POST", "/expensive-operation")
except GuardrailBlocked as e:
    # Cost limit exceeded
    print(f"Blocked: {e}")
except RateLimitExceeded as e:
    # Rate limit hit
    print(f"Rate limited: {e}")
except ExternalAPIError as e:
    # Other API errors
    print(f"API error: {e}")
```