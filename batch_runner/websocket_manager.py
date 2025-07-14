"""
WebSocket Connection Manager for Batch Report Runner

Manages real-time progress updates with throttling, authentication,
and multi-client support for batch processing notifications.
"""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from core.logging import get_logger

logger = get_logger("batch_websocket_manager")


class AsyncThrottle:
    """Async throttle to limit message frequency"""

    def __init__(self, rate_limit: float = 1.0, period: float = 2.0):
        """
        Args:
            rate_limit: Maximum messages per period
            period: Time period in seconds
        """
        self.rate_limit = rate_limit
        self.period = period
        self._last_sent = {}
        self._lock = asyncio.Lock()

    async def should_send(self, key: str) -> bool:
        """Check if message should be sent based on throttling"""
        async with self._lock:
            now = time.time()
            last_sent = self._last_sent.get(key, 0)

            if now - last_sent >= self.period / self.rate_limit:
                self._last_sent[key] = now
                return True
            return False

    def reset(self, key: str):
        """Reset throttle for a specific key"""
        if key in self._last_sent:
            del self._last_sent[key]


class WebSocketConnection:
    """Individual WebSocket connection wrapper"""

    def __init__(self, websocket: WebSocket, batch_id: str, user_id: Optional[str] = None):
        self.websocket = websocket
        self.batch_id = batch_id
        self.user_id = user_id
        self.connected_at = datetime.utcnow()
        self.last_message_at = None
        self.message_count = 0

    async def send_json(self, data: Dict[str, Any]):
        """Send JSON message with error handling"""
        try:
            await self.websocket.send_json(data)
            self.last_message_at = datetime.utcnow()
            self.message_count += 1
            logger.debug(f"Sent WebSocket message to {self.batch_id}: {data}")
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message to {self.batch_id}: {e}")
            raise

    async def send_text(self, message: str):
        """Send text message with error handling"""
        try:
            await self.websocket.send_text(message)
            self.last_message_at = datetime.utcnow()
            self.message_count += 1
        except Exception as e:
            logger.warning(f"Failed to send WebSocket text to {self.batch_id}: {e}")
            raise

    @property
    def connection_duration(self) -> float:
        """Get connection duration in seconds"""
        return (datetime.utcnow() - self.connected_at).total_seconds()


