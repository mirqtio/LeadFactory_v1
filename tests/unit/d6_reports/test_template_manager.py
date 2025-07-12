"""
Unit tests for Template Manager
"""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from jinja2.exceptions import TemplateSyntaxError

from d6_reports.template_manager import TemplateManager


class TestTemplateManager:
    """Test suite for template manager functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create template manager instance"""
        return TemplateManager()
    
    @pytest.fixture
    def sample_template(self, tmp_path):
        """Create a sample template file"""
        template_dir = tmp_path / "d6_reports" / "templates"
        template_dir.mkdir(parents=True)
        
        template_file = template_dir / "test_template.html"
        template_file.write_text("""
        <html>
        <body>
            <h1>{{ business.name }}</h1>
            <p>Score: {{ assessment.score }}</p>
        </body>
        </html>
        """)
        
        return template_file
    
    def test_list_templates(self, manager, sample_template, monkeypatch):
        """Test listing templates with git metadata"""
        # Mock the template directory
        monkeypatch.setattr(manager, "template_dir", sample_template.parent)
        
        # Mock git repo
        mock_repo = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = "abcd1234567890"
        mock_commit.author = Mock()
        mock_commit.author.__str__ = Mock(return_value="Test Author")
        mock_commit.committed_date = datetime.now().timestamp()
        mock_commit.message = "Test commit message"
        
        mock_repo.iter_commits = Mock(return_value=[mock_commit])
        
        with patch("git.Repo", return_value=mock_repo):
            templates = manager.list_templates()
        
        assert len(templates) == 1
        assert templates[0]["name"] == "test_template.html"
        assert templates[0]["git"]["sha"] == "abcd1234"
        assert templates[0]["git"]["author"] == "Test Author"
    
    def test_list_templates_no_git_history(self, manager, sample_template, monkeypatch):
        """Test listing templates when git history is not available"""
        monkeypatch.setattr(manager, "template_dir", sample_template.parent)
        
        # Mock git repo with no commits
        mock_repo = Mock()
        mock_repo.iter_commits = Mock(return_value=[])
        
        with patch("git.Repo", return_value=mock_repo):
            templates = manager.list_templates()
        
        assert len(templates) == 1
        assert templates[0]["git"]["sha"] == "unknown"
        assert templates[0]["git"]["author"] == "unknown"
    
    def test_get_template_content(self, manager, sample_template, monkeypatch):
        """Test getting template content"""
        monkeypatch.setattr(manager, "template_dir", sample_template.parent)
        
        content = manager.get_template_content("test_template.html")
        
        assert content is not None
        assert "{{ business.name }}" in content
        assert "{{ assessment.score }}" in content
    
    def test_get_template_content_not_found(self, manager):
        """Test getting non-existent template"""
        content = manager.get_template_content("non_existent.html")
        assert content is None
    
    def test_get_template_content_path_traversal(self, manager, tmp_path):
        """Test that path traversal is prevented"""
        # Create a file outside template directory
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("secret data")
        
        # Try to access it via path traversal
        content = manager.get_template_content("../../secret.txt")
        assert content is None
    
    def test_validate_template_valid(self, manager):
        """Test validating a valid template"""
        template = """
        <h1>{{ title }}</h1>
        {% for item in items %}
            <li>{{ item.name }}</li>
        {% endfor %}
        """
        
        result = manager.validate_template(template)
        
        assert result["valid"] is True
        assert "title" in result["variables"]
        assert "items" in result["variables"]
        assert len(result["errors"]) == 0
    
    def test_validate_template_invalid(self, manager):
        """Test validating an invalid template"""
        template = """
        <h1>{{ title }}</h1>
        {% for item in items %}
            <li>{{ item.name }}</li>
        {# Missing endfor #}
        """
        
        result = manager.validate_template(template)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_create_safe_environment(self, manager):
        """Test creating sandboxed environment"""
        env = manager.create_safe_environment()
        
        # Check that dangerous operations are restricted
        assert "open" not in env.globals
        assert "eval" not in env.globals
        assert "__import__" not in env.globals
        
        # Check allowed globals
        assert "range" in env.globals
        assert "len" in env.globals
        assert "str" in env.globals
    
    def test_render_preview_success(self, manager, sample_template, monkeypatch):
        """Test successful template preview rendering"""
        monkeypatch.setattr(manager, "template_dir", sample_template.parent)
        
        sample_data = {
            "business": {"name": "Test Company"},
            "assessment": {"score": 85},
        }
        
        result = manager.render_preview("test_template.html", sample_data)
        
        assert result["success"] is True
        assert "Test Company" in result["content"]
        assert "Score: 85" in result["content"]
        assert result["error"] is None
    
    def test_render_preview_error(self, manager):
        """Test template preview with rendering error"""
        result = manager.render_preview("non_existent.html", {})
        
        assert result["success"] is False
        assert result["content"] is None
        assert result["error"] is not None
    
    def test_create_template_pr_success(self, manager):
        """Test successful PR creation"""
        # Mock GitHub client
        mock_g = Mock()
        mock_repo = Mock()
        mock_branch = Mock()
        mock_branch.commit.sha = "main_sha_123"
        
        mock_repo.get_branch = Mock(return_value=mock_branch)
        mock_repo.create_git_ref = Mock()
        mock_repo.get_contents = Mock(side_effect=Exception("File not found"))
        mock_repo.create_file = Mock()
        
        mock_pr = Mock()
        mock_pr.html_url = "https://github.com/user/repo/pull/123"
        mock_pr.number = 123
        mock_repo.create_pull = Mock(return_value=mock_pr)
        
        mock_g.get_repo = Mock(return_value=mock_repo)
        
        with patch("github.Github", return_value=mock_g):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
                result = manager.create_template_pr(
                    changes={"test.html": "<h1>New content</h1>"},
                    user="testuser",
                    commit_message="Update test template"
                )
        
        assert result["success"] is True
        assert result["pr_url"] == "https://github.com/user/repo/pull/123"
        assert result["pr_number"] == 123
        assert result["error"] is None
    
    def test_create_template_pr_no_token(self, manager):
        """Test PR creation without GitHub token"""
        with patch.dict(os.environ, {}, clear=True):
            result = manager.create_template_pr(
                changes={"test.html": "<h1>New</h1>"},
                user="testuser",
                commit_message="Update"
            )
        
        assert result["success"] is False
        assert result["error"] == "GitHub token not configured"
        assert result["pr_url"] is None
    
    def test_create_template_pr_github_error(self, manager):
        """Test PR creation with GitHub API error"""
        mock_g = Mock()
        mock_g.get_repo = Mock(side_effect=Exception("API rate limit exceeded"))
        
        with patch("github.Github", return_value=mock_g):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
                result = manager.create_template_pr(
                    changes={"test.html": "<h1>New</h1>"},
                    user="testuser",
                    commit_message="Update"
                )
        
        assert result["success"] is False
        assert "API rate limit exceeded" in result["error"]
        assert result["pr_url"] is None
    
    def test_get_sample_lead_data(self, manager):
        """Test getting sample lead data"""
        data = manager.get_sample_lead_data(lead_id=1)
        
        assert "business" in data
        assert "assessment" in data
        assert "findings" in data
        assert "metadata" in data
        
        assert data["business"]["name"] == "Sample Business Inc."
        assert data["assessment"]["score"] == 85
        assert len(data["findings"]) > 0