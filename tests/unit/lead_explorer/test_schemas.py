"""
Test Lead Explorer Pydantic schemas
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from lead_explorer.schemas import (
    CreateLeadSchema,
    UpdateLeadSchema,
    LeadResponseSchema,
    QuickAddLeadSchema,
    QuickAddResponseSchema,
    LeadFilterSchema,
    PaginationSchema,
    LeadListResponseSchema,
    AuditLogResponseSchema,
    AuditTrailResponseSchema,
    ErrorResponseSchema,
    ValidationErrorSchema,
    HealthCheckResponseSchema,
    EnrichmentStatusEnum
)


class TestCreateLeadSchema:
    """Test CreateLeadSchema validation"""
    
    def test_create_lead_schema_valid_email_only(self):
        """Test valid schema with email only"""
        data = {"email": "test@example.com", "is_manual": True}
        schema = CreateLeadSchema(**data)
        
        assert schema.email == "test@example.com"
        assert schema.is_manual is True
        assert schema.domain is None
        assert schema.company_name is None
        assert schema.source is None
    
    def test_create_lead_schema_valid_domain_only(self):
        """Test valid schema with domain only"""
        data = {"domain": "example.com", "is_manual": False}
        schema = CreateLeadSchema(**data)
        
        assert schema.domain == "example.com"
        assert schema.is_manual is False
        assert schema.email is None
    
    def test_create_lead_schema_valid_full_data(self):
        """Test valid schema with all fields"""
        data = {
            "email": "test@example.com",
            "domain": "example.com", 
            "company_name": "Test Corp",
            "contact_name": "John Doe",
            "is_manual": True,
            "source": "manual_entry"
        }
        schema = CreateLeadSchema(**data)
        
        assert schema.email == "test@example.com"
        assert schema.domain == "example.com"
        assert schema.company_name == "Test Corp"
        assert schema.contact_name == "John Doe"
        assert schema.is_manual is True
        assert schema.source == "manual_entry"
    
    def test_create_lead_schema_neither_email_nor_domain(self):
        """Test validation error when neither email nor domain provided"""
        data = {"company_name": "Test Corp", "is_manual": True}
        
        with pytest.raises(ValidationError) as exc_info:
            CreateLeadSchema(**data)
        
        assert "Either email or domain must be provided" in str(exc_info.value)
    
    def test_create_lead_schema_invalid_email(self):
        """Test validation error for invalid email"""
        data = {"email": "invalid-email", "is_manual": True}
        
        with pytest.raises(ValidationError):
            CreateLeadSchema(**data)
    
    def test_create_lead_schema_invalid_domain(self):
        """Test validation error for invalid domain"""
        data = {"domain": "invalid-domain", "is_manual": True}
        
        with pytest.raises(ValidationError) as exc_info:
            CreateLeadSchema(**data)
        
        assert "Domain must contain at least one dot" in str(exc_info.value)
    
    def test_create_lead_schema_domain_validation_cases(self):
        """Test various domain validation cases"""
        # Valid domains
        valid_domains = [
            "example.com",
            "sub.example.com",
            "test-domain.co.uk",
            "123domain.org"
        ]
        
        for domain in valid_domains:
            data = {"domain": domain, "is_manual": True}
            schema = CreateLeadSchema(**data)
            assert schema.domain == domain.lower()
        
        # Invalid domains
        invalid_domains = [
            "domain",  # No dot
            ".example.com",  # Starts with dot
            "example.com.",  # Ends with dot
            "ex ample.com",  # Contains space
            "ex@mple.com"  # Contains @
        ]
        
        for domain in invalid_domains:
            data = {"domain": domain, "is_manual": True}
            with pytest.raises(ValidationError):
                CreateLeadSchema(**data)
    
    def test_create_lead_schema_domain_case_normalization(self):
        """Test that domain is normalized to lowercase"""
        data = {"domain": "EXAMPLE.COM", "is_manual": True}
        schema = CreateLeadSchema(**data)
        
        assert schema.domain == "example.com"
    
    def test_create_lead_schema_string_length_limits(self):
        """Test string length validation"""
        # Test domain length limits
        data = {"domain": "a" * 300 + ".com", "is_manual": True}
        with pytest.raises(ValidationError):
            CreateLeadSchema(**data)
        
        # Test company name length
        data = {"email": "test@example.com", "company_name": "a" * 600, "is_manual": True}
        with pytest.raises(ValidationError):
            CreateLeadSchema(**data)


class TestUpdateLeadSchema:
    """Test UpdateLeadSchema validation"""
    
    def test_update_lead_schema_empty(self):
        """Test schema with no updates"""
        schema = UpdateLeadSchema()
        
        assert schema.email is None
        assert schema.domain is None
        assert schema.company_name is None
        assert schema.contact_name is None
        assert schema.source is None
    
    def test_update_lead_schema_partial_update(self):
        """Test schema with partial updates"""
        data = {"company_name": "Updated Corp"}
        schema = UpdateLeadSchema(**data)
        
        assert schema.company_name == "Updated Corp"
        assert schema.email is None
        assert schema.domain is None
    
    def test_update_lead_schema_domain_validation(self):
        """Test domain validation in update schema"""
        # Valid domain
        data = {"domain": "updated.com"}
        schema = UpdateLeadSchema(**data)
        assert schema.domain == "updated.com"
        
        # Invalid domain
        data = {"domain": "invalid-domain"}
        with pytest.raises(ValidationError):
            UpdateLeadSchema(**data)


class TestQuickAddLeadSchema:
    """Test QuickAddLeadSchema validation"""
    
    def test_quick_add_schema_valid(self):
        """Test valid quick-add schema"""
        data = {
            "email": "test@example.com",
            "company_name": "Test Corp"
        }
        schema = QuickAddLeadSchema(**data)
        
        assert schema.email == "test@example.com"
        assert schema.company_name == "Test Corp"
    
    def test_quick_add_schema_requires_email_or_domain(self):
        """Test that quick-add requires email or domain"""
        data = {"company_name": "Test Corp"}
        
        with pytest.raises(ValidationError) as exc_info:
            QuickAddLeadSchema(**data)
        
        assert "Either email or domain must be provided for enrichment" in str(exc_info.value)


class TestLeadFilterSchema:
    """Test LeadFilterSchema validation"""
    
    def test_lead_filter_schema_empty(self):
        """Test empty filter schema"""
        schema = LeadFilterSchema()
        
        assert schema.is_manual is None
        assert schema.enrichment_status is None
        assert schema.search is None
    
    def test_lead_filter_schema_with_filters(self):
        """Test filter schema with values"""
        data = {
            "is_manual": True,
            "enrichment_status": "pending",
            "search": "test search"
        }
        schema = LeadFilterSchema(**data)
        
        assert schema.is_manual is True
        assert schema.enrichment_status == EnrichmentStatusEnum.PENDING
        assert schema.search == "test search"
    
    def test_lead_filter_schema_invalid_enrichment_status(self):
        """Test invalid enrichment status"""
        data = {"enrichment_status": "invalid_status"}
        
        with pytest.raises(ValidationError):
            LeadFilterSchema(**data)
    
    def test_lead_filter_schema_search_length_limit(self):
        """Test search string length limit"""
        data = {"search": "a" * 600}
        
        with pytest.raises(ValidationError):
            LeadFilterSchema(**data)


class TestPaginationSchema:
    """Test PaginationSchema validation"""
    
    def test_pagination_schema_defaults(self):
        """Test default pagination values"""
        schema = PaginationSchema()
        
        assert schema.skip == 0
        assert schema.limit == 100
        assert schema.sort_by == "created_at"
        assert schema.sort_order == "desc"
    
    def test_pagination_schema_custom_values(self):
        """Test custom pagination values"""
        data = {
            "skip": 50,
            "limit": 25,
            "sort_by": "email",
            "sort_order": "asc"
        }
        schema = PaginationSchema(**data)
        
        assert schema.skip == 50
        assert schema.limit == 25
        assert schema.sort_by == "email"
        assert schema.sort_order == "asc"
    
    def test_pagination_schema_validation_limits(self):
        """Test pagination validation limits"""
        # Negative skip
        with pytest.raises(ValidationError):
            PaginationSchema(skip=-1)
        
        # Zero limit
        with pytest.raises(ValidationError):
            PaginationSchema(limit=0)
        
        # Limit too high
        with pytest.raises(ValidationError):
            PaginationSchema(limit=2000)
        
        # Invalid sort order
        with pytest.raises(ValidationError):
            PaginationSchema(sort_order="invalid")


class TestLeadResponseSchema:
    """Test LeadResponseSchema"""
    
    def test_lead_response_schema_creation(self):
        """Test creating lead response schema"""
        data = {
            "id": "test-id",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "email": "test@example.com",
            "domain": "example.com",
            "company_name": "Test Corp",
            "contact_name": "John Doe",
            "enrichment_status": "pending",
            "enrichment_task_id": None,
            "enrichment_error": None,
            "is_manual": True,
            "source": "manual",
            "is_deleted": False,
            "deleted_at": None,
            "created_by": None,
            "updated_by": None,
            "deleted_by": None
        }
        
        schema = LeadResponseSchema(**data)
        
        assert schema.id == "test-id"
        assert schema.email == "test@example.com"
        assert schema.enrichment_status == "pending"
        assert schema.is_manual is True


class TestQuickAddResponseSchema:
    """Test QuickAddResponseSchema"""
    
    def test_quick_add_response_schema_creation(self):
        """Test creating quick-add response schema"""
        lead_data = {
            "id": "test-id",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "email": "test@example.com",
            "domain": "example.com",
            "company_name": "Test Corp",
            "contact_name": "John Doe",
            "enrichment_status": "in_progress",
            "enrichment_task_id": "task-123",
            "enrichment_error": None,
            "is_manual": True,
            "source": "quick_add",
            "is_deleted": False,
            "deleted_at": None,
            "created_by": None,
            "updated_by": None,
            "deleted_by": None
        }
        
        data = {
            "lead": LeadResponseSchema(**lead_data),
            "enrichment_task_id": "task-123",
            "message": "Lead created and enrichment started"
        }
        
        schema = QuickAddResponseSchema(**data)
        
        assert schema.enrichment_task_id == "task-123"
        assert schema.message == "Lead created and enrichment started"
        assert schema.lead.email == "test@example.com"


class TestLeadListResponseSchema:
    """Test LeadListResponseSchema"""
    
    def test_lead_list_response_schema_creation(self):
        """Test creating lead list response schema"""
        lead_data = {
            "id": "test-id",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "email": "test@example.com",
            "domain": "example.com",
            "company_name": "Test Corp",
            "contact_name": "John Doe",
            "enrichment_status": "pending",
            "enrichment_task_id": None,
            "enrichment_error": None,
            "is_manual": True,
            "source": "manual",
            "is_deleted": False,
            "deleted_at": None,
            "created_by": None,
            "updated_by": None,
            "deleted_by": None
        }
        
        data = {
            "leads": [LeadResponseSchema(**lead_data)],
            "total_count": 1,
            "page_info": {
                "current_page": 1,
                "total_pages": 1,
                "page_size": 100,
                "has_next": False,
                "has_previous": False
            }
        }
        
        schema = LeadListResponseSchema(**data)
        
        assert len(schema.leads) == 1
        assert schema.total_count == 1
        assert schema.page_info["current_page"] == 1


class TestAuditSchemas:
    """Test audit-related schemas"""
    
    def test_audit_log_response_schema_creation(self):
        """Test creating audit log response schema"""
        data = {
            "id": "audit-id",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "lead_id": "lead-id",
            "action": "create",
            "timestamp": datetime.utcnow(),
            "user_id": "user-123",
            "user_ip": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "old_values": None,
            "new_values": {"email": "test@example.com"},
            "checksum": "abc123"
        }
        
        schema = AuditLogResponseSchema(**data)
        
        assert schema.lead_id == "lead-id"
        assert schema.action == "create"
        assert schema.user_id == "user-123"
        assert schema.checksum == "abc123"
    
    def test_audit_trail_response_schema_creation(self):
        """Test creating audit trail response schema"""
        audit_data = {
            "id": "audit-id",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "lead_id": "lead-id",
            "action": "create",
            "timestamp": datetime.utcnow(),
            "user_id": "user-123",
            "user_ip": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "old_values": None,
            "new_values": {"email": "test@example.com"},
            "checksum": "abc123"
        }
        
        data = {
            "lead_id": "lead-id",
            "audit_logs": [AuditLogResponseSchema(**audit_data)],
            "total_count": 1
        }
        
        schema = AuditTrailResponseSchema(**data)
        
        assert schema.lead_id == "lead-id"
        assert len(schema.audit_logs) == 1
        assert schema.total_count == 1


class TestErrorSchemas:
    """Test error response schemas"""
    
    def test_error_response_schema_creation(self):
        """Test creating error response schema"""
        data = {
            "error": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": {"field": "email", "issue": "invalid format"}
        }
        
        schema = ErrorResponseSchema(**data)
        
        assert schema.error == "VALIDATION_ERROR"
        assert schema.message == "Invalid input data"
        assert schema.details["field"] == "email"
    
    def test_validation_error_schema_creation(self):
        """Test creating validation error response schema"""
        data = {
            "error": "VALIDATION_ERROR",
            "message": "Input validation failed",
            "validation_errors": [
                {"field": "email", "message": "Invalid email format"},
                {"field": "domain", "message": "Domain required"}
            ]
        }
        
        schema = ValidationErrorSchema(**data)
        
        assert schema.error == "VALIDATION_ERROR"
        assert schema.message == "Input validation failed"
        assert len(schema.validation_errors) == 2


class TestHealthCheckResponseSchema:
    """Test HealthCheckResponseSchema"""
    
    def test_health_check_response_schema_creation(self):
        """Test creating health check response schema"""
        data = {
            "status": "ok",
            "timestamp": datetime.utcnow(),
            "database": "connected",
            "message": "Lead Explorer is healthy"
        }
        
        schema = HealthCheckResponseSchema(**data)
        
        assert schema.status == "ok"
        assert schema.database == "connected"
        assert schema.message == "Lead Explorer is healthy"
    
    def test_health_check_response_schema_defaults(self):
        """Test health check response schema with defaults"""
        data = {"timestamp": datetime.utcnow()}
        
        schema = HealthCheckResponseSchema(**data)
        
        assert schema.status == "ok"
        assert schema.database == "connected"
        assert schema.message == "Lead Explorer is healthy"


class TestEnrichmentStatusEnum:
    """Test EnrichmentStatusEnum"""
    
    def test_enrichment_status_enum_values(self):
        """Test all enum values"""
        assert EnrichmentStatusEnum.PENDING.value == "pending"
        assert EnrichmentStatusEnum.IN_PROGRESS.value == "in_progress"
        assert EnrichmentStatusEnum.COMPLETED.value == "completed"
        assert EnrichmentStatusEnum.FAILED.value == "failed"
    
    def test_enrichment_status_enum_from_string(self):
        """Test creating enum from string values"""
        assert EnrichmentStatusEnum("pending") == EnrichmentStatusEnum.PENDING
        assert EnrichmentStatusEnum("in_progress") == EnrichmentStatusEnum.IN_PROGRESS
        assert EnrichmentStatusEnum("completed") == EnrichmentStatusEnum.COMPLETED
        assert EnrichmentStatusEnum("failed") == EnrichmentStatusEnum.FAILED
    
    def test_enrichment_status_enum_invalid_value(self):
        """Test creating enum with invalid value"""
        with pytest.raises(ValueError):
            EnrichmentStatusEnum("invalid_status")