"""
Test Lead Explorer audit system
"""

import hashlib
import json
from unittest.mock import Mock, patch

from database.models import AuditAction, AuditLogLead, EnrichmentStatus, Lead
from lead_explorer.audit import (
    AuditContext,
    create_audit_log,
    get_audit_summary,
    get_model_values,
    setup_audit_logging,
    verify_audit_integrity,
)


class TestAuditContext:
    """Test AuditContext functionality"""

    def test_set_and_get_user_context(self):
        """Test setting and getting user context"""
        AuditContext.set_user_context(user_id="test_user", user_ip="192.168.1.1", user_agent="TestAgent/1.0")

        context = AuditContext.get_user_context()

        assert context["user_id"] == "test_user"
        assert context["user_ip"] == "192.168.1.1"
        assert context["user_agent"] == "TestAgent/1.0"

    def test_clear_user_context(self):
        """Test clearing user context"""
        AuditContext.set_user_context(user_id="test_user")

        AuditContext.clear_user_context()

        context = AuditContext.get_user_context()
        assert context == {}

    def test_partial_user_context(self):
        """Test setting partial user context"""
        AuditContext.set_user_context(user_id="test_user")

        context = AuditContext.get_user_context()

        assert context["user_id"] == "test_user"
        assert context.get("user_ip") is None
        assert context.get("user_agent") is None


class TestGetModelValues:
    """Test get_model_values function"""

    def test_get_model_values_complete(self, created_lead):
        """Test extracting values from complete lead model"""
        values = get_model_values(created_lead)

        assert values["email"] == created_lead.email
        assert values["domain"] == created_lead.domain
        assert values["company_name"] == created_lead.company_name
        assert values["contact_name"] == created_lead.contact_name
        assert values["enrichment_status"] == created_lead.enrichment_status.value
        assert values["is_manual"] == created_lead.is_manual
        assert values["source"] == created_lead.source
        assert values["is_deleted"] == created_lead.is_deleted

    def test_get_model_values_minimal(self, db_session):
        """Test extracting values from minimal lead model"""
        lead = Lead(
            email="test@example.com", is_manual=True, enrichment_status=EnrichmentStatus.PENDING, is_deleted=False
        )

        values = get_model_values(lead)

        assert values["email"] == "test@example.com"
        assert values["domain"] is None
        assert values["company_name"] is None
        assert values["enrichment_status"] == EnrichmentStatus.PENDING.value
        assert values["is_manual"] is True
        assert values["is_deleted"] is False

    def test_get_model_values_with_enum(self, db_session):
        """Test extracting values with enum fields"""
        lead = Lead(email="test@example.com", is_manual=True, enrichment_status=EnrichmentStatus.COMPLETED)

        values = get_model_values(lead)

        assert values["enrichment_status"] == "completed"


