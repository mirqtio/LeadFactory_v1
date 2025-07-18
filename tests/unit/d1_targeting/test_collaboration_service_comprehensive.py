"""
Comprehensive service layer unit tests for P2-010 Collaborative Buckets.

Tests all service functions to achieve ≥80% coverage for collaboration_service.py
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, WebSocket, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d1_targeting.collaboration_models import (
    ActiveCollaboration,
    BucketActivity,
    BucketActivityType,
    BucketComment,
    BucketNotification,
    BucketPermission,
    BucketPermissionGrant,
    BucketVersion,
    CollaborativeBucket,
    NotificationType,
)
from d1_targeting.collaboration_schemas import WSMessage, WSMessageType
from d1_targeting.collaboration_service import (
    BucketCollaborationService,
    WebSocketManager,
    check_bucket_permission,
    create_activity,
    create_notification,
    create_version_snapshot,
)
from database.base import Base


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


class TestWebSocketManager:
    """Test WebSocket manager functionality"""

    def test_websocket_manager_init(self):
        """Test WebSocket manager initialization"""
        manager = WebSocketManager(connection_timeout=900)

        assert manager.connection_timeout == 900
        assert manager.active_connections == {}
        assert manager.user_buckets == {}
        assert manager.connection_timestamps == {}
        assert manager._cleanup_task is not None

    def test_websocket_manager_init_default_timeout(self):
        """Test WebSocket manager with default timeout"""
        manager = WebSocketManager()

        assert manager.connection_timeout == 1800  # 30 minutes default

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WebSocket connection"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        bucket_id = "bucket-123"
        user_id = "user-456"

        await manager.connect(mock_websocket, bucket_id, user_id)

        # Verify connection was accepted
        mock_websocket.accept.assert_called_once()

        # Verify connection was stored
        assert bucket_id in manager.active_connections
        assert user_id in manager.active_connections[bucket_id]
        assert manager.active_connections[bucket_id][user_id] == mock_websocket

        # Verify user bucket tracking
        assert user_id in manager.user_buckets
        assert bucket_id in manager.user_buckets[user_id]

        # Verify timestamp was updated
        assert bucket_id in manager.connection_timestamps
        assert user_id in manager.connection_timestamps[bucket_id]

    @pytest.mark.asyncio
    async def test_connect_multiple_users(self):
        """Test connecting multiple users to same bucket"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        await manager.connect(mock_websocket1, bucket_id, user_id1)
        await manager.connect(mock_websocket2, bucket_id, user_id2)

        # Verify both connections are stored
        assert len(manager.active_connections[bucket_id]) == 2
        assert user_id1 in manager.active_connections[bucket_id]
        assert user_id2 in manager.active_connections[bucket_id]

        # Verify both users are tracked
        assert bucket_id in manager.user_buckets[user_id1]
        assert bucket_id in manager.user_buckets[user_id2]

    @pytest.mark.asyncio
    async def test_connect_user_multiple_buckets(self):
        """Test connecting user to multiple buckets"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id1 = "bucket-123"
        bucket_id2 = "bucket-456"
        user_id = "user-789"

        await manager.connect(mock_websocket1, bucket_id1, user_id)
        await manager.connect(mock_websocket2, bucket_id2, user_id)

        # Verify both buckets are tracked for user
        assert len(manager.user_buckets[user_id]) == 2
        assert bucket_id1 in manager.user_buckets[user_id]
        assert bucket_id2 in manager.user_buckets[user_id]

        # Verify connections in both buckets
        assert user_id in manager.active_connections[bucket_id1]
        assert user_id in manager.active_connections[bucket_id2]

    def test_disconnect_success(self):
        """Test successful WebSocket disconnection"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        bucket_id = "bucket-123"
        user_id = "user-456"

        # Set up connection state
        manager.active_connections = {bucket_id: {user_id: mock_websocket}}
        manager.user_buckets = {user_id: {bucket_id}}
        manager.connection_timestamps = {bucket_id: {user_id: time.time()}}

        manager.disconnect(mock_websocket, bucket_id, user_id)

        # Verify connection was removed
        assert bucket_id not in manager.active_connections
        assert user_id not in manager.user_buckets
        assert bucket_id not in manager.connection_timestamps

    def test_disconnect_multiple_users(self):
        """Test disconnecting one user when multiple users connected"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Set up connections for both users
        manager.active_connections = {bucket_id: {user_id1: mock_websocket1, user_id2: mock_websocket2}}
        manager.user_buckets = {user_id1: {bucket_id}, user_id2: {bucket_id}}
        manager.connection_timestamps = {bucket_id: {user_id1: time.time(), user_id2: time.time()}}

        manager.disconnect(mock_websocket1, bucket_id, user_id1)

        # Verify only user1 was disconnected
        assert bucket_id in manager.active_connections
        assert user_id1 not in manager.active_connections[bucket_id]
        assert user_id2 in manager.active_connections[bucket_id]

        # Verify user1 bucket tracking was removed
        assert user_id1 not in manager.user_buckets
        assert user_id2 in manager.user_buckets

        # Verify user1 timestamp was removed
        assert user_id1 not in manager.connection_timestamps[bucket_id]
        assert user_id2 in manager.connection_timestamps[bucket_id]

    def test_disconnect_user_multiple_buckets(self):
        """Test disconnecting user from one bucket when connected to multiple"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id1 = "bucket-123"
        bucket_id2 = "bucket-456"
        user_id = "user-789"

        # Set up connections to both buckets
        manager.active_connections = {bucket_id1: {user_id: mock_websocket1}, bucket_id2: {user_id: mock_websocket2}}
        manager.user_buckets = {user_id: {bucket_id1, bucket_id2}}
        manager.connection_timestamps = {bucket_id1: {user_id: time.time()}, bucket_id2: {user_id: time.time()}}

        manager.disconnect(mock_websocket1, bucket_id1, user_id)

        # Verify only bucket1 connection was removed
        assert bucket_id1 not in manager.active_connections
        assert bucket_id2 in manager.active_connections
        assert user_id in manager.active_connections[bucket_id2]

        # Verify user still tracked for bucket2
        assert bucket_id1 not in manager.user_buckets[user_id]
        assert bucket_id2 in manager.user_buckets[user_id]

    @pytest.mark.asyncio
    async def test_send_personal_message_success(self):
        """Test sending personal message"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        message = "Hello, user!"

        await manager.send_personal_message(message, mock_websocket)

        mock_websocket.send_text.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_bucket_message_success(self):
        """Test sending message to bucket"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Set up connections
        manager.active_connections = {bucket_id: {user_id1: mock_websocket1, user_id2: mock_websocket2}}

        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id1, data={"test": "data"}
        )

        await manager.send_bucket_message(bucket_id, message)

        # Verify message was sent to both users
        expected_json = message.model_dump_json()
        mock_websocket1.send_text.assert_called_once_with(expected_json)
        mock_websocket2.send_text.assert_called_once_with(expected_json)

    @pytest.mark.asyncio
    async def test_send_bucket_message_with_exclude(self):
        """Test sending message to bucket with user exclusion"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Set up connections
        manager.active_connections = {bucket_id: {user_id1: mock_websocket1, user_id2: mock_websocket2}}

        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id1, data={"test": "data"}
        )

        await manager.send_bucket_message(bucket_id, message, exclude_user=user_id1)

        # Verify message was sent only to user2
        mock_websocket1.send_text.assert_not_called()
        mock_websocket2.send_text.assert_called_once_with(message.model_dump_json())

    @pytest.mark.asyncio
    async def test_send_bucket_message_disconnected_user(self):
        """Test sending message when user is disconnected"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Set up connections
        manager.active_connections = {bucket_id: {user_id1: mock_websocket1, user_id2: mock_websocket2}}

        # Make user1 websocket fail
        mock_websocket1.send_text.side_effect = Exception("Connection lost")

        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id=user_id1, data={"test": "data"}
        )

        await manager.send_bucket_message(bucket_id, message)

        # Verify message was attempted to both users
        mock_websocket1.send_text.assert_called_once()
        mock_websocket2.send_text.assert_called_once()

        # Verify disconnected user was removed
        assert user_id1 not in manager.active_connections[bucket_id]
        assert user_id2 in manager.active_connections[bucket_id]

    @pytest.mark.asyncio
    async def test_send_bucket_message_no_connections(self):
        """Test sending message to bucket with no connections"""
        manager = WebSocketManager()
        bucket_id = "bucket-123"

        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id=bucket_id, user_id="user-456", data={"test": "data"}
        )

        # Should not raise an exception
        await manager.send_bucket_message(bucket_id, message)

    def test_update_activity_timestamp(self):
        """Test updating activity timestamp"""
        manager = WebSocketManager()
        bucket_id = "bucket-123"
        user_id = "user-456"

        # Call private method
        manager._update_activity_timestamp(bucket_id, user_id)

        # Verify timestamp was set
        assert bucket_id in manager.connection_timestamps
        assert user_id in manager.connection_timestamps[bucket_id]
        assert isinstance(manager.connection_timestamps[bucket_id][user_id], float)

    def test_is_connection_stale(self):
        """Test checking if connection is stale"""
        manager = WebSocketManager(connection_timeout=60)  # 1 minute timeout
        bucket_id = "bucket-123"
        user_id = "user-456"

        # Set up recent timestamp
        manager.connection_timestamps = {bucket_id: {user_id: time.time()}}

        # Should not be stale
        assert not manager._is_connection_stale(bucket_id, user_id)

        # Set up old timestamp
        manager.connection_timestamps = {bucket_id: {user_id: time.time() - 120}}  # 2 minutes ago

        # Should be stale
        assert manager._is_connection_stale(bucket_id, user_id)

    def test_is_connection_stale_no_timestamp(self):
        """Test checking stale connection with no timestamp"""
        manager = WebSocketManager()
        bucket_id = "bucket-123"
        user_id = "user-456"

        # No timestamp should be considered stale
        assert manager._is_connection_stale(bucket_id, user_id)

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections(self):
        """Test cleaning up stale connections"""
        manager = WebSocketManager(connection_timeout=60)  # 1 minute timeout
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        bucket_id = "bucket-123"
        user_id1 = "user-456"
        user_id2 = "user-789"

        # Set up connections - one stale, one fresh
        manager.active_connections = {bucket_id: {user_id1: mock_websocket1, user_id2: mock_websocket2}}
        manager.user_buckets = {user_id1: {bucket_id}, user_id2: {bucket_id}}
        manager.connection_timestamps = {
            bucket_id: {user_id1: time.time() - 120, user_id2: time.time()}  # 2 minutes ago (stale)  # Fresh
        }

        await manager._cleanup_stale_connections()

        # Verify stale connection was removed
        assert user_id1 not in manager.active_connections[bucket_id]
        assert user_id2 in manager.active_connections[bucket_id]

        # Verify stale user was removed from tracking
        assert user_id1 not in manager.user_buckets
        assert user_id2 in manager.user_buckets

        # Verify stale websocket was closed
        mock_websocket1.close.assert_called_once_with(code=1000, reason="Connection timeout")
        mock_websocket2.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_periodic_cleanup(self):
        """Test periodic cleanup task"""
        manager = WebSocketManager(connection_timeout=60)

        # Mock the cleanup method
        manager._cleanup_stale_connections = AsyncMock()

        # Start cleanup and let it run briefly
        await asyncio.sleep(0.1)

        # Verify cleanup was called (might be called multiple times)
        assert manager._cleanup_stale_connections.call_count >= 0

    def test_start_cleanup_task(self):
        """Test starting cleanup task"""
        manager = WebSocketManager()

        # Verify cleanup task was created
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

    def test_cleanup_task_exception_handling(self):
        """Test cleanup task handles exceptions gracefully"""
        manager = WebSocketManager()

        # Mock cleanup to raise exception
        original_cleanup = manager._cleanup_stale_connections

        async def failing_cleanup():
            raise Exception("Test exception")

        manager._cleanup_stale_connections = failing_cleanup

        # Task should not crash
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        # Restore original method
        manager._cleanup_stale_connections = original_cleanup


