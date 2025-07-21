"""
Port Manager for Test Suite

Provides dynamic port allocation to prevent conflicts in parallel test execution.
"""

import socket
import threading
from contextlib import closing
from typing import Optional, Set


class PortManager:
    """Manages dynamic port allocation for test servers."""

    # Class-level lock for thread safety
    _lock = threading.Lock()
    _allocated_ports: set[int] = set()

    # Port range for test servers
    MIN_PORT = 15000
    MAX_PORT = 25000

    @classmethod
    def get_free_port(cls, preferred_port: int | None = None) -> int:
        """
        Get a free port for testing.

        Args:
            preferred_port: Try this port first if specified

        Returns:
            A free port number
        """
        with cls._lock:
            # Try preferred port first
            if preferred_port and cls._is_port_free(preferred_port):
                if preferred_port not in cls._allocated_ports:
                    cls._allocated_ports.add(preferred_port)
                    return preferred_port

            # Find a free port in range
            for port in range(cls.MIN_PORT, cls.MAX_PORT):
                if port not in cls._allocated_ports and cls._is_port_free(port):
                    cls._allocated_ports.add(port)
                    return port

            raise RuntimeError(f"No free ports available in range {cls.MIN_PORT}-{cls.MAX_PORT}")

    @classmethod
    def release_port(cls, port: int) -> None:
        """Release a port back to the pool."""
        with cls._lock:
            cls._allocated_ports.discard(port)

    @staticmethod
    def _is_port_free(port: int) -> bool:
        """Check if a port is available."""
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    @classmethod
    def reset(cls) -> None:
        """Reset the port manager (for testing)."""
        with cls._lock:
            cls._allocated_ports.clear()


def get_dynamic_port(preferred: int | None = None) -> int:
    """Convenience function to get a free port."""
    return PortManager.get_free_port(preferred)


def release_port(port: int) -> None:
    """Convenience function to release a port."""
    PortManager.release_port(port)