class TestCreateAuditLog:
    """Test create_audit_log function"""

    def test_create_audit_log_basic(self, db_session, created_lead, monkeypatch):
        """Test creating basic audit log"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        AuditContext.set_user_context(user_id="test_user", user_ip="192.168.1.1")

        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"},
        )

        # Check that audit logs were created (session event listener + manual call)
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()
        assert len(audit_logs) == 2  # One from session event, one from manual create_audit_log call

        # Find the manual audit log (has user context set)
        manual_audit_log = None
        for log in audit_logs:
            if log.user_id == "test_user" and log.user_ip == "192.168.1.1":
                manual_audit_log = log
                break

        assert manual_audit_log is not None
        assert manual_audit_log.lead_id == created_lead.id
        assert manual_audit_log.action == AuditAction.CREATE
        assert manual_audit_log.user_id == "test_user"
        assert manual_audit_log.user_ip == "192.168.1.1"
        assert manual_audit_log.checksum is not None

    def test_create_audit_log_with_old_and_new_values(self, db_session, created_lead, monkeypatch):
        """Test creating audit log with both old and new values"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        old_values = {"email": "old@example.com"}
        new_values = {"email": "new@example.com"}

        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            old_values=old_values,
            new_values=new_values,
        )

        # Get all audit logs and find the UPDATE one (the manual call)
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()

        # Find the UPDATE audit log (from manual call)
        update_audit_log = None
        for log in audit_logs:
            if log.action == AuditAction.UPDATE:
                update_audit_log = log
                break

        assert update_audit_log is not None
        assert update_audit_log.action == AuditAction.UPDATE
        assert "old@example.com" in update_audit_log.old_values
        assert "new@example.com" in update_audit_log.new_values

    def test_create_audit_log_no_user_context(self, db_session, created_lead, monkeypatch):
        """Test creating audit log without user context"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        AuditContext.clear_user_context()

        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.DELETE,
            old_values={"email": "test@example.com"},
        )

        audit_log = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).first()
        assert audit_log is not None
        assert audit_log.user_id is None
        assert audit_log.user_ip is None
        assert audit_log.user_agent is None

    def test_create_audit_log_checksum_calculation(self, db_session, created_lead, monkeypatch):
        """Test that checksum is calculated correctly"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"},
        )

        audit_log = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).first()

        # Verify checksum is a valid SHA-256 hash
        assert len(audit_log.checksum) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in audit_log.checksum)

    def test_create_audit_log_handles_exception(self, db_session, created_lead, monkeypatch):
        """Test that audit log creation handles exceptions gracefully"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        # This should not raise an exception even if there are issues
        with patch("lead_explorer.audit.logger") as mock_logger:
            create_audit_log(session=None, lead_id=created_lead.id, action=AuditAction.CREATE)  # Invalid session

            # Should log an error but not crash
            mock_logger.error.assert_called()


class TestVerifyAuditIntegrity:
    """Test verify_audit_integrity function"""

    def test_verify_audit_integrity_valid(self, db_session, created_audit_log):
        """Test verifying integrity of valid audit log"""
        # First, we need to manually calculate the correct checksum
        data = {
            "lead_id": created_audit_log.lead_id,
            "action": created_audit_log.action.value,
            "timestamp": created_audit_log.timestamp.isoformat(),
            "user_id": created_audit_log.user_id,
            "old_values": created_audit_log.old_values,
            "new_values": created_audit_log.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()

        # Update the audit log with correct checksum
        created_audit_log.checksum = expected_checksum
        db_session.commit()

        # Now verify integrity
        result = verify_audit_integrity(db_session, created_audit_log.id)

        assert result is True

    def test_verify_audit_integrity_invalid(self, db_session, created_audit_log):
        """Test verifying integrity of tampered audit log"""
        # Set an invalid checksum
        created_audit_log.checksum = "invalid_checksum"
        db_session.commit()

        result = verify_audit_integrity(db_session, created_audit_log.id)

        assert result is False

    def test_verify_audit_integrity_not_found(self, db_session):
        """Test verifying integrity of non-existent audit log"""
        result = verify_audit_integrity(db_session, "non-existent-id")

        assert result is False

    def test_verify_audit_integrity_exception(self, db_session, created_audit_log):
        """Test that verification handles exceptions gracefully"""
        # Mock the session to raise an exception
        with patch("lead_explorer.audit.logger") as mock_logger:
            mock_session = Mock()
            mock_session.query.side_effect = Exception("Database error")

            result = verify_audit_integrity(mock_session, created_audit_log.id)

            assert result is False
            mock_logger.error.assert_called()


class TestGetAuditSummary:
    """Test get_audit_summary function"""

    def test_get_audit_summary_empty(self, db_session, created_lead):
        """Test audit summary for lead with automatic audit logs from session events"""
        summary = get_audit_summary(db_session, created_lead.id)

        # created_lead fixture now triggers session event listener, so we expect 1 CREATE event
        assert summary["total_events"] == 1
        assert summary["create_events"] == 1
        assert summary["update_events"] == 0
        assert summary["delete_events"] == 0
        assert summary["first_event"] is not None
        assert summary["last_event"] is not None
        assert summary["unique_users"] == 0  # No user context set for the automatic event

    def test_get_audit_summary_with_events(self, db_session, created_lead, monkeypatch):
        """Test audit summary for lead with audit logs"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Create multiple audit logs
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"},
        )

        AuditContext.set_user_context(user_id="user1")
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            new_values={"company_name": "Updated Corp"},
        )

        AuditContext.set_user_context(user_id="user2")
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            new_values={"contact_name": "New Contact"},
        )

        summary = get_audit_summary(db_session, created_lead.id)

        # We now have: 1 automatic CREATE (from created_lead) + 1 manual CREATE + 2 manual UPDATEs = 4 total
        assert summary["total_events"] == 4
        assert summary["create_events"] == 2  # 1 automatic + 1 manual
        assert summary["update_events"] == 2
        assert summary["delete_events"] == 0
        assert summary["first_event"] is not None
        assert summary["last_event"] is not None
        assert summary["unique_users"] == 2  # user1 and user2 (automatic event may have no user)

    def test_get_audit_summary_integrity_check(self, db_session, created_lead, monkeypatch):
        """Test audit summary includes integrity verification"""
        # Temporarily disable the test environment check for audit logging
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Create an audit log
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"},
        )

        summary = get_audit_summary(db_session, created_lead.id)

        # Should include integrity verification result
        assert "integrity_verified" in summary
        assert isinstance(summary["integrity_verified"], bool)


