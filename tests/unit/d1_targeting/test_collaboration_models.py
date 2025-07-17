"""
Unit tests for P2-010: Collaborative Bucket Models
"""
import json
from datetime import datetime, timedelta

import pytest
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
    bucket_tags,
)
from database.base import Base


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


class TestCollaborativeBucket:
    """Test CollaborativeBucket model"""

    def test_create_bucket(self, db_session):
        """Test creating a collaborative bucket"""
        bucket = CollaborativeBucket(
            name="Healthcare Leads Q1",
            description="High-value healthcare leads for Q1 campaign",
            bucket_type="vertical",
            bucket_key="healthcare",
            owner_id="user-123",
            organization_id="org-456",
            is_public=False,
            enrichment_config={"sources": ["internal", "hunter"], "max_budget": 1000},
            processing_strategy="healthcare",
            priority_level="high",
        )

        db_session.add(bucket)
        db_session.commit()

        # Verify bucket was created
        saved_bucket = db_session.query(CollaborativeBucket).first()
        assert saved_bucket is not None
        assert saved_bucket.name == "Healthcare Leads Q1"
        assert saved_bucket.bucket_type == "vertical"
        assert saved_bucket.bucket_key == "healthcare"
        assert saved_bucket.owner_id == "user-123"
        assert saved_bucket.version == 1
        assert saved_bucket.lead_count == 0
        assert saved_bucket.total_enrichment_cost == 0
        assert saved_bucket.is_archived is False

    def test_bucket_with_tags(self, db_session):
        """Test bucket with tags"""
        # Create tags
        tag1 = BucketTagDefinition(
            name="urgent", description="Urgent processing needed", color="#FF0000", created_by="user-123"
        )
        tag2 = BucketTagDefinition(
            name="high-value", description="High-value leads", color="#00FF00", created_by="user-123"
        )

        db_session.add_all([tag1, tag2])
        db_session.commit()

        # Create bucket with tags
        bucket = CollaborativeBucket(
            name="Tagged Bucket",
            bucket_type="vertical",
            bucket_key="saas",
            owner_id="user-123",
        )
        bucket.tags = [tag1, tag2]

        db_session.add(bucket)
        db_session.commit()

        # Verify tags
        saved_bucket = db_session.query(CollaborativeBucket).first()
        assert len(saved_bucket.tags) == 2
        assert set(tag.name for tag in saved_bucket.tags) == {"urgent", "high-value"}

    def test_bucket_unique_constraint(self, db_session):
        """Test bucket unique constraint"""
        # Create first bucket
        bucket1 = CollaborativeBucket(
            name="Bucket 1",
            bucket_type="vertical",
            bucket_key="healthcare",
            owner_id="user-123",
            organization_id="org-456",
        )
        db_session.add(bucket1)
        db_session.commit()

        # Try to create duplicate bucket
        bucket2 = CollaborativeBucket(
            name="Bucket 2",  # Different name
            bucket_type="vertical",
            bucket_key="healthcare",  # Same type and key
            owner_id="user-456",  # Different owner
            organization_id="org-456",  # Same org
        )
        db_session.add(bucket2)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestBucketPermissionGrant:
    """Test BucketPermissionGrant model"""

    def test_create_permission_grant(self, db_session):
        """Test creating a permission grant"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Grant permission
        grant = BucketPermissionGrant(
            bucket_id=bucket.id,
            user_id="user-456",
            permission=BucketPermission.EDITOR,
            granted_by="user-123",
        )

        db_session.add(grant)
        db_session.commit()

        # Verify grant
        saved_grant = db_session.query(BucketPermissionGrant).first()
        assert saved_grant is not None
        assert saved_grant.user_id == "user-456"
        assert saved_grant.permission == BucketPermission.EDITOR
        assert saved_grant.granted_by == "user-123"
        assert saved_grant.expires_at is None

    def test_permission_with_expiry(self, db_session):
        """Test permission grant with expiry"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Grant temporary permission
        expires = datetime.utcnow() + timedelta(days=7)
        grant = BucketPermissionGrant(
            bucket_id=bucket.id,
            user_id="user-456",
            permission=BucketPermission.VIEWER,
            granted_by="user-123",
            expires_at=expires,
        )

        db_session.add(grant)
        db_session.commit()

        # Verify expiry
        saved_grant = db_session.query(BucketPermissionGrant).first()
        assert saved_grant.expires_at is not None
        assert saved_grant.expires_at > datetime.utcnow()

    def test_unique_user_bucket_permission(self, db_session):
        """Test unique constraint on user-bucket permission"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # First grant
        grant1 = BucketPermissionGrant(
            bucket_id=bucket.id,
            user_id="user-456",
            permission=BucketPermission.VIEWER,
            granted_by="user-123",
        )
        db_session.add(grant1)
        db_session.commit()

        # Try duplicate grant
        grant2 = BucketPermissionGrant(
            bucket_id=bucket.id,
            user_id="user-456",  # Same user
            permission=BucketPermission.EDITOR,  # Different permission
            granted_by="user-123",
        )
        db_session.add(grant2)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestBucketActivity:
    """Test BucketActivity model"""

    def test_create_activity(self, db_session):
        """Test creating an activity log entry"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create activity
        activity = BucketActivity(
            bucket_id=bucket.id,
            user_id="user-123",
            activity_type=BucketActivityType.CREATED,
            new_values={"name": "Test Bucket", "type": "vertical"},
        )

        db_session.add(activity)
        db_session.commit()

        # Verify activity
        saved_activity = db_session.query(BucketActivity).first()
        assert saved_activity is not None
        assert saved_activity.activity_type == BucketActivityType.CREATED
        assert saved_activity.new_values["name"] == "Test Bucket"
        assert saved_activity.old_values is None

    def test_activity_with_entity(self, db_session):
        """Test activity with entity reference"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create activity for lead addition
        activity = BucketActivity(
            bucket_id=bucket.id,
            user_id="user-123",
            activity_type=BucketActivityType.LEAD_ADDED,
            entity_type="lead",
            entity_id="lead-789",
            metadata={"source": "manual", "count": 1},
        )

        db_session.add(activity)
        db_session.commit()

        # Verify
        saved_activity = db_session.query(BucketActivity).first()
        assert saved_activity.entity_type == "lead"
        assert saved_activity.entity_id == "lead-789"
        assert saved_activity.metadata["source"] == "manual"

    def test_activity_change_tracking(self, db_session):
        """Test activity with old and new values"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Original Name",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create update activity
        activity = BucketActivity(
            bucket_id=bucket.id,
            user_id="user-123",
            activity_type=BucketActivityType.UPDATED,
            old_values={"name": "Original Name", "priority_level": None},
            new_values={"name": "Updated Name", "priority_level": "high"},
        )

        db_session.add(activity)
        db_session.commit()

        # Verify
        saved_activity = db_session.query(BucketActivity).first()
        assert saved_activity.old_values["name"] == "Original Name"
        assert saved_activity.new_values["name"] == "Updated Name"
        assert saved_activity.new_values["priority_level"] == "high"


