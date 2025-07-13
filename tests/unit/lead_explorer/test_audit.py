"""
Test Lead Explorer audit system
"""
import os
import json
import hashlib
import pytest
from unittest.mock import patch, Mock

from database.models import Lead, AuditLogLead, EnrichmentStatus, AuditAction
from lead_explorer.audit import (
    AuditContext, 
    get_model_values, 
    create_audit_log,
    verify_audit_integrity,
    get_audit_summary,
    setup_audit_logging
)


class TestAuditContext:
    """Test AuditContext functionality"""
    
    def test_set_and_get_user_context(self):
        """Test setting and getting user context"""
        AuditContext.set_user_context(
            user_id="test_user",
            user_ip="192.168.1.1",
            user_agent="TestAgent/1.0"
        )
        
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
            email="test@example.com", 
            is_manual=True, 
            enrichment_status=EnrichmentStatus.PENDING,
            is_deleted=False
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
        lead = Lead(
            email="test@example.com", 
            is_manual=True,
            enrichment_status=EnrichmentStatus.COMPLETED
        )
        
        values = get_model_values(lead)
        
        assert values["enrichment_status"] == "completed"


class TestCreateAuditLog:
    """Test create_audit_log function"""
    
    def test_create_audit_log_basic(self, db_session, created_lead):
        """Test creating basic audit log"""
        AuditContext.set_user_context(
            user_id="test_user",
            user_ip="192.168.1.1"
        )
        
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"}
        )
        
        # Check that audit log was created
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()
        assert len(audit_logs) == 1
        
        audit_log = audit_logs[0]
        assert audit_log.lead_id == created_lead.id
        assert audit_log.action == AuditAction.CREATE
        assert audit_log.user_id == "test_user"
        assert audit_log.user_ip == "192.168.1.1"
        assert audit_log.checksum is not None
    
    def test_create_audit_log_with_old_and_new_values(self, db_session, created_lead):
        """Test creating audit log with both old and new values"""
        old_values = {"email": "old@example.com"}
        new_values = {"email": "new@example.com"}
        
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            old_values=old_values,
            new_values=new_values
        )
        
        audit_log = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).first()
        assert audit_log is not None
        assert audit_log.action == AuditAction.UPDATE
        assert "old@example.com" in audit_log.old_values
        assert "new@example.com" in audit_log.new_values
    
    def test_create_audit_log_no_user_context(self, db_session, created_lead):
        """Test creating audit log without user context"""
        AuditContext.clear_user_context()
        
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.DELETE,
            old_values={"email": "test@example.com"}
        )
        
        audit_log = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).first()
        assert audit_log is not None
        assert audit_log.user_id is None
        assert audit_log.user_ip is None
        assert audit_log.user_agent is None
    
    def test_create_audit_log_checksum_calculation(self, db_session, created_lead):
        """Test that checksum is calculated correctly"""
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"}
        )
        
        audit_log = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).first()
        
        # Verify checksum is a valid SHA-256 hash
        assert len(audit_log.checksum) == 64  # SHA-256 hex length
        assert all(c in '0123456789abcdef' for c in audit_log.checksum)
    
    def test_create_audit_log_handles_exception(self, db_session, created_lead):
        """Test that audit log creation handles exceptions gracefully"""
        # This should not raise an exception even if there are issues
        with patch('lead_explorer.audit.logger') as mock_logger:
            create_audit_log(
                session=None,  # Invalid session
                lead_id=created_lead.id,
                action=AuditAction.CREATE
            )
            
            # Should log an error but not crash
            mock_logger.error.assert_called()


