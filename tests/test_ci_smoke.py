"""
Simple smoke test to verify CI environment
"""
import sys
import os


def test_python_version():
    """Test Python version is 3.11"""
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 11


def test_environment_setup():
    """Test environment variables are set"""
    assert os.getenv("USE_STUBS") == "true"
    assert os.getenv("ENVIRONMENT") == "test"
    assert os.getenv("DATABASE_URL") is not None


def test_imports_work():
    """Test basic imports work"""
    # Core imports
    from core.config import Settings
    from core.exceptions import LeadFactoryError
    
    # Database imports
    from database.base import Base
    from database.models import Business
    
    # Gateway imports
    from d0_gateway.base import BaseAPIClient
    
    assert Settings is not None
    assert LeadFactoryError is not None
    assert Base is not None
    assert Business is not None
    assert BaseAPIClient is not None


def test_stub_server_import():
    """Test stub server can be imported"""
    from stubs.server import app
    assert app is not None