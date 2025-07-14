"""
API dependencies
"""

from typing import Optional

from database.session import SessionLocal


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user_optional() -> Optional[str]:
    """Get current user if available (optional)"""
    # TODO: Implement actual authentication
    # For now, return None to allow anonymous access
    return None
