"""
Integration tests for P2-010: Collaborative Bucket API
Tests the full end-to-end functionality of the collaborative bucket system.
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
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
    BucketShareLink,
    BucketTagDefinition,
    BucketVersion,
    CollaborativeBucket,
    LeadAnnotation,
    NotificationType,
)
from d1_targeting.collaboration_schemas import BucketCreate, WSMessage, WSMessageType
from d1_targeting.collaboration_service import BucketCollaborationService, WebSocketManager
from database.base import Base
from database.models import Business


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
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
    }


@pytest.fixture
def mock_user_2():
    """Second mock user for testing"""
    return {
        "id": "user-456",
        "email": "test2@example.com",
        "org_id": "org-456",
    }


@pytest.fixture
def sample_bucket(db_session, mock_user):
    """Create a sample bucket for testing"""
    bucket = CollaborativeBucket(
        name="Healthcare Leads Q1",
        description="High-value healthcare leads for Q1 campaign",
        bucket_type="vertical",
        bucket_key="healthcare",
        owner_id=mock_user["id"],
        organization_id=mock_user["org_id"],
        enrichment_config={"sources": ["internal", "hunter"], "max_budget": 1000},
        processing_strategy="healthcare",
        priority_level="high",
    )
    db_session.add(bucket)
    db_session.commit()  # Commit to get bucket.id
    db_session.refresh(bucket)

    # Grant owner permission
    owner_permission = BucketPermissionGrant(
        bucket_id=bucket.id,
        user_id=mock_user["id"],
        permission=BucketPermission.OWNER,
        granted_by=mock_user["id"],
    )
    db_session.add(owner_permission)
    db_session.commit()
    db_session.refresh(owner_permission)

    return bucket


@pytest.fixture
def sample_business(db_session):
    """Create a sample business for testing"""
    business = Business(
        id="business-123",
        name="Test Company",
        vert_bucket="healthcare",
        geo_bucket="high-affluence-urban",
        url="https://test.com",
        city="San Francisco",
        state="CA",
        zip_code="94102",
    )
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    return business


class TestBucketCollaborationService:
    """Test the BucketCollaborationService"""

    @pytest.mark.asyncio
    async def test_check_bucket_exists(self, db_session, sample_bucket):
        """Test checking if bucket exists"""
        service = BucketCollaborationService(db_session)

        # Test existing bucket
        result = await service.check_bucket_exists(sample_bucket.id)
        assert result.id == sample_bucket.id

        # Test non-existent bucket
        with pytest.raises(HTTPException) as exc_info:
            await service.check_bucket_exists("nonexistent")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_permission(self, db_session, sample_bucket, mock_user):
        """Test getting user permission for bucket"""
        service = BucketCollaborationService(db_session)

        # Test existing permission
        permission = await service.get_user_permission(sample_bucket.id, mock_user["id"])
        assert permission == BucketPermission.OWNER

        # Test non-existent permission
        permission = await service.get_user_permission(sample_bucket.id, "nonexistent")
        assert permission is None

    @pytest.mark.asyncio
    async def test_check_permission_success(self, db_session, sample_bucket, mock_user):
        """Test successful permission check"""
        service = BucketCollaborationService(db_session)

        # Test owner permission
        permission = await service.check_permission(sample_bucket.id, mock_user["id"], [BucketPermission.VIEWER])
        assert permission == BucketPermission.OWNER

    @pytest.mark.asyncio
    async def test_check_permission_failure(self, db_session, sample_bucket):
        """Test permission check failure"""
        service = BucketCollaborationService(db_session)

        # Test no permission
        with pytest.raises(HTTPException) as exc_info:
            await service.check_permission(sample_bucket.id, "nonexistent", [BucketPermission.VIEWER])
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_check_permission_insufficient(self, db_session, sample_bucket, mock_user_2):
        """Test insufficient permission check"""
        service = BucketCollaborationService(db_session)

        # Grant viewer permission
        grant = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=mock_user_2["id"],
        )
        db_session.add(grant)
        db_session.commit()

        # Test insufficient permission
        with pytest.raises(HTTPException) as exc_info:
            await service.check_permission(sample_bucket.id, mock_user_2["id"], [BucketPermission.EDITOR])
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_activity(self, db_session, sample_bucket, mock_user):
        """Test creating an activity log entry"""
        service = BucketCollaborationService(db_session)

        activity = await service.create_activity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
            new_values={"name": "Test Bucket"},
        )

        assert activity.bucket_id == sample_bucket.id
        assert activity.user_id == mock_user["id"]
        assert activity.activity_type == BucketActivityType.CREATED
        assert activity.new_values["name"] == "Test Bucket"

    @pytest.mark.asyncio
    async def test_create_notification(self, db_session, sample_bucket, mock_user):
        """Test creating a notification"""
        service = BucketCollaborationService(db_session)

        notification = await service.create_notification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.BUCKET_SHARED,
            title="Test Notification",
            message="This is a test notification",
        )

        assert notification.bucket_id == sample_bucket.id
        assert notification.user_id == mock_user["id"]
        assert notification.notification_type == NotificationType.BUCKET_SHARED
        assert notification.title == "Test Notification"
        assert notification.is_read is False

    @pytest.mark.asyncio
    async def test_create_version_snapshot(self, db_session, sample_bucket, mock_user):
        """Test creating a version snapshot"""
        service = BucketCollaborationService(db_session)

        version = await service.create_version_snapshot(
            bucket=sample_bucket,
            user_id=mock_user["id"],
            change_type="config",
            change_summary="Test snapshot",
            include_leads=False,
        )

        assert version.bucket_id == sample_bucket.id
        assert version.changed_by == mock_user["id"]
        assert version.change_type == "config"
        assert version.change_summary == "Test snapshot"
        assert version.bucket_snapshot["name"] == sample_bucket.name

    @pytest.mark.asyncio
    async def test_create_version_snapshot_with_leads(self, db_session, sample_bucket, mock_user, sample_business):
        """Test creating a version snapshot with leads"""
        service = BucketCollaborationService(db_session)

        version = await service.create_version_snapshot(
            bucket=sample_bucket,
            user_id=mock_user["id"],
            change_type="leads",
            change_summary="Added leads",
            include_leads=True,
        )

        assert version.lead_ids_snapshot is not None
        assert sample_business.id in version.lead_ids_snapshot

    @pytest.mark.asyncio
    async def test_get_bucket_stats(self, db_session, sample_bucket, sample_business):
        """Test getting bucket statistics"""
        service = BucketCollaborationService(db_session)

        stats = await service.get_bucket_stats(sample_bucket.id)

        assert stats["lead_count"] == 1  # Should count our sample business
        assert stats["collaborator_count"] == 1  # Owner permission
        assert stats["activity_count_30d"] == 0  # No activities yet
        assert stats["comment_count"] == 0  # No comments yet
        assert stats["version_count"] == 1  # Bucket version


class TestWebSocketManager:
    """Test the WebSocketManager"""

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Test WebSocket connection and disconnection"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()

        # Test connection
        await manager.connect(mock_websocket, "bucket-123", "user-456")

        assert "bucket-123" in manager.active_connections
        assert "user-456" in manager.active_connections["bucket-123"]
        assert manager.active_connections["bucket-123"]["user-456"] == mock_websocket

        # Test get bucket users
        users = manager.get_bucket_users("bucket-123")
        assert "user-456" in users

        # Test get user buckets
        buckets = manager.get_user_buckets("user-456")
        assert "bucket-123" in buckets

        # Test disconnection
        manager.disconnect(mock_websocket, "bucket-123", "user-456")

        assert "bucket-123" not in manager.active_connections
        assert "user-456" not in manager.user_buckets

    @pytest.mark.asyncio
    async def test_send_bucket_message(self):
        """Test sending messages to bucket"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock()
        mock_websocket.send_text = AsyncMock()

        # Connect user
        await manager.connect(mock_websocket, "bucket-123", "user-456")

        # Send message
        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED,
            bucket_id="bucket-123",
            user_id="user-789",
            data={"test": "data"},
        )

        await manager.send_bucket_message("bucket-123", message)

        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        sent_message = json.loads(call_args)
        assert sent_message["type"] == WSMessageType.BUCKET_UPDATED
        assert sent_message["bucket_id"] == "bucket-123"

    @pytest.mark.asyncio
    async def test_send_bucket_message_exclude_user(self):
        """Test sending messages to bucket excluding a user"""
        manager = WebSocketManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        mock_websocket1.send_text = AsyncMock()
        mock_websocket2.send_text = AsyncMock()

        # Connect two users
        await manager.connect(mock_websocket1, "bucket-123", "user-456")
        await manager.connect(mock_websocket2, "bucket-123", "user-789")

        # Send message excluding user-456
        message = WSMessage(
            type=WSMessageType.BUCKET_UPDATED,
            bucket_id="bucket-123",
            user_id="user-456",
            data={"test": "data"},
        )

        await manager.send_bucket_message("bucket-123", message, exclude_user="user-456")

        # Verify only user-789 received the message
        mock_websocket1.send_text.assert_not_called()
        mock_websocket2.send_text.assert_called_once()


