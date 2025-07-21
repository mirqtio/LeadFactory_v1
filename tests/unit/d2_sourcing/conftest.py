"""
Shared test configuration for D2 Sourcing tests

Uses centralized fixtures from tests.fixtures package.
"""

import pytest

# Import centralized database fixture
from tests.fixtures import test_db  # noqa: F401

# Create alias for backward compatibility
db_session = test_db
