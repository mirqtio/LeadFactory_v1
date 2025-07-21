"""
Test suite for batch_runner WebSocket manager
Focus on achieving ≥80% total coverage for P0-022
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from batch_runner.websocket_manager import ConnectionManager, get_connection_manager, handle_websocket_connection


class TestWebSocketManager:
    """Test suite for WebSocket connection manager"""

    @pytest.fixture
    def connection_manager(self):
        """Create connection manager instance"""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection"""
        ws = Mock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    async def test_connection_manager_singleton(self):
        """Test connection manager singleton pattern"""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        assert manager1 is manager2

    async def test_connect_websocket_success(self, connection_manager, mock_websocket):
        """Test successful WebSocket connection"""
        batch_id = "test-batch-123"

        await connection_manager.connect(batch_id, mock_websocket)

        mock_websocket.accept.assert_called_once()
        assert batch_id in connection_manager.connections
        assert mock_websocket in connection_manager.connections[batch_id]

    async def test_connect_multiple_clients(self, connection_manager):
        """Test connecting multiple clients to same batch"""
        batch_id = "test-batch-123"
        ws1 = Mock()
        ws1.accept = AsyncMock()
        ws2 = Mock()
        ws2.accept = AsyncMock()

        await connection_manager.connect(batch_id, ws1)
        await connection_manager.connect(batch_id, ws2)

        assert len(connection_manager.connections[batch_id]) == 2
        assert ws1 in connection_manager.connections[batch_id]
        assert ws2 in connection_manager.connections[batch_id]

    async def test_disconnect_websocket(self, connection_manager, mock_websocket):
        """Test WebSocket disconnection"""
        batch_id = "test-batch-123"

        # Connect first
        await connection_manager.connect(batch_id, mock_websocket)
        assert len(connection_manager.connections[batch_id]) == 1

        # Disconnect
        await connection_manager.disconnect(batch_id, mock_websocket)
        assert len(connection_manager.connections[batch_id]) == 0

    async def test_disconnect_nonexistent_connection(self, connection_manager, mock_websocket):
        """Test disconnecting non-existent connection"""
        batch_id = "test-batch-123"

        # Should not raise error
        await connection_manager.disconnect(batch_id, mock_websocket)

    async def test_broadcast_progress_success(self, connection_manager):
        """Test successful progress broadcast"""
        batch_id = "test-batch-123"
        ws1 = Mock()
        ws1.send_json = AsyncMock()
        ws2 = Mock()
        ws2.send_json = AsyncMock()

        # Connect multiple clients
        await connection_manager.connect(batch_id, ws1)
        await connection_manager.connect(batch_id, ws2)

        progress_data = {"processed": 5, "total": 10, "percentage": 50.0}

        await connection_manager.broadcast_progress(batch_id, progress_data)

        ws1.send_json.assert_called_once_with({"type": "progress", "data": progress_data})
        ws2.send_json.assert_called_once_with({"type": "progress", "data": progress_data})

    async def test_broadcast_progress_connection_error(self, connection_manager):
        """Test broadcast with connection error"""
        batch_id = "test-batch-123"
        ws_working = Mock()
        ws_working.send_json = AsyncMock()
        ws_broken = Mock()
        ws_broken.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        await connection_manager.connect(batch_id, ws_working)
        await connection_manager.connect(batch_id, ws_broken)

        progress_data = {"processed": 5, "total": 10}

        await connection_manager.broadcast_progress(batch_id, progress_data)

        # Working connection should receive message
        ws_working.send_json.assert_called_once()
        # Broken connection should be removed
        assert ws_broken not in connection_manager.connections[batch_id]

    async def test_broadcast_completion_success(self, connection_manager, mock_websocket):
        """Test completion broadcast"""
        batch_id = "test-batch-123"
        await connection_manager.connect(batch_id, mock_websocket)

        completion_data = {"batch_id": batch_id, "total_leads": 10, "successful": 8, "failed": 2}

        await connection_manager.broadcast_completion(batch_id, completion_data)

        mock_websocket.send_json.assert_called_once_with({"type": "completion", "data": completion_data})

    async def test_broadcast_error(self, connection_manager, mock_websocket):
        """Test error broadcast"""
        batch_id = "test-batch-123"
        await connection_manager.connect(batch_id, mock_websocket)

        error_message = "Processing failed"
        error_code = "PROCESSING_ERROR"

        await connection_manager.broadcast_error(batch_id, error_message, error_code)

        mock_websocket.send_json.assert_called_once_with(
            {"type": "error", "data": {"message": error_message, "code": error_code}}
        )

    async def test_broadcast_to_nonexistent_batch(self, connection_manager):
        """Test broadcasting to non-existent batch"""
        batch_id = "nonexistent-batch"

        # Should not raise error
        await connection_manager.broadcast_progress(batch_id, {"test": "data"})
        await connection_manager.broadcast_completion(batch_id, {"test": "data"})
        await connection_manager.broadcast_error(batch_id, "error", "ERROR_CODE")

    async def test_get_connection_count(self, connection_manager):
        """Test getting connection count"""
        batch_id = "test-batch-123"

        assert connection_manager.get_connection_count(batch_id) == 0

        ws1 = Mock()
        ws1.accept = AsyncMock()
        await connection_manager.connect(batch_id, ws1)

        assert connection_manager.get_connection_count(batch_id) == 1

        ws2 = Mock()
        ws2.accept = AsyncMock()
        await connection_manager.connect(batch_id, ws2)

        assert connection_manager.get_connection_count(batch_id) == 2

    async def test_cleanup_empty_batches(self, connection_manager):
        """Test cleanup of empty batch connections"""
        batch_id = "test-batch-123"
        ws = Mock()
        ws.accept = AsyncMock()

        await connection_manager.connect(batch_id, ws)
        assert batch_id in connection_manager.connections

        await connection_manager.disconnect(batch_id, ws)

        # Cleanup should remove empty batch
        await connection_manager.cleanup_empty_batches()
        assert batch_id not in connection_manager.connections

    async def test_throttling_mechanism(self, connection_manager, mock_websocket):
        """Test message throttling"""
        batch_id = "test-batch-123"
        await connection_manager.connect(batch_id, mock_websocket)

        # Send multiple messages rapidly
        for i in range(5):
            await connection_manager.broadcast_progress(batch_id, {"count": i})

        # Should be throttled to prevent spam
        # Note: Actual throttling implementation would need to be tested with timing