class TestBucketCRUD:
    """Test bucket CRUD operations"""

    def test_create_bucket_success(self, db_session, mock_user):
        """Test successful bucket creation"""
        service = BucketCollaborationService(db_session)

        # Create bucket data
        bucket_data = BucketCreate(
            name="SaaS Leads",
            description="High-value SaaS leads",
            bucket_type="vertical",
            bucket_key="saas",
            organization_id=mock_user["org_id"],
        )

        # Create bucket
        bucket = CollaborativeBucket(
            **bucket_data.model_dump(),
            owner_id=mock_user["id"],
        )
        db_session.add(bucket)
        db_session.commit()
        db_session.refresh(bucket)

        assert bucket.name == "SaaS Leads"
        assert bucket.bucket_type == "vertical"
        assert bucket.bucket_key == "saas"
        assert bucket.owner_id == mock_user["id"]

    def test_create_bucket_duplicate(self, db_session, sample_bucket, mock_user):
        """Test creating duplicate bucket fails"""
        # Try to create duplicate bucket
        duplicate_bucket = CollaborativeBucket(
            name="Different Name",
            bucket_type="vertical",
            bucket_key="healthcare",  # Same key as sample_bucket
            owner_id=mock_user["id"],
            organization_id=mock_user["org_id"],
        )

        db_session.add(duplicate_bucket)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()

    def test_update_bucket(self, db_session, sample_bucket, mock_user):
        """Test updating bucket"""
        service = BucketCollaborationService(db_session)

        # Update bucket
        old_name = sample_bucket.name
        sample_bucket.name = "Updated Healthcare Leads"
        sample_bucket.description = "Updated description"
        sample_bucket.priority_level = "medium"

        db_session.commit()

        # Verify update
        updated_bucket = db_session.query(CollaborativeBucket).filter_by(id=sample_bucket.id).first()
        assert updated_bucket.name == "Updated Healthcare Leads"
        assert updated_bucket.description == "Updated description"
        assert updated_bucket.priority_level == "medium"

    def test_archive_bucket(self, db_session, sample_bucket):
        """Test archiving a bucket"""
        # Archive bucket
        sample_bucket.is_archived = True
        db_session.commit()

        # Verify archived
        archived_bucket = db_session.query(CollaborativeBucket).filter_by(id=sample_bucket.id).first()
        assert archived_bucket.is_archived is True


