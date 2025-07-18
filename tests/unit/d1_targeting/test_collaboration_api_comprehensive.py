"""
Comprehensive API endpoint integration tests for P2-010 Collaborative Buckets.

Tests all API endpoints to achieve ≥80% coverage for collaboration_api.py
"""
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.auth import get_current_user
from d1_targeting.collaboration_api import router
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
from d1_targeting.collaboration_schemas import (
    BucketCreate,
    BucketTagCreate,
    BucketUpdate,
    BulkLeadOperation,
    CommentCreate,
    CommentUpdate,
    LeadAnnotationCreate,
    PermissionGrantCreate,
    PermissionGrantUpdate,
    ShareLinkCreate,
)
from d1_targeting.collaboration_service import WebSocketManager
from database.base import Base
from database.models import Business
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
def test_app(db_session):
    """Create FastAPI test app with dependency overrides"""
    app = FastAPI()
    app.include_router(router)

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session

    return app


@pytest.fixture
def client(test_app, mock_user):
    """Create test client with authentication"""
    test_app.dependency_overrides[get_current_user] = lambda: mock_user
    return TestClient(test_app)


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
def sample_tag(db_session, mock_user):
    """Create a sample tag for testing"""
    tag = BucketTagDefinition(
        name="High Priority",
        color="#FF5733",
        description="High priority buckets",
        created_by=mock_user["id"],
    )
    db_session.add(tag)
    db_session.commit()
    db_session.refresh(tag)
    return tag


@pytest.fixture
def sample_business(db_session):
    """Create a sample business for testing"""
    business = Business(
        name="Test Healthcare Company",
        vert_bucket="healthcare_q1",
        website="https://testhealthcare.com",
        city="Boston",
        state="MA",
        zip_code="02101",
    )
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    return business


