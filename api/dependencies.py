"""
API dependencies
"""

from typing import Optional

from database.session import get_db as sync_get_db


def get_db():
    """Get database session"""
    # Use the sync database session from database.session
    return sync_get_db()


async def get_current_user_optional() -> Optional[str]:
    """Get current user if available (optional)"""
    # TODO: Implement actual authentication
    # For now, return None to allow anonymous access
    return None