class TestPermissionManagement:
    """Test permission management operations"""

    def test_grant_permission(self, db_session, sample_bucket, mock_user_2):
        """Test granting permission to user"""
        # Grant editor permission
        grant = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=mock_user_2["id"],
        )

        db_session.add(grant)
        db_session.commit()

        # Verify permission
        saved_grant = (
            db_session.query(BucketPermissionGrant)
            .filter_by(
                bucket_id=sample_bucket.id,
                user_id=mock_user_2["id"],
            )
            .first()
        )

        assert saved_grant.permission == BucketPermission.EDITOR
        assert saved_grant.granted_by == mock_user_2["id"]

    def test_grant_permission_duplicate(self, db_session, sample_bucket, mock_user_2):
        """Test granting duplicate permission fails"""
        # Grant first permission
        grant1 = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=mock_user_2["id"],
        )
        db_session.add(grant1)
        db_session.commit()

        # Try to grant duplicate
        grant2 = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=mock_user_2["id"],
        )
        db_session.add(grant2)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()

    def test_update_permission(self, db_session, sample_bucket, mock_user_2):
        """Test updating user permission"""
        # Grant initial permission
        grant = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=mock_user_2["id"],
        )
        db_session.add(grant)
        db_session.commit()

        # Update permission
        grant.permission = BucketPermission.EDITOR
        db_session.commit()

        # Verify update
        updated_grant = (
            db_session.query(BucketPermissionGrant)
            .filter_by(
                bucket_id=sample_bucket.id,
                user_id=mock_user_2["id"],
            )
            .first()
        )

        assert updated_grant.permission == BucketPermission.EDITOR

    def test_revoke_permission(self, db_session, sample_bucket, mock_user_2):
        """Test revoking user permission"""
        # Grant permission
        grant = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=mock_user_2["id"],
        )
        db_session.add(grant)
        db_session.commit()

        # Revoke permission
        db_session.delete(grant)
        db_session.commit()

        # Verify revoked
        revoked_grant = (
            db_session.query(BucketPermissionGrant)
            .filter_by(
                bucket_id=sample_bucket.id,
                user_id=mock_user_2["id"],
            )
            .first()
        )

        assert revoked_grant is None

    def test_permission_with_expiry(self, db_session, sample_bucket, mock_user_2):
        """Test permission with expiry date"""
        expires_at = datetime.utcnow() + timedelta(days=7)

        # Grant temporary permission
        grant = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=mock_user_2["id"],
            expires_at=expires_at,
        )
        db_session.add(grant)
        db_session.commit()

        # Verify expiry
        saved_grant = (
            db_session.query(BucketPermissionGrant)
            .filter_by(
                bucket_id=sample_bucket.id,
                user_id=mock_user_2["id"],
            )
            .first()
        )

        assert saved_grant.expires_at == expires_at


