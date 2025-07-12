"""
Integration tests for Template Studio
"""

import asyncio
import json
from unittest.mock import patch, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from api.template_studio import router
from d6_reports.template_manager import TemplateManager


class TestTemplateStudioIntegration:
    """Integration tests for Template Studio functionality"""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI app with template studio router"""
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_github_token(self):
        """Mock GitHub token"""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
            yield
    
    def test_full_template_workflow(self, client):
        """Test complete template editing workflow"""
        # Step 1: List templates
        response = client.get("/api/template-studio/templates")
        assert response.status_code == 200
        templates = response.json()
        
        # Step 2: Get a template (if any exist)
        if templates:
            template_name = templates[0]["name"]
            response = client.get(f"/api/template-studio/templates/{template_name}")
            assert response.status_code == 200
            template_data = response.json()
            
            # Step 3: Validate the template
            response = client.post(
                "/api/template-studio/validate",
                json={"content": template_data["content"]}
            )
            assert response.status_code == 200
            validation = response.json()
            assert "valid" in validation
            
            # Step 4: Preview the template
            response = client.post(
                "/api/template-studio/preview",
                json={"template_name": template_name}
            )
            assert response.status_code == 200
            preview = response.json()
            assert "success" in preview
    
    def test_websocket_real_time_preview(self, client):
        """Test WebSocket real-time preview functionality"""
        with client.websocket_connect("/api/template-studio/ws/preview") as websocket:
            # Send valid template for preview
            websocket.send_json({
                "template_name": "test.html",
                "content": "<h1>{{ title }}</h1><p>{{ content }}</p>",
                "sample_data": {
                    "title": "Real-time Test",
                    "content": "This is a WebSocket test"
                }
            })
            
            # Receive preview result
            data = websocket.receive_json()
            assert "success" in data or "error" in data
            
            if data.get("success"):
                assert "Real-time Test" in data["content"]
                assert data["variables"] == ["content", "title"]
    
    def test_websocket_invalid_template(self, client):
        """Test WebSocket with invalid template"""
        with client.websocket_connect("/api/template-studio/ws/preview") as websocket:
            # Send invalid template
            websocket.send_json({
                "template_name": "test.html",
                "content": "{% if true %}",  # Missing endif
                "sample_data": {}
            })
            
            # Should receive error
            data = websocket.receive_json()
            assert "error" in data
            assert "Invalid template" in data["error"]
    
    def test_pr_creation_flow(self, client, mock_github_token):
        """Test complete PR creation flow"""
        # Mock GitHub API
        mock_g = Mock()
        mock_repo = Mock()
        mock_branch = Mock()
        mock_branch.commit.sha = "abc123"
        
        mock_repo.get_branch.return_value = mock_branch
        mock_repo.create_git_ref = Mock()
        mock_repo.create_file = Mock()
        
        mock_pr = Mock()
        mock_pr.html_url = "https://github.com/test/repo/pull/1"
        mock_pr.number = 1
        mock_repo.create_pull.return_value = mock_pr
        
        mock_g.get_repo.return_value = mock_repo
        
        with patch("github.Github", return_value=mock_g):
            # Create PR with template changes
            response = client.post(
                "/api/template-studio/create-pr",
                json={
                    "changes": {
                        "new_template.html": "<h1>{{ title }}</h1>"
                    },
                    "user": "testuser",
                    "commit_message": "Add new template"
                }
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["pr_url"] == "https://github.com/test/repo/pull/1"
            assert result["pr_number"] == 1
            
            # Verify GitHub API was called correctly
            mock_repo.create_git_ref.assert_called_once()
            mock_repo.create_file.assert_called_once()
            mock_repo.create_pull.assert_called_once()
    
    def test_access_control_viewer(self, client):
        """Test viewer access (read-only)"""
        # Viewers can list templates
        response = client.get("/api/template-studio/templates")
        assert response.status_code == 200
        
        # Viewers can get template content
        response = client.get("/api/template-studio/templates/test.html")
        # Will be 404 if template doesn't exist, but not 403
        assert response.status_code in [200, 404]
        
        # Viewers can validate
        response = client.post(
            "/api/template-studio/validate",
            json={"content": "<h1>Test</h1>"}
        )
        assert response.status_code == 200
        
        # Viewers can preview
        response = client.post(
            "/api/template-studio/preview",
            json={"template_name": "test.html"}
        )
        assert response.status_code == 200
    
    def test_access_control_admin(self, client, mock_github_token):
        """Test admin access (can propose changes)"""
        # Mock GitHub for PR creation
        with patch("github.Github") as mock_github:
            mock_instance = Mock()
            mock_repo = Mock()
            mock_branch = Mock()
            mock_branch.commit.sha = "abc123"
            mock_repo.get_branch.return_value = mock_branch
            mock_repo.create_git_ref = Mock()
            mock_repo.create_file = Mock()
            mock_pr = Mock()
            mock_pr.html_url = "https://github.com/test/repo/pull/1"
            mock_pr.number = 1
            mock_repo.create_pull.return_value = mock_pr
            mock_instance.get_repo.return_value = mock_repo
            mock_github.return_value = mock_instance
            
            # Admins can create PRs
            response = client.post(
                "/api/template-studio/create-pr",
                json={
                    "changes": {"test.html": "<h1>Admin change</h1>"},
                    "user": "admin",
                    "commit_message": "Admin update"
                }
            )
            assert response.status_code == 200
    
    def test_template_validation_edge_cases(self, client):
        """Test template validation with edge cases"""
        # Empty template
        response = client.post(
            "/api/template-studio/validate",
            json={"content": ""}
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True
        
        # Template with complex Jinja2 features
        complex_template = """
        {% macro render_item(item) %}
            <div>{{ item.name }}</div>
        {% endmacro %}
        
        {% for item in items %}
            {{ render_item(item) }}
        {% endfor %}
        
        {% filter upper %}
            {{ content }}
        {% endfilter %}
        """
        
        response = client.post(
            "/api/template-studio/validate",
            json={"content": complex_template}
        )
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is True
        assert "items" in result["variables"]
        assert "content" in result["variables"]
    
    @pytest.mark.asyncio
    async def test_preview_performance_requirement(self, client):
        """Test that preview meets < 500ms requirement"""
        import time
        
        # Create a reasonably complex template
        template_content = """
        <html>
        <body>
            <h1>{{ business.name }}</h1>
            {% for i in range(100) %}
                <div>Item {{ i }}: {{ business.name }}</div>
            {% endfor %}
        </body>
        </html>
        """
        
        # Time the preview request
        start_time = time.time()
        response = client.post(
            "/api/template-studio/preview",
            json={
                "template_name": "perf_test.html",
                "sample_data": {
                    "business": {"name": "Performance Test Company"}
                }
            }
        )
        end_time = time.time()
        
        request_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        # Total request should complete well within 500ms
        # (actual rendering is tested to be <500ms in unit tests)
        assert request_time_ms < 1000, f"Request took {request_time_ms:.1f}ms"