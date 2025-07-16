"""
Simple unit tests for cost enforcement middleware without database dependencies
"""
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d0_gateway.middleware.cost_enforcement import (
    OperationPriority,
    PreflightCostEstimator,
    SlidingWindowCounter,
    TokenBucket,
)


class TestTokenBucket:
    """Test token bucket rate limiter"""

    def test_token_bucket_initialization(self):
        """Test token bucket initializes correctly"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10.0

    def test_token_consumption(self):
        """Test consuming tokens from bucket"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Should succeed with full bucket
        success, retry_after = bucket.consume(5)
        assert success is True
        assert retry_after is None
        assert bucket.tokens == 5.0

        # Should fail when not enough tokens
        success, retry_after = bucket.consume(6)
        assert success is False
        assert retry_after > 0

    def test_token_refill(self):
        """Test token refill mechanism"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens per second

        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens == 0.0

        # Mock time passage
        with patch("time.time") as mock_time:
            mock_time.return_value = bucket.last_refill + 2.5  # 2.5 seconds later

            # Should have refilled 5 tokens
            success, _ = bucket.consume(5)
            assert success is True
            assert bucket.tokens == 0.0  # 5 refilled, 5 consumed

    def test_cost_based_limiting(self):
        """Test cost-based token bucket"""
        bucket = TokenBucket(
            capacity=10, refill_rate=1.0, cost_capacity=Decimal("10.00"), cost_refill_rate=Decimal("1.00")
        )

        # Should succeed with cost within limit
        success, retry_after = bucket.consume(1, cost=Decimal("5.00"))
        assert success is True
        assert bucket.cost_tokens == 5.0

        # Should fail when cost exceeds remaining
        success, retry_after = bucket.consume(1, cost=Decimal("6.00"))
        assert success is False
        assert retry_after > 0


class TestSlidingWindowCounter:
    """Test sliding window counter for cost tracking"""

    def test_sliding_window_initialization(self):
        """Test sliding window initializes correctly"""
        window = SlidingWindowCounter(timedelta(hours=1))
        assert window.window_size == timedelta(hours=1)
        assert window.get_total() == Decimal("0")

    def test_adding_events(self):
        """Test adding events to window"""
        window = SlidingWindowCounter(timedelta(hours=1))

        window.add(Decimal("10.00"))
        window.add(Decimal("5.00"))

        assert window.get_total() == Decimal("15.00")

    def test_window_cleanup(self):
        """Test old events are removed from window"""
        window = SlidingWindowCounter(timedelta(hours=1))

        # Add event in the past
        old_time = datetime.utcnow() - timedelta(hours=2)
        window.add(Decimal("10.00"), old_time)

        # Add current event
        window.add(Decimal("5.00"))

        # Only current event should be counted
        assert window.get_total() == Decimal("5.00")


class TestPreflightCostEstimator:
    """Test pre-flight cost estimation"""

    def test_estimator_initialization(self):
        """Test estimator initializes with cost models"""
        estimator = PreflightCostEstimator()
        assert "openai" in estimator._cost_models
        assert "dataaxle" in estimator._cost_models

    def test_openai_cost_estimation(self):
        """Test OpenAI cost estimation"""
        estimator = PreflightCostEstimator()

        estimate = estimator.estimate("openai", "chat_completion", model="gpt-4", estimated_tokens=1000)

        assert estimate.provider == "openai"
        assert estimate.operation == "chat_completion"
        assert estimate.estimated_cost == Decimal("0.03")  # $0.03 per 1K tokens
        assert estimate.confidence == 0.95

    def test_fixed_cost_estimation(self):
        """Test fixed cost estimation"""
        estimator = PreflightCostEstimator()

        estimate = estimator.estimate("dataaxle", "match_business")

        assert estimate.provider == "dataaxle"
        assert estimate.operation == "match_business"
        assert estimate.estimated_cost == Decimal("0.05")
        assert estimate.confidence == 0.95

    def test_fallback_estimation(self):
        """Test fallback when model fails"""
        estimator = PreflightCostEstimator()

        # Mock the cost model to raise an exception
        original_model = estimator._cost_models["openai"]["chat_completion"]
        estimator._cost_models["openai"]["chat_completion"] = MagicMock(side_effect=Exception("Test error"))

        try:
            estimate = estimator.estimate("openai", "chat_completion")

            assert estimate.estimated_cost == Decimal("0.01")  # Fallback cost
            assert estimate.confidence == 0.7
            assert estimate.based_on == "fallback"
        finally:
            # Restore original model
            estimator._cost_models["openai"]["chat_completion"] = original_model


class TestOperationPriority:
    """Test operation priority enum"""

    def test_priority_values(self):
        """Test priority enum values"""
        assert OperationPriority.CRITICAL.value == "critical"
        assert OperationPriority.HIGH.value == "high"
        assert OperationPriority.NORMAL.value == "normal"
        assert OperationPriority.LOW.value == "low"

    def test_priority_comparison(self):
        """Test priority levels are distinct"""
        priorities = [
            OperationPriority.CRITICAL,
            OperationPriority.HIGH,
            OperationPriority.NORMAL,
            OperationPriority.LOW,
        ]
        # Ensure all priorities are unique
        assert len(priorities) == len(set(priorities))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
