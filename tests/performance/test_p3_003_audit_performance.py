"""
Performance tests for P3-003 Lead Explorer Audit Trail
Validates audit logging performance requirements for production deployment
"""

import time
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base
from database.models import AuditAction
from lead_explorer.audit import AuditContext, create_audit_log
from lead_explorer.models import Lead
from lead_explorer.repository import LeadRepository

# Mark entire module as performance test
pytestmark = pytest.mark.performance


class TestP3003AuditPerformance:
    """Performance tests for P3-003 audit logging system"""

    @pytest.fixture(scope="function")
    def db_session(self):
        """Create isolated database session for performance testing"""
        engine = create_engine(
            "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        Base.metadata.drop_all(engine)

    @pytest.fixture
    def sample_lead(self, db_session):
        """Create sample lead for performance testing"""
        lead = Lead(
            email="audit-perf-test@example.com", domain="example.com", company_name="Audit Performance Test Corp"
        )
        db_session.add(lead)
        db_session.commit()
        return lead

    def test_audit_log_creation_performance(self, db_session, sample_lead):
        """Test audit log creation performance < 50ms per operation"""
        # Set audit context
        AuditContext.set_user_context(
            user_id="perf-test-user", user_ip="127.0.0.1", user_agent="Performance Test Agent"
        )

        start_time = time.time()

        # Create audit log entry
        create_audit_log(
            session=db_session,
            lead_id=sample_lead.id,
            action=AuditAction.UPDATE,
            old_values={"company_name": "Old Company"},
            new_values={"company_name": "New Company"},
        )

        end_time = time.time()

        response_time_ms = (end_time - start_time) * 1000

        assert response_time_ms < 50, f"Audit log creation time {response_time_ms:.2f}ms exceeds 50ms limit"

    def test_audit_bulk_operations_performance(self, db_session):
        """Test bulk audit logging performance for batch operations"""
        # Create multiple leads for bulk testing
        leads = []
        for i in range(10):
            lead = Lead(email=f"bulk-test-{i}@example.com", domain="example.com", company_name=f"Bulk Test Corp {i}")
            leads.append(lead)

        db_session.add_all(leads)
        db_session.commit()

        # Test bulk audit logging performance
        AuditContext.set_user_context(user_id="bulk-perf-test", user_ip="127.0.0.1", user_agent="Bulk Performance Test")

        start_time = time.time()

        # Create audit logs for all leads
        for lead in leads:
            create_audit_log(
                session=db_session,
                lead_id=lead.id,
                action=AuditAction.CREATE,
                old_values=None,
                new_values={"company_name": lead.company_name},
            )

            end_time = time.time()

            total_time_ms = (end_time - start_time) * 1000
            avg_time_per_log = total_time_ms / len(leads)

            assert total_time_ms < 500, f"Bulk audit logging time {total_time_ms:.2f}ms exceeds 500ms limit"
            assert avg_time_per_log < 50, f"Average audit log time {avg_time_per_log:.2f}ms exceeds 50ms limit"

    def test_audit_query_performance(self, db_session):
        """Test audit log query performance for reporting"""
        # Create sample audit logs
        AuditContext.set_user_context(
            user_id="query-perf-test", user_ip="127.0.0.1", user_agent="Query Performance Test"
        )

        # Create sample lead for audit logs
        lead = Lead(email="query-test@example.com", domain="example.com", company_name="Query Test Corp")
        db_session.add(lead)
        db_session.commit()

        # Create multiple audit log entries
        for i in range(20):
            create_audit_log(
                session=db_session,
                lead_id=lead.id,
                action=AuditAction.UPDATE,
                old_values={"company_name": f"Old Company {i}"},
                new_values={"company_name": f"New Company {i}"},
            )

        # Test audit log query performance
        start_time = time.time()

        # Query audit logs for the lead
        audit_logs = db_session.execute(
            text("SELECT * FROM audit_log_lead WHERE lead_id = :lead_id ORDER BY timestamp DESC LIMIT 10"),
            {"lead_id": str(lead.id)},
        ).fetchall()

        end_time = time.time()

        query_time_ms = (end_time - start_time) * 1000

        assert len(audit_logs) > 0, "Audit logs should be created"
        assert query_time_ms < 100, f"Audit query time {query_time_ms:.2f}ms exceeds 100ms limit"

    def test_session_event_overhead_performance(self, db_session):
        """Test session event listener overhead performance"""
        # Create repository for lead operations
        repo = LeadRepository(db_session)

        # Test lead creation with session events active
        start_time = time.time()

        lead = repo.create_lead(
            email="session-event-test@example.com", domain="example.com", company_name="Session Event Test Corp"
        )
        db_session.commit()

        end_time = time.time()

        operation_time_ms = (end_time - start_time) * 1000

        # Session event overhead should be minimal (< 100ms total operation time)
        assert operation_time_ms < 100, f"Lead creation with audit events {operation_time_ms:.2f}ms exceeds 100ms limit"

        # Verify audit log was created
        audit_logs = db_session.execute(
            text("SELECT COUNT(*) as count FROM audit_log_lead WHERE lead_id = :lead_id"), {"lead_id": str(lead.id)}
        ).fetchone()

        assert audit_logs.count > 0, "Audit log should be automatically created by session events"

    @pytest.mark.parametrize("operation_count", [1, 5, 10])
    def test_concurrent_audit_performance(self, db_session, operation_count):
        """Test concurrent audit logging performance scalability"""
        leads = []

        # Create leads for concurrent testing
        for i in range(operation_count):
            lead = Lead(email=f"concurrent-{i}@example.com", domain="example.com", company_name=f"Concurrent Corp {i}")
            leads.append(lead)

        db_session.add_all(leads)
        db_session.commit()

        # Test concurrent audit operations
        AuditContext.set_user_context(
            user_id=f"concurrent-test-{operation_count}", user_ip="127.0.0.1", user_agent="Concurrent Performance Test"
        )

        start_time = time.time()

        # Simulate concurrent audit operations
        for lead in leads:
            create_audit_log(
                session=db_session,
                lead_id=lead.id,
                action=AuditAction.UPDATE,
                old_values={"company_name": f"Old {lead.company_name}"},
                new_values={"company_name": f"Updated {lead.company_name}"},
            )

            end_time = time.time()

            total_time_ms = (end_time - start_time) * 1000
            avg_time_per_operation = total_time_ms / operation_count

            # Performance should scale linearly (< 50ms per operation)
            assert (
                avg_time_per_operation < 50
            ), f"Average concurrent audit time {avg_time_per_operation:.2f}ms exceeds 50ms limit for {operation_count} operations"

            # Total time should not exceed reasonable bounds
            max_total_time = operation_count * 60  # 60ms per operation max
            assert (
                total_time_ms < max_total_time
            ), f"Total concurrent audit time {total_time_ms:.2f}ms exceeds {max_total_time}ms limit"
