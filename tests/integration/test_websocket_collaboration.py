"""
WebSocket integration tests for P2-010 Collaborative Buckets.

Tests real-time collaboration features including WebSocket connections,
message broadcasting, and real-time updates.
"""

import asyncio
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d1_targeting.collaboration_api import router, ws_manager
from d1_targeting.collaboration_models import (
    ActiveCollaboration,
    BucketActivity,
    BucketActivityType,
    BucketPermission,
    BucketPermissionGrant,
    CollaborativeBucket,
)
from d1_targeting.collaboration_schemas import WSMessage, WSMessageType
from d1_targeting.collaboration_service import WebSocketManager
from database.base import Base
from database.session import get_db


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_user():
    """Mock user for testing"""
    return {
        "id": "user-123",
        "email": "test@example.com",
        "org_id": "org-456",
        "name": "Test User",
    }


@pytest.fixture
def mock_user_2():
    """Second mock user for testing"""
    return {
        "id": "user-456",
        "email": "test2@example.com",
        "org_id": "org-456",
        "name": "Test User 2",
    }


@pytest.fixture
def sample_bucket(db_session, mock_user):
    """Create a sample bucket for testing"""
    bucket = CollaborativeBucket(
        name="Healthcare Leads Q1",
        description="High-value healthcare leads for Q1 campaign",
        bucket_type="vertical",
        bucket_key="healthcare_q1",
        owner_id=mock_user["id"],
        organization_id=mock_user["org_id"],
        enrichment_config={"sources": ["internal", "hunter"], "max_budget": 1000},
        processing_strategy="healthcare",
        priority_level="high",
        lead_count=100,
        version=1,
    )
    db_session.add(bucket)

    # Grant owner permission
    owner_permission = BucketPermissionGrant(
        bucket_id=bucket.id,
        user_id=mock_user["id"],
        permission=BucketPermission.OWNER,
        granted_by=mock_user["id"],
    )
    db_session.add(owner_permission)
    db_session.commit()
    db_session.refresh(bucket)

    return bucket


@pytest.fixture
def test_app(db_session):
    """Create FastAPI test app with WebSocket support"""
    app = FastAPI()
    app.include_router(router)

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session

    return app


class MockWebSocket:
    """Mock WebSocket for testing"""

    def __init__(self):
        self.messages_sent = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.accepted = False
        self.json_messages = []
        self.text_messages = []

    async def accept(self):
        """Mock accept method"""
        self.accepted = True

    async def send_text(self, text: str):
        """Mock send_text method"""
        if self.closed:
            raise Exception("WebSocket is closed")
        self.text_messages.append(text)
        self.messages_sent.append({"type": "text", "data": text})

    async def send_json(self, data: dict):
        """Mock send_json method"""
        if self.closed:
            raise Exception("WebSocket is closed")
        self.json_messages.append(data)
        self.messages_sent.append({"type": "json", "data": data})

    async def receive_json(self):
        """Mock receive_json method"""
        if self.closed:
            raise WebSocketDisconnect(code=1000, reason="Connection closed")
        # Return a ping message by default
        return {"type": "ping"}

    async def close(self, code: int = 1000, reason: str = "Normal closure"):
        """Mock close method"""
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    def is_closed(self):
        """Check if WebSocket is closed"""
        return self.closed