class TestBucketComment:
    """Test BucketComment model"""

    def test_create_comment(self, db_session):
        """Test creating a comment"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create comment
        comment = BucketComment(
            bucket_id=bucket.id,
            user_id="user-123",
            content="This bucket looks promising!",
        )

        db_session.add(comment)
        db_session.commit()

        # Verify
        saved_comment = db_session.query(BucketComment).first()
        assert saved_comment is not None
        assert saved_comment.content == "This bucket looks promising!"
        assert saved_comment.is_edited is False
        assert saved_comment.is_deleted is False
        assert saved_comment.parent_comment_id is None
        assert saved_comment.lead_id is None

    def test_comment_on_lead(self, db_session):
        """Test comment on specific lead"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create comment on lead
        comment = BucketComment(
            bucket_id=bucket.id,
            user_id="user-123",
            lead_id="lead-789",
            content="This lead needs follow-up",
            mentioned_users=["user-456", "user-789"],
        )

        db_session.add(comment)
        db_session.commit()

        # Verify
        saved_comment = db_session.query(BucketComment).first()
        assert saved_comment.lead_id == "lead-789"
        assert len(saved_comment.mentioned_users) == 2
        assert "user-456" in saved_comment.mentioned_users

    def test_comment_reply(self, db_session):
        """Test reply to comment"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create parent comment
        parent = BucketComment(
            bucket_id=bucket.id,
            user_id="user-123",
            content="Original comment",
        )
        db_session.add(parent)
        db_session.commit()

        # Create reply
        reply = BucketComment(
            bucket_id=bucket.id,
            user_id="user-456",
            parent_comment_id=parent.id,
            content="Reply to original",
        )
        db_session.add(reply)
        db_session.commit()

        # Verify relationship - query the parent again to ensure relationships are loaded
        saved_parent = db_session.query(BucketComment).filter_by(id=parent.id).first()
        assert saved_parent is not None

        # Check that the reply exists by querying it directly
        replies = db_session.query(BucketComment).filter_by(parent_comment_id=parent.id).all()
        assert len(replies) == 1
        assert replies[0].content == "Reply to original"

    def test_soft_delete_comment(self, db_session):
        """Test soft deleting a comment"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create comment
        comment = BucketComment(
            bucket_id=bucket.id,
            user_id="user-123",
            content="To be deleted",
        )
        db_session.add(comment)
        db_session.commit()

        # Soft delete
        comment.is_deleted = True
        comment.content = "[Deleted]"
        db_session.commit()

        # Verify
        saved_comment = db_session.query(BucketComment).first()
        assert saved_comment.is_deleted is True
        assert saved_comment.content == "[Deleted]"


