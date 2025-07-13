"""
Test Lead Explorer API endpoints
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from lead_explorer.api import router
from database.models import EnrichmentStatus


@pytest.fixture
def app():
    """Create FastAPI app for testing"""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/lead-explorer")
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def mock_lead_repo():
    """Mock lead repository"""
    return Mock()


@pytest.fixture
def mock_audit_repo():
    """Mock audit repository"""
    return Mock()


class TestCreateLeadAPI:
    """Test POST /leads endpoint"""
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_create_lead_success(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test successful lead creation"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead.email = "test@example.com"
        mock_lead.domain = "example.com"
        mock_lead.company_name = "Test Corp"
        mock_lead.contact_name = "John Doe"
        mock_lead.is_manual = True
        mock_lead.source = "manual"
        mock_lead.enrichment_status = EnrichmentStatus.PENDING
        mock_lead.enrichment_task_id = None
        mock_lead.enrichment_error = None
        mock_lead.is_deleted = False
        mock_lead.deleted_at = None
        mock_lead.created_by = None
        mock_lead.updated_by = None
        mock_lead.deleted_by = None
        mock_lead.created_at = "2023-01-01T00:00:00"
        mock_lead.updated_at = "2023-01-01T00:00:00"
        
        mock_lead_repo.create_lead.return_value = mock_lead
        
        # Make request
        response = client.post(
            "/api/v1/lead-explorer/leads",
            json={
                "email": "test@example.com",
                "domain": "example.com",
                "company_name": "Test Corp",
                "contact_name": "John Doe",
                "is_manual": True,
                "source": "manual"
            }
        )
        
        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["domain"] == "example.com"
        assert data["company_name"] == "Test Corp"
        
        # Verify repository was called
        mock_lead_repo.create_lead.assert_called_once()
    
    def test_create_lead_validation_error(self, client):
        """Test validation error when no email or domain provided"""
        response = client.post(
            "/api/v1/lead-explorer/leads",
            json={
                "company_name": "Test Corp",
                "is_manual": True
            }
        )
        
        assert response.status_code == 422
    
    def test_create_lead_invalid_email(self, client):
        """Test validation error for invalid email"""
        response = client.post(
            "/api/v1/lead-explorer/leads",
            json={
                "email": "invalid-email",
                "is_manual": True
            }
        )
        
        assert response.status_code == 422
    
    def test_create_lead_invalid_domain(self, client):
        """Test validation error for invalid domain"""
        response = client.post(
            "/api/v1/lead-explorer/leads",
            json={
                "domain": "invalid-domain",
                "is_manual": True
            }
        )
        
        assert response.status_code == 422


class TestListLeadsAPI:
    """Test GET /leads endpoint"""
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_list_leads_success(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test successful lead listing"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead.email = "test@example.com"
        mock_lead.domain = "example.com"
        mock_lead.company_name = "Test Corp"
        mock_lead.contact_name = "John Doe"
        mock_lead.is_manual = True
        mock_lead.source = "manual"
        mock_lead.enrichment_status = EnrichmentStatus.PENDING
        mock_lead.enrichment_task_id = None
        mock_lead.enrichment_error = None
        mock_lead.is_deleted = False
        mock_lead.deleted_at = None
        mock_lead.created_by = None
        mock_lead.updated_by = None
        mock_lead.deleted_by = None
        mock_lead.created_at = "2023-01-01T00:00:00"
        mock_lead.updated_at = "2023-01-01T00:00:00"
        
        mock_lead_repo.list_leads.return_value = ([mock_lead], 1)
        
        # Make request
        response = client.get("/api/v1/lead-explorer/leads")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["leads"]) == 1
        assert data["leads"][0]["email"] == "test@example.com"
        assert "page_info" in data
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_list_leads_with_filters(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test lead listing with filters"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.list_leads.return_value = ([], 0)
        
        # Make request with filters
        response = client.get(
            "/api/v1/lead-explorer/leads",
            params={
                "is_manual": True,
                "enrichment_status": "pending",
                "search": "test"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify repository was called with filters
        mock_lead_repo.list_leads.assert_called_once()
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_list_leads_pagination(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test lead listing with pagination"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.list_leads.return_value = ([], 0)
        
        # Make request with pagination
        response = client.get(
            "/api/v1/lead-explorer/leads",
            params={
                "skip": 10,
                "limit": 5,
                "sort_by": "created_at",
                "sort_order": "desc"
            }
        )
        
        # Verify response
        assert response.status_code == 200


class TestGetLeadAPI:
    """Test GET /leads/{lead_id} endpoint"""
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_get_lead_success(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test successful lead retrieval"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead.email = "test@example.com"
        mock_lead.domain = "example.com"
        mock_lead.company_name = "Test Corp"
        mock_lead.contact_name = "John Doe"
        mock_lead.is_manual = True
        mock_lead.source = "manual"
        mock_lead.enrichment_status = EnrichmentStatus.PENDING
        mock_lead.enrichment_task_id = None
        mock_lead.enrichment_error = None
        mock_lead.is_deleted = False
        mock_lead.deleted_at = None
        mock_lead.created_by = None
        mock_lead.updated_by = None
        mock_lead.deleted_by = None
        mock_lead.created_at = "2023-01-01T00:00:00"
        mock_lead.updated_at = "2023-01-01T00:00:00"
        
        mock_lead_repo.get_lead_by_id.return_value = mock_lead
        
        # Make request
        response = client.get("/api/v1/lead-explorer/leads/test-id")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
        assert data["email"] == "test@example.com"
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_get_lead_not_found(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test lead not found"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.get_lead_by_id.return_value = None
        
        # Make request
        response = client.get("/api/v1/lead-explorer/leads/non-existent")
        
        # Verify response
        assert response.status_code == 404


class TestUpdateLeadAPI:
    """Test PUT /leads/{lead_id} endpoint"""
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_update_lead_success(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test successful lead update"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead.email = "updated@example.com"
        mock_lead.domain = "example.com"
        mock_lead.company_name = "Updated Corp"
        mock_lead.contact_name = "John Doe"
        mock_lead.is_manual = True
        mock_lead.source = "manual"
        mock_lead.enrichment_status = EnrichmentStatus.PENDING
        mock_lead.enrichment_task_id = None
        mock_lead.enrichment_error = None
        mock_lead.is_deleted = False
        mock_lead.deleted_at = None
        mock_lead.created_by = None
        mock_lead.updated_by = "test_user"
        mock_lead.deleted_by = None
        mock_lead.created_at = "2023-01-01T00:00:00"
        mock_lead.updated_at = "2023-01-01T00:00:00"
        
        mock_lead_repo.update_lead.return_value = mock_lead
        
        # Make request
        response = client.put(
            "/api/v1/lead-explorer/leads/test-id",
            json={
                "email": "updated@example.com",
                "company_name": "Updated Corp"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        assert data["company_name"] == "Updated Corp"
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_update_lead_not_found(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test updating non-existent lead"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.update_lead.return_value = None
        
        # Make request
        response = client.put(
            "/api/v1/lead-explorer/leads/non-existent",
            json={"company_name": "Updated Corp"}
        )
        
        # Verify response
        assert response.status_code == 404


class TestDeleteLeadAPI:
    """Test DELETE /leads/{lead_id} endpoint"""
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_delete_lead_success(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test successful lead deletion"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead.email = "test@example.com"
        mock_lead.domain = "example.com"
        mock_lead.company_name = "Test Corp"
        mock_lead.contact_name = "John Doe"
        mock_lead.is_manual = True
        mock_lead.source = "manual"
        mock_lead.enrichment_status = EnrichmentStatus.PENDING
        mock_lead.enrichment_task_id = None
        mock_lead.enrichment_error = None
        mock_lead.is_deleted = False
        mock_lead.deleted_at = None
        mock_lead.created_by = None
        mock_lead.updated_by = None
        mock_lead.deleted_by = None
        mock_lead.created_at = "2023-01-01T00:00:00"
        mock_lead.updated_at = "2023-01-01T00:00:00"
        
        mock_lead_repo.get_lead_by_id.return_value = mock_lead
        mock_lead_repo.soft_delete_lead.return_value = True
        
        # Make request
        response = client.delete("/api/v1/lead-explorer/leads/test-id")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_delete_lead_not_found(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test deleting non-existent lead"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.get_lead_by_id.return_value = None
        
        # Make request
        response = client.delete("/api/v1/lead-explorer/leads/non-existent")
        
        # Verify response
        assert response.status_code == 404


class TestQuickAddLeadAPI:
    """Test POST /leads/quick-add endpoint"""
    
    @patch('lead_explorer.api.get_enrichment_coordinator')
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    async def test_quick_add_lead_success(self, mock_repo_class, mock_get_db, mock_get_coordinator, client, mock_lead_repo):
        """Test successful quick-add lead"""
        # Setup mocks
        mock_db = Mock()
        mock_db.refresh = Mock()  # Mock the refresh method to do nothing
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_repo_class.return_value = mock_lead_repo
        
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead.email = "test@example.com"
        mock_lead.domain = "example.com"
        mock_lead.company_name = "Test Corp"
        mock_lead.contact_name = "John Doe"
        mock_lead.is_manual = True
        mock_lead.source = "quick_add"
        mock_lead.enrichment_status = EnrichmentStatus.IN_PROGRESS
        mock_lead.enrichment_task_id = "task-123"
        mock_lead.enrichment_error = None
        mock_lead.is_deleted = False
        mock_lead.deleted_at = None
        mock_lead.created_by = None
        mock_lead.updated_by = None
        mock_lead.deleted_by = None
        mock_lead.created_at = "2023-01-01T00:00:00"
        mock_lead.updated_at = "2023-01-01T00:00:00"
        
        mock_lead_repo.create_lead.return_value = mock_lead
        
        mock_coordinator = AsyncMock()
        mock_coordinator.start_enrichment.return_value = "task-123"
        mock_get_coordinator.return_value = mock_coordinator
        
        # Make request
        response = client.post(
            "/api/v1/lead-explorer/leads/quick-add",
            json={
                "email": "test@example.com",
                "domain": "example.com",
                "company_name": "Test Corp"
            }
        )
        
        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["enrichment_task_id"] == "task-123"
        assert data["message"] == "Lead created and enrichment started"
        assert data["lead"]["email"] == "test@example.com"


class TestHealthCheckAPI:
    """Test GET /health endpoint"""
    
    @patch('lead_explorer.api.get_db')
    def test_health_check_success(self, mock_get_db, client):
        """Test successful health check"""
        # Setup mocks
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_get_db.return_value.__enter__.return_value = mock_db
        
        # Make request
        response = client.get("/api/v1/lead-explorer/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert "timestamp" in data
        assert "message" in data
    
    @patch('lead_explorer.api.get_db')
    def test_health_check_database_error(self, mock_get_db, client):
        """Test health check with database error"""
        # Setup mocks to raise exception
        mock_db = Mock()
        mock_db.execute.side_effect = Exception("Database error")
        mock_get_db.return_value.__enter__.return_value = mock_db
        
        # Make request
        response = client.get("/api/v1/lead-explorer/health")
        
        # Verify response
        assert response.status_code == 503


class TestAuditTrailAPI:
    """Test GET /leads/{lead_id}/audit-trail endpoint"""
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    @patch('lead_explorer.api.AuditRepository')
    def test_get_audit_trail_success(self, mock_audit_repo_class, mock_lead_repo_class, mock_get_db, client):
        """Test successful audit trail retrieval"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        
        mock_lead_repo = Mock()
        mock_lead = Mock()
        mock_lead.id = "test-id"
        mock_lead_repo.get_lead_by_id.return_value = mock_lead
        mock_lead_repo_class.return_value = mock_lead_repo
        
        mock_audit_repo = Mock()
        mock_audit_log = Mock()
        mock_audit_log.id = "audit-id"
        mock_audit_log.action = "CREATE"
        mock_audit_log.timestamp = "2023-01-01T00:00:00"
        mock_audit_repo.get_audit_trail.return_value = [mock_audit_log]
        mock_audit_repo_class.return_value = mock_audit_repo
        
        # Make request
        response = client.get("/api/v1/lead-explorer/leads/test-id/audit-trail")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == "test-id"
        assert data["total_count"] == 1
        assert len(data["audit_logs"]) == 1
    
    @patch('lead_explorer.api.get_db')
    @patch('lead_explorer.api.LeadRepository')
    def test_get_audit_trail_lead_not_found(self, mock_repo_class, mock_get_db, client):
        """Test audit trail for non-existent lead"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo = Mock()
        mock_repo.get_lead_by_id.return_value = None
        mock_repo_class.return_value = mock_repo
        
        # Make request
        response = client.get("/api/v1/lead-explorer/leads/non-existent/audit-trail")
        
        # Verify response
        assert response.status_code == 404