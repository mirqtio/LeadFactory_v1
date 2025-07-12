"""
Template Manager for Git operations and template utilities
"""

import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import git
from github import Github, Auth
from jinja2 import Environment, FileSystemLoader, meta
from jinja2.sandbox import SandboxedEnvironment

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """Manages template operations with Git integration"""
    
    def __init__(self):
        self.template_dir = Path("d6_reports/templates")
        self.repo = git.Repo(".")  # Current repository
        self.github_token = os.getenv("GITHUB_TOKEN")
        
    def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all templates with git metadata
        
        Returns:
            List of template info including path, SHA, last modified, author
        """
        templates = []
        
        for template_path in self.template_dir.rglob("*.html"):
            relative_path = template_path.relative_to(self.template_dir)
            
            # Get git info
            try:
                # Get last commit for this file
                commits = list(self.repo.iter_commits(paths=str(template_path), max_count=1))
                if commits:
                    last_commit = commits[0]
                    git_info = {
                        "sha": last_commit.hexsha[:8],
                        "author": str(last_commit.author),
                        "date": datetime.fromtimestamp(last_commit.committed_date).isoformat(),
                        "message": last_commit.message.strip(),
                    }
                else:
                    git_info = self._default_git_info()
            except Exception as e:
                logger.warning(f"Failed to get git info for {template_path}: {e}")
                git_info = self._default_git_info()
            
            # Get file info
            stat = template_path.stat()
            content = template_path.read_text()
            
            templates.append({
                "name": str(relative_path),
                "path": str(template_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "git": git_info,
                "checksum": hashlib.md5(content.encode()).hexdigest(),
            })
        
        return sorted(templates, key=lambda t: t["name"])
    
    def _default_git_info(self) -> Dict[str, str]:
        """Default git info when not available"""
        return {
            "sha": "unknown",
            "author": "unknown",
            "date": datetime.now().isoformat(),
            "message": "No git history",
        }
    
    def get_template_content(self, template_name: str) -> Optional[str]:
        """
        Get the content of a template
        
        Args:
            template_name: Name of the template relative to template directory
            
        Returns:
            Template content or None if not found
        """
        template_path = self.template_dir / template_name
        
        if not template_path.exists() or not template_path.is_file():
            return None
            
        # Security check - ensure path is within template directory
        try:
            template_path.relative_to(self.template_dir)
        except ValueError:
            logger.warning(f"Attempted to access template outside directory: {template_name}")
            return None
            
        return template_path.read_text()
    
    def validate_template(self, content: str) -> Dict[str, Any]:
        """
        Validate a Jinja2 template
        
        Args:
            content: Template content to validate
            
        Returns:
            Validation result with success flag and any errors
        """
        try:
            env = SandboxedEnvironment()
            env.parse(content)
            
            # Extract variables used in template
            ast = env.parse(content)
            variables = meta.find_undeclared_variables(ast)
            
            return {
                "valid": True,
                "variables": sorted(variables),
                "errors": [],
            }
        except Exception as e:
            return {
                "valid": False,
                "variables": [],
                "errors": [str(e)],
            }
    
    def create_safe_environment(self) -> SandboxedEnvironment:
        """
        Create a sandboxed Jinja2 environment for safe rendering
        
        Returns:
            Configured sandboxed environment
        """
        env = SandboxedEnvironment(
            autoescape=True,
            loader=FileSystemLoader(str(self.template_dir))
        )
        
        # Restrict to safe globals only
        env.globals = {
            'range': range,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'now': datetime.now,
        }
        
        return env
    
    def render_preview(self, template_name: str, sample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a template preview with sample data
        
        Args:
            template_name: Template to render
            sample_data: Sample data for rendering
            
        Returns:
            Preview result with rendered content or error
        """
        try:
            env = self.create_safe_environment()
            template = env.get_template(template_name)
            rendered = template.render(**sample_data)
            
            return {
                "success": True,
                "content": rendered,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": str(e),
            }
    
    def create_template_pr(
        self, 
        changes: Dict[str, str], 
        user: str,
        commit_message: str
    ) -> Dict[str, Any]:
        """
        Create a GitHub PR with template changes
        
        Args:
            changes: Dict of template_name -> new_content
            user: Username making the changes
            commit_message: Commit message for the changes
            
        Returns:
            PR creation result with URL or error
        """
        if not self.github_token:
            return {
                "success": False,
                "error": "GitHub token not configured",
                "pr_url": None,
            }
        
        try:
            # Initialize GitHub client
            g = Github(auth=Auth.Token(self.github_token))
            repo_name = os.getenv("GITHUB_REPOSITORY", "user/LeadFactory_v1_Final")
            repo = g.get_repo(repo_name)
            
            # Create new branch
            base_branch = repo.get_branch("main")
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            new_branch = f"template-update-{timestamp}"
            repo.create_git_ref(
                f"refs/heads/{new_branch}", 
                base_branch.commit.sha
            )
            
            # Update files
            for template_name, content in changes.items():
                file_path = f"d6_reports/templates/{template_name}"
                
                try:
                    # Get existing file
                    file = repo.get_contents(file_path, ref="main")
                    repo.update_file(
                        file_path,
                        f"Update template: {template_name}",
                        content,
                        file.sha,
                        branch=new_branch
                    )
                except Exception:
                    # File doesn't exist, create it
                    repo.create_file(
                        file_path,
                        f"Create template: {template_name}",
                        content,
                        branch=new_branch
                    )
            
            # Create PR
            pr_body = f"""## Template Studio Update
            
Updated by: {user}
Timestamp: {datetime.now().isoformat()}
Commit: {commit_message}

### Changes
- Modified templates via Template Studio

### Review Checklist
- [ ] Templates render correctly
- [ ] No syntax errors
- [ ] Content changes are appropriate
- [ ] No sensitive data exposed

🤖 Generated with [LeadFactory Template Studio](https://leadfactory.com/template-studio)
"""
            
            pr = repo.create_pull(
                title=f"Template Update: {commit_message}",
                body=pr_body,
                base="main",
                head=new_branch
            )
            
            return {
                "success": True,
                "error": None,
                "pr_url": pr.html_url,
                "pr_number": pr.number,
            }
            
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return {
                "success": False,
                "error": str(e),
                "pr_url": None,
            }
    
    def get_sample_lead_data(self, lead_id: int = 1) -> Dict[str, Any]:
        """
        Get sample lead data for template preview
        
        Args:
            lead_id: ID of sample lead (default 1)
            
        Returns:
            Sample data dictionary
        """
        # This would normally fetch from database
        # For now, return mock data
        return {
            "business": {
                "name": "Sample Business Inc.",
                "website": "https://example.com",
                "phone": "(555) 123-4567",
                "email": "info@example.com",
                "address": "123 Main St, Anytown, USA",
            },
            "assessment": {
                "score": 85,
                "tier": "A",
                "performance_score": 92,
                "seo_score": 78,
                "mobile_score": 88,
            },
            "findings": [
                {
                    "title": "Page Load Speed",
                    "description": "Your page loads in 2.3 seconds",
                    "impact": "high",
                    "effort": "medium",
                },
                {
                    "title": "Mobile Optimization",
                    "description": "Site is mobile-friendly",
                    "impact": "medium",
                    "effort": "low",
                },
            ],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "report_version": "1.0",
            },
        }