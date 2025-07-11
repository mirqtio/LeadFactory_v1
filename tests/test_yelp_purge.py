"""
Test Yelp Purge - P0-009

Verifies that all Yelp remnants have been removed from the codebase.

Acceptance Criteria:
- No Yelp imports in codebase
- No active Yelp code (only comments/docs allowed)
- No Yelp routes in stub server
- No Yelp database columns or models
"""

import subprocess
import os
import pytest


class TestYelpPurge:
    """Verify all Yelp remnants have been removed"""

    def test_no_yelp_imports(self):
        """Test that there are no Yelp imports in Python files"""
        # Search for Yelp imports
        cmd = ['grep', '-r', '--include=*.py', '-E', 'from.*[Yy]elp|import.*[Yy]elp', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        # Filter out comments and this test file
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            active_imports = []
            for line in lines:
                # Skip this test file
                if 'test_yelp_purge.py' in line:
                    continue
                # Skip commented lines
                if '#' in line:
                    code_part = line.split('#')[0]
                    if 'yelp' in code_part.lower() and ('import' in code_part or 'from' in code_part):
                        active_imports.append(line)
                else:
                    active_imports.append(line)
            
            assert len(active_imports) == 0, f"Found active Yelp imports:\n" + "\n".join(active_imports)

    def test_no_yelp_classes(self):
        """Test that there are no Yelp class definitions"""
        cmd = ['grep', '-r', '--include=*.py', '-E', 'class.*[Yy]elp', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            active_classes = []
            for line in lines:
                # Skip this test file
                if 'test_yelp_purge.py' in line:
                    continue
                # Skip commented lines
                if '#' not in line or line.strip().index('#') > line.strip().index('class'):
                    active_classes.append(line)
            
            assert len(active_classes) == 0, f"Found active Yelp classes:\n" + "\n".join(active_classes)

    def test_no_yelp_models(self):
        """Test that there are no Yelp database models"""
        # Check for YelpMetadata or yelp-related table names
        cmd = ['grep', '-r', '--include=*.py', '-E', 'YelpMetadata|__tablename__.*yelp', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            active_models = []
            for line in lines:
                # Skip test files and comments
                if 'test' in line or '#' in line:
                    continue
                # Skip migration files (they're historical)
                if 'alembic/versions' in line:
                    continue
                active_models.append(line)
            
            assert len(active_models) == 0, f"Found active Yelp models:\n" + "\n".join(active_models)

    def test_no_yelp_exceptions(self):
        """Test that there are no Yelp-specific exceptions"""
        cmd = ['grep', '-r', '--include=*.py', '-E', '[Yy]elp.*Exception', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            active_exceptions = []
            for line in lines:
                # Skip test files and comments
                if 'test' in line or '#' in line:
                    continue
                # Skip this file
                if 'test_yelp_purge.py' in line:
                    continue
                active_exceptions.append(line)
            
            assert len(active_exceptions) == 0, f"Found active Yelp exceptions:\n" + "\n".join(active_exceptions)

    def test_no_yelp_in_stub_server(self):
        """Test that stub server has no Yelp endpoints"""
        stub_path = 'stubs/server.py'
        if os.path.exists(stub_path):
            with open(stub_path, 'r') as f:
                content = f.read()
            
            # Check for Yelp routes
            assert '/yelp' not in content.lower() or all(
                line.strip().startswith('#') 
                for line in content.split('\n') 
                if '/yelp' in line.lower()
            ), "Found Yelp routes in stub server"

    def test_no_yelp_api_keys(self):
        """Test that there are no Yelp API key references in code"""
        cmd = ['grep', '-r', '--include=*.py', '-iE', 'yelp_api_key|YELP_API_KEY', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            active_keys = []
            for line in lines:
                # Skip test files, comments, and env examples
                if 'test' in line or '#' in line or '.env.example' in line:
                    continue
                # Skip this file
                if 'test_yelp_purge.py' in line:
                    continue
                active_keys.append(line)
            
            assert len(active_keys) == 0, f"Found active Yelp API key references:\n" + "\n".join(active_keys)

    def test_no_yelp_id_usage(self):
        """Test that yelp_id is not used in active code"""
        cmd = ['grep', '-r', '--include=*.py', 'yelp_id', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            active_usage = []
            for line in lines:
                # Skip migration files (they're historical)
                if 'alembic/versions' in line:
                    continue
                # Skip comments
                if '#' in line and line.strip().index('#') < line.strip().find('yelp_id'):
                    continue
                # Skip this test file
                if 'test_yelp_purge.py' in line:
                    continue
                active_usage.append(line)
            
            assert len(active_usage) == 0, f"Found active yelp_id usage:\n" + "\n".join(active_usage)

    def test_documentation_only_yelp_references(self):
        """Test that Yelp references in docs are marked as removed"""
        # Check key documentation files
        docs_to_check = ['README.md', 'CHANGELOG.md', 'PRD.md']
        
        for doc in docs_to_check:
            if os.path.exists(doc):
                with open(doc, 'r') as f:
                    content = f.read()
                
                if 'yelp' in content.lower():
                    # Should mention that Yelp was removed
                    assert any(phrase in content.lower() for phrase in [
                        'yelp provider was removed',
                        'yelp removed',
                        'removed yelp',
                        'yelp.*removed',
                        'deleted.*yelp'
                    ]), f"{doc} mentions Yelp but doesn't indicate it was removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])