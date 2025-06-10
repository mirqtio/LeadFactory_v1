"""
Circuit breaker pattern implementation for graceful degradation
"""
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Dict, Optional

from core.logging import get_logger


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""

    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: int = 60  # Seconds before testing recovery
    success_threshold: int = 3  # Successes to close from half-open
    timeout_duration: int = 30  # Request timeout in seconds


class CircuitBreaker:
    """Circuit breaker for external API calls"""

    def __init__(self, provider: str, config: Optional[CircuitBreakerConfig] = None):
        self.provider = provider
        self.config = config or CircuitBreakerConfig()
        self.logger = get_logger(f"circuit_breaker.{provider}", domain="d0")

        # Circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.lock = Lock()

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        with self.lock:
            now = time.time()

            if self.state == CircuitState.CLOSED:
                return True

            elif self.state == CircuitState.OPEN:
                # Check if we should move to half-open
                if now - self.last_failure_time >= self.config.recovery_timeout:
                    self.logger.info(
                        f"Circuit breaker half-opening for {self.provider}"
                    )
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    return True
                return False

            elif self.state == CircuitState.HALF_OPEN:
                # Allow limited requests to test recovery
                return True

        return False

    def record_success(self) -> None:
        """Record a successful request"""
        with self.lock:
            if self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

            elif self.state == CircuitState.HALF_OPEN:
                self.success_count += 1

                # Close circuit if enough successes
                if self.success_count >= self.config.success_threshold:
                    self.logger.info(f"Circuit breaker closing for {self.provider}")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0

    def record_failure(self) -> None:
        """Record a failed request"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.CLOSED:
                # Open circuit if too many failures
                if self.failure_count >= self.config.failure_threshold:
                    self.logger.warning(
                        f"Circuit breaker opening for {self.provider} "
                        f"after {self.failure_count} failures"
                    )
                    self.state = CircuitState.OPEN

            elif self.state == CircuitState.HALF_OPEN:
                # Go back to open on any failure during testing
                self.logger.warning(f"Circuit breaker re-opening for {self.provider}")
                self.state = CircuitState.OPEN
                self.success_count = 0

    def get_state_info(self) -> Dict[str, any]:
        """Get current circuit breaker state information"""
        with self.lock:
            # Calculate can_execute without calling the method to avoid deadlock
            now = time.time()
            can_exec = True
            
            if self.state == CircuitState.OPEN:
                can_exec = now - self.last_failure_time >= self.config.recovery_timeout
            elif self.state == CircuitState.HALF_OPEN:
                can_exec = True
            # CLOSED state can always execute
            
            return {
                "provider": self.provider,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "last_failure_time": self.last_failure_time,
                "can_execute": can_exec,
            }

    def reset(self) -> None:
        """Reset circuit breaker to closed state"""
        with self.lock:
            self.logger.info(f"Resetting circuit breaker for {self.provider}")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = 0

    def force_open(self) -> None:
        """Force circuit breaker to open state (for testing)"""
        with self.lock:
            self.logger.warning(f"Forcing circuit breaker open for {self.provider}")
            self.state = CircuitState.OPEN
            self.last_failure_time = time.time()

    def force_half_open(self) -> None:
        """Force circuit breaker to half-open state (for testing)"""
        with self.lock:
            self.logger.info(f"Forcing circuit breaker half-open for {self.provider}")
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
