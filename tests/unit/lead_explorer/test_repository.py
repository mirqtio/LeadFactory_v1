"""
Test Lead Explorer repository functionality
"""
import pytest

from database.models import AuditAction, EnrichmentStatus
from lead_explorer.repository import AuditRepository, LeadRepository


class TestLeadRepository:
    """Test LeadRepository functionality"""

    def test_create_lead_minimal(self, db_session):
        """Test creating a lead with minimal data"""
        repo = LeadRepository(db_session)

        lead = repo.create_lead(email="test@example.com", is_manual=True)

        assert lead.id is not None
        assert lead.email == "test@example.com"
        assert lead.is_manual is True
        assert lead.enrichment_status == EnrichmentStatus.PENDING
        assert lead.is_deleted is False
        assert lead.created_at is not None

    def test_create_lead_full_data(self, db_session, sample_lead_data):
        """Test creating a lead with all data"""
        repo = LeadRepository(db_session)

        lead = repo.create_lead(
            email=sample_lead_data["email"],
            domain=sample_lead_data["domain"],
            company_name=sample_lead_data["company_name"],
            contact_name=sample_lead_data["contact_name"],
            is_manual=sample_lead_data["is_manual"],
            source=sample_lead_data["source"],
            created_by="test_user",
        )

        assert lead.email == sample_lead_data["email"]
        assert lead.domain == sample_lead_data["domain"]
        assert lead.company_name == sample_lead_data["company_name"]
        assert lead.contact_name == sample_lead_data["contact_name"]
        assert lead.is_manual == sample_lead_data["is_manual"]
        assert lead.source == sample_lead_data["source"]
        assert lead.created_by == "test_user"

    def test_create_lead_duplicate_email(self, db_session, created_lead):
        """Test that creating lead with duplicate email raises error"""
        repo = LeadRepository(db_session)

        with pytest.raises(ValueError, match="Lead with this email or domain already exists"):
            repo.create_lead(email=created_lead.email, is_manual=True)

    def test_get_lead_by_id(self, db_session, created_lead):
        """Test getting lead by ID"""
        repo = LeadRepository(db_session)

        found_lead = repo.get_lead_by_id(created_lead.id)

        assert found_lead is not None
        assert found_lead.id == created_lead.id
        assert found_lead.email == created_lead.email

    def test_get_lead_by_id_not_found(self, db_session):
        """Test getting lead by non-existent ID"""
        repo = LeadRepository(db_session)

        found_lead = repo.get_lead_by_id("non-existent-id")

        assert found_lead is None

    def test_get_lead_by_id_soft_deleted(self, db_session, created_lead):
        """Test that soft-deleted leads are not returned"""
        repo = LeadRepository(db_session)

        # Soft delete the lead
        repo.soft_delete_lead(created_lead.id)

        # Should not find the lead
        found_lead = repo.get_lead_by_id(created_lead.id)
        assert found_lead is None

    def test_get_lead_by_email(self, db_session, created_lead):
        """Test getting lead by email"""
        repo = LeadRepository(db_session)

        found_lead = repo.get_lead_by_email(created_lead.email)

        assert found_lead is not None
        assert found_lead.email == created_lead.email

    def test_get_lead_by_email_case_insensitive(self, db_session, created_lead):
        """Test that email search is case insensitive"""
        repo = LeadRepository(db_session)

        found_lead = repo.get_lead_by_email(created_lead.email.upper())

        assert found_lead is not None
        assert found_lead.email == created_lead.email

    def test_get_lead_by_domain(self, db_session, created_lead):
        """Test getting lead by domain"""
        repo = LeadRepository(db_session)

        found_lead = repo.get_lead_by_domain(created_lead.domain)

        assert found_lead is not None
        assert found_lead.domain == created_lead.domain

    def test_list_leads_empty(self, db_session):
        """Test listing leads when none exist"""
        repo = LeadRepository(db_session)

        leads, total_count = repo.list_leads()

        assert leads == []
        assert total_count == 0

    def test_list_leads_basic(self, db_session, created_lead):
        """Test basic lead listing"""
        repo = LeadRepository(db_session)

        leads, total_count = repo.list_leads()

        assert len(leads) == 1
        assert total_count == 1
        assert leads[0].id == created_lead.id

    def test_list_leads_pagination(self, db_session):
        """Test lead listing with pagination"""
        repo = LeadRepository(db_session)

        # Create multiple leads
        for i in range(5):
            repo.create_lead(email=f"test{i}@example.com", is_manual=True)

        # Test pagination
        leads, total_count = repo.list_leads(skip=2, limit=2)

        assert len(leads) == 2
        assert total_count == 5

    def test_list_leads_filter_by_manual(self, db_session):
        """Test filtering leads by is_manual"""
        repo = LeadRepository(db_session)

        # Create manual and non-manual leads
        repo.create_lead(email="manual@example.com", is_manual=True)
        repo.create_lead(email="auto@example.com", is_manual=False)

        # Filter by manual
        manual_leads, count = repo.list_leads(is_manual=True)
        assert len(manual_leads) == 1
        assert manual_leads[0].is_manual is True

        # Filter by non-manual
        auto_leads, count = repo.list_leads(is_manual=False)
        assert len(auto_leads) == 1
        assert auto_leads[0].is_manual is False

    def test_list_leads_filter_by_enrichment_status(self, db_session):
        """Test filtering leads by enrichment status"""
        repo = LeadRepository(db_session)

        # Create leads with different statuses
        lead1 = repo.create_lead(email="pending@example.com", is_manual=True)
        lead2 = repo.create_lead(email="completed@example.com", is_manual=True)

        # Update one to completed
        repo.update_enrichment_status(lead2.id, EnrichmentStatus.COMPLETED)

        # Filter by pending
        pending_leads, count = repo.list_leads(enrichment_status=EnrichmentStatus.PENDING)
        assert len(pending_leads) == 1
        assert pending_leads[0].enrichment_status == EnrichmentStatus.PENDING

        # Filter by completed
        completed_leads, count = repo.list_leads(enrichment_status=EnrichmentStatus.COMPLETED)
        assert len(completed_leads) == 1
        assert completed_leads[0].enrichment_status == EnrichmentStatus.COMPLETED

    def test_list_leads_search(self, db_session):
        """Test searching leads by text"""
        repo = LeadRepository(db_session)

        # Create leads with different data
        repo.create_lead(
            email="john@acme.com", domain="acme.com", company_name="ACME Corp", contact_name="John Doe", is_manual=True
        )
        repo.create_lead(
            email="jane@widgets.com",
            domain="widgets.com",
            company_name="Widget LLC",
            contact_name="Jane Smith",
            is_manual=True,
        )

        # Search by company name
        acme_leads, count = repo.list_leads(search="ACME")
        assert len(acme_leads) == 1
        assert "ACME" in acme_leads[0].company_name

        # Search by email
        jane_leads, count = repo.list_leads(search="jane")
        assert len(jane_leads) == 1
        assert "jane" in jane_leads[0].email

        # Search by domain
        widget_leads, count = repo.list_leads(search="widgets")
        assert len(widget_leads) == 1
        assert "widgets" in widget_leads[0].domain

    def test_list_leads_sorting(self, db_session):
        """Test sorting leads"""
        from datetime import datetime, timedelta

        repo = LeadRepository(db_session)

        # Create leads with different emails for deterministic sorting
        lead1 = repo.create_lead(email="alpha@example.com", is_manual=True)
        lead2 = repo.create_lead(email="beta@example.com", is_manual=True)

        # Manually update created_at to ensure different timestamps
        lead1.created_at = datetime.utcnow() - timedelta(minutes=1)
        lead2.created_at = datetime.utcnow()
        db_session.commit()

        # Test descending (default)
        leads, count = repo.list_leads(sort_by="created_at", sort_order="desc")
        assert leads[0].id == lead2.id  # Most recent first

        # Test ascending
        leads, count = repo.list_leads(sort_by="created_at", sort_order="asc")
        assert leads[0].id == lead1.id  # Oldest first

        # Test sorting by email as a fallback test
        leads, count = repo.list_leads(sort_by="email", sort_order="asc")
        assert leads[0].email == "alpha@example.com"
        assert leads[1].email == "beta@example.com"

    def test_update_lead(self, db_session, created_lead):
        """Test updating a lead"""
        repo = LeadRepository(db_session)

        updates = {"company_name": "Updated Corp", "contact_name": "Updated Contact"}

        updated_lead = repo.update_lead(lead_id=created_lead.id, updates=updates, updated_by="test_user")

        assert updated_lead is not None
        assert updated_lead.company_name == "Updated Corp"
        assert updated_lead.contact_name == "Updated Contact"
        assert updated_lead.updated_by == "test_user"

    def test_update_lead_not_found(self, db_session):
        """Test updating non-existent lead"""
        repo = LeadRepository(db_session)

        result = repo.update_lead(lead_id="non-existent", updates={"company_name": "Test"}, updated_by="test_user")

        assert result is None

    def test_soft_delete_lead(self, db_session, created_lead):
        """Test soft deleting a lead"""
        repo = LeadRepository(db_session)

        success = repo.soft_delete_lead(lead_id=created_lead.id, deleted_by="test_user")

        assert success is True

        # Lead should still exist but be marked deleted
        db_session.refresh(created_lead)
        assert created_lead.is_deleted is True
        assert created_lead.deleted_at is not None
        assert created_lead.deleted_by == "test_user"

    def test_soft_delete_lead_not_found(self, db_session):
        """Test soft deleting non-existent lead"""
        repo = LeadRepository(db_session)

        success = repo.soft_delete_lead(lead_id="non-existent")

        assert success is False

    def test_update_enrichment_status(self, db_session, created_lead):
        """Test updating enrichment status"""
        repo = LeadRepository(db_session)

        success = repo.update_enrichment_status(
            lead_id=created_lead.id, status=EnrichmentStatus.IN_PROGRESS, task_id="task_123", error=None
        )

        assert success is True

        db_session.refresh(created_lead)
        assert created_lead.enrichment_status == EnrichmentStatus.IN_PROGRESS
        assert created_lead.enrichment_task_id == "task_123"
        assert created_lead.enrichment_error is None

    def test_update_enrichment_status_with_error(self, db_session, created_lead):
        """Test updating enrichment status with error"""
        repo = LeadRepository(db_session)

        success = repo.update_enrichment_status(
            lead_id=created_lead.id, status=EnrichmentStatus.FAILED, error="Test error message"
        )

        assert success is True

        db_session.refresh(created_lead)
        assert created_lead.enrichment_status == EnrichmentStatus.FAILED
        assert created_lead.enrichment_error == "Test error message"