class TestBucketVersion:
    """Test BucketVersion model"""

    def test_create_version(self, db_session):
        """Test creating a version snapshot"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            description="Original description",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
            version=1,
        )
        db_session.add(bucket)
        db_session.commit()

        # Create version snapshot
        version = BucketVersion(
            bucket_id=bucket.id,
            version_number=1,
            change_type="config",
            change_summary="Initial bucket creation",
            bucket_snapshot={
                "name": "Test Bucket",
                "description": "Original description",
                "bucket_type": "vertical",
                "bucket_key": "test",
                "tags": [],
            },
            changed_by="user-123",
        )

        db_session.add(version)
        db_session.commit()

        # Verify
        saved_version = db_session.query(BucketVersion).first()
        assert saved_version is not None
        assert saved_version.version_number == 1
        assert saved_version.change_type == "config"
        assert saved_version.bucket_snapshot["name"] == "Test Bucket"
        assert saved_version.lead_ids_snapshot is None

    def test_version_with_leads(self, db_session):
        """Test version with lead snapshot"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
            version=2,
        )
        db_session.add(bucket)
        db_session.commit()

        # Create version with lead snapshot
        version = BucketVersion(
            bucket_id=bucket.id,
            version_number=2,
            change_type="leads",
            change_summary="Added 5 new leads",
            bucket_snapshot={
                "name": "Test Bucket",
                "bucket_type": "vertical",
                "bucket_key": "test",
            },
            lead_ids_snapshot=["lead-1", "lead-2", "lead-3", "lead-4", "lead-5"],
            changed_by="user-123",
        )

        db_session.add(version)
        db_session.commit()

        # Verify
        saved_version = db_session.query(BucketVersion).first()
        assert len(saved_version.lead_ids_snapshot) == 5
        assert "lead-3" in saved_version.lead_ids_snapshot


