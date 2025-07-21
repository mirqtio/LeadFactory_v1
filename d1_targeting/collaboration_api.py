"""
P2-010: Collaborative Bucket API

FastAPI endpoints for multi-user bucket collaboration including
sharing, permissions, activity tracking, and real-time updates.
"""

import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from core.auth import get_current_user
from core.config import get_settings
from database.models import Business
from database.session import get_db

from .collaboration_models import (
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
from .collaboration_schemas import (
    ActivityFeedResponse,
    BucketCreate,
    BucketListResponse,
    BucketResponse,
    BucketTagCreate,
    BucketTagResponse,
    BucketUpdate,
    BulkLeadOperation,
    BulkOperationResponse,
    CollaborationStatusResponse,
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    LeadAnnotationCreate,
    LeadAnnotationResponse,
    NotificationListResponse,
    PermissionGrantCreate,
    PermissionGrantResponse,
    PermissionGrantUpdate,
    ShareLinkCreate,
    ShareLinkResponse,
    UserInfo,
    VersionListResponse,
    VersionResponse,
    WSMessage,
    WSMessageType,
)
from .collaboration_service import (
    BucketCollaborationService,
    WebSocketManager,
    check_bucket_permission,
    create_activity,
    create_notification,
    create_version_snapshot,
)

# Initialize router
router = APIRouter(prefix="/api/v1/buckets", tags=["collaborative-buckets"])

# Initialize WebSocket manager
ws_manager = WebSocketManager()

# Initialize settings
settings = get_settings()


# Bucket CRUD endpoints
@router.post("/", response_model=BucketResponse)
async def create_bucket(
    bucket: BucketCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new collaborative bucket"""
    service = BucketCollaborationService(db)

    # Check if bucket already exists
    existing = (
        db.query(CollaborativeBucket)
        .filter(
            and_(
                CollaborativeBucket.organization_id == bucket.organization_id,
                CollaborativeBucket.bucket_type == bucket.bucket_type,
                CollaborativeBucket.bucket_key == bucket.bucket_key,
                CollaborativeBucket.is_archived == False,
            )
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bucket with this type and key already exists in the organization",
        )

    # Create bucket
    db_bucket = CollaborativeBucket(
        **bucket.model_dump(exclude={"tags"}),
        owner_id=current_user["id"],
    )

    # Add tags if provided
    if bucket.tags:
        tags = db.query(BucketTagDefinition).filter(BucketTagDefinition.id.in_(bucket.tags)).all()
        db_bucket.tags = tags

    db.add(db_bucket)

    # Grant owner permission
    permission = BucketPermissionGrant(
        bucket_id=db_bucket.id,
        user_id=current_user["id"],
        permission=BucketPermission.OWNER,
        granted_by=current_user["id"],
    )
    db.add(permission)

    # Create activity
    await create_activity(
        db,
        bucket_id=db_bucket.id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.CREATED,
        new_values={"name": db_bucket.name, "type": db_bucket.bucket_type},
    )

    db.commit()
    db.refresh(db_bucket)

    # Set user permission for response
    db_bucket.user_permission = BucketPermission.OWNER

    return db_bucket


@router.get("/{bucket_id}", response_model=BucketResponse)
async def get_bucket(
    bucket_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific bucket"""
    # Check permission
    permission = await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Get bucket with relationships
    bucket = (
        db.query(CollaborativeBucket)
        .options(selectinload(CollaborativeBucket.tags))
        .filter(CollaborativeBucket.id == bucket_id)
        .first()
    )

    if not bucket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found")

    # Add user permission and active collaborators
    bucket.user_permission = permission

    active_count = (
        db.query(func.count(ActiveCollaboration.id)).filter(ActiveCollaboration.bucket_id == bucket_id).scalar()
    )
    bucket.active_collaborators = active_count

    return bucket


@router.get("/", response_model=BucketListResponse)
async def list_buckets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    bucket_type: str | None = None,
    is_archived: bool = False,
    search: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List buckets accessible to the current user"""
    # Base query - buckets where user has permission
    query = (
        db.query(CollaborativeBucket)
        .join(BucketPermissionGrant, CollaborativeBucket.id == BucketPermissionGrant.bucket_id)
        .filter(
            BucketPermissionGrant.user_id == current_user["id"],
            CollaborativeBucket.is_archived == is_archived,
        )
    )

    # Apply filters
    if bucket_type:
        query = query.filter(CollaborativeBucket.bucket_type == bucket_type)

    if search:
        query = query.filter(
            or_(
                CollaborativeBucket.name.ilike(f"%{search}%"),
                CollaborativeBucket.description.ilike(f"%{search}%"),
                CollaborativeBucket.bucket_key.ilike(f"%{search}%"),
            )
        )

    # Get total count
    total = query.count()

    # Apply pagination
    buckets = (
        query.options(selectinload(CollaborativeBucket.tags), selectinload(CollaborativeBucket.permissions))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Add user permissions to each bucket
    for bucket in buckets:
        user_perm = next((p for p in bucket.permissions if p.user_id == current_user["id"]), None)
        bucket.user_permission = user_perm.permission if user_perm else None

    return BucketListResponse(
        buckets=buckets,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{bucket_id}", response_model=BucketResponse)
async def update_bucket(
    bucket_id: str,
    bucket_update: BucketUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.EDITOR, BucketPermission.ADMIN])

    # Get bucket
    bucket = db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

    if not bucket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found")

    # Create version snapshot before update
    await create_version_snapshot(db, bucket, current_user["id"], "config", "Bucket configuration updated")

    # Track changes for activity
    old_values = {}
    new_values = {}

    # Update fields
    update_data = bucket_update.model_dump(exclude_unset=True, exclude={"tags"})
    for field, value in update_data.items():
        old_value = getattr(bucket, field)
        if old_value != value:
            old_values[field] = old_value
            new_values[field] = value
            setattr(bucket, field, value)

    # Update tags if provided
    if bucket_update.tags is not None:
        old_tag_ids = [t.id for t in bucket.tags]
        if set(old_tag_ids) != set(bucket_update.tags):
            tags = db.query(BucketTagDefinition).filter(BucketTagDefinition.id.in_(bucket_update.tags)).all()
            bucket.tags = tags
            old_values["tags"] = old_tag_ids
            new_values["tags"] = bucket_update.tags

    # Increment version
    bucket.version += 1
    bucket.updated_at = datetime.utcnow()

    # Create activity
    if old_values:
        await create_activity(
            db,
            bucket_id=bucket_id,
            user_id=current_user["id"],
            activity_type=BucketActivityType.UPDATED,
            old_values=old_values,
            new_values=new_values,
        )

        # Send WebSocket notification
        await ws_manager.send_bucket_message(
            bucket_id,
            WSMessage(
                type=WSMessageType.BUCKET_UPDATED,
                bucket_id=bucket_id,
                user_id=current_user["id"],
                data={"changes": new_values},
            ),
        )

    db.commit()
    db.refresh(bucket)

    return bucket


@router.delete("/{bucket_id}")
async def delete_bucket(
    bucket_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete (archive) a bucket"""
    # Check permission - only owner can delete
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.OWNER])

    # Get bucket
    bucket = db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

    if not bucket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found")

    # Archive instead of hard delete
    bucket.is_archived = True
    bucket.updated_at = datetime.utcnow()

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.ARCHIVED,
    )

    db.commit()

    return {"message": "Bucket archived successfully"}


