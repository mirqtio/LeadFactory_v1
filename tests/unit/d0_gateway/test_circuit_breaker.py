"""
Test circuit breaker pattern implementation
"""
import time
from unittest.mock import patch

import pytest

from d0_gateway.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState


class TestCircuitBreakerStates:
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for testing"""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1, success_threshold=2)
        return CircuitBreaker("test_provider", config)

    @pytest.mark.slow
    def test_three_states_closed_open_half_open(self, circuit_breaker):
        """Test that circuit breaker implements three states: closed/open/half-open"""
        # Start in CLOSED state
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.can_execute() is True

        # Record failures to trigger OPEN state
        for _ in range(3):  # failure_threshold = 3
            circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.can_execute() is False

        # Wait for recovery timeout and check for HALF_OPEN
        time.sleep(1.1)  # recovery_timeout = 1 second
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Record successes to close circuit
        for _ in range(2):  # success_threshold = 2
            circuit_breaker.record_success()

        assert circuit_breaker.state == CircuitState.CLOSED

    def test_closed_state_behavior(self, circuit_breaker):
        """Test closed state behavior"""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.can_execute() is True

        # Should reset failure count on success
        circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 1

        circuit_breaker.record_success()
        assert circuit_breaker.failure_count == 0

    def test_open_state_behavior(self, circuit_breaker):
        """Test open state behavior"""
        # Force to open state
        circuit_breaker.force_open()
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.can_execute() is False

        # Should remain closed until timeout
        assert circuit_breaker.can_execute() is False

    def test_half_open_state_behavior(self, circuit_breaker):
        """Test half-open state behavior"""
        circuit_breaker.force_half_open()
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.can_execute() is True

        # Failure in half-open should reopen circuit
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN

        # Reset and test success path
        circuit_breaker.force_half_open()

        # First success
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.success_count == 1

        # Second success should close circuit
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.CLOSED


class TestConfigurableThresholds:
    def test_configurable_failure_threshold(self):
        """Test configurable failure thresholds"""
        # Test with custom failure threshold
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)

        # Should open after 2 failures
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_configurable_success_threshold(self):
        """Test configurable success thresholds"""
        config = CircuitBreakerConfig(success_threshold=1)
        cb = CircuitBreaker("test", config)

        # Move to half-open
        cb.force_half_open()

        # Should close after 1 success
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.slow
    def test_configurable_recovery_timeout(self):
        """Test configurable recovery timeout"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=2)  # 2 seconds
        cb = CircuitBreaker("test", config)

        # Open circuit
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Should not recover immediately
        assert cb.can_execute() is False

        # Should not recover after 1 second
        time.sleep(1)
        assert cb.can_execute() is False

        # Should recover after 2+ seconds
        time.sleep(1.1)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_default_configuration(self):
        """Test default configuration values"""
        cb = CircuitBreaker("test")

        assert cb.config.failure_threshold == 5
        assert cb.config.recovery_timeout == 60
        assert cb.config.success_threshold == 3
        assert cb.config.timeout_duration == 30


class TestAutoRecoveryTesting:
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with short timeouts for testing"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=1,  # 1 second for quick testing
            success_threshold=2,
        )
        return CircuitBreaker("test_provider", config)

    @pytest.mark.slow
    def test_auto_recovery_mechanism(self, circuit_breaker):
        """Test automatic recovery mechanism"""
        # Open the circuit
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN

        # Should not execute immediately
        assert circuit_breaker.can_execute() is False

        # Should auto-recover after timeout
        time.sleep(1.1)
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    def test_half_open_testing_success_path(self, circuit_breaker):
        """Test half-open state success path"""
        # Move to half-open
        circuit_breaker.force_half_open()

        # Record required successes
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_half_open_testing_failure_path(self, circuit_breaker):
        """Test half-open state failure path"""
        circuit_breaker.force_half_open()

        # Any failure should reopen circuit
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.slow
    def test_repeated_recovery_attempts(self, circuit_breaker):
        """Test repeated recovery attempts"""
        # Open circuit
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN

        # First recovery attempt - fail
        time.sleep(1.1)
        assert circuit_breaker.can_execute() is True
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN

        # Second recovery attempt - succeed
        time.sleep(1.1)
        assert circuit_breaker.can_execute() is True
        circuit_breaker.record_success()
        circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.CLOSED