class TestBucketNotification:
    """Test BucketNotification model"""

    def test_create_notification(self, db_session):
        """Test creating a notification"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create notification
        notification = BucketNotification(
            bucket_id=bucket.id,
            user_id="user-456",
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Bucket Access Granted",
            message="You have been granted editor access to Test Bucket",
            related_user_id="user-123",
        )

        db_session.add(notification)
        db_session.commit()

        # Verify
        saved_notification = db_session.query(BucketNotification).first()
        assert saved_notification is not None
        assert saved_notification.notification_type == NotificationType.PERMISSION_GRANTED
        assert saved_notification.is_read is False
        assert saved_notification.is_email_sent is False
        assert saved_notification.read_at is None

    def test_notification_with_entity(self, db_session):
        """Test notification with related entity"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create mention notification
        notification = BucketNotification(
            bucket_id=bucket.id,
            user_id="user-456",
            notification_type=NotificationType.COMMENT_MENTION,
            title="You were mentioned",
            message="User123 mentioned you in a comment",
            related_user_id="user-123",
            related_entity_type="comment",
            related_entity_id="comment-789",
        )

        db_session.add(notification)
        db_session.commit()

        # Verify
        saved_notification = db_session.query(BucketNotification).first()
        assert saved_notification.related_entity_type == "comment"
        assert saved_notification.related_entity_id == "comment-789"

    def test_mark_notification_read(self, db_session):
        """Test marking notification as read"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create notification
        notification = BucketNotification(
            bucket_id=bucket.id,
            user_id="user-456",
            notification_type=NotificationType.BUCKET_UPDATED,
            title="Bucket Updated",
            message="Test Bucket has been updated",
        )
        db_session.add(notification)
        db_session.commit()

        # Mark as read
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db_session.commit()

        # Verify
        saved_notification = db_session.query(BucketNotification).first()
        assert saved_notification.is_read is True
        assert saved_notification.read_at is not None


class TestLeadAnnotation:
    """Test LeadAnnotation model"""

    def test_create_annotation(self, db_session):
        """Test creating a lead annotation"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create annotation
        annotation = LeadAnnotation(
            bucket_id=bucket.id,
            lead_id="lead-789",
            user_id="user-123",
            annotation_type="note",
            content="High priority lead - follow up ASAP",
            metadata={"importance": "high"},
        )

        db_session.add(annotation)
        db_session.commit()

        # Verify
        saved_annotation = db_session.query(LeadAnnotation).first()
        assert saved_annotation is not None
        assert saved_annotation.annotation_type == "note"
        assert saved_annotation.content == "High priority lead - follow up ASAP"
        assert saved_annotation.metadata["importance"] == "high"

    def test_annotation_types(self, db_session):
        """Test different annotation types"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create different annotations
        annotations = [
            LeadAnnotation(
                bucket_id=bucket.id,
                lead_id="lead-1",
                user_id="user-123",
                annotation_type="tag",
                metadata={"tags": ["urgent", "high-value"]},
            ),
            LeadAnnotation(
                bucket_id=bucket.id,
                lead_id="lead-1",
                user_id="user-123",
                annotation_type="status",
                content="qualified",
                metadata={"previous_status": "new"},
            ),
            LeadAnnotation(
                bucket_id=bucket.id,
                lead_id="lead-1",
                user_id="user-123",
                annotation_type="priority",
                content="high",
                metadata={"score": 95},
            ),
        ]

        db_session.add_all(annotations)
        db_session.commit()

        # Verify
        saved_annotations = db_session.query(LeadAnnotation).all()
        assert len(saved_annotations) == 3

        types = [a.annotation_type for a in saved_annotations]
        assert "tag" in types
        assert "status" in types
        assert "priority" in types


class TestBucketShareLink:
    """Test BucketShareLink model"""

    def test_create_share_link(self, db_session):
        """Test creating a share link"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create share link
        share_link = BucketShareLink(
            bucket_id=bucket.id,
            share_token="abc123def456",
            permission=BucketPermission.VIEWER,
            created_by="user-123",
        )

        db_session.add(share_link)
        db_session.commit()

        # Verify
        saved_link = db_session.query(BucketShareLink).first()
        assert saved_link is not None
        assert saved_link.share_token == "abc123def456"
        assert saved_link.permission == BucketPermission.VIEWER
        assert saved_link.is_active is True
        assert saved_link.max_uses is None
        assert saved_link.current_uses == 0

    def test_share_link_with_limits(self, db_session):
        """Test share link with usage limits"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create limited share link
        expires = datetime.utcnow() + timedelta(days=7)
        share_link = BucketShareLink(
            bucket_id=bucket.id,
            share_token="xyz789",
            permission=BucketPermission.COMMENTER,
            max_uses=5,
            expires_at=expires,
            created_by="user-123",
        )

        db_session.add(share_link)
        db_session.commit()

        # Simulate usage
        share_link.current_uses = 3
        db_session.commit()

        # Verify
        saved_link = db_session.query(BucketShareLink).first()
        assert saved_link.max_uses == 5
        assert saved_link.current_uses == 3
        assert saved_link.expires_at is not None
        assert saved_link.expires_at > datetime.utcnow()

    def test_deactivate_share_link(self, db_session):
        """Test deactivating a share link"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create share link
        share_link = BucketShareLink(
            bucket_id=bucket.id,
            share_token="temp123",
            permission=BucketPermission.EDITOR,
            created_by="user-123",
        )
        db_session.add(share_link)
        db_session.commit()

        # Deactivate
        share_link.is_active = False
        db_session.commit()

        # Verify
        saved_link = db_session.query(BucketShareLink).first()
        assert saved_link.is_active is False