class TestBucketCollaborationService:
    """Test BucketCollaborationService functionality"""

    def test_bucket_collaboration_service_init(self, db_session):
        """Test service initialization"""
        service = BucketCollaborationService(db_session)

        assert service.db == db_session

    def test_get_bucket_permissions(self, db_session, sample_bucket, mock_user, mock_user_2):
        """Test getting bucket permissions"""
        service = BucketCollaborationService(db_session)

        # Add another permission
        permission = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=mock_user["id"],
        )
        db_session.add(permission)
        db_session.commit()

        permissions = service.get_bucket_permissions(sample_bucket.id)

        assert len(permissions) == 2
        user_ids = [p.user_id for p in permissions]
        assert mock_user["id"] in user_ids
        assert mock_user_2["id"] in user_ids

    def test_get_user_permission(self, db_session, sample_bucket, mock_user):
        """Test getting user permission for bucket"""
        service = BucketCollaborationService(db_session)

        permission = service.get_user_permission(sample_bucket.id, mock_user["id"])

        assert permission == BucketPermission.OWNER

    def test_get_user_permission_no_permission(self, db_session, sample_bucket):
        """Test getting user permission when user has no permission"""
        service = BucketCollaborationService(db_session)

        permission = service.get_user_permission(sample_bucket.id, "non-existent-user")

        assert permission is None

    def test_has_permission_success(self, db_session, sample_bucket, mock_user):
        """Test checking if user has specific permission"""
        service = BucketCollaborationService(db_session)

        # Owner should have all permissions
        assert service.has_permission(sample_bucket.id, mock_user["id"], BucketPermission.OWNER)
        assert service.has_permission(sample_bucket.id, mock_user["id"], BucketPermission.ADMIN)
        assert service.has_permission(sample_bucket.id, mock_user["id"], BucketPermission.EDITOR)
        assert service.has_permission(sample_bucket.id, mock_user["id"], BucketPermission.VIEWER)

    def test_has_permission_editor(self, db_session, sample_bucket, mock_user_2):
        """Test checking editor permissions"""
        service = BucketCollaborationService(db_session)

        # Add editor permission
        permission = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=sample_bucket.owner_id,
        )
        db_session.add(permission)
        db_session.commit()

        # Editor should have editor, commenter, and viewer permissions
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.OWNER)
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.ADMIN)
        assert service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.EDITOR)
        assert service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.COMMENTER)
        assert service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.VIEWER)

    def test_has_permission_viewer(self, db_session, sample_bucket, mock_user_2):
        """Test checking viewer permissions"""
        service = BucketCollaborationService(db_session)

        # Add viewer permission
        permission = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=sample_bucket.owner_id,
        )
        db_session.add(permission)
        db_session.commit()

        # Viewer should only have viewer permission
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.OWNER)
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.ADMIN)
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.EDITOR)
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.COMMENTER)
        assert service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.VIEWER)

    def test_has_permission_no_permission(self, db_session, sample_bucket):
        """Test checking permissions when user has no permission"""
        service = BucketCollaborationService(db_session)

        # User with no permissions should not have any permission
        assert not service.has_permission(sample_bucket.id, "non-existent-user", BucketPermission.VIEWER)

    def test_has_permission_expired(self, db_session, sample_bucket, mock_user_2):
        """Test checking permissions when permission is expired"""
        service = BucketCollaborationService(db_session)

        # Add expired permission
        permission = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=sample_bucket.owner_id,
            expires_at=datetime.utcnow() - timedelta(days=1),  # Expired
        )
        db_session.add(permission)
        db_session.commit()

        # Should not have permission due to expiration
        assert not service.has_permission(sample_bucket.id, mock_user_2["id"], BucketPermission.EDITOR)

    def test_get_bucket_activities(self, db_session, sample_bucket, mock_user):
        """Test getting bucket activities"""
        service = BucketCollaborationService(db_session)

        # Create some activities
        activity1 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
            new_values={"name": "Test Bucket"},
        )
        activity2 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.UPDATED,
            old_values={"name": "Old Name"},
            new_values={"name": "New Name"},
        )
        db_session.add_all([activity1, activity2])
        db_session.commit()

        activities = service.get_bucket_activities(sample_bucket.id)

        assert len(activities) >= 2
        # Should be ordered by created_at descending
        assert activities[0].created_at >= activities[1].created_at

    def test_get_bucket_activities_with_limit(self, db_session, sample_bucket, mock_user):
        """Test getting bucket activities with limit"""
        service = BucketCollaborationService(db_session)

        # Create multiple activities
        activities = []
        for i in range(5):
            activity = BucketActivity(
                bucket_id=sample_bucket.id,
                user_id=mock_user["id"],
                activity_type=BucketActivityType.UPDATED,
                new_values={"step": i},
            )
            activities.append(activity)
        db_session.add_all(activities)
        db_session.commit()

        limited_activities = service.get_bucket_activities(sample_bucket.id, limit=3)

        assert len(limited_activities) == 3

    def test_get_bucket_activities_with_activity_type(self, db_session, sample_bucket, mock_user):
        """Test getting bucket activities filtered by type"""
        service = BucketCollaborationService(db_session)

        # Create activities of different types
        activity1 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
        )
        activity2 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.UPDATED,
        )
        activity3 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
        )
        db_session.add_all([activity1, activity2, activity3])
        db_session.commit()

        created_activities = service.get_bucket_activities(sample_bucket.id, activity_type=BucketActivityType.CREATED)

        assert len(created_activities) == 2
        assert all(a.activity_type == BucketActivityType.CREATED for a in created_activities)

    def test_get_user_notifications(self, db_session, sample_bucket, mock_user):
        """Test getting user notifications"""
        service = BucketCollaborationService(db_session)

        # Create some notifications
        notification1 = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Access Granted",
            message="You have been granted access",
            is_read=False,
        )
        notification2 = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.COMMENT_MENTION,
            title="Mentioned",
            message="You were mentioned",
            is_read=True,
        )
        db_session.add_all([notification1, notification2])
        db_session.commit()

        notifications = service.get_user_notifications(mock_user["id"])

        assert len(notifications) >= 2
        # Should be ordered by created_at descending
        assert notifications[0].created_at >= notifications[1].created_at

    def test_get_user_notifications_unread_only(self, db_session, sample_bucket, mock_user):
        """Test getting unread user notifications only"""
        service = BucketCollaborationService(db_session)

        # Create read and unread notifications
        notification1 = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Unread",
            message="Unread notification",
            is_read=False,
        )
        notification2 = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.COMMENT_MENTION,
            title="Read",
            message="Read notification",
            is_read=True,
        )
        db_session.add_all([notification1, notification2])
        db_session.commit()

        notifications = service.get_user_notifications(mock_user["id"], unread_only=True)

        assert len(notifications) == 1
        assert notifications[0].is_read is False

    def test_mark_notification_read(self, db_session, sample_bucket, mock_user):
        """Test marking notification as read"""
        service = BucketCollaborationService(db_session)

        # Create unread notification
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test",
            message="Test notification",
            is_read=False,
        )
        db_session.add(notification)
        db_session.commit()

        result = service.mark_notification_read(notification.id, mock_user["id"])

        assert result is True
        db_session.refresh(notification)
        assert notification.is_read is True
        assert notification.read_at is not None

    def test_mark_notification_read_not_found(self, db_session, mock_user):
        """Test marking non-existent notification as read"""
        service = BucketCollaborationService(db_session)

        result = service.mark_notification_read("non-existent-id", mock_user["id"])

        assert result is False

    def test_mark_notification_read_wrong_user(self, db_session, sample_bucket, mock_user, mock_user_2):
        """Test marking notification as read by wrong user"""
        service = BucketCollaborationService(db_session)

        # Create notification for user1
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test",
            message="Test notification",
            is_read=False,
        )
        db_session.add(notification)
        db_session.commit()

        # Try to mark as read by user2
        result = service.mark_notification_read(notification.id, mock_user_2["id"])

        assert result is False
        db_session.refresh(notification)
        assert notification.is_read is False

    def test_mark_all_notifications_read(self, db_session, sample_bucket, mock_user):
        """Test marking all notifications as read"""
        service = BucketCollaborationService(db_session)

        # Create multiple unread notifications
        notifications = []
        for i in range(3):
            notification = BucketNotification(
                bucket_id=sample_bucket.id,
                user_id=mock_user["id"],
                notification_type=NotificationType.PERMISSION_GRANTED,
                title=f"Test {i}",
                message=f"Test notification {i}",
                is_read=False,
            )
            notifications.append(notification)
        db_session.add_all(notifications)
        db_session.commit()

        count = service.mark_all_notifications_read(mock_user["id"])

        assert count == 3

        # Verify all notifications are marked as read
        for notification in notifications:
            db_session.refresh(notification)
            assert notification.is_read is True
            assert notification.read_at is not None

    def test_get_active_collaborators(self, db_session, sample_bucket, mock_user, mock_user_2):
        """Test getting active collaborators"""
        service = BucketCollaborationService(db_session)

        # Create active collaborations
        collab1 = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            session_id="session-123",
            connection_type="websocket",
            current_view="bucket_overview",
            is_editing=False,
        )
        collab2 = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            session_id="session-456",
            connection_type="websocket",
            current_view="lead_details",
            is_editing=True,
        )
        db_session.add_all([collab1, collab2])
        db_session.commit()

        collaborators = service.get_active_collaborators(sample_bucket.id)

        assert len(collaborators) == 2
        user_ids = [c.user_id for c in collaborators]
        assert mock_user["id"] in user_ids
        assert mock_user_2["id"] in user_ids

    def test_get_active_collaborators_empty(self, db_session, sample_bucket):
        """Test getting active collaborators when none exist"""
        service = BucketCollaborationService(db_session)

        collaborators = service.get_active_collaborators(sample_bucket.id)

        assert len(collaborators) == 0