class ConnectionManager:
    """Manages WebSocket connections for batch processing updates"""

    def __init__(self):
        # Active connections by batch_id
        self.active_connections: Dict[str, WebSocketConnection] = {}

        # Connections by user (for user-specific broadcasts)
        self.user_connections: Dict[str, Set[str]] = {}

        # Throttle instances per batch
        self.throttles: Dict[str, AsyncThrottle] = {}

        # Statistics
        self.total_connections = 0
        self.total_messages_sent = 0

    async def connect(self, websocket: WebSocket, batch_id: str, user_id: Optional[str] = None) -> bool:
        """
        Accept WebSocket connection and register it

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            await websocket.accept()

            # Create connection wrapper
            connection = WebSocketConnection(websocket, batch_id, user_id)

            # Store connection
            self.active_connections[batch_id] = connection

            # Track user connections
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(batch_id)

            # Create throttle for this batch
            self.throttles[batch_id] = AsyncThrottle(rate_limit=1.0, period=2.0)

            self.total_connections += 1

            logger.info(f"WebSocket connected for batch {batch_id}, user {user_id}")

            # Send initial connection confirmation
            await connection.send_json(
                {
                    "type": "connection_established",
                    "batch_id": batch_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "Connected to batch progress updates",
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection for batch {batch_id}: {e}")
            return False

    def disconnect(self, batch_id: str):
        """Disconnect and clean up WebSocket connection"""
        connection = self.active_connections.get(batch_id)
        if connection:
            # Remove from user connections
            if connection.user_id and connection.user_id in self.user_connections:
                self.user_connections[connection.user_id].discard(batch_id)
                if not self.user_connections[connection.user_id]:
                    del self.user_connections[connection.user_id]

            # Clean up throttle
            if batch_id in self.throttles:
                del self.throttles[batch_id]

            # Remove connection
            del self.active_connections[batch_id]

            logger.info(f"WebSocket disconnected for batch {batch_id}")

    async def broadcast_progress(self, batch_id: str, progress_data: Dict[str, Any], force: bool = False) -> bool:
        """
        Broadcast progress update to specific batch connection

        Args:
            batch_id: Batch ID to send update to
            progress_data: Progress information
            force: Skip throttling if True

        Returns:
            bool: True if message sent successfully
        """
        connection = self.active_connections.get(batch_id)
        if not connection:
            logger.debug(f"No active connection for batch {batch_id}")
            return False

        # Check throttling unless forced
        throttle = self.throttles.get(batch_id)
        if not force and throttle and not await throttle.should_send(batch_id):
            logger.debug(f"Message throttled for batch {batch_id}")
            return False

        try:
            # Prepare message
            message = {
                "type": "progress_update",
                "batch_id": batch_id,
                "timestamp": datetime.utcnow().isoformat(),
                **progress_data,
            }

            await connection.send_json(message)
            self.total_messages_sent += 1

            logger.debug(f"Broadcast progress to batch {batch_id}: {progress_data}")
            return True

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected during broadcast for batch {batch_id}")
            self.disconnect(batch_id)
            return False
        except Exception as e:
            logger.error(f"Failed to broadcast to batch {batch_id}: {e}")
            self.disconnect(batch_id)
            return False

    async def broadcast_completion(self, batch_id: str, completion_data: Dict[str, Any]):
        """Broadcast batch completion with final results"""
        message = {
            "type": "batch_completed",
            "batch_id": batch_id,
            "timestamp": datetime.utcnow().isoformat(),
            **completion_data,
        }

        await self.broadcast_progress(batch_id, message, force=True)

    async def broadcast_error(self, batch_id: str, error_message: str, error_code: Optional[str] = None):
        """Broadcast error message"""
        message = {
            "type": "batch_error",
            "batch_id": batch_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error_message": error_message,
            "error_code": error_code,
        }

        await self.broadcast_progress(batch_id, message, force=True)

    async def send_lead_update(self, batch_id: str, lead_data: Dict[str, Any]):
        """Send individual lead processing update"""
        message = {"type": "lead_update", "batch_id": batch_id, "timestamp": datetime.utcnow().isoformat(), **lead_data}

        await self.broadcast_progress(batch_id, message, force=False)

    def get_connection_info(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a connection"""
        connection = self.active_connections.get(batch_id)
        if not connection:
            return None

        return {
            "batch_id": batch_id,
            "user_id": connection.user_id,
            "connected_at": connection.connected_at.isoformat(),
            "connection_duration_seconds": connection.connection_duration,
            "message_count": connection.message_count,
            "last_message_at": connection.last_message_at.isoformat() if connection.last_message_at else None,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics"""
        active_count = len(self.active_connections)
        active_users = len(self.user_connections)

        return {
            "active_connections": active_count,
            "active_users": active_users,
            "total_connections_created": self.total_connections,
            "total_messages_sent": self.total_messages_sent,
            "connections_by_batch": list(self.active_connections.keys()),
            "users_connected": list(self.user_connections.keys()),
        }

    async def cleanup_stale_connections(self, max_duration_seconds: int = 3600):
        """Clean up connections that have been open too long without activity"""
        datetime.utcnow()
        stale_batches = []

        for batch_id, connection in self.active_connections.items():
            if connection.connection_duration > max_duration_seconds:
                stale_batches.append(batch_id)

        for batch_id in stale_batches:
            logger.info(f"Cleaning up stale WebSocket connection for batch {batch_id}")
            self.disconnect(batch_id)

        return len(stale_batches)

    @asynccontextmanager
    async def connection_context(self, websocket: WebSocket, batch_id: str, user_id: Optional[str] = None):
        """Context manager for handling WebSocket connection lifecycle"""
        connected = await self.connect(websocket, batch_id, user_id)
        if not connected:
            raise ConnectionError(f"Failed to establish WebSocket connection for batch {batch_id}")

        try:
            yield self.active_connections[batch_id]
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected for batch {batch_id}")
        except Exception as e:
            logger.error(f"WebSocket error for batch {batch_id}: {e}")
        finally:
            self.disconnect(batch_id)


# Singleton instance
_connection_manager = None


def get_connection_manager() -> ConnectionManager:
    """Get singleton connection manager instance"""
    global _connection_manager
    if not _connection_manager:
        _connection_manager = ConnectionManager()
    return _connection_manager


async def handle_websocket_connection(websocket: WebSocket, batch_id: str, user_id: Optional[str] = None):
    """
    Handle WebSocket connection for batch progress updates

    Usage in FastAPI endpoint:
    @app.websocket("/batch/{batch_id}/progress")
    async def websocket_endpoint(websocket: WebSocket, batch_id: str):
        await handle_websocket_connection(websocket, batch_id)
    """
    manager = get_connection_manager()

    async with manager.connection_context(websocket, batch_id, user_id):
        try:
            # Keep connection alive and handle incoming messages
            while True:
                # Wait for client messages (heartbeat, etc.)
                data = await websocket.receive_text()

                # Handle client messages if needed
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from batch {batch_id}: {data}")

        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected for batch {batch_id}")
        except Exception as e:
            logger.error(f"WebSocket error for batch {batch_id}: {e}")
            await manager.broadcast_error(batch_id, f"Connection error: {str(e)}", "CONNECTION_ERROR")