# Permission management endpoints
@router.post("/{bucket_id}/permissions", response_model=PermissionGrantResponse)
async def grant_permission(
    bucket_id: str,
    grant: PermissionGrantCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant permission to a user for a bucket"""
    # Check permission - only admin/owner can grant permissions
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER])

    # Check if permission already exists
    existing = (
        db.query(BucketPermissionGrant)
        .filter(
            and_(
                BucketPermissionGrant.bucket_id == bucket_id,
                BucketPermissionGrant.user_id == grant.user_id,
            )
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has permission for this bucket")

    # Create permission grant
    db_grant = BucketPermissionGrant(
        bucket_id=bucket_id,
        user_id=grant.user_id,
        permission=grant.permission,
        granted_by=current_user["id"],
        expires_at=grant.expires_at,
    )
    db.add(db_grant)

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.SHARED,
        entity_type="permission",
        entity_id=grant.user_id,
        new_values={"permission": grant.permission.value},
    )

    # Create notification
    if grant.send_notification:
        bucket = db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

        await create_notification(
            db,
            bucket_id=bucket_id,
            user_id=grant.user_id,
            notification_type=NotificationType.PERMISSION_GRANTED,
            title="Bucket Access Granted",
            message=f"You have been granted {grant.permission.value} access to '{bucket.name}'",
            related_user_id=current_user["id"],
        )

    db.commit()
    db.refresh(db_grant)

    return db_grant


@router.get("/{bucket_id}/permissions", response_model=list[PermissionGrantResponse])
async def list_permissions(
    bucket_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all permissions for a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Get permissions
    permissions = db.query(BucketPermissionGrant).filter(BucketPermissionGrant.bucket_id == bucket_id).all()

    # Add user info (mock for now)
    for perm in permissions:
        perm.user_info = UserInfo(
            user_id=perm.user_id, name=f"User {perm.user_id[:8]}", email=f"user{perm.user_id[:8]}@example.com"
        )

    return permissions


@router.patch("/{bucket_id}/permissions/{user_id}", response_model=PermissionGrantResponse)
async def update_permission(
    bucket_id: str,
    user_id: str,
    permission_update: PermissionGrantUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a user's permission for a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER])

    # Get permission grant
    grant = (
        db.query(BucketPermissionGrant)
        .filter(
            and_(
                BucketPermissionGrant.bucket_id == bucket_id,
                BucketPermissionGrant.user_id == user_id,
            )
        )
        .first()
    )

    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission grant not found")

    # Don't allow changing owner permission
    if grant.permission == BucketPermission.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify owner permission")

    # Update permission
    old_permission = grant.permission
    grant.permission = permission_update.permission
    if permission_update.expires_at is not None:
        grant.expires_at = permission_update.expires_at

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.PERMISSION_CHANGED,
        entity_type="permission",
        entity_id=user_id,
        old_values={"permission": old_permission.value},
        new_values={"permission": permission_update.permission.value},
    )

    # Send WebSocket notification
    await ws_manager.send_bucket_message(
        bucket_id,
        WSMessage(
            type=WSMessageType.PERMISSION_CHANGED,
            bucket_id=bucket_id,
            user_id=current_user["id"],
            data={
                "affected_user_id": user_id,
                "new_permission": permission_update.permission.value,
            },
        ),
    )

    db.commit()
    db.refresh(grant)

    return grant


@router.delete("/{bucket_id}/permissions/{user_id}")
async def revoke_permission(
    bucket_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a user's permission for a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER])

    # Get permission grant
    grant = (
        db.query(BucketPermissionGrant)
        .filter(
            and_(
                BucketPermissionGrant.bucket_id == bucket_id,
                BucketPermissionGrant.user_id == user_id,
            )
        )
        .first()
    )

    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission grant not found")

    # Don't allow revoking owner permission
    if grant.permission == BucketPermission.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot revoke owner permission")

    # Delete permission
    db.delete(grant)

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.UNSHARED,
        entity_type="permission",
        entity_id=user_id,
        old_values={"permission": grant.permission.value},
    )

    # Create notification
    bucket = db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

    await create_notification(
        db,
        bucket_id=bucket_id,
        user_id=user_id,
        notification_type=NotificationType.PERMISSION_REVOKED,
        title="Bucket Access Revoked",
        message=f"Your access to '{bucket.name}' has been revoked",
        related_user_id=current_user["id"],
    )

    db.commit()

    return {"message": "Permission revoked successfully"}


# Activity feed endpoints
@router.get("/{bucket_id}/activities", response_model=ActivityFeedResponse)
async def get_activity_feed(
    bucket_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    activity_type: BucketActivityType | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get activity feed for a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Build query
    query = db.query(BucketActivity).filter(BucketActivity.bucket_id == bucket_id)

    if activity_type:
        query = query.filter(BucketActivity.activity_type == activity_type)

    # Order by most recent
    query = query.order_by(BucketActivity.created_at.desc())

    # Get total count
    total = query.count()

    # Apply pagination
    activities = query.offset((page - 1) * page_size).limit(page_size).all()

    # Add user info (mock for now)
    for activity in activities:
        activity.user_info = UserInfo(
            user_id=activity.user_id,
            name=f"User {activity.user_id[:8]}",
            email=f"user{activity.user_id[:8]}@example.com",
        )

    return ActivityFeedResponse(
        activities=activities,
        total=total,
        page=page,
        page_size=page_size,
    )


# Comment endpoints
@router.post("/{bucket_id}/comments", response_model=CommentResponse)
async def create_comment(
    bucket_id: str,
    comment: CommentCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a comment on a bucket or lead"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.COMMENTER])

    # Create comment
    db_comment = BucketComment(
        bucket_id=bucket_id,
        user_id=current_user["id"],
        **comment.model_dump(),
    )
    db.add(db_comment)

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.COMMENT_ADDED,
        entity_type="comment",
        entity_id=db_comment.id,
        new_values={"lead_id": comment.lead_id} if comment.lead_id else None,
    )

    # Create notifications for mentions
    if comment.mentioned_users:
        bucket = db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

        for mentioned_user_id in comment.mentioned_users:
            await create_notification(
                db,
                bucket_id=bucket_id,
                user_id=mentioned_user_id,
                notification_type=NotificationType.COMMENT_MENTION,
                title="You were mentioned in a comment",
                message=f"You were mentioned in a comment on '{bucket.name}'",
                related_user_id=current_user["id"],
                related_entity_type="comment",
                related_entity_id=db_comment.id,
            )

    # Send WebSocket notification
    await ws_manager.send_bucket_message(
        bucket_id,
        WSMessage(
            type=WSMessageType.COMMENT_ADDED,
            bucket_id=bucket_id,
            user_id=current_user["id"],
            data={
                "comment_id": db_comment.id,
                "lead_id": comment.lead_id,
                "content": comment.content[:100],  # Preview
            },
        ),
    )

    db.commit()
    db.refresh(db_comment)

    # Add user info
    db_comment.user_info = UserInfo(
        user_id=current_user["id"],
        name=f"User {current_user['id'][:8]}",
        email=f"user{current_user['id'][:8]}@example.com",
    )

    return db_comment


@router.get("/{bucket_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    bucket_id: str,
    lead_id: str | None = None,
    parent_comment_id: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List comments for a bucket or specific lead"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Build query
    query = db.query(BucketComment).filter(
        BucketComment.bucket_id == bucket_id,
        BucketComment.is_deleted == False,
    )

    if lead_id:
        query = query.filter(BucketComment.lead_id == lead_id)

    if parent_comment_id is not None:
        query = query.filter(BucketComment.parent_comment_id == parent_comment_id)
    elif parent_comment_id is None and lead_id is None:
        # Top-level comments only
        query = query.filter(BucketComment.parent_comment_id.is_(None))

    # Order by creation time
    comments = query.order_by(BucketComment.created_at).all()

    # Add user info and reply count
    for comment in comments:
        comment.user_info = UserInfo(
            user_id=comment.user_id, name=f"User {comment.user_id[:8]}", email=f"user{comment.user_id[:8]}@example.com"
        )

        # Get reply count
        reply_count = (
            db.query(func.count(BucketComment.id))
            .filter(
                BucketComment.parent_comment_id == comment.id,
                BucketComment.is_deleted == False,
            )
            .scalar()
        )
        comment.reply_count = reply_count

    return comments


@router.patch("/{bucket_id}/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    bucket_id: str,
    comment_id: str,
    comment_update: CommentUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a comment"""
    # Get comment
    comment = (
        db.query(BucketComment)
        .filter(
            and_(
                BucketComment.id == comment_id,
                BucketComment.bucket_id == bucket_id,
                BucketComment.is_deleted == False,
            )
        )
        .first()
    )

    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # Check if user is comment author
    if comment.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own comments")

    # Update comment
    comment.content = comment_update.content
    comment.is_edited = True
    if comment_update.mentioned_users is not None:
        comment.mentioned_users = comment_update.mentioned_users

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.COMMENT_UPDATED,
        entity_type="comment",
        entity_id=comment_id,
    )

    db.commit()
    db.refresh(comment)

    # Add user info
    comment.user_info = UserInfo(
        user_id=current_user["id"],
        name=f"User {current_user['id'][:8]}",
        email=f"user{current_user['id'][:8]}@example.com",
    )

    return comment


