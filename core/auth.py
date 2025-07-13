"""
Simple authentication utilities for internal routes
"""
import os
from typing import Optional


def verify_internal_token(token: str) -> bool:
    """
    Verify internal authentication token
    
    Args:
        token: The token to verify
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    # Get expected token from environment
    expected_token = os.environ.get("INTERNAL_API_TOKEN", "internal-token-default")
    
    # In test environment, accept default token
    if os.environ.get("ENVIRONMENT") == "test":
        return token in [expected_token, "test-token"]
    
    return token == expected_token


def get_current_user() -> Optional[str]:
    """
    Get current authenticated user
    
    Returns:
        Optional[str]: Username if authenticated, None otherwise
    """
    # TODO: Implement actual user authentication
    return "system"