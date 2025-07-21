"""
Basic coverage boost tests for P2-010 Collaborative Buckets.

Simple tests to increase coverage for collaboration API and service files.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d1_targeting.collaboration_models import (
    ActiveCollaboration,
    BucketActivity,
    BucketActivityType,
    BucketNotification,
    BucketPermission,
    BucketPermissionGrant,
    CollaborativeBucket,
    NotificationType,
)
from d1_targeting.collaboration_schemas import WSMessage, WSMessageType
from d1_targeting.collaboration_service import BucketCollaborationService, WebSocketManager
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
def sample_bucket(db_session, mock_user):
    """Create a sample bucket for testing"""
    bucket = CollaborativeBucket(
        name="Test Bucket",
        description="A test bucket",
        bucket_type="vertical",
        bucket_key="test_key",
        owner_id=mock_user["id"],
        organization_id=mock_user["org_id"],
        version=1,
    )
    db_session.add(bucket)

    # Grant owner permission
    permission = BucketPermissionGrant(
        bucket_id=bucket.id,
        user_id=mock_user["id"],
        permission=BucketPermission.OWNER,
        granted_by=mock_user["id"],
    )
    db_session.add(permission)
    db_session.commit()
    db_session.refresh(bucket)

    return bucket


class TestBucketCollaborationService:
    """Test BucketCollaborationService for coverage"""

    def test_service_init(self, db_session):
        """Test service initialization"""
        service = BucketCollaborationService(db_session)
        assert service.db == db_session

    def test_get_bucket_permissions(self, db_session, sample_bucket):
        """Test getting bucket permissions"""
        service = BucketCollaborationService(db_session)
        permissions = service.get_bucket_permissions(sample_bucket.id)
        assert len(permissions) == 1
        assert permissions[0].permission == BucketPermission.OWNER

    def test_get_user_permission(self, db_session, sample_bucket, mock_user):
        """Test getting user permission"""
        service = BucketCollaborationService(db_session)
        permission = service.get_user_permission(sample_bucket.id, mock_user["id"])
        assert permission == BucketPermission.OWNER

    def test_has_permission(self, db_session, sample_bucket, mock_user):
        """Test checking user permissions"""
        service = BucketCollaborationService(db_session)
        assert service.has_permission(sample_bucket.id, mock_user["id"], BucketPermission.OWNER)
        assert service.has_permission(sample_bucket.id, mock_user["id"], BucketPermission.VIEWER)

    def test_has_permission_no_permission(self, db_session, sample_bucket):
        """Test checking permissions with no permission"""
        service = BucketCollaborationService(db_session)
        assert not service.has_permission(sample_bucket.id, "no-permission-user", BucketPermission.VIEWER)

    def test_get_bucket_activities(self, db_session, sample_bucket, mock_user):
        """Test getting bucket activities"""
        service = BucketCollaborationService(db_session)

        # Create some activities
        activity = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
        )
        db_session.add(activity)
        db_session.commit()

        activities = service.get_bucket_activities(sample_bucket.id)
        assert len(activities) == 1
        assert activities[0].activity_type == BucketActivityType.CREATED

    def test_get_user_notifications(self, db_session, sample_bucket, mock_user):
        """Test getting user notifications"""
        service = BucketCollaborationService(db_session)

        # Create notification
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test",
            message="Test message",
            is_read=False,
        )
        db_session.add(notification)
        db_session.commit()

        notifications = service.get_user_notifications(mock_user["id"])
        assert len(notifications) == 1
        assert notifications[0].is_read is False

    def test_mark_notification_read(self, db_session, sample_bucket, mock_user):
        """Test marking notification as read"""
        service = BucketCollaborationService(db_session)

        # Create notification
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test",
            message="Test message",
            is_read=False,
        )
        db_session.add(notification)
        db_session.commit()

        result = service.mark_notification_read(notification.id, mock_user["id"])
        assert result is True

        db_session.refresh(notification)
        assert notification.is_read is True

    def test_mark_all_notifications_read(self, db_session, sample_bucket, mock_user):
        """Test marking all notifications as read"""
        service = BucketCollaborationService(db_session)

        # Create multiple notifications
        for i in range(3):
            notification = BucketNotification(
                bucket_id=sample_bucket.id,
                user_id=mock_user["id"],
                notification_type=NotificationType.PERMISSION_GRANTED,
                title=f"Test {i}",
                message=f"Test message {i}",
                is_read=False,
            )
            db_session.add(notification)
        db_session.commit()

        count = service.mark_all_notifications_read(mock_user["id"])
        assert count == 3

    def test_get_active_collaborators(self, db_session, sample_bucket, mock_user):
        """Test getting active collaborators"""
        service = BucketCollaborationService(db_session)

        # Create active collaboration
        collab = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            session_id="test-session",
            connection_type="websocket",
        )
        db_session.add(collab)
        db_session.commit()

        collaborators = service.get_active_collaborators(sample_bucket.id)
        assert len(collaborators) == 1
        assert collaborators[0].user_id == mock_user["id"]


class TestWebSocketManager:
    """Test WebSocketManager for coverage"""

    def test_websocket_manager_init(self):
        """Test WebSocketManager initialization"""
        manager = WebSocketManager(connection_timeout=900)
        assert manager.connection_timeout == 900
        assert manager.active_connections == {}
        assert manager.user_buckets == {}
        assert manager.connection_timestamps == {}

    def test_websocket_manager_default_init(self):
        """Test WebSocketManager with default values"""
        manager = WebSocketManager()
        assert manager.connection_timeout == 1800  # 30 minutes

    def test_disconnect_empty_state(self):
        """Test disconnect with no existing connections"""
        manager = WebSocketManager()
        mock_websocket = MagicMock()

        # Should not raise exception
        manager.disconnect(mock_websocket, "bucket-123", "user-456")

        # State should remain empty
        assert manager.active_connections == {}
        assert manager.user_buckets == {}

    def test_update_activity_timestamp(self):
        """Test updating activity timestamp"""
        manager = WebSocketManager()
        bucket_id = "bucket-123"
        user_id = "user-456"

        manager._update_activity_timestamp(bucket_id, user_id)

        assert bucket_id in manager.connection_timestamps
        assert user_id in manager.connection_timestamps[bucket_id]

    def test_connection_stats(self):
        """Test getting connection statistics"""
        manager = WebSocketManager()

        # Add some mock data
        manager.active_connections = {
            "bucket-1": {"user-1": MagicMock(), "user-2": MagicMock()},
            "bucket-2": {"user-3": MagicMock()},
        }
        manager.user_buckets = {"user-1": {"bucket-1"}, "user-2": {"bucket-1"}, "user-3": {"bucket-2"}}

        stats = manager.get_connection_stats()
        assert stats["total_connections"] == 3
        assert stats["total_buckets"] == 2
        assert stats["total_users"] == 3

    def test_stop_cleanup_task(self):
        """Test stopping cleanup task"""
        manager = WebSocketManager()

        # Mock cleanup task
        manager._cleanup_task = MagicMock()
        manager._cleanup_task.done.return_value = False

        manager.stop_cleanup_task()

        manager._cleanup_task.cancel.assert_called_once()

    def test_stop_cleanup_task_no_task(self):
        """Test stopping cleanup task when no task exists"""
        manager = WebSocketManager()

        # Should not raise exception
        manager.stop_cleanup_task()

        assert manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_send_bucket_message_no_bucket(self):
        """Test sending message to non-existent bucket"""
        manager = WebSocketManager()

        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED, bucket_id="non-existent", user_id="user-123", data={"test": "data"}
        )

        # Should not raise exception
        await manager.send_bucket_message("non-existent", message)

    @pytest.mark.asyncio
    async def test_send_personal_message(self):
        """Test sending personal message"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()

        await manager.send_personal_message("test message", mock_websocket)

        mock_websocket.send_text.assert_called_once_with("test message")