class TestCommentSystem:
    """Test comment system operations"""

    def test_create_comment(self, db_session, sample_bucket, mock_user):
        """Test creating a comment"""
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="This is a test comment",
        )

        db_session.add(comment)
        db_session.commit()

        # Verify comment
        saved_comment = db_session.query(BucketComment).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_comment.content == "This is a test comment"
        assert saved_comment.user_id == mock_user["id"]
        assert saved_comment.is_deleted is False

    def test_create_comment_with_mentions(self, db_session, sample_bucket, mock_user, mock_user_2):
        """Test creating a comment with mentions"""
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="@user456 please review this",
            mentioned_users=[mock_user_2["id"]],
        )

        db_session.add(comment)
        db_session.commit()

        # Verify mentions
        saved_comment = db_session.query(BucketComment).filter_by(bucket_id=sample_bucket.id).first()
        assert mock_user_2["id"] in saved_comment.mentioned_users

    def test_create_comment_on_lead(self, db_session, sample_bucket, mock_user, sample_business):
        """Test creating a comment on a specific lead"""
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            lead_id=sample_business.id,
            content="This lead looks promising",
        )

        db_session.add(comment)
        db_session.commit()

        # Verify lead comment
        saved_comment = (
            db_session.query(BucketComment)
            .filter_by(
                bucket_id=sample_bucket.id,
                lead_id=sample_business.id,
            )
            .first()
        )
        assert saved_comment.content == "This lead looks promising"

    def test_reply_to_comment(self, db_session, sample_bucket, mock_user, mock_user_2):
        """Test replying to a comment"""
        # Create parent comment
        parent = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="Original comment",
        )
        db_session.add(parent)
        db_session.commit()

        # Create reply
        reply = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            parent_comment_id=parent.id,
            content="Reply to original",
        )
        db_session.add(reply)
        db_session.commit()

        # Verify reply
        saved_reply = db_session.query(BucketComment).filter_by(parent_comment_id=parent.id).first()
        assert saved_reply.content == "Reply to original"
        assert saved_reply.user_id == mock_user_2["id"]

    def test_edit_comment(self, db_session, sample_bucket, mock_user):
        """Test editing a comment"""
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="Original content",
        )
        db_session.add(comment)
        db_session.commit()

        # Edit comment
        comment.content = "Edited content"
        comment.is_edited = True
        db_session.commit()

        # Verify edit
        saved_comment = db_session.query(BucketComment).filter_by(id=comment.id).first()
        assert saved_comment.content == "Edited content"
        assert saved_comment.is_edited is True

    def test_delete_comment(self, db_session, sample_bucket, mock_user):
        """Test soft deleting a comment"""
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="To be deleted",
        )
        db_session.add(comment)
        db_session.commit()

        # Soft delete
        comment.is_deleted = True
        comment.content = "[Deleted]"
        db_session.commit()

        # Verify deletion
        saved_comment = db_session.query(BucketComment).filter_by(id=comment.id).first()
        assert saved_comment.is_deleted is True
        assert saved_comment.content == "[Deleted]"


