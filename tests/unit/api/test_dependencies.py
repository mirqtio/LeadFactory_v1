"""
Tests for API dependencies
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.dependencies import close_redis, get_async_db, get_current_user_optional, get_db, get_redis


class TestDatabaseDependencies:
    """Test database dependency functions"""

    def test_get_db(self):
        """Test synchronous database session dependency"""
        # Mock SessionLocal
        with patch("api.dependencies.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            # Get generator
            gen = get_db()

            # Get session from generator
            session = next(gen)

            # Verify we got the mock session
            assert session == mock_session

            # Clean up generator
            try:
                next(gen)
            except StopIteration:
                pass

            # Verify session was closed
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_async_db_with_postgresql(self):
        """Test async database session with PostgreSQL"""
        # Mock settings and AsyncSessionLocal
        with patch("api.dependencies.settings") as mock_settings:
            with patch("api.dependencies.AsyncSessionLocal") as mock_async_session_local:
                # Configure mocks
                mock_settings.database_url = "postgresql://user:pass@localhost/db"
                mock_async_session = AsyncMock()
                mock_async_session_local.return_value.__aenter__.return_value = mock_async_session
                mock_async_session_local.return_value.__aexit__.return_value = None

                # Get async generator
                gen = get_async_db()

                # Get session from generator
                session = await gen.__anext__()

                # Verify we got the mock session
                assert session == mock_async_session

                # Clean up generator
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

                # Verify session was closed
                mock_async_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_async_db_with_sqlite_raises_error(self):
        """Test async database raises error with SQLite"""
        # Mock AsyncSessionLocal as None (SQLite case)
        with patch("api.dependencies.AsyncSessionLocal", None):
            gen = get_async_db()

            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="Async database not available for SQLite"):
                await gen.__anext__()


class TestRedisDependencies:
    """Test Redis dependency functions"""

    @pytest.mark.asyncio
    async def test_get_redis_creates_singleton(self):
        """Test Redis client is created as singleton"""
        # Mock redis client
        mock_redis = AsyncMock()

        # Create async mock for from_url that returns the mock_redis
        async def mock_from_url(*args, **kwargs):
            return mock_redis

        with patch("api.dependencies.aioredis.from_url", side_effect=mock_from_url) as mock_from_url_patch:
            with patch("api.dependencies.settings") as mock_settings:
                mock_settings.redis_url = "redis://localhost:6379/0"

                # Reset global state
                import api.dependencies

                api.dependencies._redis_client = None

                # First call should create client
                client1 = await get_redis()
                assert client1 == mock_redis
                mock_from_url_patch.assert_called_once_with(
                    "redis://localhost:6379/0", decode_responses=True, encoding="utf-8"
                )

                # Second call should return same client
                client2 = await get_redis()
                assert client2 == mock_redis
                assert mock_from_url_patch.call_count == 1  # Not called again

                # Clean up
                await close_redis()

    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Test Redis connection closure"""
        # Mock redis client
        mock_redis = AsyncMock()

        # Set up global client
        import api.dependencies

        api.dependencies._redis_client = mock_redis

        # Close connection
        await close_redis()

        # Verify close was called
        mock_redis.close.assert_called_once()

        # Verify client was reset
        assert api.dependencies._redis_client is None


class TestAuthDependencies:
    """Test authentication dependencies"""

    @pytest.mark.asyncio
    async def test_get_current_user_optional_returns_none(self):
        """Test optional user dependency returns None"""
        user = await get_current_user_optional()
        assert user is None