class TestServiceFunctions:
    """Test service utility functions"""

    @pytest.mark.asyncio
    async def test_check_bucket_permission_success(self, db_session, sample_bucket, mock_user):
        """Test successful permission check"""
        from d1_targeting.collaboration_service import check_bucket_permission

        permission = await check_bucket_permission(
            db_session, sample_bucket.id, mock_user["id"], [BucketPermission.OWNER]
        )
        assert permission == BucketPermission.OWNER

    @pytest.mark.asyncio
    async def test_check_bucket_permission_insufficient(self, db_session, sample_bucket):
        """Test insufficient permission check"""
        from fastapi import HTTPException

        from d1_targeting.collaboration_service import check_bucket_permission

        with pytest.raises(HTTPException) as exc_info:
            await check_bucket_permission(db_session, sample_bucket.id, "no-permission-user", [BucketPermission.OWNER])
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_activity(self, db_session, sample_bucket, mock_user):
        """Test creating activity"""
        from d1_targeting.collaboration_service import create_activity

        await create_activity(
            db_session,
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
            entity_type="bucket",
            entity_id="test-entity",
            old_values={"name": "old"},
            new_values={"name": "new"},
        )

        # Verify activity was created
        activity = db_session.query(BucketActivity).filter(BucketActivity.bucket_id == sample_bucket.id).first()
        assert activity is not None
        assert activity.activity_type == BucketActivityType.CREATED

    @pytest.mark.asyncio
    async def test_create_notification(self, db_session, sample_bucket, mock_user):
        """Test creating notification"""
        from d1_targeting.collaboration_service import create_notification

        await create_notification(
            db_session,
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test Notification",
            message="Test message",
        )

        # Verify notification was created
        notification = (
            db_session.query(BucketNotification).filter(BucketNotification.bucket_id == sample_bucket.id).first()
        )
        assert notification is not None
        assert notification.title == "Test Notification"

    @pytest.mark.asyncio
    async def test_create_version_snapshot(self, db_session, sample_bucket, mock_user):
        """Test creating version snapshot"""
        from d1_targeting.collaboration_service import create_version_snapshot

        await create_version_snapshot(
            db_session,
            bucket=sample_bucket,
            user_id=mock_user["id"],
            change_type="config",
            description="Test snapshot",
        )

        # Verify version was created
        from d1_targeting.collaboration_models import BucketVersion

        version = db_session.query(BucketVersion).filter(BucketVersion.bucket_id == sample_bucket.id).first()
        assert version is not None
        assert version.description == "Test snapshot"
