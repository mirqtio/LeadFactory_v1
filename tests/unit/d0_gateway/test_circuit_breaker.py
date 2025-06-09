"""
Test circuit breaker pattern implementation
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch

from d0_gateway.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig


class TestCircuitBreakerStates:

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for testing"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1,
            success_threshold=2
        )
        return CircuitBreaker("test_provider", config)

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

    def test_configurable_recovery_timeout(self):
        """Test configurable recovery timeout"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=2  # 2 seconds
        )
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
            success_threshold=2
        )
        return CircuitBreaker("test_provider", config)

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


class TestThreadSafeImplementation:

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for threading tests"""
        config = CircuitBreakerConfig(failure_threshold=10, success_threshold=5)
        return CircuitBreaker("thread_test", config)

    def test_thread_safe_state_changes(self, circuit_breaker):
        """Test thread-safe state changes"""
        results = []
        exceptions = []

        def worker_success():
            try:
                for _ in range(50):
                    circuit_breaker.record_success()
                    time.sleep(0.001)  # Small delay
                results.append("success")
            except Exception as e:
                exceptions.append(e)

        def worker_failure():
            try:
                for _ in range(50):
                    circuit_breaker.record_failure()
                    time.sleep(0.001)  # Small delay
                results.append("failure")
            except Exception as e:
                exceptions.append(e)

        def worker_can_execute():
            try:
                for _ in range(50):
                    circuit_breaker.can_execute()
                    time.sleep(0.001)  # Small delay
                results.append("execute")
            except Exception as e:
                exceptions.append(e)

        # Start multiple threads
        threads = [
            threading.Thread(target=worker_success),
            threading.Thread(target=worker_failure),
            threading.Thread(target=worker_can_execute),
            threading.Thread(target=worker_success),
            threading.Thread(target=worker_failure)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should not have any exceptions
        assert len(exceptions) == 0
        assert len(results) == 5

    def test_concurrent_state_access(self, circuit_breaker):
        """Test concurrent access to state information"""
        state_infos = []

        def get_state_info():
            for _ in range(20):
                info = circuit_breaker.get_state_info()
                state_infos.append(info)
                time.sleep(0.001)

        def modify_state():
            for _ in range(10):
                circuit_breaker.record_failure()
                time.sleep(0.002)
                circuit_breaker.record_success()
                time.sleep(0.002)

        # Run concurrent operations
        threads = [
            threading.Thread(target=get_state_info),
            threading.Thread(target=modify_state),
            threading.Thread(target=get_state_info)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should have collected state info without errors
        assert len(state_infos) == 40

        # Each state info should be valid
        for info in state_infos:
            assert 'provider' in info
            assert 'state' in info
            assert 'failure_count' in info
            assert info['provider'] == 'thread_test'


class TestCircuitBreakerUtilities:

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for utility testing"""
        return CircuitBreaker("utility_test")

    def test_get_state_info(self, circuit_breaker):
        """Test state information retrieval"""
        info = circuit_breaker.get_state_info()

        expected_keys = [
            'provider', 'state', 'failure_count', 'success_count',
            'failure_threshold', 'recovery_timeout', 'last_failure_time',
            'can_execute'
        ]

        for key in expected_keys:
            assert key in info

        assert info['provider'] == 'utility_test'
        assert info['state'] == 'closed'
        assert info['failure_count'] == 0
        assert info['can_execute'] is True

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
        with patch.object(circuit_breaker.logger, 'info') as mock_info, \
             patch.object(circuit_breaker.logger, 'warning') as mock_warning:

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
            timeout_duration=45
        )

        assert custom_config.failure_threshold == 10
        assert custom_config.recovery_timeout == 120
        assert custom_config.success_threshold == 5
        assert custom_config.timeout_duration == 45

    def test_config_with_circuit_breaker(self):
        """Test configuration integration with circuit breaker"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1
        )

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
