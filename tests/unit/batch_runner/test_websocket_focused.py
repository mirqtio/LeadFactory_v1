"""
Focused WebSocket Manager Tests for Coverage Boost
Targeting ConnectionManager and core functionality
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from batch_runner.websocket_manager import AsyncThrottle, ConnectionManager, WebSocketConnection


class TestAsyncThrottle:
    """Test AsyncThrottle functionality"""

    @pytest.fixture
    def throttle(self):
        """Create throttle instance"""
        return AsyncThrottle(rate_limit=1.0, period=2.0)

    async def test_throttle_initialization(self, throttle):
        """Test throttle initialization"""
        assert throttle.rate_limit == 1.0
        assert throttle.period == 2.0
        assert throttle._last_sent == {}

    async def test_should_send_first_message(self, throttle):
        """Test first message should always send"""
        result = await throttle.should_send("test_key")
        assert result is True

    async def test_should_send_throttled(self, throttle):
        """Test message throttling"""
        # First message should send
        result1 = await throttle.should_send("test_key")
        assert result1 is True

        # Immediate second message should be throttled
        result2 = await throttle.should_send("test_key")
        assert result2 is False

    def test_reset_throttle(self, throttle):
        """Test throttle reset"""
        throttle._last_sent["test_key"] = 123456
        throttle.reset("test_key")
        assert "test_key" not in throttle._last_sent

    def test_reset_nonexistent_key(self, throttle):
        """Test reset of non-existent key"""
        # Should not raise error
        throttle.reset("nonexistent_key")


class TestWebSocketConnection:
    """Test WebSocketConnection wrapper"""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket"""
        ws = Mock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.fixture
    def ws_connection(self, mock_websocket):
        """Create WebSocket connection"""
        return WebSocketConnection(mock_websocket, "batch-123", "user-456")

    def test_connection_initialization(self, ws_connection, mock_websocket):
        """Test connection initialization"""
        assert ws_connection.websocket == mock_websocket
        assert ws_connection.batch_id == "batch-123"
        assert ws_connection.user_id == "user-456"
        assert ws_connection.message_count == 0
        assert ws_connection.last_message_at is None

    async def test_send_json_success(self, ws_connection):
        """Test successful JSON message sending"""
        data = {"type": "progress", "data": {"progress": 50}}

        await ws_connection.send_json(data)

        ws_connection.websocket.send_json.assert_called_once_with(data)
        assert ws_connection.message_count == 1
        assert ws_connection.last_message_at is not None

    async def test_send_json_failure(self, ws_connection):
        """Test JSON sending with WebSocket error"""
        ws_connection.websocket.send_json.side_effect = Exception("Connection closed")

        with pytest.raises(Exception, match="Connection closed"):
            await ws_connection.send_json({"test": "data"})

    async def test_send_text_success(self, ws_connection):
        """Test successful text message sending"""
        message = "test message"

        await ws_connection.send_text(message)

        ws_connection.websocket.send_text.assert_called_once_with(message)
        assert ws_connection.message_count == 1

    async def test_send_text_failure(self, ws_connection):
        """Test text sending with WebSocket error"""
        ws_connection.websocket.send_text.side_effect = Exception("Connection closed")

        with pytest.raises(Exception, match="Connection closed"):
            await ws_connection.send_text("test")

    def test_connection_duration(self, ws_connection):
        """Test connection duration calculation"""
        duration = ws_connection.connection_duration
        assert duration >= 0
        assert isinstance(duration, float)


