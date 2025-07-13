"""
Test Lead Explorer domain models
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from database.models import Lead, AuditLogLead, EnrichmentStatus, AuditAction


class TestLeadModel:
    """Test Lead model functionality"""

    def test_lead_creation_with_required_fields(self, db_session):
        """Test creating a lead with minimal required data"""
        lead = Lead(
            email="test@example.com",
            is_manual=True
        )

        db_session.add(lead)
        db_session.commit()

        assert lead.id is not None
        assert lead.email == "test@example.com"
        assert lead.is_manual is True
        assert lead.enrichment_status == EnrichmentStatus.PENDING
        assert lead.is_deleted is False
        assert lead.created_at is not None
        assert lead.updated_at is not None

    def test_lead_creation_with_domain_only(self, db_session):
        """Test creating a lead with only domain"""
        lead = Lead(
            domain="example.com",
            is_manual=False,
            source="csv_upload"
        )

        db_session.add(lead)
        db_session.commit()

        assert lead.id is not None
        assert lead.domain == "example.com"
        assert lead.email is None
        assert lead.is_manual is False
        assert lead.source == "csv_upload"

    def test_lead_with_all_fields(self, db_session, sample_lead_data):
        """Test creating a lead with all fields populated"""
        lead_data = {
            **sample_lead_data,
            "enrichment_status": EnrichmentStatus.COMPLETED,
            "enrichment_task_id": "task_123",
            "enrichment_error": None,
            "created_by": "user_123",
            "updated_by": "user_456"
        }

        lead = Lead(**lead_data)
        db_session.add(lead)
        db_session.commit()

        assert lead.email == sample_lead_data["email"]
        assert lead.domain == sample_lead_data["domain"]
        assert lead.company_name == sample_lead_data["company_name"]
        assert lead.contact_name == sample_lead_data["contact_name"]
        assert lead.enrichment_status == EnrichmentStatus.COMPLETED
        assert lead.enrichment_task_id == "task_123"
        assert lead.created_by == "user_123"
        assert lead.updated_by == "user_456"

    def test_lead_email_uniqueness(self, db_session):
        """Test that email must be unique"""
        # Create first lead
        lead1 = Lead(email="unique@example.com", is_manual=True)
        db_session.add(lead1)
        db_session.commit()

        # Try to create second lead with same email
        lead2 = Lead(email="unique@example.com", is_manual=True)
        db_session.add(lead2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_lead_domain_uniqueness(self, db_session):
        """Test that domain must be unique"""
        # Create first lead
        lead1 = Lead(domain="unique.com", is_manual=True)
        db_session.add(lead1)
        db_session.commit()

        # Try to create second lead with same domain
        lead2 = Lead(domain="unique.com", is_manual=True)
        db_session.add(lead2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_lead_soft_delete(self, db_session, created_lead):
        """Test soft delete functionality"""
        # Soft delete the lead
        created_lead.is_deleted = True
        created_lead.deleted_at = datetime.utcnow()
        created_lead.deleted_by = "admin_user"

        db_session.commit()

        assert created_lead.is_deleted is True
        assert created_lead.deleted_at is not None
        assert created_lead.deleted_by == "admin_user"

        # Lead should still exist in database
        found_lead = db_session.query(Lead).filter_by(id=created_lead.id).first()
        assert found_lead is not None
        assert found_lead.is_deleted is True

    def test_lead_enrichment_status_enum(self, db_session):
        """Test enrichment status enum values"""
        lead = Lead(email="test@example.com", is_manual=True)

        # Test all enum values
        for status in EnrichmentStatus:
            lead.enrichment_status = status
            db_session.add(lead)
            db_session.commit()

            db_session.refresh(lead)
            assert lead.enrichment_status == status

    def test_lead_id_generation(self, db_session):
        """Test that lead IDs are auto-generated UUIDs"""
        lead = Lead(email="test@example.com", is_manual=True)
        db_session.add(lead)
        db_session.commit()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(lead.id)
        assert str(uuid_obj) == lead.id

    def test_lead_timestamps(self, db_session):
        """Test that timestamps are set correctly"""
        before_creation = datetime.utcnow().replace(microsecond=0)

        lead = Lead(email="test@example.com", is_manual=True)
        db_session.add(lead)
        db_session.commit()

        after_creation = datetime.utcnow().replace(microsecond=0)

        # SQLite doesn't store microseconds, so we compare without them
        assert before_creation <= lead.created_at.replace(microsecond=0) <= after_creation
        assert before_creation <= lead.updated_at.replace(microsecond=0) <= after_creation
        assert lead.created_at == lead.updated_at  # Should be same initially


class TestAuditLogLeadModel:
    """Test AuditLogLead model functionality"""

    def test_audit_log_creation(self, db_session, created_lead):
        """Test creating an audit log entry"""
        audit_log = AuditLogLead(
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            user_id="test_user",
            user_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            new_values='{"email": "test@example.com"}',
            checksum="abc123"
        )

        db_session.add(audit_log)
        db_session.commit()

        assert audit_log.id is not None
        assert audit_log.lead_id == created_lead.id
        assert audit_log.action == AuditAction.CREATE
        assert audit_log.user_id == "test_user"
        assert audit_log.user_ip == "192.168.1.1"
        assert audit_log.user_agent == "TestAgent/1.0"
        assert audit_log.new_values == '{"email": "test@example.com"}'
        assert audit_log.checksum == "abc123"
        assert audit_log.timestamp is not None

    def test_audit_log_all_actions(self, db_session, created_lead):
        """Test all audit action types"""
        for action in AuditAction:
            audit_log = AuditLogLead(
                lead_id=created_lead.id,
                action=action,
                user_id="test_user",
                checksum="test_checksum"
            )

            db_session.add(audit_log)
            db_session.commit()

            db_session.refresh(audit_log)
            assert audit_log.action == action

    def test_audit_log_with_old_and_new_values(self, db_session, created_lead):
        """Test audit log with both old and new values (UPDATE scenario)"""
        audit_log = AuditLogLead(
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            user_id="test_user",
            old_values='{"email": "old@example.com"}',
            new_values='{"email": "new@example.com"}',
            checksum="update_checksum"
        )

        db_session.add(audit_log)
        db_session.commit()

        assert audit_log.old_values == '{"email": "old@example.com"}'
        assert audit_log.new_values == '{"email": "new@example.com"}'

    def test_audit_log_minimal_data(self, db_session, created_lead):
        """Test audit log with minimal required data"""
        audit_log = AuditLogLead(
            lead_id=created_lead.id,
            action=AuditAction.DELETE,
            checksum="minimal_checksum"
        )

        db_session.add(audit_log)
        db_session.commit()

        assert audit_log.lead_id == created_lead.id
        assert audit_log.action == AuditAction.DELETE
        assert audit_log.user_id is None
        assert audit_log.user_ip is None
        assert audit_log.user_agent is None
        assert audit_log.checksum == "minimal_checksum"

    def test_audit_log_timestamp_auto_generation(self, db_session, created_lead):
        """Test that timestamp is automatically generated"""
        before_creation = datetime.utcnow().replace(microsecond=0)

        audit_log = AuditLogLead(
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            checksum="timestamp_test"
        )

        db_session.add(audit_log)
        db_session.commit()

        after_creation = datetime.utcnow().replace(microsecond=0)

        # SQLite doesn't store microseconds, so we compare without them
        assert before_creation <= audit_log.timestamp.replace(microsecond=0) <= after_creation

    def test_audit_log_id_generation(self, db_session, created_lead):
        """Test that audit log IDs are auto-generated UUIDs"""
        audit_log = AuditLogLead(
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            checksum="id_test"
        )

        db_session.add(audit_log)
        db_session.commit()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(audit_log.id)
        assert str(uuid_obj) == audit_log.id


class TestEnrichmentStatusEnum:
    """Test EnrichmentStatus enum"""

    def test_enrichment_status_values(self):
        """Test that enum has expected values"""
        assert EnrichmentStatus.PENDING.value == "pending"
        assert EnrichmentStatus.IN_PROGRESS.value == "in_progress"
        assert EnrichmentStatus.COMPLETED.value == "completed"
        assert EnrichmentStatus.FAILED.value == "failed"

    def test_enrichment_status_count(self):
        """Test that enum has expected number of values"""
        assert len(list(EnrichmentStatus)) == 4


class TestAuditActionEnum:
    """Test AuditAction enum"""

    def test_audit_action_values(self):
        """Test that enum has expected values"""
        assert AuditAction.CREATE.value == "create"
        assert AuditAction.UPDATE.value == "update"
        assert AuditAction.DELETE.value == "delete"

    def test_audit_action_count(self):
        """Test that enum has expected number of values"""
        assert len(list(AuditAction)) == 3
