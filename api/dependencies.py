"""
API dependencies
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import SessionLocal


async def get_db() -> AsyncSession:
    """Get database session"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user_optional() -> Optional[str]:
    """Get current user if available (optional)"""
    # TODO: Implement actual authentication
    # For now, return None to allow anonymous access
    return None