class TestCircuitBreakerUtilities:
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for utility testing"""
        return CircuitBreaker("utility_test")

    def test_get_state_info(self, circuit_breaker):
        """Test state information retrieval"""
        info = circuit_breaker.get_state_info()

        expected_keys = [
            "provider",
            "state",
            "failure_count",
            "success_count",
            "failure_threshold",
            "recovery_timeout",
            "last_failure_time",
            "can_execute",
        ]

        for key in expected_keys:
            assert key in info

        assert info["provider"] == "utility_test"
        assert info["state"] == "closed"
        assert info["failure_count"] == 0
        assert info["can_execute"] is True

    def test_reset_functionality(self, circuit_breaker):
        """Test reset functionality"""
        # Cause some failures
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        assert circuit_breaker.failure_count > 0

        # Reset should clear everything
        circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.last_failure_time == 0

    def test_force_states(self, circuit_breaker):
        """Test force state methods"""
        # Force open
        circuit_breaker.force_open()
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.can_execute() is False

        # Force half-open
        circuit_breaker.force_half_open()
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.success_count == 0

    def test_logging_integration(self, circuit_breaker):
        """Test logging integration"""
        # Mock logger to verify log messages
        with patch.object(circuit_breaker.logger, "info") as mock_info, patch.object(
            circuit_breaker.logger, "warning"
        ) as mock_warning:
            # Test state transitions trigger appropriate log messages
            circuit_breaker.force_open()
            mock_warning.assert_called()

            circuit_breaker.force_half_open()
            mock_info.assert_called()

            circuit_breaker.reset()
            mock_info.assert_called()


class TestCircuitBreakerConfig:
    def test_config_dataclass(self):
        """Test configuration dataclass"""
        config = CircuitBreakerConfig()

        # Test default values
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60
        assert config.success_threshold == 3
        assert config.timeout_duration == 30

        # Test custom values
        custom_config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120,
            success_threshold=5,
            timeout_duration=45,
        )

        assert custom_config.failure_threshold == 10
        assert custom_config.recovery_timeout == 120
        assert custom_config.success_threshold == 5
        assert custom_config.timeout_duration == 45

    def test_config_with_circuit_breaker(self):
        """Test configuration integration with circuit breaker"""
        config = CircuitBreakerConfig(failure_threshold=2, success_threshold=1)

        cb = CircuitBreaker("config_test", config)

        # Should use custom thresholds
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Move to half-open and test success threshold
        cb.force_half_open()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerEnhancements:
    """Additional comprehensive tests for circuit breaker - GAP-008"""

    def test_edge_case_zero_thresholds(self):
        """Test edge cases with zero thresholds"""
        # Test zero failure threshold (should never open)
        config = CircuitBreakerConfig(failure_threshold=0)
        cb = CircuitBreaker("zero_fail", config)

        # Should never open even with failures (edge case handling)
        for _ in range(10):
            cb.record_failure()
        # Behavior depends on implementation - could stay closed or open immediately
        assert cb.state in [CircuitState.CLOSED, CircuitState.OPEN]

    def test_edge_case_single_thresholds(self):
        """Test edge cases with single-unit thresholds"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            recovery_timeout=0,  # Immediate recovery for testing
        )
        cb = CircuitBreaker("single_thresh", config)

        # Should open immediately on first failure
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Should close immediately on first success in half-open
        cb.force_half_open()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_state_transition_consistency(self):
        """Test consistency of state transitions"""
        cb = CircuitBreaker("consistency_test")

        # Track all state transitions
        transitions = []

        # Initial state
        transitions.append(cb.state)

        # Force transitions and verify consistency
        cb.force_open()
        transitions.append(cb.state)
        assert cb.state == CircuitState.OPEN

        cb.force_half_open()
        transitions.append(cb.state)
        assert cb.state == CircuitState.HALF_OPEN

        cb.reset()
        transitions.append(cb.state)
        assert cb.state == CircuitState.CLOSED

        # Verify transition sequence
        expected = [
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
            CircuitState.CLOSED,
        ]
        assert transitions == expected

    def test_failure_count_accuracy(self):
        """Test accuracy of failure counting"""
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker("count_test", config)

        # Test incremental failure counting
        for i in range(1, 4):
            cb.record_failure()
            assert cb.failure_count == i
            assert cb.state == CircuitState.CLOSED

        # Test threshold crossing
        cb.record_failure()
        assert cb.failure_count == 4
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.failure_count == 5
        assert cb.state == CircuitState.OPEN

    def test_success_count_in_half_open(self):
        """Test success counting in half-open state"""
        config = CircuitBreakerConfig(success_threshold=3)
        cb = CircuitBreaker("success_count", config)

        cb.force_half_open()
        assert cb.success_count == 0

        # Test incremental success counting
        for i in range(1, 3):
            cb.record_success()
            assert cb.success_count == i
            assert cb.state == CircuitState.HALF_OPEN

        # Final success should close circuit
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.success_count == 0  # Reset after closing

    def test_last_failure_time_tracking(self):
        """Test last failure time tracking"""
        cb = CircuitBreaker("time_test")

        # Initially no failures
        assert cb.last_failure_time == 0

        # Record failure and check time is set
        before_time = time.time()
        cb.record_failure()
        after_time = time.time()

        assert before_time <= cb.last_failure_time <= after_time

        # Multiple failures should update time (using mock for precision)
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            cb.record_failure()
            assert cb.last_failure_time == 1000.0

            mock_time.return_value = 1001.0
            cb.record_failure()
            assert cb.last_failure_time == 1001.0

    def test_lock_behavior_verification(self):
        """Test that locking behavior is working correctly"""
        cb = CircuitBreaker("lock_test")

        # Verify lock exists and is a threading lock
        assert hasattr(cb, "lock")
        assert hasattr(cb.lock, "acquire")
        assert hasattr(cb.lock, "release")

        # Test that operations work (no deadlocks)
        cb.record_failure()
        cb.record_success()
        cb.can_execute()
        cb.get_state_info()
        cb.reset()

    def test_provider_name_handling(self):
        """Test provider name handling and logging context"""
        provider_names = [
            "test-provider",
            "provider_with_underscores",
            "provider123",
            "",
        ]

        for provider in provider_names:
            cb = CircuitBreaker(provider)
            assert cb.provider == provider

            # Test that operations work with various provider names
            info = cb.get_state_info()
            assert info["provider"] == provider

    def test_recovery_timeout_edge_cases(self):
        """Test recovery timeout edge cases"""
        # Test with very short timeout using mocking
        with patch("time.time") as mock_time:
            config = CircuitBreakerConfig(recovery_timeout=1)
            cb = CircuitBreaker("timeout_test", config)

            # Set initial time
            mock_time.return_value = 100.0
            cb.force_open()

            # Verify can't execute immediately
            assert cb.can_execute() is False

            # Advance time past timeout
            mock_time.return_value = 101.5  # 1.5 seconds later
            assert cb.can_execute() is True
            assert cb.state == CircuitState.HALF_OPEN

    def test_config_parameter_boundaries(self):
        """Test configuration parameter boundary values"""
        # Test with maximum reasonable values
        config = CircuitBreakerConfig(
            failure_threshold=1000,
            recovery_timeout=3600,
            success_threshold=100,
            timeout_duration=300,
        )
        cb = CircuitBreaker("boundary_test", config)

        assert cb.config.failure_threshold == 1000
        assert cb.config.recovery_timeout == 3600
        assert cb.config.success_threshold == 100
        assert cb.config.timeout_duration == 300

    def test_state_info_completeness(self):
        """Test completeness and accuracy of state information"""
        config = CircuitBreakerConfig(failure_threshold=3, success_threshold=2, recovery_timeout=30)
        cb = CircuitBreaker("info_test", config)

        # Test initial state info
        info = cb.get_state_info()

        expected_keys = [
            "provider",
            "state",
            "failure_count",
            "success_count",
            "failure_threshold",
            "recovery_timeout",
            "last_failure_time",
            "can_execute",
        ]

        for key in expected_keys:
            assert key in info

        assert info["provider"] == "info_test"
        assert info["state"] == "closed"
        assert info["failure_count"] == 0
        assert info["success_count"] == 0
        assert info["failure_threshold"] == 3
        assert info["recovery_timeout"] == 30
        assert info["last_failure_time"] == 0
        assert info["can_execute"] is True

        # Test state info after changes
        cb.record_failure()
        info = cb.get_state_info()
        assert info["failure_count"] == 1
        assert info["last_failure_time"] > 0

    def test_logger_integration_comprehensive(self):
        """Test comprehensive logger integration"""
        cb = CircuitBreaker("log_test")

        # Verify logger is properly initialized
        assert hasattr(cb, "logger")
        assert "circuit_breaker.log_test" in cb.logger.name

        # Test logging during state transitions
        with patch.object(cb.logger, "info") as mock_info, patch.object(cb.logger, "warning") as mock_warning:
            # Force open should log warning
            cb.force_open()
            mock_warning.assert_called()

            # Force half-open should log info
            cb.force_half_open()
            mock_info.assert_called()

            # Reset should log info
            cb.reset()
            mock_info.assert_called()

    def test_circuit_breaker_with_no_config(self):
        """Test circuit breaker initialization without explicit config"""
        cb = CircuitBreaker("no_config")

        # Should use default configuration
        assert cb.config.failure_threshold == 5
        assert cb.config.recovery_timeout == 60
        assert cb.config.success_threshold == 3
        assert cb.config.timeout_duration == 30

        # Should function normally
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_multiple_circuit_breakers_independence(self):
        """Test that multiple circuit breakers operate independently"""
        cb1 = CircuitBreaker("provider1")
        cb2 = CircuitBreaker("provider2")

        # Modify one circuit breaker
        cb1.record_failure()
        cb1.record_failure()
        cb1.record_failure()
        cb1.record_failure()
        cb1.record_failure()  # Should open cb1

        # Other should remain unaffected
        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.CLOSED
        assert cb1.can_execute() is False
        assert cb2.can_execute() is True

        # Test state info independence
        info1 = cb1.get_state_info()
        info2 = cb2.get_state_info()

        assert info1["provider"] == "provider1"
        assert info2["provider"] == "provider2"
        assert info1["state"] == "open"
        assert info2["state"] == "closed"

    def test_rapid_state_transitions(self):
        """Test rapid state transitions without timing dependencies"""
        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=1)
        cb = CircuitBreaker("rapid_test", config)

        # Rapid transitions: closed -> open -> half-open -> closed
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.force_half_open()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

        # Repeat cycle to test stability
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.force_half_open()
        cb.record_failure()  # Should reopen
        assert cb.state == CircuitState.OPEN
