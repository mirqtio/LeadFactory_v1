"""Minimal test to debug CI issues"""
import sys
import os

def test_basic():
    """Most basic test possible"""
    assert True
    
def test_environment():
    """Test environment variables are set"""
    assert os.getenv('ENVIRONMENT') == 'test'
    assert os.getenv('USE_STUBS') == 'true'
    
def test_python_version():
    """Test Python version"""
    assert sys.version_info[:2] == (3, 11)
    
if __name__ == "__main__":
    print(f"Python: {sys.version}")
    print(f"CWD: {os.getcwd()}")
    print(f"PYTHONPATH: {os.getenv('PYTHONPATH')}")
    print(f"Files in tests/: {os.listdir('tests') if os.path.exists('tests') else 'NOT FOUND'}")