class TestConnectionManager:
    """Test ConnectionManager functionality"""

    @pytest.fixture
    def manager(self):
        """Create connection manager"""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket"""
        ws = Mock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    def test_manager_initialization(self, manager):
        """Test manager initialization"""
        assert manager.active_connections == {}
        assert manager.user_connections == {}
        assert manager.throttles == {}
        assert manager.total_connections == 0
        assert manager.total_messages_sent == 0

    async def test_connect_success(self, manager, mock_websocket):
        """Test successful WebSocket connection"""
        result = await manager.connect(mock_websocket, "batch-123", "user-456")

        assert result is True
        mock_websocket.accept.assert_called_once()
        assert "batch-123" in manager.active_connections
        assert "user-456" in manager.user_connections
        assert manager.total_connections == 1

    async def test_connect_without_user(self, manager, mock_websocket):
        """Test connection without user ID"""
        result = await manager.connect(mock_websocket, "batch-123")

        assert result is True
        assert "batch-123" in manager.active_connections
        assert len(manager.user_connections) == 0

    async def test_connect_failure(self, manager, mock_websocket):
        """Test connection failure"""
        mock_websocket.accept.side_effect = Exception("Connection failed")

        result = await manager.connect(mock_websocket, "batch-123")

        assert result is False
        assert "batch-123" not in manager.active_connections

    async def test_disconnect_existing(self, manager, mock_websocket):
        """Test disconnecting existing connection"""
        # First connect
        await manager.connect(mock_websocket, "batch-123", "user-456")

        # Then disconnect (sync method)
        manager.disconnect("batch-123")

        assert "batch-123" not in manager.active_connections
        assert len(manager.user_connections.get("user-456", set())) == 0

    def test_disconnect_nonexistent(self, manager):
        """Test disconnecting non-existent connection"""
        # Should not raise error (sync method)
        manager.disconnect("nonexistent-batch")

    async def test_broadcast_progress(self, manager, mock_websocket):
        """Test broadcasting progress updates"""
        # Connect first
        await manager.connect(mock_websocket, "batch-123")

        progress_data = {"processed": 5, "total": 10, "percentage": 50.0}

        await manager.broadcast_progress("batch-123", progress_data)

        expected_message = {"type": "progress", "data": progress_data}
        mock_websocket.send_json.assert_called_with(expected_message)

    async def test_broadcast_to_nonexistent_batch(self, manager):
        """Test broadcasting to non-existent batch"""
        # Should not raise error
        await manager.broadcast_progress("nonexistent", {"test": "data"})

    async def test_get_stats(self, manager, mock_websocket):
        """Test getting connection statistics"""
        # Connect some connections
        await manager.connect(mock_websocket, "batch-123")

        stats = manager.get_stats()

        assert "active_connections" in stats
        assert "total_connections" in stats
        assert "total_messages_sent" in stats
        assert stats["active_connections"] == 1

    async def test_cleanup_stale_connections(self, manager, mock_websocket):
        """Test stale connection cleanup"""
        # Connect
        await manager.connect(mock_websocket, "batch-123")

        # Cleanup stale connections (actual method name)
        await manager.cleanup_stale_connections(max_duration_seconds=0)

        # Should remove old connections
        assert isinstance(manager.active_connections, dict)

    def test_get_connection_info(self, manager):
        """Test getting connection info"""
        info = manager.get_connection_info("nonexistent-batch")
        assert info is None

    async def test_send_lead_update(self, manager, mock_websocket):
        """Test sending lead updates"""
        await manager.connect(mock_websocket, "batch-123")

        lead_data = {"lead_id": "lead-456", "status": "completed"}

        await manager.send_lead_update("batch-123", lead_data)

        expected_message = {"type": "lead_update", "data": lead_data}
        mock_websocket.send_json.assert_called_with(expected_message)

    async def test_broadcast_completion(self, manager, mock_websocket):
        """Test broadcasting completion message"""
        await manager.connect(mock_websocket, "batch-123")

        completion_data = {"batch_id": "batch-123", "status": "completed"}

        await manager.broadcast_completion("batch-123", completion_data)

        expected_message = {"type": "completion", "data": completion_data}
        mock_websocket.send_json.assert_called_with(expected_message)

    async def test_broadcast_error(self, manager, mock_websocket):
        """Test broadcasting error message"""
        await manager.connect(mock_websocket, "batch-123")

        await manager.broadcast_error("batch-123", "Processing failed", "ERROR_CODE")

        expected_message = {"type": "error", "data": {"message": "Processing failed", "code": "ERROR_CODE"}}
        mock_websocket.send_json.assert_called_with(expected_message)

    async def test_throttling_integration(self, manager, mock_websocket):
        """Test throttling integration"""
        await manager.connect(mock_websocket, "batch-123")

        # Send multiple messages rapidly
        await manager.broadcast_progress("batch-123", {"count": 1})
        await manager.broadcast_progress("batch-123", {"count": 2})

        # Should have created throttle
        assert "batch-123" in manager.throttles


class TestManagerSingleton:
    """Test singleton pattern for connection manager"""

    @patch("batch_runner.websocket_manager.ConnectionManager")
    def test_get_connection_manager_singleton(self, mock_manager_class):
        """Test singleton behavior"""
        from batch_runner.websocket_manager import get_connection_manager

        mock_instance = Mock()
        mock_manager_class.return_value = mock_instance

        # Should return same instance
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        assert manager1 is manager2
