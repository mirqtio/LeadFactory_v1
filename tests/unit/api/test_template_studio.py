"""
Unit tests for Template Studio API
"""

import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from api.template_studio import router, TemplateManager


class TestTemplateStudioAPI:
    """Test suite for Template Studio API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client with the router"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    
    @pytest.fixture
    def mock_manager(self):
        """Create mock template manager"""
        manager = Mock(spec=TemplateManager)
        return manager
    
    def test_list_templates(self, client, mock_manager):
        """Test listing templates endpoint"""
        mock_templates = [
            {
                "name": "template1.html",
                "path": "/path/to/template1.html",
                "size": 1024,
                "modified": "2024-01-01T12:00:00",
                "git": {
                    "sha": "abc123",
                    "author": "Test User",
                    "date": "2024-01-01T10:00:00",
                    "message": "Initial commit",
                },
                "checksum": "checksum123",
            }
        ]
        
        mock_manager.list_templates.return_value = mock_templates
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.get("/api/template-studio/templates")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "template1.html"
        assert data[0]["git"]["sha"] == "abc123"
    
    def test_get_template_content(self, client, mock_manager):
        """Test getting template content"""
        mock_manager.get_template_content.return_value = "<h1>{{ title }}</h1>"
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.get("/api/template-studio/templates/test.html")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test.html"
        assert data["content"] == "<h1>{{ title }}</h1>"
    
    def test_get_template_not_found(self, client, mock_manager):
        """Test getting non-existent template"""
        mock_manager.get_template_content.return_value = None
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.get("/api/template-studio/templates/missing.html")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Template not found"
    
    def test_validate_template_valid(self, client, mock_manager):
        """Test validating a valid template"""
        mock_manager.validate_template.return_value = {
            "valid": True,
            "variables": ["title", "content"],
            "errors": [],
        }
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/validate",
                json={"content": "<h1>{{ title }}</h1>"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "title" in data["variables"]
        assert len(data["errors"]) == 0
    
    def test_validate_template_invalid(self, client, mock_manager):
        """Test validating an invalid template"""
        mock_manager.validate_template.return_value = {
            "valid": False,
            "variables": [],
            "errors": ["Unexpected end of template"],
        }
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/validate",
                json={"content": "{% if true %}"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
    
    def test_preview_template_success(self, client, mock_manager):
        """Test successful template preview"""
        mock_manager.render_preview.return_value = {
            "success": True,
            "content": "<h1>Test Company</h1>",
            "error": None,
        }
        mock_manager.get_sample_lead_data.return_value = {"test": "data"}
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/preview",
                json={"template_name": "test.html"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content"] == "<h1>Test Company</h1>"
        assert data["error"] is None
    
    def test_preview_template_timeout(self, client, mock_manager):
        """Test template preview timeout"""
        import asyncio
        
        async def slow_render(*args, **kwargs):
            await asyncio.sleep(1)  # Simulate slow rendering
            return {"success": True, "content": "Too slow", "error": None}
        
        mock_manager.render_preview = Mock(side_effect=slow_render)
        mock_manager.get_sample_lead_data.return_value = {"test": "data"}
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/preview",
                json={"template_name": "test.html"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "timeout" in data["error"].lower()
    
    def test_create_pr_success(self, client, mock_manager):
        """Test successful PR creation"""
        mock_manager.validate_template.return_value = {
            "valid": True,
            "variables": [],
            "errors": [],
        }
        
        mock_manager.create_template_pr.return_value = {
            "success": True,
            "error": None,
            "pr_url": "https://github.com/user/repo/pull/123",
            "pr_number": 123,
        }
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/create-pr",
                json={
                    "changes": {"test.html": "<h1>New content</h1>"},
                    "user": "testuser",
                    "commit_message": "Update test template",
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["pr_url"] == "https://github.com/user/repo/pull/123"
        assert data["pr_number"] == 123
    
    def test_create_pr_invalid_template(self, client, mock_manager):
        """Test PR creation with invalid template"""
        mock_manager.validate_template.return_value = {
            "valid": False,
            "variables": [],
            "errors": ["Syntax error"],
        }
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/create-pr",
                json={
                    "changes": {"test.html": "{% if invalid"},
                    "user": "testuser",
                    "commit_message": "Bad template",
                }
            )
        
        assert response.status_code == 400
        assert "Invalid template" in response.json()["detail"]
    
    def test_create_pr_github_error(self, client, mock_manager):
        """Test PR creation with GitHub error"""
        mock_manager.validate_template.return_value = {
            "valid": True,
            "variables": [],
            "errors": [],
        }
        
        mock_manager.create_template_pr.return_value = {
            "success": False,
            "error": "GitHub API rate limit exceeded",
            "pr_url": None,
        }
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.post(
                "/api/template-studio/create-pr",
                json={
                    "changes": {"test.html": "<h1>New</h1>"},
                    "user": "testuser",
                    "commit_message": "Update",
                }
            )
        
        assert response.status_code == 500
        assert "GitHub API rate limit" in response.json()["detail"]
    
    def test_get_sample_data(self, client, mock_manager):
        """Test getting sample lead data"""
        mock_data = {
            "business": {"name": "Test Company"},
            "assessment": {"score": 90},
        }
        
        mock_manager.get_sample_lead_data.return_value = mock_data
        
        with patch("api.template_studio.get_template_manager", return_value=mock_manager):
            response = client.get("/api/template-studio/sample-data/1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["business"]["name"] == "Test Company"
        assert data["assessment"]["score"] == 90
    
    def test_template_studio_ui(self, client):
        """Test that UI endpoint returns HTML"""
        response = client.get("/api/template-studio/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Template Studio" in response.text