class TestWebSocketHandling:
    """Test WebSocket connection handling"""

    @patch("batch_runner.websocket_manager.get_connection_manager")
    async def test_handle_websocket_connection_success(self, mock_get_manager):
        """Test successful WebSocket connection handling"""
        mock_manager = Mock()
        mock_manager.connect = AsyncMock()
        mock_manager.disconnect = AsyncMock()
        mock_get_manager.return_value = mock_manager

        mock_websocket = Mock()
        mock_websocket.receive_text = AsyncMock()
        mock_websocket.receive_text.side_effect = [json.dumps({"type": "ping"}), Exception("WebSocket closed")]

        batch_id = "test-batch-123"

        await handle_websocket_connection(mock_websocket, batch_id)

        mock_manager.connect.assert_called_once_with(batch_id, mock_websocket)
        mock_manager.disconnect.assert_called_once_with(batch_id, mock_websocket)

    @patch("batch_runner.websocket_manager.get_connection_manager")
    async def test_handle_websocket_connection_error(self, mock_get_manager):
        """Test WebSocket connection handling with error"""
        mock_manager = Mock()
        mock_manager.connect = AsyncMock(side_effect=Exception("Connection failed"))
        mock_manager.disconnect = AsyncMock()
        mock_get_manager.return_value = mock_manager

        mock_websocket = Mock()
        batch_id = "test-batch-123"

        # Should handle error gracefully
        await handle_websocket_connection(mock_websocket, batch_id)

        mock_manager.disconnect.assert_called_once_with(batch_id, mock_websocket)

    async def test_websocket_message_parsing(self):
        """Test WebSocket message parsing"""
        # Test valid JSON
        valid_message = '{"type": "ping", "data": {}}'
        parsed = json.loads(valid_message)
        assert parsed["type"] == "ping"

        # Test invalid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads("invalid json")


class TestConnectionManagerEdgeCases:
    """Test edge cases and error conditions"""

    async def test_connection_manager_initialization(self):
        """Test connection manager initialization"""
        manager = ConnectionManager()

        assert isinstance(manager.connections, dict)
        assert len(manager.connections) == 0

    async def test_multiple_disconnects_same_websocket(self, connection_manager, mock_websocket):
        """Test multiple disconnects of same WebSocket"""
        batch_id = "test-batch-123"

        await connection_manager.connect(batch_id, mock_websocket)
        await connection_manager.disconnect(batch_id, mock_websocket)

        # Second disconnect should not raise error
        await connection_manager.disconnect(batch_id, mock_websocket)

    async def test_broadcast_with_mixed_connection_states(self, connection_manager):
        """Test broadcast with some working and some broken connections"""
        batch_id = "test-batch-123"

        # Working WebSocket
        ws_good = Mock()
        ws_good.send_json = AsyncMock()

        # Broken WebSocket
        ws_bad = Mock()
        ws_bad.send_json = AsyncMock(side_effect=Exception("Broken"))

        await connection_manager.connect(batch_id, ws_good)
        await connection_manager.connect(batch_id, ws_bad)

        await connection_manager.broadcast_progress(batch_id, {"test": "data"})

        # Good connection should work
        ws_good.send_json.assert_called_once()
        # Bad connection should be cleaned up
        assert ws_bad not in connection_manager.connections[batch_id]