class TestBucketCRUD:
    """Test bucket CRUD operations"""

    def test_create_bucket_success(self, client, mock_user, sample_tag):
        """Test successful bucket creation"""
        bucket_data = {
            "name": "New Test Bucket",
            "description": "A test bucket for unit tests",
            "bucket_type": "vertical",
            "bucket_key": "test_vertical",
            "organization_id": mock_user["org_id"],
            "enrichment_config": {"sources": ["internal"]},
            "processing_strategy": "default",
            "priority_level": "medium",
            "tags": [sample_tag.id],
        }

        response = client.post("/api/v1/buckets/", json=bucket_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == bucket_data["name"]
        assert data["bucket_type"] == bucket_data["bucket_type"]
        assert data["user_permission"] == "owner"
        assert len(data["tags"]) == 1
        assert data["tags"][0]["id"] == sample_tag.id

    def test_create_bucket_duplicate_key(self, client, mock_user, sample_bucket):
        """Test creating bucket with duplicate key fails"""
        bucket_data = {
            "name": "Duplicate Bucket",
            "description": "This should fail",
            "bucket_type": "vertical",
            "bucket_key": "healthcare_q1",  # Same as sample_bucket
            "organization_id": mock_user["org_id"],
            "enrichment_config": {"sources": ["internal"]},
            "processing_strategy": "default",
            "priority_level": "medium",
        }

        response = client.post("/api/v1/buckets/", json=bucket_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_get_bucket_success(self, client, sample_bucket):
        """Test successful bucket retrieval"""
        response = client.get(f"/api/v1/buckets/{sample_bucket.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_bucket.id
        assert data["name"] == sample_bucket.name
        assert data["user_permission"] == "owner"
        assert "active_collaborators" in data

    def test_get_bucket_not_found(self, client):
        """Test getting non-existent bucket"""
        response = client.get("/api/v1/buckets/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_buckets_success(self, client, sample_bucket):
        """Test listing buckets"""
        response = client.get("/api/v1/buckets/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["buckets"]) >= 1
        assert data["page"] == 1
        assert data["page_size"] == 20

        # Check bucket data
        bucket = data["buckets"][0]
        assert bucket["id"] == sample_bucket.id
        assert "user_permission" in bucket

    def test_list_buckets_with_filters(self, client, sample_bucket):
        """Test listing buckets with filters"""
        response = client.get(
            "/api/v1/buckets/",
            params={
                "bucket_type": "vertical",
                "search": "Healthcare",
                "page": 1,
                "page_size": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all(b["bucket_type"] == "vertical" for b in data["buckets"])

    @patch("d1_targeting.collaboration_api.create_activity")
    @patch("d1_targeting.collaboration_api.create_version_snapshot")
    def test_update_bucket_success(self, mock_create_version, mock_create_activity, client, sample_bucket):
        """Test successful bucket update"""
        mock_create_activity.return_value = AsyncMock()
        mock_create_version.return_value = AsyncMock()

        update_data = {
            "name": "Updated Healthcare Leads",
            "description": "Updated description",
            "priority_level": "critical",
        }

        response = client.patch(f"/api/v1/buckets/{sample_bucket.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["priority_level"] == update_data["priority_level"]
        assert data["version"] == 2  # Should be incremented

        # Verify activity was created
        mock_create_activity.assert_called_once()
        mock_create_version.assert_called_once()

    def test_update_bucket_not_found(self, client):
        """Test updating non-existent bucket"""
        update_data = {"name": "Updated Name"}

        response = client.patch("/api/v1/buckets/non-existent-id", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("d1_targeting.collaboration_api.create_activity")
    def test_delete_bucket_success(self, mock_create_activity, client, sample_bucket):
        """Test successful bucket deletion (archiving)"""
        mock_create_activity.return_value = AsyncMock()

        response = client.delete(f"/api/v1/buckets/{sample_bucket.id}")

        assert response.status_code == 200
        assert "archived successfully" in response.json()["message"]

        # Verify activity was created
        mock_create_activity.assert_called_once()

    def test_delete_bucket_not_found(self, client):
        """Test deleting non-existent bucket"""
        response = client.delete("/api/v1/buckets/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestPermissionManagement:
    """Test permission management endpoints"""

    def test_grant_permission_success(self, client, sample_bucket, mock_user_2):
        """Test successful permission grant"""
        grant_data = {
            "user_id": mock_user_2["id"],
            "permission": "editor",
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "send_notification": True,
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity, patch(
            "d1_targeting.collaboration_api.create_notification"
        ) as mock_notification:
            mock_activity.return_value = AsyncMock()
            mock_notification.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/permissions", json=grant_data)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == mock_user_2["id"]
        assert data["permission"] == "editor"
        assert data["expires_at"] is not None

        # Verify activity and notification were created
        mock_activity.assert_called_once()
        mock_notification.assert_called_once()

    def test_grant_permission_duplicate(self, client, sample_bucket, mock_user):
        """Test granting permission to user who already has permission"""
        grant_data = {
            "user_id": mock_user["id"],  # Owner already has permission
            "permission": "editor",
        }

        response = client.post(f"/api/v1/buckets/{sample_bucket.id}/permissions", json=grant_data)

        assert response.status_code == 409
        assert "already has permission" in response.json()["detail"]

    def test_list_permissions_success(self, client, sample_bucket):
        """Test listing bucket permissions"""
        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/permissions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1  # At least the owner permission

        # Check owner permission
        owner_perm = next(p for p in data if p["permission"] == "owner")
        assert owner_perm["user_info"]["user_id"] == sample_bucket.owner_id

    def test_update_permission_success(self, client, sample_bucket, mock_user_2, db_session):
        """Test successful permission update"""
        # First create a permission to update
        permission = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.VIEWER,
            granted_by=sample_bucket.owner_id,
        )
        db_session.add(permission)
        db_session.commit()

        update_data = {
            "permission": "editor",
            "expires_at": (datetime.utcnow() + timedelta(days=60)).isoformat(),
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.patch(
                f"/api/v1/buckets/{sample_bucket.id}/permissions/{mock_user_2['id']}", json=update_data
            )

        assert response.status_code == 200
        data = response.json()
        assert data["permission"] == "editor"
        assert data["expires_at"] is not None

        # Verify activity was created
        mock_activity.assert_called_once()

    def test_update_permission_not_found(self, client, sample_bucket):
        """Test updating non-existent permission"""
        update_data = {"permission": "editor"}

        response = client.patch(f"/api/v1/buckets/{sample_bucket.id}/permissions/non-existent-user", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_owner_permission_forbidden(self, client, sample_bucket, mock_user):
        """Test updating owner permission is forbidden"""
        update_data = {"permission": "editor"}

        response = client.patch(f"/api/v1/buckets/{sample_bucket.id}/permissions/{mock_user['id']}", json=update_data)

        assert response.status_code == 403
        assert "Cannot modify owner permission" in response.json()["detail"]

    def test_revoke_permission_success(self, client, sample_bucket, mock_user_2, db_session):
        """Test successful permission revocation"""
        # First create a permission to revoke
        permission = BucketPermissionGrant(
            bucket_id=sample_bucket.id,
            user_id=mock_user_2["id"],
            permission=BucketPermission.EDITOR,
            granted_by=sample_bucket.owner_id,
        )
        db_session.add(permission)
        db_session.commit()

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity, patch(
            "d1_targeting.collaboration_api.create_notification"
        ) as mock_notification:
            mock_activity.return_value = AsyncMock()
            mock_notification.return_value = AsyncMock()

            response = client.delete(f"/api/v1/buckets/{sample_bucket.id}/permissions/{mock_user_2['id']}")

        assert response.status_code == 200
        assert "revoked successfully" in response.json()["message"]

        # Verify activity and notification were created
        mock_activity.assert_called_once()
        mock_notification.assert_called_once()

    def test_revoke_owner_permission_forbidden(self, client, sample_bucket, mock_user):
        """Test revoking owner permission is forbidden"""
        response = client.delete(f"/api/v1/buckets/{sample_bucket.id}/permissions/{mock_user['id']}")

        assert response.status_code == 403
        assert "Cannot revoke owner permission" in response.json()["detail"]


class TestActivityFeed:
    """Test activity feed endpoints"""

    def test_get_activity_feed_success(self, client, sample_bucket, db_session):
        """Test getting activity feed"""
        # Create some activities
        activity1 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            activity_type=BucketActivityType.CREATED,
            new_values={"name": sample_bucket.name},
        )
        activity2 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            activity_type=BucketActivityType.UPDATED,
            old_values={"name": "Old Name"},
            new_values={"name": "New Name"},
        )
        db_session.add_all([activity1, activity2])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/activities")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["activities"]) >= 2
        assert data["page"] == 1
        assert data["page_size"] == 50

        # Check activities have user info
        for activity in data["activities"]:
            assert "user_info" in activity
            assert activity["user_info"]["user_id"] is not None

    def test_get_activity_feed_with_filter(self, client, sample_bucket, db_session):
        """Test getting activity feed with type filter"""
        # Create activities of different types
        activity1 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            activity_type=BucketActivityType.CREATED,
        )
        activity2 = BucketActivity(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            activity_type=BucketActivityType.UPDATED,
        )
        db_session.add_all([activity1, activity2])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/activities", params={"activity_type": "created"})

        assert response.status_code == 200
        data = response.json()
        assert all(a["activity_type"] == "created" for a in data["activities"])

    def test_get_activity_feed_pagination(self, client, sample_bucket, db_session):
        """Test activity feed pagination"""
        # Create multiple activities
        activities = []
        for i in range(25):
            activity = BucketActivity(
                bucket_id=sample_bucket.id,
                user_id=sample_bucket.owner_id,
                activity_type=BucketActivityType.UPDATED,
                new_values={"step": i},
            )
            activities.append(activity)
        db_session.add_all(activities)
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/activities", params={"page": 1, "page_size": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) == 10
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] >= 25


class TestComments:
    """Test comment endpoints"""

    def test_create_comment_success(self, client, sample_bucket, sample_business):
        """Test successful comment creation"""
        comment_data = {
            "content": "This is a test comment",
            "lead_id": sample_business.id,
            "mentioned_users": ["user-789"],
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity, patch(
            "d1_targeting.collaboration_api.create_notification"
        ) as mock_notification:
            mock_activity.return_value = AsyncMock()
            mock_notification.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/comments", json=comment_data)

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == comment_data["content"]
        assert data["lead_id"] == comment_data["lead_id"]
        assert data["mentioned_users"] == comment_data["mentioned_users"]
        assert "user_info" in data

        # Verify activity and notification were created
        mock_activity.assert_called_once()
        mock_notification.assert_called_once()

    def test_create_bucket_comment_success(self, client, sample_bucket):
        """Test successful bucket-level comment creation"""
        comment_data = {
            "content": "This is a bucket comment",
            "lead_id": None,
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/comments", json=comment_data)

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == comment_data["content"]
        assert data["lead_id"] is None

        # Verify activity was created
        mock_activity.assert_called_once()

    def test_list_comments_success(self, client, sample_bucket, db_session):
        """Test listing comments"""
        # Create some comments
        comment1 = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            content="First comment",
        )
        comment2 = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            content="Second comment",
        )
        db_session.add_all([comment1, comment2])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/comments")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

        # Check comments have user info and reply count
        for comment in data:
            assert "user_info" in comment
            assert "reply_count" in comment

    def test_list_comments_with_filters(self, client, sample_bucket, sample_business, db_session):
        """Test listing comments with filters"""
        # Create comments for different leads
        comment1 = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            content="Lead comment",
            lead_id=sample_business.id,
        )
        comment2 = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            content="Bucket comment",
            lead_id=None,
        )
        db_session.add_all([comment1, comment2])
        db_session.commit()

        # Test lead filter
        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/comments", params={"lead_id": sample_business.id})

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(c["lead_id"] == sample_business.id for c in data)

    def test_update_comment_success(self, client, sample_bucket, db_session):
        """Test successful comment update"""
        # Create a comment to update
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            content="Original content",
        )
        db_session.add(comment)
        db_session.commit()

        update_data = {
            "content": "Updated content",
            "mentioned_users": ["user-999"],
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.patch(f"/api/v1/buckets/{sample_bucket.id}/comments/{comment.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == update_data["content"]
        assert data["mentioned_users"] == update_data["mentioned_users"]
        assert data["is_edited"] is True

        # Verify activity was created
        mock_activity.assert_called_once()

    def test_update_comment_not_found(self, client, sample_bucket):
        """Test updating non-existent comment"""
        update_data = {"content": "Updated content"}

        response = client.patch(f"/api/v1/buckets/{sample_bucket.id}/comments/non-existent-id", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_delete_comment_success(self, client, sample_bucket, db_session):
        """Test successful comment deletion"""
        # Create a comment to delete
        comment = BucketComment(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            content="To be deleted",
        )
        db_session.add(comment)
        db_session.commit()

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.delete(f"/api/v1/buckets/{sample_bucket.id}/comments/{comment.id}")

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify activity was created
        mock_activity.assert_called_once()

    def test_delete_comment_not_found(self, client, sample_bucket):
        """Test deleting non-existent comment"""
        response = client.delete(f"/api/v1/buckets/{sample_bucket.id}/comments/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestVersionHistory:
    """Test version history endpoints"""

    def test_get_version_history_success(self, client, sample_bucket, db_session):
        """Test getting version history"""
        # Create some versions
        version1 = BucketVersion(
            bucket_id=sample_bucket.id,
            version_number=1,
            change_type="config",
            changed_by=sample_bucket.owner_id,
            description="Initial version",
            snapshot_data={"name": "Original Name"},
        )
        version2 = BucketVersion(
            bucket_id=sample_bucket.id,
            version_number=2,
            change_type="config",
            changed_by=sample_bucket.owner_id,
            description="Updated version",
            snapshot_data={"name": "Updated Name"},
        )
        db_session.add_all([version1, version2])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/versions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["versions"]) >= 2

        # Check versions have user info
        for version in data["versions"]:
            assert "user_info" in version
            assert version["user_info"]["user_id"] is not None

    def test_get_version_success(self, client, sample_bucket, db_session):
        """Test getting specific version"""
        # Create a version
        version = BucketVersion(
            bucket_id=sample_bucket.id,
            version_number=1,
            change_type="config",
            changed_by=sample_bucket.owner_id,
            description="Test version",
            snapshot_data={"name": "Test Name"},
        )
        db_session.add(version)
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/versions/{version.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == version.id
        assert data["version_number"] == 1
        assert data["description"] == "Test version"
        assert "user_info" in data

    def test_get_version_not_found(self, client, sample_bucket):
        """Test getting non-existent version"""
        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/versions/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestLeadAnnotations:
    """Test lead annotation endpoints"""

    def test_create_lead_annotation_success(self, client, sample_bucket, sample_business):
        """Test successful lead annotation creation"""
        annotation_data = {
            "lead_id": sample_business.id,
            "annotation_type": "quality_score",
            "value": "high",
            "notes": "This is a high-quality lead",
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/annotations", json=annotation_data)

        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == annotation_data["lead_id"]
        assert data["annotation_type"] == annotation_data["annotation_type"]
        assert data["value"] == annotation_data["value"]
        assert data["notes"] == annotation_data["notes"]
        assert "user_info" in data

        # Verify activity was created
        mock_activity.assert_called_once()

    def test_create_lead_annotation_lead_not_found(self, client, sample_bucket):
        """Test creating annotation for non-existent lead"""
        annotation_data = {
            "lead_id": "non-existent-lead",
            "annotation_type": "quality_score",
            "value": "high",
        }

        response = client.post(f"/api/v1/buckets/{sample_bucket.id}/annotations", json=annotation_data)

        assert response.status_code == 404
        assert "not found in bucket" in response.json()["detail"]

    def test_list_lead_annotations_success(self, client, sample_bucket, sample_business, db_session):
        """Test listing lead annotations"""
        # Create some annotations
        annotation1 = LeadAnnotation(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            lead_id=sample_business.id,
            annotation_type="quality_score",
            value="high",
        )
        annotation2 = LeadAnnotation(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            lead_id=sample_business.id,
            annotation_type="priority",
            value="urgent",
        )
        db_session.add_all([annotation1, annotation2])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/annotations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

        # Check annotations have user info
        for annotation in data:
            assert "user_info" in annotation

    def test_list_lead_annotations_with_filters(self, client, sample_bucket, sample_business, db_session):
        """Test listing annotations with filters"""
        # Create annotations with different types
        annotation1 = LeadAnnotation(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            lead_id=sample_business.id,
            annotation_type="quality_score",
            value="high",
        )
        annotation2 = LeadAnnotation(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            lead_id=sample_business.id,
            annotation_type="priority",
            value="urgent",
        )
        db_session.add_all([annotation1, annotation2])
        db_session.commit()

        # Test with lead_id filter
        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/annotations", params={"lead_id": sample_business.id})

        assert response.status_code == 200
        data = response.json()
        assert all(a["lead_id"] == sample_business.id for a in data)

        # Test with annotation_type filter
        response = client.get(
            f"/api/v1/buckets/{sample_bucket.id}/annotations", params={"annotation_type": "quality_score"}
        )

        assert response.status_code == 200
        data = response.json()
        assert all(a["annotation_type"] == "quality_score" for a in data)


class TestShareLinks:
    """Test share link endpoints"""

    def test_create_share_link_success(self, client, sample_bucket):
        """Test successful share link creation"""
        share_data = {
            "permission": "viewer",
            "max_uses": 10,
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        with patch("d1_targeting.collaboration_api.settings") as mock_settings:
            mock_settings.BASE_URL = "https://example.com"

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/share-links", json=share_data)

        assert response.status_code == 200
        data = response.json()
        assert data["permission"] == share_data["permission"]
        assert data["max_uses"] == share_data["max_uses"]
        assert data["expires_at"] is not None
        assert "share_url" in data
        assert "share_token" in data
        assert data["is_active"] is True

    def test_list_share_links_success(self, client, sample_bucket, db_session):
        """Test listing share links"""
        # Create a share link
        share_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="test-token-123",
            permission=BucketPermission.VIEWER,
            max_uses=5,
            current_uses=2,
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_by=sample_bucket.owner_id,
        )
        db_session.add(share_link)
        db_session.commit()

        with patch("d1_targeting.collaboration_api.settings") as mock_settings:
            mock_settings.BASE_URL = "https://example.com"

            response = client.get(f"/api/v1/buckets/{sample_bucket.id}/share-links")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Check share URLs are built
        for link in data:
            assert "share_url" in link
            assert "example.com" in link["share_url"]

    def test_list_share_links_active_only(self, client, sample_bucket, db_session):
        """Test listing active share links only"""
        # Create active and inactive share links
        active_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="active-token",
            permission=BucketPermission.VIEWER,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_by=sample_bucket.owner_id,
        )
        inactive_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="inactive-token",
            permission=BucketPermission.VIEWER,
            is_active=False,
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_by=sample_bucket.owner_id,
        )
        db_session.add_all([active_link, inactive_link])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/share-links", params={"active_only": True})

        assert response.status_code == 200
        data = response.json()
        assert all(link["is_active"] for link in data)

    def test_revoke_share_link_success(self, client, sample_bucket, db_session):
        """Test successful share link revocation"""
        # Create a share link
        share_link = BucketShareLink(
            bucket_id=sample_bucket.id,
            share_token="test-token-456",
            permission=BucketPermission.VIEWER,
            created_by=sample_bucket.owner_id,
        )
        db_session.add(share_link)
        db_session.commit()

        response = client.delete(f"/api/v1/buckets/{sample_bucket.id}/share-links/{share_link.id}")

        assert response.status_code == 200
        assert "revoked successfully" in response.json()["message"]

    def test_revoke_share_link_not_found(self, client, sample_bucket):
        """Test revoking non-existent share link"""
        response = client.delete(f"/api/v1/buckets/{sample_bucket.id}/share-links/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestNotifications:
    """Test notification endpoints"""

    def test_list_notifications_success(self, client, sample_bucket, db_session, mock_user):
        """Test listing notifications"""
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
            title="Mentioned in Comment",
            message="You were mentioned",
            is_read=True,
        )
        db_session.add_all([notification1, notification2])
        db_session.commit()

        response = client.get("/api/v1/buckets/notifications")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["notifications"]) >= 2
        assert data["unread_count"] >= 1

        # Check notifications have bucket info
        for notification in data["notifications"]:
            assert "bucket_info" in notification
            if notification["bucket_info"]:
                assert notification["bucket_info"]["id"] == sample_bucket.id

    def test_list_notifications_unread_only(self, client, sample_bucket, db_session, mock_user):
        """Test listing unread notifications only"""
        # Create read and unread notifications
        read_notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Read Notification",
            message="This is read",
            is_read=True,
        )
        unread_notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.COMMENT_MENTION,
            title="Unread Notification",
            message="This is unread",
            is_read=False,
        )
        db_session.add_all([read_notification, unread_notification])
        db_session.commit()

        response = client.get("/api/v1/buckets/notifications", params={"unread_only": True})

        assert response.status_code == 200
        data = response.json()
        assert all(not n["is_read"] for n in data["notifications"])

    def test_mark_notification_read_success(self, client, sample_bucket, db_session, mock_user):
        """Test marking notification as read"""
        # Create an unread notification
        notification = BucketNotification(
            bucket_id=sample_bucket.id,
            user_id=mock_user["id"],
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Test Notification",
            message="Test message",
            is_read=False,
        )
        db_session.add(notification)
        db_session.commit()

        response = client.patch(f"/api/v1/buckets/notifications/{notification.id}/read")

        assert response.status_code == 200
        assert "marked as read" in response.json()["message"]

        # Verify notification is marked as read
        db_session.refresh(notification)
        assert notification.is_read is True
        assert notification.read_at is not None

    def test_mark_notification_read_not_found(self, client):
        """Test marking non-existent notification as read"""
        response = client.patch("/api/v1/buckets/notifications/non-existent-id/read")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_mark_all_notifications_read_success(self, client, sample_bucket, db_session, mock_user):
        """Test marking all notifications as read"""
        # Create multiple unread notifications
        notifications = []
        for i in range(3):
            notification = BucketNotification(
                bucket_id=sample_bucket.id,
                user_id=mock_user["id"],
                notification_type=NotificationType.PERMISSION_GRANTED,
                title=f"Test Notification {i}",
                message=f"Test message {i}",
                is_read=False,
            )
            notifications.append(notification)
        db_session.add_all(notifications)
        db_session.commit()

        response = client.post("/api/v1/buckets/notifications/mark-all-read")

        assert response.status_code == 200
        assert "All notifications marked as read" in response.json()["message"]

        # Verify all notifications are marked as read
        for notification in notifications:
            db_session.refresh(notification)
            assert notification.is_read is True


class TestBulkOperations:
    """Test bulk lead operations"""

    def test_bulk_add_leads_success(self, client, sample_bucket, db_session):
        """Test bulk adding leads to bucket"""
        # Create some businesses
        businesses = []
        for i in range(3):
            business = Business(
                name=f"Test Business {i}",
                website=f"https://test{i}.com",
                city="Boston",
                state="MA",
                zip_code="02101",
            )
            businesses.append(business)
        db_session.add_all(businesses)
        db_session.commit()

        operation_data = {
            "operation": "add",
            "lead_ids": [b.id for b in businesses],
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/leads/bulk", json=operation_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 3
        assert data["failure_count"] == 0
        assert data["failures"] is None

        # Verify activity was created for each lead
        assert mock_activity.call_count == 3

    def test_bulk_remove_leads_success(self, client, sample_bucket, db_session):
        """Test bulk removing leads from bucket"""
        # Create some businesses already in the bucket
        businesses = []
        for i in range(3):
            business = Business(
                name=f"Test Business {i}",
                website=f"https://test{i}.com",
                city="Boston",
                state="MA",
                zip_code="02101",
                vert_bucket=sample_bucket.bucket_key,  # Already in bucket
            )
            businesses.append(business)
        db_session.add_all(businesses)
        db_session.commit()

        operation_data = {
            "operation": "remove",
            "lead_ids": [b.id for b in businesses],
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/leads/bulk", json=operation_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 3
        assert data["failure_count"] == 0

        # Verify activity was created for each lead
        assert mock_activity.call_count == 3

    def test_bulk_operation_with_failures(self, client, sample_bucket, db_session):
        """Test bulk operation with some failures"""
        # Create one valid business
        business = Business(
            name="Valid Business",
            website="https://valid.com",
            city="Boston",
            state="MA",
            zip_code="02101",
        )
        db_session.add(business)
        db_session.commit()

        operation_data = {
            "operation": "add",
            "lead_ids": [business.id, "invalid-id-1", "invalid-id-2"],
        }

        with patch("d1_targeting.collaboration_api.create_activity") as mock_activity:
            mock_activity.return_value = AsyncMock()

            response = client.post(f"/api/v1/buckets/{sample_bucket.id}/leads/bulk", json=operation_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 1
        assert data["failure_count"] == 2
        assert data["failures"] is not None
        assert len(data["failures"]) == 2


class TestCollaborationStatus:
    """Test collaboration status endpoint"""

    def test_get_collaboration_status_success(self, client, sample_bucket, db_session):
        """Test getting collaboration status"""
        # Create some active collaborations
        collab1 = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id=sample_bucket.owner_id,
            session_id="session-123",
            connection_type="websocket",
            current_view="bucket_overview",
            is_editing=False,
        )
        collab2 = ActiveCollaboration(
            bucket_id=sample_bucket.id,
            user_id="user-456",
            session_id="session-456",
            connection_type="websocket",
            current_view="lead_details",
            is_editing=True,
        )
        db_session.add_all([collab1, collab2])
        db_session.commit()

        response = client.get(f"/api/v1/buckets/{sample_bucket.id}/collaboration-status")

        assert response.status_code == 200
        data = response.json()
        assert data["bucket_id"] == sample_bucket.id
        assert data["total_collaborators"] >= 2
        assert len(data["active_collaborators"]) >= 2

        # Check collaborators have user info
        for collab in data["active_collaborators"]:
            assert "user_info" in collab
            assert collab["user_info"]["user_id"] is not None


class TestTagManagement:
    """Test tag management endpoints"""

    def test_create_tag_success(self, client, mock_user):
        """Test successful tag creation"""
        tag_data = {
            "name": "Urgent",
            "color": "#FF0000",
            "description": "Urgent priority buckets",
        }

        response = client.post("/api/v1/buckets/tags", json=tag_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == tag_data["name"]
        assert data["color"] == tag_data["color"]
        assert data["description"] == tag_data["description"]
        assert data["created_by"] == mock_user["id"]

    def test_create_tag_duplicate_name(self, client, sample_tag):
        """Test creating tag with duplicate name"""
        tag_data = {
            "name": sample_tag.name,  # Same name as existing tag
            "color": "#00FF00",
            "description": "Duplicate tag",
        }

        response = client.post("/api/v1/buckets/tags", json=tag_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_list_tags_success(self, client, sample_tag):
        """Test listing tags"""
        response = client.get("/api/v1/buckets/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Check sample tag is in the list
        tag_names = [tag["name"] for tag in data]
        assert sample_tag.name in tag_names