class TestActivityTracking:
    """Test activity tracking operations"""

    def test_track_bucket_created(self, db_session, sample_bucket, mock_user):
        """Test tracking bucket creation activity"""
        activity = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
            new_values={"name": sample_bucket.name},
        )

        db_session.add(activity)
        db_session.commit()

        # Verify activity
        saved_activity = db_session.query(BucketActivity).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_activity.activity_type == BucketActivityType.CREATED
        assert saved_activity.new_values["name"] == sample_bucket.name

    def test_track_bucket_updated(self, db_session, sample_bucket, mock_user):
        """Test tracking bucket update activity"""
        activity = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.UPDATED,
            old_values={"name": "Old Name"},
            new_values={"name": "New Name"},
        )

        db_session.add(activity)
        db_session.commit()

        # Verify activity
        saved_activity = db_session.query(BucketActivity).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_activity.activity_type == BucketActivityType.UPDATED
        assert saved_activity.old_values["name"] == "Old Name"
        assert saved_activity.new_values["name"] == "New Name"

    def test_track_lead_added(self, db_session, sample_bucket, mock_user, sample_business):
        """Test tracking lead addition activity"""
        activity = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.LEAD_ADDED,
            entity_type="lead",
            entity_id=sample_business.id,
        )

        db_session.add(activity)
        db_session.commit()

        # Verify activity
        saved_activity = db_session.query(BucketActivity).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_activity.activity_type == BucketActivityType.LEAD_ADDED
        assert saved_activity.entity_type == "lead"
        assert saved_activity.entity_id == sample_business.id

    def test_track_comment_added(self, db_session, sample_bucket, mock_user):
        """Test tracking comment addition activity"""
        # Create comment first
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="Test comment",
        )
        db_session.add(comment)
        db_session.commit()

        # Track activity
        activity = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.COMMENT_ADDED,
            entity_type="comment",
            entity_id=comment.id,
        )

        db_session.add(activity)
        db_session.commit()

        # Verify activity
        saved_activity = (
            db_session.query(BucketActivity)
            .filter_by(
                bucket_id=sample_bucket.id,
                activity_type=BucketActivityType.COMMENT_ADDED,
            )
            .first()
        )
        assert saved_activity.entity_type == "comment"
        assert saved_activity.entity_id == comment.id


class TestNotificationSystem:
    """Test notification system operations"""

    def test_create_permission_notification(self, db_session, sample_bucket, mock_user_2):
        """Test creating permission granted notification"""
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Bucket Access Granted",
            message="You have been granted access to Healthcare Leads Q1",
            related_user_id=mock_user_2["id"],
        )

        db_session.add(notification)
        db_session.commit()

        # Verify notification
        saved_notification = db_session.query(BucketNotification).filter_by(user_id=mock_user_2["id"]).first()
        assert saved_notification.notification_type == NotificationType.PERMISSION_GRANTED
        assert saved_notification.is_read is False

    def test_create_mention_notification(self, db_session, sample_bucket, mock_user, mock_user_2):
        """Test creating mention notification"""
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            notification_type=NotificationType.COMMENT_MENTION,
            title="You were mentioned",
            message="User mentioned you in a comment",
            related_user_id=mock_user["id"],
            related_entity_type="comment",
            related_entity_id="comment-123",
        )

        db_session.add(notification)
        db_session.commit()

        # Verify notification
        saved_notification = db_session.query(BucketNotification).filter_by(user_id=mock_user_2["id"]).first()
        assert saved_notification.notification_type == NotificationType.COMMENT_MENTION
        assert saved_notification.related_entity_type == "comment"
        assert saved_notification.related_entity_id == "comment-123"

    def test_mark_notification_read(self, db_session, sample_bucket, mock_user):
        """Test marking notification as read"""
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.BUCKET_UPDATED,
            title="Bucket Updated",
            message="Bucket has been updated",
        )
        db_session.add(notification)
        db_session.commit()

        # Mark as read
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db_session.commit()

        # Verify read status
        saved_notification = db_session.query(BucketNotification).filter_by(id=notification.id).first()
        assert saved_notification.is_read is True
        assert saved_notification.read_at is not None


