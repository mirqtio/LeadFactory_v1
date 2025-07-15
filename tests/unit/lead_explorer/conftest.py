"""
Shared test configuration for Lead Explorer tests
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base
from lead_explorer.models import AuditAction, AuditLogLead, Lead  # noqa: F401

# Import all models to ensure foreign key references are available
try:
    import database.models  # noqa: F401
    import lead_explorer.models  # noqa: F401
except ImportError:
    pass


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()


@pytest.fixture
def sample_lead_data():
    """Sample lead data for testing with unique domain"""
    # Generate unique domain to avoid constraint violations
    unique_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test-{unique_id}@example-{unique_id}.com",
        "domain": f"example-{unique_id}.com",
        "company_name": f"Example Corp {unique_id}",
        "contact_name": "John Doe",
        "is_manual": True,
        "source": "manual_entry",
    }


@pytest.fixture
def created_lead(db_session, sample_lead_data):
    """Create a sample lead in the database"""
    lead = Lead(**sample_lead_data)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


@pytest.fixture
def sample_audit_data():
    """Sample audit data for testing"""
    return {
        "action": AuditAction.CREATE,
        "user_id": "test_user",
        "user_ip": "127.0.0.1",
        "user_agent": "TestAgent/1.0",
        "new_values": '{"email": "test@example.com", "domain": "example.com"}',
        "checksum": "test_checksum",
    }


@pytest.fixture
def created_audit_log(db_session, created_lead, sample_audit_data):
    """Create a sample audit log in the database"""
    audit_log = AuditLogLead(lead_id=created_lead.id, **sample_audit_data)
    db_session.add(audit_log)
    db_session.commit()
    db_session.refresh(audit_log)
    return audit_log
