"""
Test Lead Explorer API endpoints
"""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.models import EnrichmentStatus
from lead_explorer.api import router


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

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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
                "source": "manual",
            },
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
        response = client.post("/api/v1/lead-explorer/leads", json={"company_name": "Test Corp", "is_manual": True})

        assert response.status_code == 422

    def test_create_lead_invalid_email(self, client):
        """Test validation error for invalid email"""
        response = client.post("/api/v1/lead-explorer/leads", json={"email": "invalid-email", "is_manual": True})

        assert response.status_code == 422

    def test_create_lead_invalid_domain(self, client):
        """Test validation error for invalid domain"""
        response = client.post("/api/v1/lead-explorer/leads", json={"domain": "invalid-domain", "is_manual": True})

        assert response.status_code == 422


class TestListLeadsAPI:
    """Test GET /leads endpoint"""

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
    def test_list_leads_with_filters(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test lead listing with filters"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.list_leads.return_value = ([], 0)

        # Make request with filters
        response = client.get(
            "/api/v1/lead-explorer/leads", params={"is_manual": True, "enrichment_status": "pending", "search": "test"}
        )

        # Verify response
        assert response.status_code == 200

        # Verify repository was called with filters
        mock_lead_repo.list_leads.assert_called_once()

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
    def test_list_leads_pagination(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test lead listing with pagination"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.list_leads.return_value = ([], 0)

        # Make request with pagination
        response = client.get(
            "/api/v1/lead-explorer/leads",
            params={"skip": 10, "limit": 5, "sort_by": "created_at", "sort_order": "desc"},
        )

        # Verify response
        assert response.status_code == 200


class TestGetLeadAPI:
    """Test GET /leads/{lead_id} endpoint"""

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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
            "/api/v1/lead-explorer/leads/test-id", json={"email": "updated@example.com", "company_name": "Updated Corp"}
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        assert data["company_name"] == "Updated Corp"

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
    def test_update_lead_not_found(self, mock_repo_class, mock_get_db, client, mock_lead_repo):
        """Test updating non-existent lead"""
        # Setup mocks
        mock_get_db.return_value.__enter__.return_value = Mock()
        mock_repo_class.return_value = mock_lead_repo
        mock_lead_repo.update_lead.return_value = None

        # Make request
        response = client.put("/api/v1/lead-explorer/leads/non-existent", json={"company_name": "Updated Corp"})

        # Verify response
        assert response.status_code == 404


class TestDeleteLeadAPI:
    """Test DELETE /leads/{lead_id} endpoint"""

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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

    @patch("sqlalchemy.orm.session.Session.refresh")
    @patch("lead_explorer.api.get_enrichment_coordinator")
    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
    async def test_quick_add_lead_success(
        self, mock_repo_class, mock_get_db, mock_get_coordinator, mock_session_refresh, client, mock_lead_repo
    ):
        """Test successful quick-add lead"""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_repo_class.return_value = mock_lead_repo

        # Mock the session refresh to do nothing
        mock_session_refresh.return_value = None

        # Create a mock lead object
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
            json={"email": "test@example.com", "domain": "example.com", "company_name": "Test Corp"},
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["enrichment_task_id"] == "task-123"
        assert data["message"] == "Lead created and enrichment started"
        assert data["lead"]["email"] == "test@example.com"


class TestHealthCheckAPI:
    """Test GET /health endpoint"""

    def test_health_check_success(self, client, app):
        """Test successful health check"""
        from lead_explorer.api import get_db

        # Create a mock session with the expected behavior
        mock_session = Mock()

        # Mock execute for SELECT 1
        mock_session.execute.return_value = Mock()

        # Mock the query chain for total leads count
        mock_query = Mock()
        mock_filter1 = Mock()
        mock_filter1.count.return_value = 10  # total leads

        # Mock the query chain for manual leads count
        mock_filter2 = Mock()
        mock_filter2.count.return_value = 5  # manual leads

        # Set up query to return different filters on consecutive calls
        mock_query.filter.side_effect = [mock_filter1, mock_filter2]
        mock_session.query.return_value = mock_query

        # Override the dependency
        app.dependency_overrides[get_db] = lambda: mock_session

        # Make request
        response = client.get("/api/v1/lead-explorer/health")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert "timestamp" in data
        assert "message" in data
        assert "10 total leads" in data["message"]
        assert "5 manual" in data["message"]

        # Clean up
        app.dependency_overrides.clear()

    def test_health_check_database_error(self, client, app):
        """Test health check with database error"""
        from lead_explorer.api import get_db

        # Create a mock session that raises an error
        mock_session = Mock()
        mock_session.execute.side_effect = Exception("Database connection failed")

        # Override the dependency
        app.dependency_overrides[get_db] = lambda: mock_session

        # Make request
        response = client.get("/api/v1/lead-explorer/health")

        # Verify response
        assert response.status_code == 503

        # Clean up
        app.dependency_overrides.clear()


class TestAuditTrailAPI:
    """Test GET /leads/{lead_id}/audit-trail endpoint"""

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
    @patch("lead_explorer.api.AuditRepository")
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
        mock_audit_log.lead_id = "test-id"
        mock_audit_log.action = "create"  # lowercase for enum
        mock_audit_log.timestamp = datetime(2023, 1, 1, 0, 0, 0)
        mock_audit_log.created_at = datetime(2023, 1, 1, 0, 0, 0)
        mock_audit_log.updated_at = datetime(2023, 1, 1, 0, 0, 0)
        mock_audit_log.user_id = "test-user"
        mock_audit_log.user_ip = "127.0.0.1"
        mock_audit_log.user_agent = "test-agent"
        mock_audit_log.old_values = {}
        mock_audit_log.new_values = {"email": "test@example.com"}
        mock_audit_log.checksum = "abc123"
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

    @patch("lead_explorer.api.get_db")
    @patch("lead_explorer.api.LeadRepository")
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