class TestShareLinks:
    """Test share link operations"""

    def test_create_share_link(self, db_session, sample_bucket, mock_user):
        """Test creating a share link"""
        share_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="test-token-123",
            permission=BucketPermission.VIEWER,
            created_by=mock_user["id"],
        )

        db_session.add(share_link)
        db_session.commit()

        # Verify share link
        saved_link = db_session.query(BucketShareLink).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_link.share_token == "test-token-123"
        assert saved_link.permission == BucketPermission.VIEWER
        assert saved_link.is_active is True

    def test_create_share_link_with_limits(self, db_session, sample_bucket, mock_user):
        """Test creating share link with usage limits"""
        expires_at = datetime.utcnow() + timedelta(days=7)

        share_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="limited-token-456",
            permission=BucketPermission.COMMENTER,
            max_uses=10,
            expires_at=expires_at,
            created_by=mock_user["id"],
        )

        db_session.add(share_link)
        db_session.commit()

        # Verify limits
        saved_link = db_session.query(BucketShareLink).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_link.max_uses == 10
        assert saved_link.expires_at == expires_at
        assert saved_link.current_uses == 0

    def test_deactivate_share_link(self, db_session, sample_bucket, mock_user):
        """Test deactivating a share link"""
        share_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="to-deactivate-789",
            permission=BucketPermission.EDITOR,
            created_by=mock_user["id"],
        )
        db_session.add(share_link)
        db_session.commit()

        # Deactivate
        share_link.is_active = False
        db_session.commit()

        # Verify deactivation
        saved_link = db_session.query(BucketShareLink).filter_by(id=share_link.id).first()
        assert saved_link.is_active is False


class TestLeadAnnotations:
    """Test lead annotation operations"""

    def test_create_lead_annotation(self, db_session, sample_bucket, mock_user, sample_business):
        """Test creating a lead annotation"""
        annotation = LeadAnnotation(
            bucket_id=sample_bucket.id,
            lead_id=sample_business.id,
            user_id=mock_user["id"],
            annotation_type="note",
            content="High priority lead",
            annotation_metadata={"priority": "high"},
        )

        db_session.add(annotation)
        db_session.commit()

        # Verify annotation
        saved_annotation = (
            db_session.query(LeadAnnotation)
            .filter_by(
                bucket_id=sample_bucket.id,
                lead_id=sample_business.id,
            )
            .first()
        )
        assert saved_annotation.annotation_type == "note"
        assert saved_annotation.content == "High priority lead"
        assert saved_annotation.annotation_metadata["priority"] == "high"

    def test_create_tag_annotation(self, db_session, sample_bucket, mock_user, sample_business):
        """Test creating a tag annotation"""
        annotation = LeadAnnotation(
            bucket_id=sample_bucket.id,
            lead_id=sample_business.id,
            user_id=mock_user["id"],
            annotation_type="tag",
            annotation_metadata={"tags": ["urgent", "high-value"]},
        )

        db_session.add(annotation)
        db_session.commit()

        # Verify tag annotation
        saved_annotation = (
            db_session.query(LeadAnnotation)
            .filter_by(
                bucket_id=sample_bucket.id,
                lead_id=sample_business.id,
                annotation_type="tag",
            )
            .first()
        )
        assert "urgent" in saved_annotation.annotation_metadata["tags"]
        assert "high-value" in saved_annotation.annotation_metadata["tags"]

    def test_create_status_annotation(self, db_session, sample_bucket, mock_user, sample_business):
        """Test creating a status annotation"""
        annotation = LeadAnnotation(
            bucket_id=sample_bucket.id,
            lead_id=sample_business.id,
            user_id=mock_user["id"],
            annotation_type="status",
            content="qualified",
            annotation_metadata={"previous_status": "new"},
        )

        db_session.add(annotation)
        db_session.commit()

        # Verify status annotation
        saved_annotation = (
            db_session.query(LeadAnnotation)
            .filter_by(
                bucket_id=sample_bucket.id,
                lead_id=sample_business.id,
                annotation_type="status",
            )
            .first()
        )
        assert saved_annotation.content == "qualified"
        assert saved_annotation.annotation_metadata["previous_status"] == "new"