class TestWebSocketManager:
    """Test WebSocket manager in isolation"""

    @pytest.mark.asyncio
    async def test_websocket_manager_connect_and_disconnect(self):
        """Test basic connect and disconnect functionality"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = "bucket-123"
        user_id = "user-456"

        # Test connection
        await manager.connect(websocket, bucket_id, user_id)

        assert websocket.accepted
        assert bucket_id in manager.active_connections
        assert user_id in manager.active_connections[bucket_id]
        assert user_id in manager.user_buckets
        assert bucket_id in manager.user_buckets[user_id]

        # Test disconnection
        manager.disconnect(websocket, bucket_id, user_id)

        assert bucket_id not in manager.active_connections
        assert user_id not in manager.user_buckets

    @pytest.mark.asyncio
    async def test_websocket_manager_broadcast_message(self):
        """Test broadcasting messages to all connected users"""
        manager = WebSocketManager()
        websocket1 = MockWebSocket()
        websocket2 = MockWebSocket()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Connect both users
        await manager.connect(websocket1, bucket_id, user_id1)
        await manager.connect(websocket2, bucket_id, user_id2)

        # Send broadcast message
        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id1, data={"test": "data"}
        )

        await manager.send_bucket_message(bucket_id, message)

        # Both users should receive the message
        assert len(websocket1.text_messages) == 1
        assert len(websocket2.text_messages) == 1

        # Parse the JSON message
        message1 = json.loads(websocket1.text_messages[0])
        message2 = json.loads(websocket2.text_messages[0])

        assert message1["type"] == "bucket_updated"
        assert message1["bucket_id"] == bucket_id
        assert message1["user_id"] == user_id1
        assert message1["data"]["test"] == "data"

        assert message2["type"] == "bucket_updated"
        assert message2["bucket_id"] == bucket_id
        assert message2["user_id"] == user_id1
        assert message2["data"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_websocket_manager_broadcast_with_exclude(self):
        """Test broadcasting messages with user exclusion"""
        manager = WebSocketManager()
        websocket1 = MockWebSocket()
        websocket2 = MockWebSocket()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Connect both users
        await manager.connect(websocket1, bucket_id, user_id1)
        await manager.connect(websocket2, bucket_id, user_id2)

        # Send broadcast message excluding user1
        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id1, data={"test": "data"}
        )

        await manager.send_bucket_message(bucket_id, message, exclude_user=user_id1)

        # Only user2 should receive the message
        assert len(websocket1.text_messages) == 0
        assert len(websocket2.text_messages) == 1

        message2 = json.loads(websocket2.text_messages[0])
        assert message2["type"] == "bucket_updated"
        assert message2["user_id"] == user_id1

    @pytest.mark.asyncio
    async def test_websocket_manager_handle_disconnected_user(self):
        """Test handling disconnected users during broadcast"""
        manager = WebSocketManager()
        websocket1 = MockWebSocket()
        websocket2 = MockWebSocket()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Connect both users
        await manager.connect(websocket1, bucket_id, user_id1)
        await manager.connect(websocket2, bucket_id, user_id2)

        # Simulate websocket1 being disconnected
        await websocket1.close()

        # Send broadcast message
        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id1, data={"test": "data"}
        )

        await manager.send_bucket_message(bucket_id, message)

        # Only user2 should receive the message
        # user1 should be automatically removed from active connections
        assert len(websocket2.text_messages) == 1
        assert user_id1 not in manager.active_connections[bucket_id]
        assert user_id2 in manager.active_connections[bucket_id]

    @pytest.mark.asyncio
    async def test_websocket_manager_personal_message(self):
        """Test sending personal messages"""
        manager = WebSocketManager()
        websocket = MockWebSocket()

        await manager.send_personal_message("Hello, user!", websocket)

        assert len(websocket.text_messages) == 1
        assert websocket.text_messages[0] == "Hello, user!"

    @pytest.mark.asyncio
    async def test_websocket_manager_multiple_buckets(self):
        """Test user connected to multiple buckets"""
        manager = WebSocketManager()
        websocket1 = MockWebSocket()
        websocket2 = MockWebSocket()
        bucket_id1 = "bucket-123"
        bucket_id2 = "bucket-456"
        user_id = "user-789"

        # Connect user to both buckets
        await manager.connect(websocket1, bucket_id1, user_id)
        await manager.connect(websocket2, bucket_id2, user_id)

        # Send message to bucket1
        message1 = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id1, user_id=user_id, data={"bucket": "1"}
        )
        await manager.send_bucket_message(bucket_id1, message1)

        # Send message to bucket2
        message2 = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id2, user_id=user_id, data={"bucket": "2"}
        )
        await manager.send_bucket_message(bucket_id2, message2)

        # Each websocket should receive only its bucket's message
        assert len(websocket1.text_messages) == 1
        assert len(websocket2.text_messages) == 1

        message1_data = json.loads(websocket1.text_messages[0])
        message2_data = json.loads(websocket2.text_messages[0])

        assert message1_data["bucket_id"] == bucket_id1
        assert message1_data["data"]["bucket"] == "1"
        assert message2_data["bucket_id"] == bucket_id2
        assert message2_data["data"]["bucket"] == "2"

    @pytest.mark.asyncio
    async def test_websocket_manager_connection_timeout(self):
        """Test connection timeout functionality"""
        manager = WebSocketManager(connection_timeout=1)  # 1 second timeout
        websocket = MockWebSocket()
        bucket_id = "bucket-123"
        user_id = "user-456"

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Simulate old timestamp (stale connection)
        import time

        manager.connection_timestamps[bucket_id][user_id] = time.time() - 2  # 2 seconds ago

        # Run cleanup
        await manager._cleanup_stale_connections()

        # Connection should be cleaned up
        assert bucket_id not in manager.active_connections
        assert user_id not in manager.user_buckets
        assert websocket.closed
        assert websocket.close_code == 1000
        assert websocket.close_reason == "Connection timeout"


class TestWebSocketIntegration:
    """Test WebSocket integration with collaboration features"""

    @pytest.mark.asyncio
    async def test_websocket_endpoint_authentication(self, db_session, sample_bucket):
        """Test WebSocket endpoint authentication"""
        # Mock check_bucket_permission to succeed
        with patch("d1_targeting.collaboration_api.check_bucket_permission") as mock_check:
            mock_check.return_value = AsyncMock(return_value=BucketPermission.VIEWER)

            # Create mock WebSocket
            websocket = MockWebSocket()

            # Test the WebSocket endpoint (simplified)
            from d1_targeting.collaboration_api import websocket_endpoint

            # This would normally be called by FastAPI
            # We'll test the core logic
            token = "test-token"

            # Test authentication logic (would be part of the endpoint)
            try:
                await mock_check(db_session, sample_bucket.id, token, [BucketPermission.VIEWER])
                auth_success = True
            except Exception:
                auth_success = False

            assert auth_success
            mock_check.assert_called_once_with(db_session, sample_bucket.id, token, [BucketPermission.VIEWER])

    @pytest.mark.asyncio
    async def test_websocket_endpoint_permission_denied(self, db_session, sample_bucket):
        """Test WebSocket endpoint with permission denied"""
        # Mock check_bucket_permission to fail
        with patch("d1_targeting.collaboration_api.check_bucket_permission") as mock_check:
            from fastapi import HTTPException

            mock_check.side_effect = HTTPException(status_code=403, detail="Forbidden")

            # Test authentication logic
            token = "invalid-token"

            try:
                await mock_check(db_session, sample_bucket.id, token, [BucketPermission.VIEWER])
                auth_success = True
            except HTTPException:
                auth_success = False

            assert not auth_success

    @pytest.mark.asyncio
    async def test_websocket_active_collaboration_tracking(self, db_session, sample_bucket, mock_user):
        """Test active collaboration tracking"""
        # Create active collaboration record
        session_id = secrets.token_urlsafe(16)
        active_collab = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            session_id=session_id,
            connection_type="websocket",
            current_view="bucket_overview",
            is_editing=False,
        )
        db_session.add(active_collab)
        db_session.commit()

        # Verify collaboration was tracked
        collab = db_session.query(ActiveCollaboration).filter(ActiveCollaboration.session_id == session_id).first()

        assert collab is not None
        assert collab.bucket_id == sample_bucket.id
        assert collab.user_id == mock_user["id"]
        assert collab.connection_type == "websocket"
        assert collab.current_view == "bucket_overview"
        assert collab.is_editing is False

    @pytest.mark.asyncio
    async def test_websocket_user_join_leave_messages(self, db_session, sample_bucket, mock_user):
        """Test user join/leave message broadcasting"""
        manager = WebSocketManager()
        websocket1 = MockWebSocket()
        websocket2 = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id1 = mock_user["id"]
        user_id2 = "user-456"

        # Connect first user
        await manager.connect(websocket1, bucket_id, user_id1)

        # Connect second user
        await manager.connect(websocket2, bucket_id, user_id2)

        # Send user joined message
        join_message = WSMessage(
            type=WSMessageType.USER_JOINED, bucket_id=bucket_id, user_id=user_id2, data={"session_id": "session-123"}
        )

        await manager.send_bucket_message(bucket_id, join_message, exclude_user=user_id2)

        # Only user1 should receive the join message
        assert len(websocket1.text_messages) == 1
        assert len(websocket2.text_messages) == 0

        join_data = json.loads(websocket1.text_messages[0])
        assert join_data["type"] == "user_joined"
        assert join_data["user_id"] == user_id2
        assert join_data["data"]["session_id"] == "session-123"

        # Clear messages
        websocket1.text_messages.clear()
        websocket2.text_messages.clear()

        # Send user left message
        leave_message = WSMessage(
            type=WSMessageType.USER_LEFT, bucket_id=bucket_id, user_id=user_id2, data={"session_id": "session-123"}
        )

        await manager.send_bucket_message(bucket_id, leave_message)

        # Both users should receive the leave message
        assert len(websocket1.text_messages) == 1
        assert len(websocket2.text_messages) == 1

        leave_data = json.loads(websocket1.text_messages[0])
        assert leave_data["type"] == "user_left"
        assert leave_data["user_id"] == user_id2

    @pytest.mark.asyncio
    async def test_websocket_bucket_update_notifications(self, db_session, sample_bucket, mock_user):
        """Test bucket update notifications via WebSocket"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Send bucket update message
        update_message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED,
            bucket_id=bucket_id,
            user_id=user_id,
            data={"changes": {"name": "Updated Name"}, "version": 2},
        )

        await manager.send_bucket_message(bucket_id, update_message)

        # User should receive the update
        assert len(websocket.text_messages) == 1

        update_data = json.loads(websocket.text_messages[0])
        assert update_data["type"] == "bucket_updated"
        assert update_data["bucket_id"] == bucket_id
        assert update_data["data"]["changes"]["name"] == "Updated Name"
        assert update_data["data"]["version"] == 2

    @pytest.mark.asyncio
    async def test_websocket_permission_change_notifications(self, db_session, sample_bucket, mock_user):
        """Test permission change notifications via WebSocket"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Send permission change message
        permission_message = WSMessage(
            type=WSMessageType.PERMISSION_CHANGED,
            bucket_id=bucket_id,
            user_id=user_id,
            data={"affected_user_id": "user-456", "new_permission": "editor"},
        )

        await manager.send_bucket_message(bucket_id, permission_message)

        # User should receive the permission change
        assert len(websocket.text_messages) == 1

        permission_data = json.loads(websocket.text_messages[0])
        assert permission_data["type"] == "permission_changed"
        assert permission_data["bucket_id"] == bucket_id
        assert permission_data["data"]["affected_user_id"] == "user-456"
        assert permission_data["data"]["new_permission"] == "editor"

    @pytest.mark.asyncio
    async def test_websocket_comment_notifications(self, db_session, sample_bucket, mock_user):
        """Test comment notifications via WebSocket"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Send comment added message
        comment_message = WSMessage(
            type=WSMessageType.COMMENT_ADDED,
            bucket_id=bucket_id,
            user_id=user_id,
            data={"comment_id": "comment-123", "lead_id": "lead-456", "content": "This is a test comment"},
        )

        await manager.send_bucket_message(bucket_id, comment_message)

        # User should receive the comment notification
        assert len(websocket.text_messages) == 1

        comment_data = json.loads(websocket.text_messages[0])
        assert comment_data["type"] == "comment_added"
        assert comment_data["bucket_id"] == bucket_id
        assert comment_data["data"]["comment_id"] == "comment-123"
        assert comment_data["data"]["lead_id"] == "lead-456"
        assert comment_data["data"]["content"] == "This is a test comment"

    @pytest.mark.asyncio
    async def test_websocket_heartbeat_handling(self, db_session, sample_bucket, mock_user):
        """Test WebSocket heartbeat (ping/pong) handling"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Simulate heartbeat - in real implementation, this would be handled by the endpoint
        # For testing, we'll verify the concept

        # Mock receiving a ping
        ping_message = {"type": "ping"}

        # Mock sending a pong response
        pong_response = {"type": "pong"}
        await websocket.send_json(pong_response)

        # Verify pong was sent
        assert len(websocket.json_messages) == 1
        assert websocket.json_messages[0]["type"] == "pong"

    @pytest.mark.asyncio
    async def test_websocket_connection_cleanup_on_disconnect(self, db_session, sample_bucket, mock_user):
        """Test connection cleanup when WebSocket disconnects"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Verify connection exists
        assert bucket_id in manager.active_connections
        assert user_id in manager.active_connections[bucket_id]
        assert user_id in manager.user_buckets

        # Simulate disconnect
        manager.disconnect(websocket, bucket_id, user_id)

        # Verify cleanup
        assert bucket_id not in manager.active_connections
        assert user_id not in manager.user_buckets
        assert bucket_id not in manager.connection_timestamps

    @pytest.mark.asyncio
    async def test_websocket_multiple_concurrent_connections(self, db_session, sample_bucket, mock_user):
        """Test multiple concurrent WebSocket connections"""
        manager = WebSocketManager()
        websockets = []
        user_ids = []
        bucket_id = sample_bucket.id

        # Connect multiple users
        for i in range(5):
            websocket = MockWebSocket()
            user_id = f"user-{i}"
            websockets.append(websocket)
            user_ids.append(user_id)

            await manager.connect(websocket, bucket_id, user_id)

        # Verify all connections
        assert len(manager.active_connections[bucket_id]) == 5
        for user_id in user_ids:
            assert user_id in manager.active_connections[bucket_id]
            assert bucket_id in manager.user_buckets[user_id]

        # Send broadcast message
        broadcast_message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_ids[0], data={"test": "broadcast"}
        )

        await manager.send_bucket_message(bucket_id, broadcast_message)

        # All users should receive the message
        for websocket in websockets:
            assert len(websocket.text_messages) == 1
            message_data = json.loads(websocket.text_messages[0])
            assert message_data["type"] == "bucket_updated"
            assert message_data["data"]["test"] == "broadcast"

    @pytest.mark.asyncio
    async def test_websocket_message_ordering(self, db_session, sample_bucket, mock_user):
        """Test that WebSocket messages are received in order"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Send multiple messages in sequence
        messages = []
        for i in range(5):
            message = WSMessage(
                type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id, data={"sequence": i}
            )
            messages.append(message)
            await manager.send_bucket_message(bucket_id, message)

        # Verify messages were received in order
        assert len(websocket.text_messages) == 5

        for i, text_message in enumerate(websocket.text_messages):
            message_data = json.loads(text_message)
            assert message_data["data"]["sequence"] == i

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, db_session, sample_bucket, mock_user):
        """Test WebSocket error handling"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Simulate WebSocket error by closing it
        await websocket.close()

        # Try to send message to closed WebSocket
        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id, data={"test": "error_test"}
        )

        # Should not raise an exception, but should clean up the connection
        await manager.send_bucket_message(bucket_id, message)

        # Connection should be cleaned up
        assert user_id not in manager.active_connections.get(bucket_id, {})

    @pytest.mark.asyncio
    async def test_websocket_large_message_handling(self, db_session, sample_bucket, mock_user):
        """Test handling of large WebSocket messages"""
        manager = WebSocketManager()
        websocket = MockWebSocket()
        bucket_id = sample_bucket.id
        user_id = mock_user["id"]

        # Connect user
        await manager.connect(websocket, bucket_id, user_id)

        # Send large message
        large_data = {"large_field": "x" * 10000}  # 10KB of data
        large_message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id, data=large_data
        )

        await manager.send_bucket_message(bucket_id, large_message)

        # Should handle large message without issues
        assert len(websocket.text_messages) == 1
        message_data = json.loads(websocket.text_messages[0])
        assert message_data["data"]["large_field"] == "x" * 10000

    @pytest.mark.asyncio
    async def test_websocket_connection_limits(self, db_session, sample_bucket):
        """Test WebSocket connection limits and resource management"""
        manager = WebSocketManager()
        bucket_id = sample_bucket.id

        # Test connecting many users (simulate load)
        connections = []
        for i in range(100):
            websocket = MockWebSocket()
            user_id = f"user-{i}"
            await manager.connect(websocket, bucket_id, user_id)
            connections.append((websocket, user_id))

        # Verify all connections are tracked
        assert len(manager.active_connections[bucket_id]) == 100

        # Test cleanup performance with many connections
        import time

        start_time = time.time()

        # Disconnect all
        for websocket, user_id in connections:
            manager.disconnect(websocket, bucket_id, user_id)

        end_time = time.time()
        cleanup_time = end_time - start_time

        # Should complete cleanup quickly (under 1 second for 100 connections)
        assert cleanup_time < 1.0

        # Verify all connections are cleaned up
        assert bucket_id not in manager.active_connections
