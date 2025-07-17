"""
Test Synchronization Utilities

Provides proper synchronization primitives to replace time.sleep() 
and prevent race conditions in tests.
"""

import asyncio
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional
from unittest.mock import Mock


class SyncEvent:
    """Thread-safe event for test synchronization."""

    def __init__(self):
        self._event = threading.Event()
        self._results = []
        self._lock = threading.Lock()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for the event to be set."""
        return self._event.wait(timeout)

    def set(self, result: Any = None) -> None:
        """Set the event and optionally store a result."""
        with self._lock:
            if result is not None:
                self._results.append(result)
        self._event.set()

    def clear(self) -> None:
        """Clear the event."""
        self._event.clear()
        with self._lock:
            self._results.clear()

    def get_results(self) -> list:
        """Get all stored results."""
        with self._lock:
            return self._results.copy()

    def is_set(self) -> bool:
        """Check if event is set."""
        return self._event.is_set()


class AsyncSyncEvent:
    """Async-compatible event for test synchronization."""

    def __init__(self):
        self._event = asyncio.Event()
        self._results = []
        self._lock = asyncio.Lock()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for the event to be set."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def set(self, result: Any = None) -> None:
        """Set the event and optionally store a result."""
        async with self._lock:
            if result is not None:
                self._results.append(result)
        self._event.set()

    def clear(self) -> None:
        """Clear the event."""
        self._event.clear()
        self._results.clear()

    async def get_results(self) -> list:
        """Get all stored results."""
        async with self._lock:
            return self._results.copy()

    def is_set(self) -> bool:
        """Check if event is set."""
        return self._event.is_set()


def wait_for_condition(
    condition: Callable[[], bool], timeout: float = 5.0, interval: float = 0.1, message: str = "Condition not met"
) -> None:
    """
    Wait for a condition to become true.

    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum time to wait
        interval: Check interval
        message: Error message if timeout

    Raises:
        TimeoutError: If condition not met within timeout
    """
    start_time = time.time()

    while not condition():
        if time.time() - start_time > timeout:
            raise TimeoutError(f"{message} after {timeout}s")
        time.sleep(interval)


async def async_wait_for_condition(
    condition: Callable[[], bool], timeout: float = 5.0, interval: float = 0.1, message: str = "Condition not met"
) -> None:
    """
    Async wait for a condition to become true.

    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum time to wait
        interval: Check interval
        message: Error message if timeout

    Raises:
        TimeoutError: If condition not met within timeout
    """
    start_time = time.time()

    while not condition():
        if time.time() - start_time > timeout:
            raise TimeoutError(f"{message} after {timeout}s")
        await asyncio.sleep(interval)


@contextmanager
def synchronized_threads(num_threads: int):
    """
    Context manager for synchronized thread testing.

    Usage:
        with synchronized_threads(5) as sync:
            # Start threads
            for i in range(5):
                thread = threading.Thread(target=worker, args=(sync,))
                thread.start()

            # Wait for all threads to be ready
            sync.wait_all_ready()

            # Signal all threads to proceed
            sync.signal_proceed()

            # Wait for all threads to complete
            sync.wait_all_complete()
    """

    class ThreadSynchronizer:
        def __init__(self, num_threads: int):
            self.num_threads = num_threads
            self.ready_count = 0
            self.complete_count = 0
            self.ready_lock = threading.Lock()
            self.complete_lock = threading.Lock()
            self.ready_event = threading.Event()
            self.proceed_event = threading.Event()
            self.complete_event = threading.Event()
            self.threads = []

        def mark_ready(self):
            """Called by thread when ready."""
            with self.ready_lock:
                self.ready_count += 1
                if self.ready_count == self.num_threads:
                    self.ready_event.set()

        def wait_for_signal(self):
            """Called by thread to wait for proceed signal."""
            self.proceed_event.wait()

        def mark_complete(self):
            """Called by thread when complete."""
            with self.complete_lock:
                self.complete_count += 1
                if self.complete_count == self.num_threads:
                    self.complete_event.set()

        def wait_all_ready(self, timeout: float = 5.0):
            """Wait for all threads to be ready."""
            if not self.ready_event.wait(timeout):
                raise TimeoutError(f"Only {self.ready_count}/{self.num_threads} threads ready")

        def signal_proceed(self):
            """Signal all threads to proceed."""
            self.proceed_event.set()

        def wait_all_complete(self, timeout: float = 10.0):
            """Wait for all threads to complete."""
            if not self.complete_event.wait(timeout):
                raise TimeoutError(f"Only {self.complete_count}/{self.num_threads} threads complete")

    sync = ThreadSynchronizer(num_threads)
    yield sync


class RetryWithBackoff:
    """Retry operations with exponential backoff."""

    def __init__(
        self, max_attempts: int = 3, initial_delay: float = 0.1, max_delay: float = 5.0, backoff_factor: float = 2.0
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def __call__(self, func: Callable) -> Callable:
        """Decorator for retrying functions."""

        def wrapper(*args, **kwargs):
            delay = self.initial_delay
            last_exception = None

            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_attempts - 1:
                        time.sleep(delay)
                        delay = min(delay * self.backoff_factor, self.max_delay)

            raise last_exception

        return wrapper


@contextmanager
def mock_time(initial_time: float = 0.0):
    """
    Context manager to mock time.time() for deterministic testing.

    Usage:
        with mock_time(1000.0) as time_mock:
            # time.time() returns 1000.0
            assert time.time() == 1000.0

            # Advance time
            time_mock.advance(5.0)
            assert time.time() == 1005.0
    """

    class TimeMock:
        def __init__(self, initial: float):
            self.current_time = initial
            self._lock = threading.Lock()

        def __call__(self):
            with self._lock:
                return self.current_time

        def advance(self, seconds: float):
            """Advance the mocked time."""
            with self._lock:
                self.current_time += seconds

        def set_time(self, timestamp: float):
            """Set the mocked time to specific value."""
            with self._lock:
                self.current_time = timestamp

    time_mock = TimeMock(initial_time)
    original_time = time.time

    # Monkey patch time.time
    time.time = time_mock

    try:
        yield time_mock
    finally:
        # Restore original time.time
        time.time = original_time


# Convenience functions
retry_on_failure = RetryWithBackoff()


def ensure_cleanup(*resources):
    """
    Decorator to ensure resources are cleaned up even if test fails.

    Usage:
        @ensure_cleanup(server, client)
        def test_something(server, client):
            # test code
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                for resource in resources:
                    if hasattr(resource, "cleanup"):
                        resource.cleanup()
                    elif hasattr(resource, "close"):
                        resource.close()
                    elif hasattr(resource, "stop"):
                        resource.stop()

        return wrapper

    return decorator