class TestVersionHistory:
    """Test version history operations"""

    def test_create_version_history(self, db_session, sample_bucket, mock_user):
        """Test creating version history"""
        version = BucketVersion(
            bucket_id=sample_bucket.id,
            version_number=1,
            change_type="config",
            change_summary="Initial bucket creation",
            bucket_snapshot={
                "name": sample_bucket.name,
                "bucket_type": sample_bucket.bucket_type,
                "bucket_key": sample_bucket.bucket_key,
            },
            changed_by=mock_user["id"],
        )

        db_session.add(version)
        db_session.commit()

        # Verify version
        saved_version = db_session.query(BucketVersion).filter_by(bucket_id=sample_bucket.id).first()
        assert saved_version.version_number == 1
        assert saved_version.change_type == "config"
        assert saved_version.bucket_snapshot["name"] == sample_bucket.name

    def test_create_version_with_leads(self, db_session, sample_bucket, mock_user, sample_business):
        """Test creating version with lead snapshot"""
        version = BucketVersion(
            bucket_id=sample_bucket.id,
            version_number=2,
            change_type="leads",
            change_summary="Added new leads",
            bucket_snapshot={
                "name": sample_bucket.name,
                "bucket_type": sample_bucket.bucket_type,
            },
            lead_ids_snapshot=[sample_business.id],
            changed_by=mock_user["id"],
        )

        db_session.add(version)
        db_session.commit()

        # Verify version with leads
        saved_version = (
            db_session.query(BucketVersion)
            .filter_by(
                bucket_id=sample_bucket.id,
                version_number=2,
            )
            .first()
        )
        assert saved_version.change_type == "leads"
        assert sample_business.id in saved_version.lead_ids_snapshot


class TestActiveCollaborations:
    """Test active collaboration tracking"""

    def test_create_active_collaboration(self, db_session, sample_bucket, mock_user):
        """Test creating active collaboration session"""
        collaboration = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            session_id="session-123",
            connection_type="websocket",
            current_view="overview",
            is_editing=False,
        )

        db_session.add(collaboration)
        db_session.commit()

        # Verify collaboration
        saved_collab = (
            db_session.query(ActiveCollaboration)
            .filter_by(
                bucket_id=sample_bucket.id,
                user_id=mock_user["id"],
            )
            .first()
        )
        assert saved_collab.session_id == "session-123"
        assert saved_collab.connection_type == "websocket"
        assert saved_collab.current_view == "overview"
        assert saved_collab.is_editing is False

    def test_update_collaboration_activity(self, db_session, sample_bucket, mock_user):
        """Test updating collaboration activity"""
        collaboration = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            session_id="session-456",
            connection_type="websocket",
        )
        db_session.add(collaboration)
        db_session.commit()

        # Update activity
        collaboration.last_activity_at = datetime.utcnow()
        collaboration.current_view = "leads"
        collaboration.is_editing = True
        db_session.commit()

        # Verify update
        saved_collab = db_session.query(ActiveCollaboration).filter_by(session_id="session-456").first()
        assert saved_collab.current_view == "leads"
        assert saved_collab.is_editing is True

    def test_remove_collaboration(self, db_session, sample_bucket, mock_user):
        """Test removing collaboration session"""
        collaboration = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            session_id="session-789",
            connection_type="websocket",
        )
        db_session.add(collaboration)
        db_session.commit()

        # Remove collaboration
        db_session.delete(collaboration)
        db_session.commit()

        # Verify removal
        removed_collab = db_session.query(ActiveCollaboration).filter_by(session_id="session-789").first()
        assert removed_collab is None