class TestActiveCollaboration:
    """Test ActiveCollaboration model"""

    def test_create_active_collaboration(self, db_session):
        """Test creating an active collaboration session"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create active collaboration
        collab = ActiveCollaboration(
            bucket_id=bucket.id,
            user_id="user-123",
            session_id="session-abc123",
            connection_type="websocket",
            current_view="overview",
            is_editing=False,
        )

        db_session.add(collab)
        db_session.commit()

        # Verify
        saved_collab = db_session.query(ActiveCollaboration).first()
        assert saved_collab is not None
        assert saved_collab.session_id == "session-abc123"
        assert saved_collab.connection_type == "websocket"
        assert saved_collab.current_view == "overview"
        assert saved_collab.is_editing is False

    def test_update_activity(self, db_session):
        """Test updating last activity"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # Create active collaboration
        collab = ActiveCollaboration(
            bucket_id=bucket.id,
            user_id="user-123",
            session_id="session-xyz789",
            connection_type="polling",
        )
        db_session.add(collab)
        db_session.commit()

        # Update activity
        original_activity = collab.last_activity_at
        collab.last_activity_at = datetime.utcnow()
        collab.current_view = "leads"
        collab.is_editing = True
        db_session.commit()

        # Verify
        saved_collab = db_session.query(ActiveCollaboration).first()
        assert saved_collab.last_activity_at > original_activity
        assert saved_collab.current_view == "leads"
        assert saved_collab.is_editing is True

    def test_unique_user_bucket_active(self, db_session):
        """Test unique constraint on active user-bucket"""
        # Create bucket
        bucket = CollaborativeBucket(
            name="Test Bucket",
            bucket_type="vertical",
            bucket_key="test",
            owner_id="user-123",
        )
        db_session.add(bucket)
        db_session.commit()

        # First session
        collab1 = ActiveCollaboration(
            bucket_id=bucket.id,
            user_id="user-123",
            session_id="session-1",
            connection_type="websocket",
        )
        db_session.add(collab1)
        db_session.commit()

        # Try duplicate user-bucket
        collab2 = ActiveCollaboration(
            bucket_id=bucket.id,
            user_id="user-123",  # Same user
            session_id="session-2",  # Different session
            connection_type="websocket",
        )
        db_session.add(collab2)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()