@router.delete("/{bucket_id}/comments/{comment_id}")
async def delete_comment(
    bucket_id: str,
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a comment (soft delete)"""
    # Get comment
    comment = (
        db.query(BucketComment)
        .filter(
            and_(
                BucketComment.id == comment_id,
                BucketComment.bucket_id == bucket_id,
                BucketComment.is_deleted == False,
            )
        )
        .first()
    )

    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # Check permission - author or bucket admin/owner
    if comment.user_id != current_user["id"]:
        await check_bucket_permission(
            db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER]
        )

    # Soft delete
    comment.is_deleted = True
    comment.content = "[Deleted]"
    comment.mentioned_users = []

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.COMMENT_DELETED,
        entity_type="comment",
        entity_id=comment_id,
    )

    db.commit()

    return {"message": "Comment deleted successfully"}


# Version history endpoints
@router.get("/{bucket_id}/versions", response_model=VersionListResponse)
async def get_version_history(
    bucket_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get version history for a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Build query
    query = (
        db.query(BucketVersion)
        .filter(BucketVersion.bucket_id == bucket_id)
        .order_by(BucketVersion.version_number.desc())
    )

    # Get total count
    total = query.count()

    # Apply pagination
    versions = query.offset((page - 1) * page_size).limit(page_size).all()

    # Add user info
    for version in versions:
        version.user_info = UserInfo(
            user_id=version.changed_by,
            name=f"User {version.changed_by[:8]}",
            email=f"user{version.changed_by[:8]}@example.com",
        )

    return VersionListResponse(
        versions=versions,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{bucket_id}/versions/{version_id}", response_model=VersionResponse)
async def get_version(
    bucket_id: str,
    version_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific version of a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Get version
    version = (
        db.query(BucketVersion)
        .filter(
            and_(
                BucketVersion.id == version_id,
                BucketVersion.bucket_id == bucket_id,
            )
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    # Add user info
    version.user_info = UserInfo(
        user_id=version.changed_by,
        name=f"User {version.changed_by[:8]}",
        email=f"user{version.changed_by[:8]}@example.com",
    )

    return version


# Lead annotation endpoints
@router.post("/{bucket_id}/annotations", response_model=LeadAnnotationResponse)
async def create_lead_annotation(
    bucket_id: str,
    annotation: LeadAnnotationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an annotation for a lead in the bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.EDITOR])

    # Check if lead exists in bucket
    lead_exists = (
        db.query(Business)
        .filter(
            and_(
                Business.id == annotation.lead_id,
                or_(
                    Business.vert_bucket
                    == db.query(CollaborativeBucket.bucket_key)
                    .filter(CollaborativeBucket.id == bucket_id)
                    .scalar_subquery(),
                    Business.geo_bucket
                    == db.query(CollaborativeBucket.bucket_key)
                    .filter(CollaborativeBucket.id == bucket_id)
                    .scalar_subquery(),
                ),
            )
        )
        .first()
    )

    if not lead_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found in bucket")

    # Create annotation
    db_annotation = LeadAnnotation(
        bucket_id=bucket_id,
        user_id=current_user["id"],
        **annotation.model_dump(),
    )
    db.add(db_annotation)

    # Create activity
    await create_activity(
        db,
        bucket_id=bucket_id,
        user_id=current_user["id"],
        activity_type=BucketActivityType.LEAD_UPDATED,
        entity_type="annotation",
        entity_id=annotation.lead_id,
        new_values={"type": annotation.annotation_type},
    )

    db.commit()
    db.refresh(db_annotation)

    # Add user info
    db_annotation.user_info = UserInfo(
        user_id=current_user["id"],
        name=f"User {current_user['id'][:8]}",
        email=f"user{current_user['id'][:8]}@example.com",
    )

    return db_annotation


@router.get("/{bucket_id}/annotations", response_model=list[LeadAnnotationResponse])
async def list_lead_annotations(
    bucket_id: str,
    lead_id: str | None = None,
    annotation_type: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List annotations for leads in the bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Build query
    query = db.query(LeadAnnotation).filter(LeadAnnotation.bucket_id == bucket_id)

    if lead_id:
        query = query.filter(LeadAnnotation.lead_id == lead_id)

    if annotation_type:
        query = query.filter(LeadAnnotation.annotation_type == annotation_type)

    # Order by creation time
    annotations = query.order_by(LeadAnnotation.created_at.desc()).all()

    # Add user info
    for annotation in annotations:
        annotation.user_info = UserInfo(
            user_id=annotation.user_id,
            name=f"User {annotation.user_id[:8]}",
            email=f"user{annotation.user_id[:8]}@example.com",
        )

    return annotations


# Share link endpoints
@router.post("/{bucket_id}/share-links", response_model=ShareLinkResponse)
async def create_share_link(
    bucket_id: str,
    share_link: ShareLinkCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a shareable link for the bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER])

    # Generate unique token
    share_token = secrets.urlsafe(32)

    # Create share link
    db_share_link = BucketShareLink(
        bucket_id=bucket_id,
        share_token=share_token,
        permission=share_link.permission,
        max_uses=share_link.max_uses,
        expires_at=share_link.expires_at,
        created_by=current_user["id"],
    )
    db.add(db_share_link)

    db.commit()
    db.refresh(db_share_link)

    # Build share URL
    base_url = settings.BASE_URL or "http://localhost:8000"
    db_share_link.share_url = f"{base_url}/buckets/shared/{share_token}"

    return db_share_link


@router.get("/{bucket_id}/share-links", response_model=list[ShareLinkResponse])
async def list_share_links(
    bucket_id: str,
    active_only: bool = True,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List share links for the bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER])

    # Build query
    query = db.query(BucketShareLink).filter(BucketShareLink.bucket_id == bucket_id)

    if active_only:
        query = query.filter(
            BucketShareLink.is_active == True,
            or_(BucketShareLink.expires_at.is_(None), BucketShareLink.expires_at > datetime.utcnow()),
        )

    # Order by creation time
    share_links = query.order_by(BucketShareLink.created_at.desc()).all()

    # Build share URLs
    base_url = settings.BASE_URL or "http://localhost:8000"
    for link in share_links:
        link.share_url = f"{base_url}/buckets/shared/{link.share_token}"

    return share_links


@router.delete("/{bucket_id}/share-links/{share_link_id}")
async def revoke_share_link(
    bucket_id: str,
    share_link_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a share link"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.ADMIN, BucketPermission.OWNER])

    # Get share link
    share_link = (
        db.query(BucketShareLink)
        .filter(
            and_(
                BucketShareLink.id == share_link_id,
                BucketShareLink.bucket_id == bucket_id,
            )
        )
        .first()
    )

    if not share_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")

    # Deactivate link
    share_link.is_active = False

    db.commit()

    return {"message": "Share link revoked successfully"}


# Notification endpoints
@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications for the current user"""
    # Build query with JOIN to avoid N+1 queries
    query = (
        db.query(BucketNotification, CollaborativeBucket)
        .join(CollaborativeBucket, BucketNotification.bucket_id == CollaborativeBucket.id)
        .filter(BucketNotification.user_id == current_user["id"])
    )

    if unread_only:
        query = query.filter(BucketNotification.is_read == False)

    # Order by creation time
    query = query.order_by(BucketNotification.created_at.desc())

    # Get unread count
    unread_count = (
        db.query(func.count(BucketNotification.id))
        .filter(
            BucketNotification.user_id == current_user["id"],
            BucketNotification.is_read == False,
        )
        .scalar()
    )

    # Get total count (need to count just notifications, not the join result)
    total = (
        db.query(func.count(BucketNotification.id)).filter(BucketNotification.user_id == current_user["id"]).scalar()
    )

    if unread_only:
        total = unread_count

    # Apply pagination and get results
    results = query.offset((page - 1) * page_size).limit(page_size).all()

    # Process notifications with bucket info from JOIN (no additional queries needed)
    notifications = []
    for notification, bucket in results:
        notification.bucket_info = (
            {
                "id": bucket.id,
                "name": bucket.name,
                "type": bucket.bucket_type,
            }
            if bucket
            else None
        )
        notifications.append(notification)

    return NotificationListResponse(
        notifications=notifications,
        unread_count=unread_count,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read"""
    # Get notification
    notification = (
        db.query(BucketNotification)
        .filter(
            and_(
                BucketNotification.id == notification_id,
                BucketNotification.user_id == current_user["id"],
            )
        )
        .first()
    )

    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    # Mark as read
    notification.is_read = True
    notification.read_at = datetime.utcnow()

    db.commit()

    return {"message": "Notification marked as read"}


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user"""
    # Update all unread notifications
    db.query(BucketNotification).filter(
        BucketNotification.user_id == current_user["id"],
        BucketNotification.is_read == False,
    ).update({"is_read": True, "read_at": datetime.utcnow()})

    db.commit()

    return {"message": "All notifications marked as read"}


# Bulk lead operations
@router.post("/{bucket_id}/leads/bulk", response_model=BulkOperationResponse)
async def bulk_lead_operation(
    bucket_id: str,
    operation: BulkLeadOperation,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Perform bulk operations on leads in the bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.EDITOR])

    # Get bucket
    bucket = db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

    if not bucket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found")

    success_count = 0
    failure_count = 0
    failures = []

    try:
        # Use bulk operations for better performance
        if operation.operation == "add":
            # Bulk update leads - add to bucket
            if bucket.bucket_type == "vertical":
                update_result = (
                    db.query(Business)
                    .filter(Business.id.in_(operation.lead_ids))
                    .update({"vert_bucket": bucket.bucket_key}, synchronize_session=False)
                )
            elif bucket.bucket_type == "geographic":
                update_result = (
                    db.query(Business)
                    .filter(Business.id.in_(operation.lead_ids))
                    .update({"geo_bucket": bucket.bucket_key}, synchronize_session=False)
                )

            # Create bulk activities for successful operations
            activity_type = BucketActivityType.LEAD_ADDED
            success_count = update_result

        elif operation.operation == "remove":
            # Bulk remove leads from bucket
            if bucket.bucket_type == "vertical":
                update_result = (
                    db.query(Business)
                    .filter(Business.id.in_(operation.lead_ids), Business.vert_bucket == bucket.bucket_key)
                    .update({"vert_bucket": None}, synchronize_session=False)
                )
            elif bucket.bucket_type == "geographic":
                update_result = (
                    db.query(Business)
                    .filter(Business.id.in_(operation.lead_ids), Business.geo_bucket == bucket.bucket_key)
                    .update({"geo_bucket": None}, synchronize_session=False)
                )

            # Create bulk activities for successful operations
            activity_type = BucketActivityType.LEAD_REMOVED
            success_count = update_result

        # Create activities for all successful operations in bulk
        if success_count > 0:
            activities = []
            for lead_id in operation.lead_ids[:success_count]:  # Only create activities for successful operations
                activity = BucketActivity(
                    bucket_id=bucket_id,
                    user_id=current_user["id"],
                    activity_type=activity_type,
                    entity_type="lead",
                    entity_id=lead_id,
                    created_at=datetime.utcnow(),
                )
                activities.append(activity)

            # Bulk insert activities
            db.bulk_save_objects(activities)

        # Any leads that couldn't be processed go to failures
        failure_count = len(operation.lead_ids) - success_count
        if failure_count > 0:
            failed_leads = operation.lead_ids[success_count:]
            failures = [{"lead_id": lead_id, "error": "Lead not found or operation failed"} for lead_id in failed_leads]

    except Exception as e:
        failure_count = len(operation.lead_ids)
        success_count = 0
        failures = [{"lead_id": lead_id, "error": str(e)} for lead_id in operation.lead_ids]

    # Update lead count
    if bucket.bucket_type == "vertical":
        lead_count = db.query(func.count(Business.id)).filter(Business.vert_bucket == bucket.bucket_key).scalar()
    else:
        lead_count = db.query(func.count(Business.id)).filter(Business.geo_bucket == bucket.bucket_key).scalar()

    bucket.lead_count = lead_count
    bucket.updated_at = datetime.utcnow()

    # Send WebSocket notification
    await ws_manager.send_bucket_message(
        bucket_id,
        WSMessage(
            type=WSMessageType.BUCKET_UPDATED,
            bucket_id=bucket_id,
            user_id=current_user["id"],
            data={
                "operation": operation.operation,
                "lead_count": lead_count,
                "affected_leads": len(operation.lead_ids),
            },
        ),
    )

    db.commit()

    return BulkOperationResponse(
        success_count=success_count,
        failure_count=failure_count,
        failures=failures if failures else None,
    )


# WebSocket endpoint for real-time collaboration
@router.websocket("/{bucket_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    bucket_id: str,
    token: str = Query(...),  # Auth token
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for real-time bucket collaboration"""
    # Validate token and get user (simplified)
    user_id = token  # In production, validate JWT token

    # Check bucket permission
    try:
        await check_bucket_permission(db, bucket_id, user_id, [BucketPermission.VIEWER])
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept connection
    await ws_manager.connect(websocket, bucket_id, user_id)

    # Create active collaboration record
    session_id = secrets.token_urlsafe(16)
    active_collab = ActiveCollaboration(
        bucket_id=bucket_id,
        user_id=user_id,
        session_id=session_id,
        connection_type="websocket",
    )
    db.add(active_collab)
    db.commit()

    try:
        # Send user joined notification
        await ws_manager.send_bucket_message(
            bucket_id,
            WSMessage(
                type=WSMessageType.USER_JOINED,
                bucket_id=bucket_id,
                user_id=user_id,
                data={"session_id": session_id},
            ),
            exclude_user=user_id,
        )

        while True:
            # Receive messages
            data = await websocket.receive_json()

            # Update last activity
            db.query(ActiveCollaboration).filter(ActiveCollaboration.session_id == session_id).update(
                {
                    "last_activity_at": datetime.utcnow(),
                    "current_view": data.get("current_view"),
                    "is_editing": data.get("is_editing", False),
                }
            )
            db.commit()

            # Handle different message types
            if data.get("type") == "ping":
                # Heartbeat
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        # Remove active collaboration
        db.query(ActiveCollaboration).filter(ActiveCollaboration.session_id == session_id).delete()
        db.commit()

        # Disconnect and notify
        ws_manager.disconnect(websocket, bucket_id, user_id)

        await ws_manager.send_bucket_message(
            bucket_id,
            WSMessage(
                type=WSMessageType.USER_LEFT,
                bucket_id=bucket_id,
                user_id=user_id,
                data={"session_id": session_id},
            ),
        )


# Collaboration status endpoint
@router.get("/{bucket_id}/collaboration-status", response_model=CollaborationStatusResponse)
async def get_collaboration_status(
    bucket_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current collaboration status for a bucket"""
    # Check permission
    await check_bucket_permission(db, bucket_id, current_user["id"], [BucketPermission.VIEWER])

    # Get active collaborators
    active_collabs = db.query(ActiveCollaboration).filter(ActiveCollaboration.bucket_id == bucket_id).all()

    # Add user info
    for collab in active_collabs:
        collab.user_info = UserInfo(
            user_id=collab.user_id, name=f"User {collab.user_id[:8]}", email=f"user{collab.user_id[:8]}@example.com"
        )

    return CollaborationStatusResponse(
        bucket_id=bucket_id,
        active_collaborators=active_collabs,
        total_collaborators=len(active_collabs),
    )


# Tag management endpoints
@router.post("/tags", response_model=BucketTagResponse)
async def create_tag(
    tag: BucketTagCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new tag for buckets"""
    # Check if tag already exists
    existing = db.query(BucketTagDefinition).filter(BucketTagDefinition.name == tag.name).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag with this name already exists")

    # Create tag
    db_tag = BucketTagDefinition(
        **tag.model_dump(),
        created_by=current_user["id"],
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)

    return db_tag


@router.get("/tags", response_model=list[BucketTagResponse])
async def list_tags(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available tags"""
    tags = db.query(BucketTagDefinition).order_by(BucketTagDefinition.name).all()

    return tags


# Performance monitoring endpoints
@router.get("/performance/memory-stats")
async def get_memory_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get memory usage statistics for WebSocket connections"""
    # Get WebSocket manager stats
    ws_stats = ws_manager.get_connection_stats()

    # Get database connection pool stats (if available)
    db_stats = {}
    try:
        if hasattr(db.get_bind(), "pool"):
            pool = db.get_bind().pool
            db_stats = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalidated": pool.invalidated(),
            }
    except Exception:
        db_stats = {"error": "Could not retrieve database pool stats"}

    return {
        "websocket_connections": ws_stats,
        "database_pool": db_stats,
        "performance_recommendations": _get_performance_recommendations(ws_stats),
    }


def _get_performance_recommendations(ws_stats: dict[str, Any]) -> list[str]:
    """Generate performance recommendations based on current stats"""
    recommendations = []

    total_connections = ws_stats.get("total_connections", 0)
    total_buckets = ws_stats.get("total_buckets", 0)
    total_users = ws_stats.get("total_users", 0)

    # Connection recommendations
    if total_connections > 1000:
        recommendations.append("Consider implementing connection pooling for high connection counts")

    if total_buckets > 100:
        recommendations.append("Monitor memory usage for bucket connection tracking")

    if total_users > 500:
        recommendations.append("Consider implementing user session cleanup")

    # Connection density recommendations
    if total_connections > 0 and total_buckets > 0:
        avg_connections_per_bucket = total_connections / total_buckets
        if avg_connections_per_bucket > 20:
            recommendations.append("High connection density detected - consider bucket-based connection limits")

    return recommendations if recommendations else ["Performance metrics are within normal ranges"]