class TestVerifyAuditIntegrity:
    """Test verify_audit_integrity function"""
    
    def test_verify_audit_integrity_valid(self, db_session, created_audit_log):
        """Test verifying integrity of valid audit log"""
        # First, we need to manually calculate the correct checksum
        data = {
            'lead_id': created_audit_log.lead_id,
            'action': created_audit_log.action.value,
            'timestamp': created_audit_log.timestamp.isoformat(),
            'user_id': created_audit_log.user_id,
            'old_values': created_audit_log.old_values,
            'new_values': created_audit_log.new_values,
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
        with patch('lead_explorer.audit.logger') as mock_logger:
            mock_session = Mock()
            mock_session.query.side_effect = Exception("Database error")
            
            result = verify_audit_integrity(mock_session, created_audit_log.id)
            
            assert result is False
            mock_logger.error.assert_called()


class TestGetAuditSummary:
    """Test get_audit_summary function"""
    
    def test_get_audit_summary_empty(self, db_session, created_lead):
        """Test audit summary for lead with no audit logs"""
        summary = get_audit_summary(db_session, created_lead.id)
        
        assert summary["total_events"] == 0
        assert summary["create_events"] == 0
        assert summary["update_events"] == 0
        assert summary["delete_events"] == 0
        assert summary["first_event"] is None
        assert summary["last_event"] is None
        assert summary["unique_users"] == 0
    
    def test_get_audit_summary_with_events(self, db_session, created_lead):
        """Test audit summary for lead with audit logs"""
        # Create multiple audit logs
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"}
        )
        
        AuditContext.set_user_context(user_id="user1")
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            new_values={"company_name": "Updated Corp"}
        )
        
        AuditContext.set_user_context(user_id="user2")
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            new_values={"contact_name": "New Contact"}
        )
        
        summary = get_audit_summary(db_session, created_lead.id)
        
        assert summary["total_events"] == 3
        assert summary["create_events"] == 1
        assert summary["update_events"] == 2
        assert summary["delete_events"] == 0
        assert summary["first_event"] is not None
        assert summary["last_event"] is not None
        assert summary["unique_users"] == 2  # user1 and user2
    
    def test_get_audit_summary_integrity_check(self, db_session, created_lead):
        """Test audit summary includes integrity verification"""
        # Create an audit log
        create_audit_log(
            session=db_session,
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            new_values={"email": "test@example.com"}
        )
        
        summary = get_audit_summary(db_session, created_lead.id)
        
        # Should include integrity verification result
        assert "integrity_verified" in summary
        assert isinstance(summary["integrity_verified"], bool)


class TestAuditEventListeners:
    """Test SQLAlchemy event listeners for audit logging"""
    
    @pytest.mark.skipif(os.getenv('ENVIRONMENT') == 'test', 
                        reason="Audit event listeners are disabled in test environment")
    def test_audit_listener_on_insert(self, db_session):
        """Test that lead creation triggers audit log"""
        AuditContext.set_user_context(user_id="test_user")
        
        # Create a lead (should trigger after_insert listener)
        lead = Lead(email="test@example.com", is_manual=True)
        db_session.add(lead)
        db_session.commit()
        
        # Check that audit log was created
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=lead.id).all()
        assert len(audit_logs) == 1
        assert audit_logs[0].action == AuditAction.CREATE
    
    @pytest.mark.skipif(os.getenv('ENVIRONMENT') == 'test', 
                        reason="Audit event listeners are disabled in test environment")
    def test_audit_listener_on_update(self, db_session, created_lead):
        """Test that lead update triggers audit log"""
        AuditContext.set_user_context(user_id="test_user")
        
        # Update the lead (should trigger after_update listener)
        created_lead.company_name = "Updated Company"
        db_session.commit()
        
        # Check that audit log was created
        audit_logs = db_session.query(AuditLogLead).filter_by(lead_id=created_lead.id).all()
        update_logs = [log for log in audit_logs if log.action == AuditAction.UPDATE]
        assert len(update_logs) >= 1


class TestSetupAuditLogging:
    """Test setup_audit_logging function"""
    
    def test_setup_audit_logging(self):
        """Test that setup function runs without error"""
        # This should not raise any exceptions
        setup_audit_logging()
        
        # The function mainly registers event listeners which are
        # tested implicitly by other tests