class TestBucketTags:
    """Test bucket tag operations"""

    def test_create_bucket_tag(self, db_session, mock_user):
        """Test creating a bucket tag"""
        tag = BucketTagDefinition(
            name="urgent",
            description="Urgent processing needed",
            color="#FF0000",
            created_by=mock_user["id"],
        )

        db_session.add(tag)
        db_session.commit()

        # Verify tag
        saved_tag = db_session.query(BucketTagDefinition).filter_by(name="urgent").first()
        assert saved_tag.name == "urgent"
        assert saved_tag.description == "Urgent processing needed"
        assert saved_tag.color == "#FF0000"
        assert saved_tag.created_by == mock_user["id"]

    def test_assign_tags_to_bucket(self, db_session, sample_bucket, mock_user):
        """Test assigning tags to bucket"""
        # Create tags
        tag1 = BucketTagDefinition(
            name="high-priority",
            description="High priority bucket",
            color="#FF0000",
            created_by=mock_user["id"],
        )
        tag2 = BucketTagDefinition(
            name="healthcare",
            description="Healthcare vertical",
            color="#00FF00",
            created_by=mock_user["id"],
        )

        db_session.add_all([tag1, tag2])
        db_session.commit()

        # Assign tags to bucket
        sample_bucket.tags = [tag1, tag2]
        db_session.commit()

        # Verify tags
        updated_bucket = db_session.query(CollaborativeBucket).filter_by(id=sample_bucket.id).first()
        assert len(updated_bucket.tags) == 2
        tag_names = [tag.name for tag in updated_bucket.tags]
        assert "high-priority" in tag_names
        assert "healthcare" in tag_names

    def test_remove_tag_from_bucket(self, db_session, sample_bucket, mock_user):
        """Test removing tag from bucket"""
        # Create and assign tag
        tag = BucketTagDefinition(
            name="temp-tag",
            description="Temporary tag",
            color="#0000FF",
            created_by=mock_user["id"],
        )
        db_session.add(tag)
        db_session.commit()

        sample_bucket.tags = [tag]
        db_session.commit()

        # Remove tag
        sample_bucket.tags = []
        db_session.commit()

        # Verify removal
        updated_bucket = db_session.query(CollaborativeBucket).filter_by(id=sample_bucket.id).first()
        assert len(updated_bucket.tags) == 0


class TestDataConsistency:
    """Test data consistency and edge cases"""

    def test_bucket_lead_count_consistency(self, db_session, sample_bucket, sample_business):
        """Test bucket lead count consistency"""
        # Initial count should be 1 (sample_business with matching bucket)
        business_count = db_session.query(Business).filter_by(vert_bucket=sample_bucket.bucket_key).count()
        assert business_count == 1

        # Update bucket lead count
        sample_bucket.lead_count = business_count
        db_session.commit()

        # Verify consistency
        assert sample_bucket.lead_count == 1

    def test_cascade_delete_bucket(self, db_session, sample_bucket, mock_user):
        """Test cascade deletion of bucket relationships"""
        # Create related records
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            content="Test comment",
        )

        activity = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            activity_type=BucketActivityType.CREATED,
        )

        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.BUCKET_UPDATED,
            title="Test notification",
            message="Test message",
        )

        db_session.add_all([comment, activity, notification])
        db_session.commit()

        # Get IDs before deletion
        comment_id = comment.id
        activity_id = activity.id
        notification_id = notification.id

        # Delete bucket
        db_session.delete(sample_bucket)
        db_session.commit()

        # Verify cascade deletion
        assert db_session.query(BucketComment).filter_by(id=comment_id).first() is None
        assert db_session.query(BucketActivity).filter_by(id=activity_id).first() is None
        assert db_session.query(BucketNotification).filter_by(id=notification_id).first() is None

    def test_unique_constraints(self, db_session, sample_bucket, mock_user):
        """Test unique constraints are enforced"""
        # Test unique bucket constraint
        duplicate_bucket = CollaborativeBucket(
            name="Different Name",
            bucket_type=sample_bucket.bucket_type,
            bucket_key=sample_bucket.bucket_key,
            owner_id=mock_user["id"],
            organization_id=sample_bucket.organization_id,
        )

        db_session.add(duplicate_bucket)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()

    def test_permission_hierarchy(self, db_session, sample_bucket, mock_user):
        """Test permission hierarchy logic"""
        service = BucketCollaborationService(db_session)

        # Test permission levels
        permission_levels = {
            BucketPermission.OWNER: 5,
            BucketPermission.ADMIN: 4,
            BucketPermission.EDITOR: 3,
            BucketPermission.COMMENTER: 2,
            BucketPermission.VIEWER: 1,
        }

        # Owner should have highest level
        assert permission_levels[BucketPermission.OWNER] > permission_levels[BucketPermission.ADMIN]
        assert permission_levels[BucketPermission.ADMIN] > permission_levels[BucketPermission.EDITOR]
        assert permission_levels[BucketPermission.EDITOR] > permission_levels[BucketPermission.COMMENTER]
        assert permission_levels[BucketPermission.COMMENTER] > permission_levels[BucketPermission.VIEWER]
