"""
Database cleanup utilities for test isolation
"""
import pytest
from sqlalchemy import text

# Tables that need to be cleaned between tests
# Order matters due to foreign key constraints
CLEANUP_TABLES = [
    "audit_log_leads",
    "leads",
    "businesses",
    "assessments",
    "emails",
    "purchases",
    "report_generations",
    "cost_ledger_entries",
]


@pytest.fixture(autouse=True)
def cleanup_database(db_session):
    """Automatically clean up database tables after each test."""
    # Let the test run
    yield

    # Clean up after the test
    try:
        # Use raw SQL to truncate tables to avoid ORM overhead
        for table in CLEANUP_TABLES:
            try:
                # For PostgreSQL, use TRUNCATE with CASCADE
                if "postgresql" in str(db_session.bind.url):
                    db_session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                else:
                    # For SQLite, use DELETE
                    db_session.execute(text(f"DELETE FROM {table}"))
            except Exception:
                # Table might not exist in all test scenarios
                pass

        db_session.commit()
    except Exception as e:
        print(f"Warning: Database cleanup failed: {e}")
        db_session.rollback()