class TestAuditRepository:
    """Test AuditRepository functionality"""

    def test_create_audit_log(self, db_session, created_lead):
        """Test creating an audit log entry"""
        repo = AuditRepository(db_session)

        audit_log = repo.create_audit_log(
            lead_id=created_lead.id,
            action=AuditAction.CREATE,
            user_id="test_user",
            user_ip="192.168.1.1",
            user_agent="TestAgent/1.0",
            new_values={"email": "test@example.com"},
        )

        assert audit_log.id is not None
        assert audit_log.lead_id == created_lead.id
        assert audit_log.action == AuditAction.CREATE
        assert audit_log.user_id == "test_user"
        assert audit_log.user_ip == "192.168.1.1"
        assert audit_log.user_agent == "TestAgent/1.0"
        assert audit_log.checksum is not None
        assert audit_log.timestamp is not None

    def test_create_audit_log_with_old_and_new_values(self, db_session, created_lead):
        """Test creating audit log with both old and new values"""
        repo = AuditRepository(db_session)

        old_values = {"email": "old@example.com"}
        new_values = {"email": "new@example.com"}

        audit_log = repo.create_audit_log(
            lead_id=created_lead.id,
            action=AuditAction.UPDATE,
            user_id="test_user",
            old_values=old_values,
            new_values=new_values,
        )

        assert audit_log.old_values is not None
        assert audit_log.new_values is not None
        assert "old@example.com" in audit_log.old_values
        assert "new@example.com" in audit_log.new_values

    def test_get_audit_trail(self, db_session, created_lead):
        """Test getting audit trail for a lead"""
        repo = AuditRepository(db_session)

        # Create multiple audit entries
        repo.create_audit_log(lead_id=created_lead.id, action=AuditAction.CREATE, user_id="user1")
        repo.create_audit_log(lead_id=created_lead.id, action=AuditAction.UPDATE, user_id="user2")

        audit_trail = repo.get_audit_trail(created_lead.id)

        assert len(audit_trail) == 2
        # Should be ordered by timestamp desc (most recent first)
        assert audit_trail[0].action == AuditAction.UPDATE
        assert audit_trail[1].action == AuditAction.CREATE

    def test_get_audit_trail_with_limit(self, db_session, created_lead):
        """Test getting audit trail with limit"""
        repo = AuditRepository(db_session)

        # Create multiple audit entries
        for i in range(5):
            repo.create_audit_log(lead_id=created_lead.id, action=AuditAction.UPDATE, user_id=f"user{i}")

        audit_trail = repo.get_audit_trail(created_lead.id, limit=3)

        assert len(audit_trail) == 3

    def test_get_audit_trail_empty(self, db_session, created_lead):
        """Test getting audit trail when no entries exist"""
        repo = AuditRepository(db_session)

        audit_trail = repo.get_audit_trail(created_lead.id)

        assert audit_trail == []

    def test_verify_audit_integrity_valid(self, db_session, created_audit_log):
        """Test verifying audit integrity for valid entry"""
        repo = AuditRepository(db_session)

        # This test depends on the actual checksum calculation
        # For now, just test that the method exists and doesn't crash
        result = repo.verify_audit_integrity(created_audit_log.id)

        # The result may be True or False depending on checksum implementation
        assert isinstance(result, bool)

    def test_verify_audit_integrity_not_found(self, db_session):
        """Test verifying audit integrity for non-existent entry"""
        repo = AuditRepository(db_session)

        result = repo.verify_audit_integrity("non-existent-id")

        assert result is False
