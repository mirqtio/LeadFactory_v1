"""
Performance tests for Lead Explorer API

Validates response time requirements (<500ms)
"""
import time
import pytest
from fastapi.testclient import TestClient

from main import app
from database.session import SessionLocal
from lead_explorer.repository import LeadRepository


class TestLeadExplorerPerformance:
    """Performance tests for Lead Explorer endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        """Create database session"""
        session = SessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def sample_lead(self, db_session):
        """Create a sample lead for testing"""
        repo = LeadRepository(db_session)
        
        # Try to find existing lead first
        existing_lead = db_session.query(Lead).filter_by(email="perf-test@example.com").first()
        if existing_lead:
            yield existing_lead
            return
            
        # Create new lead with unique email/domain
        unique_suffix = str(int(time.time() * 1000))
        lead = repo.create_lead(
            email=f"perf-test-{unique_suffix}@example.com",
            domain=f"perf-test-{unique_suffix}.example.com",
            company_name="Performance Test Corp"
        )
        db_session.commit()
        yield lead
        # Cleanup
        try:
            db_session.delete(lead)
            db_session.commit()
        except Exception:
            db_session.rollback()
    
    def test_create_lead_performance(self, client):
        """Test POST /leads response time < 500ms"""
        data = {
            "email": f"test-{time.time()}@example.com",
            "domain": "example.com",
            "company_name": "Test Company"
        }
        
        start_time = time.time()
        response = client.post("/api/v1/leads", json=data)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code in [201, 422]  # 422 if duplicate
        assert response_time_ms < 500, f"Response time {response_time_ms:.2f}ms exceeds 500ms limit"
    
    def test_get_lead_performance(self, client, sample_lead):
        """Test GET /leads/{id} response time < 500ms"""
        start_time = time.time()
        response = client.get(f"/api/v1/leads/{sample_lead.id}")
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time_ms < 500, f"Response time {response_time_ms:.2f}ms exceeds 500ms limit"
    
    def test_list_leads_performance(self, client):
        """Test GET /leads response time < 500ms"""
        start_time = time.time()
        response = client.get("/api/v1/leads?limit=100")
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time_ms < 500, f"Response time {response_time_ms:.2f}ms exceeds 500ms limit"
    
    def test_update_lead_performance(self, client, sample_lead):
        """Test PUT /leads/{id} response time < 500ms"""
        data = {"company_name": "Updated Company"}
        
        start_time = time.time()
        response = client.put(f"/api/v1/leads/{sample_lead.id}", json=data)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time_ms < 500, f"Response time {response_time_ms:.2f}ms exceeds 500ms limit"
    
    def test_delete_lead_performance(self, client, sample_lead):
        """Test DELETE /leads/{id} response time < 500ms"""
        start_time = time.time()
        response = client.delete(f"/api/v1/leads/{sample_lead.id}")
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time_ms < 500, f"Response time {response_time_ms:.2f}ms exceeds 500ms limit"
    
    @pytest.mark.parametrize("page_size", [10, 50, 100])
    def test_pagination_performance(self, client, page_size):
        """Test pagination performance with different page sizes"""
        start_time = time.time()
        response = client.get(f"/api/v1/leads?limit={page_size}")
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time_ms < 500, f"Response time {response_time_ms:.2f}ms exceeds 500ms for page_size={page_size}"