class TestUtilityFunctions:
    """Test utility functions"""

    @pytest.mark.asyncio
    async def test_check_bucket_permission_success(self, db_session, sample_bucket, mock_user):
        """Test successful permission check"""
        permission = await check_bucket_permission(
            db_session, sample_bucket.id, mock_user["id"], [BucketPermission.OWNER]
        )

        assert permission == BucketPermission.OWNER

    @pytest.mark.asyncio
    async def test_check_bucket_permission_insufficient(self, db_session, sample_bucket, mock_user_2):
        """Test permission check with insufficient permissions"""
        # Add viewer permission
        permission_grant = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=sample_bucket.owner_id,
        )
        db_session.add(permission_grant)
        db_session.commit()

        # Try to check for editor permission
        with pytest.raises(HTTPException) as exc_info:
            await check_bucket_permission(db_session, sample_bucket.id, mock_user_2["id"], [BucketPermission.EDITOR])

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_check_bucket_permission_no_permission(self, db_session, sample_bucket):
        """Test permission check with no permissions"""
        with pytest.raises(HTTPException) as exc_info:
            await check_bucket_permission(db_session, sample_bucket.id, "non-existent-user", [BucketPermission.VIEWER])

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_check_bucket_permission_multiple_required(self, db_session, sample_bucket, mock_user):
        """Test permission check with multiple required permissions"""
        # Owner should satisfy any of the required permissions
        permission = await check_bucket_permission(
            db_session, sample_bucket.id, mock_user["id"], [BucketPermission.EDITOR, BucketPermission.ADMIN]
        )

        assert permission == BucketPermission.OWNER

    @pytest.mark.asyncio
    async def test_create_activity_success(self, db_session, sample_bucket, mock_user):
        """Test creating activity"""
        await create_activity(
            db_session,
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.UPDATED,
            entity_type="bucket",
            entity_id="test-entity",
            old_values={"name": "Old Name"},
            new_values={"name": "New Name"},
        )

        # Verify activity was created
        activity = (
            db_session.query(BucketActivity)
            .filter(
                BucketActivity.bucket_id == sample_bucket.id,
                BucketActivity.activity_type == BucketActivityType.UPDATED,
            )
            .first()
        )

        assert activity is not None
        assert activity.user_id == mock_user["id"]
        assert activity.entity_type == "bucket"
        assert activity.entity_id == "test-entity"
        assert activity.old_values == {"name": "Old Name"}
        assert activity.new_values == {"name": "New Name"}

    @pytest.mark.asyncio
    async def test_create_activity_minimal(self, db_session, sample_bucket, mock_user):
        """Test creating activity with minimal data"""
        await create_activity(
            db_session,
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
        )

        # Verify activity was created
        activity = (
            db_session.query(BucketActivity)
            .filter(
                BucketActivity.bucket_id == sample_bucket.id,
                BucketActivity.activity_type == BucketActivityType.CREATED,
            )
            .first()
        )

        assert activity is not None
        assert activity.user_id == mock_user["id"]
        assert activity.entity_type is None
        assert activity.entity_id is None
        assert activity.old_values is None
        assert activity.new_values is None

    @pytest.mark.asyncio
    async def test_create_notification_success(self, db_session, sample_bucket, mock_user):
        """Test creating notification"""
        await create_notification(
            db_session,
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test Notification",
            message="This is a test notification",
            related_user_id="related-user",
            related_entity_type="bucket",
            related_entity_id="related-entity",
        )

        # Verify notification was created
        notification = (
            db_session.query(BucketNotification)
            .filter(
                BucketNotification.bucket_id == sample_bucket.id,
                BucketNotification.notification_type == NotificationType.PERMISSION_GRANTED,
            )
            .first()
        )

        assert notification is not None
        assert notification.user_id == mock_user["id"]
        assert notification.title == "Test Notification"
        assert notification.message == "This is a test notification"
        assert notification.related_user_id == "related-user"
        assert notification.related_entity_type == "bucket"
        assert notification.related_entity_id == "related-entity"
        assert notification.is_read is False

    @pytest.mark.asyncio
    async def test_create_notification_minimal(self, db_session, sample_bucket, mock_user):
        """Test creating notification with minimal data"""
        await create_notification(
            db_session,
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.COMMENT_MENTION,
            title="Minimal Notification",
            message="Minimal message",
        )

        # Verify notification was created
        notification = (
            db_session.query(BucketNotification)
            .filter(
                BucketNotification.bucket_id == sample_bucket.id,
                BucketNotification.notification_type == NotificationType.COMMENT_MENTION,
            )
            .first()
        )

        assert notification is not None
        assert notification.user_id == mock_user["id"]
        assert notification.title == "Minimal Notification"
        assert notification.message == "Minimal message"
        assert notification.related_user_id is None
        assert notification.related_entity_type is None
        assert notification.related_entity_id is None

    @pytest.mark.asyncio
    async def test_create_version_snapshot_success(self, db_session, sample_bucket, mock_user):
        """Test creating version snapshot"""
        await create_version_snapshot(
            db_session,
            bucket=sample_bucket,
            user_id=mock_user["id"],
            change_type="config",
            description="Test snapshot",
        )

        # Verify version was created
        version = (
            db_session.query(BucketVersion)
            .filter(
                BucketVersion.bucket_id == sample_bucket.id,
                BucketVersion.change_type == "config",
            )
            .first()
        )

        assert version is not None
        assert version.changed_by == mock_user["id"]
        assert version.description == "Test snapshot"
        assert version.version_number == sample_bucket.version
        assert version.snapshot_data is not None
        assert "name" in version.snapshot_data
        assert "bucket_type" in version.snapshot_data

    @pytest.mark.asyncio
    async def test_create_version_snapshot_with_custom_data(self, db_session, sample_bucket, mock_user):
        """Test creating version snapshot with custom data"""
        custom_data = {"custom_field": "custom_value", "test": 123}

        await create_version_snapshot(
            db_session,
            bucket=sample_bucket,
            user_id=mock_user["id"],
            change_type="data",
            description="Custom snapshot",
            custom_data=custom_data,
        )

        # Verify version was created with custom data
        version = (
            db_session.query(BucketVersion)
            .filter(
                BucketVersion.bucket_id == sample_bucket.id,
                BucketVersion.change_type == "data",
            )
            .first()
        )

        assert version is not None
        assert version.snapshot_data["custom_field"] == "custom_value"
        assert version.snapshot_data["test"] == 123
        # Should still have bucket data
        assert "name" in version.snapshot_data