class TestAuditEventListeners:
    """Test SQLAlchemy event listeners for audit logging"""

    def test_audit_listener_on_insert(self, db_session, monkeypatch):
        """Test that lead creation triggers audit log via session event listeners"""
        # Enable audit logging for testing
        monkeypatch.setenv("ENABLE_AUDIT_LOGGING", "true")

        AuditContext.set_user_context(user_id="test_user")

        # Create a lead - this should trigger the after_flush event listener
        lead = Lead(email="test@example.com", is_manual=True)
        db_session.add(lead)
        db_session.commit()

        # Check that audit log was created by the session event listener
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=lead.id).all()
        assert len(audit_logs) >= 1

        # Find the CREATE audit log
        create_logs = [log for log in audit_logs if log.action == AuditAction.CREATE]
        assert len(create_logs) == 1
        assert create_logs[0].user_id == "test_user"
        assert "test@example.com" in create_logs[0].new_values

    def test_audit_listener_on_update(self, db_session, created_lead, monkeypatch):
        """Test that lead update triggers audit log via session event listeners"""
        # Enable audit logging for testing
        monkeypatch.setenv("ENABLE_AUDIT_LOGGING", "true")

        AuditContext.set_user_context(user_id="test_user")

        # Get initial count of audit logs
        initial_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()
        initial_update_count = len([log for log in initial_logs if log.action == AuditAction.UPDATE])

        # Update the lead - this should trigger the after_flush event listener
        created_lead.company_name = "Updated Company"
        db_session.commit()

        # Check that audit log was created by the session event listener
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()
        update_logs = [log for log in audit_logs if log.action == AuditAction.UPDATE]
        assert len(update_logs) >= 1

        # Find the most recent update log
        recent_update = max(update_logs, key=lambda log: log.timestamp)
        assert recent_update.old_values is not None
        assert recent_update.new_values is not None
        assert "Updated Company" in recent_update.new_values

    def test_audit_listener_on_soft_delete(self, db_session, created_lead, monkeypatch):
        """Test that soft delete (is_deleted flag) triggers audit log as UPDATE"""
        # Enable audit logging for testing
        monkeypatch.setenv("ENABLE_AUDIT_LOGGING", "true")

        AuditContext.set_user_context(user_id="test_user")

        # Soft delete the lead - this should trigger the after_flush event listener
        created_lead.is_deleted = True
        db_session.commit()

        # Check that audit log was created with soft delete marker
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()
        update_logs = [log for log in audit_logs if log.action == AuditAction.UPDATE]
        assert len(update_logs) >= 1

        # Find the soft delete log
        soft_delete_log = None
        for log in update_logs:
            if log.new_values and "_soft_delete" in log.new_values:
                soft_delete_log = log
                break

        assert soft_delete_log is not None
        assert soft_delete_log.action == AuditAction.UPDATE
        assert '"_soft_delete": true' in soft_delete_log.new_values

    def test_audit_listener_disabled(self, db_session, monkeypatch):
        """Test that audit logging can be disabled with ENABLE_AUDIT_LOGGING=false"""
        # Disable audit logging
        monkeypatch.setenv("ENABLE_AUDIT_LOGGING", "false")

        # Create a lead
        lead = Lead(email="disabled@example.com", is_manual=True)
        db_session.add(lead)
        db_session.commit()

        # Check that no audit log was created
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=lead.id).all()
        assert len(audit_logs) == 0


class TestSetupAuditLogging:
    """Test setup_audit_logging function"""

    def test_setup_audit_logging(self):
        """Test that setup function runs without error"""
        # This should not raise any exceptions
        setup_audit_logging()

        # The function mainly registers event listeners which are
        # tested implicitly by other tests
