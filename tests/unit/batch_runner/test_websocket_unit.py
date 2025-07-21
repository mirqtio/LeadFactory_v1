"""
Unit tests for WebSocket Manager module
Tests WebSocket connection management and throttling without network dependencies
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from batch_runner.websocket_manager import AsyncThrottle, ConnectionManager


class TestAsyncThrottle:
    """Unit tests for AsyncThrottle class"""

    @pytest.mark.asyncio
    async def test_throttle_initialization(self):
        """Test AsyncThrottle initialization"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        assert throttle.rate_limit == 1.0
        assert throttle.period == 2.0
        assert throttle._last_sent == {}
        assert throttle._lock is not None

    @pytest.mark.asyncio
    async def test_should_send_first_call_immediate(self):
        """Test first call should send immediately"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        # Mock time to control timing
        with patch("time.time", return_value=100.0):
            result = await throttle.should_send("test-key")
            assert result is True
            assert throttle._last_sent["test-key"] == 100.0

    @pytest.mark.asyncio
    async def test_should_send_throttling_enforcement(self):
        """Test throttling prevents rapid calls"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        # First call
        with patch("time.time", return_value=100.0):
            result1 = await throttle.should_send("test-key")
            assert result1 is True

        # Second call too soon - should be blocked
        with patch("time.time", return_value=100.5):
            result2 = await throttle.should_send("test-key")
            assert result2 is False

    @pytest.mark.asyncio
    async def test_should_send_period_elapsed(self):
        """Test sending allowed when period has elapsed"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        # First call
        with patch("time.time", return_value=100.0):
            result1 = await throttle.should_send("test-key")
            assert result1 is True

        # Second call after period - should be allowed
        with patch("time.time", return_value=102.5):
            result2 = await throttle.should_send("test-key")
            assert result2 is True
            assert throttle._last_sent["test-key"] == 102.5

    @pytest.mark.asyncio
    async def test_should_send_different_keys(self):
        """Test different keys are throttled independently"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        # First key
        with patch("time.time", return_value=100.0):
            result1 = await throttle.should_send("key1")
            assert result1 is True

        # Different key immediately - should be allowed
        with patch("time.time", return_value=100.0):
            result2 = await throttle.should_send("key2")
            assert result2 is True

        # Same key too soon - should be blocked
        with patch("time.time", return_value=100.5):
            result3 = await throttle.should_send("key1")
            assert result3 is False

    @pytest.mark.asyncio
    async def test_reset_key(self):
        """Test reset functionality"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        # First call
        with patch("time.time", return_value=100.0):
            await throttle.should_send("test-key")
            assert "test-key" in throttle._last_sent

        # Reset the key
        throttle.reset("test-key")
        assert "test-key" not in throttle._last_sent

    @pytest.mark.asyncio
    async def test_concurrent_access_with_lock(self):
        """Test concurrent access uses lock properly"""
        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)

        # Mock the lock to verify it's used
        mock_lock = AsyncMock()
        throttle._lock = mock_lock

        with patch("time.time", return_value=100.0):
            await throttle.should_send("test-key")
            mock_lock.__aenter__.assert_called()
            mock_lock.__aexit__.assert_called()


class TestConnectionManager:
    """Unit tests for ConnectionManager class"""

    def test_connection_manager_initialization(self):
        """Test ConnectionManager initialization"""
        manager = ConnectionManager()

        assert hasattr(manager, "active_connections")
        assert hasattr(manager, "throttles")
        assert isinstance(manager.active_connections, dict)
        assert isinstance(manager.throttles, dict)

    @pytest.mark.asyncio
    async def test_connect_websocket(self):
        """Test WebSocket connection"""
        manager = ConnectionManager()

        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()

        batch_id = "test-batch-123"
        user_id = "user-456"

        # Test connection
        result = await manager.connect(mock_websocket, batch_id, user_id)

        # Verify connection succeeded
        assert result is True

        # Verify connection is stored
        assert batch_id in manager.active_connections
        connection = manager.active_connections[batch_id]
        assert connection.batch_id == batch_id
        assert connection.user_id == user_id
        assert connection.websocket == mock_websocket

        # Verify throttle is created
        assert batch_id in manager.throttles

        # Verify user tracking
        assert user_id in manager.user_connections
        assert batch_id in manager.user_connections[user_id]

    def test_disconnect_websocket(self):
        """Test WebSocket disconnection"""
        manager = ConnectionManager()

        batch_id = "test-batch-123"
        user_id = "user-456"

        # Manually add connection to test disconnection
        from batch_runner.websocket_manager import WebSocketConnection

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(mock_websocket, batch_id, user_id)

        manager.active_connections[batch_id] = connection
        manager.user_connections[user_id] = {batch_id}
        manager.throttles[batch_id] = AsyncMock()

        # Test disconnection
        manager.disconnect(batch_id)

        # Verify connection is removed
        assert batch_id not in manager.active_connections
        assert batch_id not in manager.throttles
        assert user_id not in manager.user_connections

    @pytest.mark.asyncio
    async def test_broadcast_progress(self):
        """Test broadcasting progress updates"""
        manager = ConnectionManager()

        # Create a mock WebSocketConnection
        from batch_runner.websocket_manager import WebSocketConnection

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(mock_websocket, "test-batch", "user-123")
        connection.send_json = AsyncMock()

        batch_id = "test-batch-123"
        manager.active_connections[batch_id] = connection

        # Create throttle
        from batch_runner.websocket_manager import AsyncThrottle

        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)
        manager.throttles[batch_id] = throttle

        # Test broadcast
        progress_data = {
            "processed": 5,
            "total": 10,
            "progress_percentage": 50.0,
        }

        # Mock throttle to allow sending
        with patch.object(throttle, "should_send", return_value=True):
            result = await manager.broadcast_progress(batch_id, progress_data)

        # Verify broadcast succeeded
        assert result is True
        connection.send_json.assert_called_once()

        # Verify message structure
        call_args = connection.send_json.call_args[0][0]
        assert call_args["type"] == "progress_update"
        assert call_args["batch_id"] == batch_id
        assert call_args["processed"] == 5

    @pytest.mark.asyncio
    async def test_broadcast_progress_throttled(self):
        """Test broadcast is throttled properly"""
        manager = ConnectionManager()

        # Create connection
        from batch_runner.websocket_manager import WebSocketConnection

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(mock_websocket, "test-batch", "user-123")
        connection.send_json = AsyncMock()

        batch_id = "test-batch-123"
        manager.active_connections[batch_id] = connection

        # Create throttle
        from batch_runner.websocket_manager import AsyncThrottle

        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)
        manager.throttles[batch_id] = throttle

        progress_data = {"processed": 5, "total": 10}

        # Mock throttle to block sending
        with patch.object(throttle, "should_send", return_value=False):
            result = await manager.broadcast_progress(batch_id, progress_data)

        # Verify broadcast was throttled
        assert result is False
        connection.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_progress_force(self):
        """Test force broadcast bypasses throttling"""
        manager = ConnectionManager()

        # Create connection
        from batch_runner.websocket_manager import WebSocketConnection

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(mock_websocket, "test-batch", "user-123")
        connection.send_json = AsyncMock()

        batch_id = "test-batch-123"
        manager.active_connections[batch_id] = connection

        # Create throttle (not needed for force)
        from batch_runner.websocket_manager import AsyncThrottle

        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)
        manager.throttles[batch_id] = throttle

        progress_data = {"message": "Forced message"}

        # Force broadcast should bypass throttling
        result = await manager.broadcast_progress(batch_id, progress_data, force=True)

        # Verify broadcast succeeded
        assert result is True
        connection.send_json.assert_called_once()

    def test_get_stats(self):
        """Test getting connection statistics"""
        manager = ConnectionManager()

        # Add some mock connections
        from batch_runner.websocket_manager import WebSocketConnection

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()

        connection1 = WebSocketConnection(mock_ws1, "batch-1", "user-1")
        connection2 = WebSocketConnection(mock_ws2, "batch-2", "user-1")
        connection3 = WebSocketConnection(mock_ws3, "batch-3", "user-2")

        manager.active_connections = {"batch-1": connection1, "batch-2": connection2, "batch-3": connection3}
        manager.user_connections = {"user-1": {"batch-1", "batch-2"}, "user-2": {"batch-3"}}
        manager.total_connections = 5
        manager.total_messages_sent = 100

        stats = manager.get_stats()

        assert stats["active_connections"] == 3
        assert stats["active_users"] == 2
        assert stats["total_connections_created"] == 5
        assert stats["total_messages_sent"] == 100
        assert set(stats["connections_by_batch"]) == {"batch-1", "batch-2", "batch-3"}
        assert set(stats["users_connected"]) == {"user-1", "user-2"}

    def test_get_connection_info(self):
        """Test getting connection information"""
        manager = ConnectionManager()

        batch_id = "test-batch-123"
        user_id = "user-456"

        # Create connection
        from batch_runner.websocket_manager import WebSocketConnection

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(mock_websocket, batch_id, user_id)
        connection.message_count = 5

        manager.active_connections[batch_id] = connection

        # Test getting info
        info = manager.get_connection_info(batch_id)

        assert info is not None
        assert info["batch_id"] == batch_id
        assert info["user_id"] == user_id
        assert info["message_count"] == 5
        assert "connected_at" in info
        assert "connection_duration_seconds" in info

    def test_get_connection_info_not_found(self):
        """Test getting info for non-existent connection"""
        manager = ConnectionManager()

        info = manager.get_connection_info("nonexistent-batch")
        assert info is None

    @pytest.mark.asyncio
    async def test_handle_websocket_connection_function_exists(self):
        """Test that handle_websocket_connection function exists"""
        from batch_runner.websocket_manager import handle_websocket_connection

        # Test that function exists and is callable
        assert callable(handle_websocket_connection)

    def test_get_connection_manager_singleton(self):
        """Test connection manager singleton pattern"""
        from batch_runner.websocket_manager import get_connection_manager

        # Get manager instances
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        # Verify they are the same instance (singleton)
        assert manager1 is manager2
        assert isinstance(manager1, ConnectionManager)

    @pytest.mark.asyncio
    async def test_message_serialization(self):
        """Test message serialization for WebSocket"""
        manager = ConnectionManager()

        # Create connection
        from batch_runner.websocket_manager import WebSocketConnection

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(mock_websocket, "test-batch-123", "user-123")
        connection.send_json = AsyncMock()

        batch_id = "test-batch-123"
        manager.active_connections[batch_id] = connection

        # Create throttle
        from batch_runner.websocket_manager import AsyncThrottle

        throttle = AsyncThrottle(rate_limit=1.0, period=2.0)
        manager.throttles[batch_id] = throttle

        # Test complex message data
        message_data = {
            "processed": 5,
            "total": 10,
            "successful": 4,
            "failed": 1,
            "progress_percentage": 50.0,
            "current_lead": "lead-5",
            "message": "Processing leads",
            "error_message": None,
            "error_code": None,
        }

        # Mock throttle to allow sending
        with patch.object(throttle, "should_send", return_value=True):
            result = await manager.broadcast_progress(batch_id, message_data)

        # Verify broadcast succeeded
        assert result is True
        connection.send_json.assert_called_once()

        # Verify message structure
        call_args = connection.send_json.call_args[0][0]
        assert call_args["type"] == "progress_update"
        assert call_args["batch_id"] == batch_id
        assert call_args["processed"] == 5
        assert call_args["progress_percentage"] == 50.0
        assert "timestamp" in call_args
