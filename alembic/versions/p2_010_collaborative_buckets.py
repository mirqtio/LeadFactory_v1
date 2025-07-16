"""P2-010: Add collaborative bucket tables

Revision ID: p2_010_collaborative_buckets
Revises: p2_000_account_management
Create Date: 2025-01-16 12:00:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p2_010_collaborative_buckets"
down_revision = "p2_000_account_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE bucketpermission AS ENUM ('owner', 'admin', 'editor', 'viewer', 'commenter')")
    op.execute(
        "CREATE TYPE bucketactivitytype AS ENUM ('created', 'updated', 'shared', 'unshared', 'permission_changed', 'lead_added', 'lead_removed', 'lead_updated', 'comment_added', 'comment_updated', 'comment_deleted', 'enrichment_started', 'enrichment_completed', 'exported', 'archived', 'restored')"
    )
    op.execute(
        "CREATE TYPE notificationtype AS ENUM ('bucket_shared', 'permission_granted', 'permission_revoked', 'comment_mention', 'lead_assigned', 'enrichment_complete', 'bucket_updated')"
    )

    # Create collaborative_buckets table
    op.create_table(
        "collaborative_buckets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("bucket_type", sa.String(length=80), nullable=False),
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True, default=False),
        sa.Column("is_archived", sa.Boolean(), nullable=True, default=False),
        sa.Column("enrichment_config", sa.JSON(), nullable=True),
        sa.Column("processing_strategy", sa.String(length=50), nullable=True),
        sa.Column("priority_level", sa.String(length=20), nullable=True),
        sa.Column("lead_count", sa.Integer(), nullable=True, default=0),
        sa.Column("last_enriched_at", sa.DateTime(), nullable=True),
        sa.Column("total_enrichment_cost", sa.Integer(), nullable=True, default=0),
        sa.Column("version", sa.Integer(), nullable=True, default=1),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "bucket_type", "bucket_key", name="uq_org_bucket_type_key"),
    )
    op.create_index("idx_collab_bucket_owner", "collaborative_buckets", ["owner_id"], unique=False)
    op.create_index("idx_collab_bucket_org", "collaborative_buckets", ["organization_id"], unique=False)
    op.create_index("idx_collab_bucket_type_key", "collaborative_buckets", ["bucket_type", "bucket_key"], unique=False)
    op.create_index("idx_collab_bucket_archived", "collaborative_buckets", ["is_archived"], unique=False)

    # Create bucket_permission_grants table
    op.create_table(
        "bucket_permission_grants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "permission",
            postgresql.ENUM(
                "owner", "admin", "editor", "viewer", "commenter", name="bucketpermission", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("granted_by", sa.String(), nullable=False),
        sa.Column("granted_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_id", "user_id", name="uq_bucket_user_permission"),
    )
    op.create_index("idx_bucket_permission_user", "bucket_permission_grants", ["user_id"], unique=False)
    op.create_index("idx_bucket_permission_bucket", "bucket_permission_grants", ["bucket_id"], unique=False)

    # Create bucket_activities table
    op.create_table(
        "bucket_activities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "activity_type",
            postgresql.ENUM(
                "created",
                "updated",
                "shared",
                "unshared",
                "permission_changed",
                "lead_added",
                "lead_removed",
                "lead_updated",
                "comment_added",
                "comment_updated",
                "comment_deleted",
                "enrichment_started",
                "enrichment_completed",
                "exported",
                "archived",
                "restored",
                name="bucketactivitytype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_bucket_activity_bucket_created", "bucket_activities", ["bucket_id", "created_at"], unique=False
    )
    op.create_index("idx_bucket_activity_user_created", "bucket_activities", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_bucket_activities_activity_type"), "bucket_activities", ["activity_type"], unique=False)
    op.create_index(op.f("ix_bucket_activities_created_at"), "bucket_activities", ["created_at"], unique=False)
    op.create_index(op.f("ix_bucket_activities_user_id"), "bucket_activities", ["user_id"], unique=False)

    # Create bucket_comments table
    op.create_table(
        "bucket_comments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("lead_id", sa.String(), nullable=True),
        sa.Column("parent_comment_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mentioned_users", sa.JSON(), nullable=True),
        sa.Column("is_edited", sa.Boolean(), nullable=True, default=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=True, default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_comment_id"], ["bucket_comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bucket_comment_bucket", "bucket_comments", ["bucket_id"], unique=False)
    op.create_index("idx_bucket_comment_lead", "bucket_comments", ["lead_id"], unique=False)
    op.create_index("idx_bucket_comment_user", "bucket_comments", ["user_id"], unique=False)

    # Create bucket_versions table
    op.create_table(
        "bucket_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("bucket_snapshot", sa.JSON(), nullable=False),
        sa.Column("lead_ids_snapshot", sa.JSON(), nullable=True),
        sa.Column("changed_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_id", "version_number", name="uq_bucket_version"),
    )
    op.create_index("idx_bucket_version_bucket_created", "bucket_versions", ["bucket_id", "created_at"], unique=False)

    # Create bucket_notifications table
    op.create_table(
        "bucket_notifications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "notification_type",
            postgresql.ENUM(
                "bucket_shared",
                "permission_granted",
                "permission_revoked",
                "comment_mention",
                "lead_assigned",
                "enrichment_complete",
                "bucket_updated",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_user_id", sa.String(), nullable=True),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", sa.String(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True, default=False),
        sa.Column("is_email_sent", sa.Boolean(), nullable=True, default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bucket_notification_user_read", "bucket_notifications", ["user_id", "is_read"], unique=False)
    op.create_index("idx_bucket_notification_created", "bucket_notifications", ["created_at"], unique=False)
    op.create_index(op.f("ix_bucket_notifications_is_read"), "bucket_notifications", ["is_read"], unique=False)
    op.create_index(op.f("ix_bucket_notifications_user_id"), "bucket_notifications", ["user_id"], unique=False)

    # Create lead_annotations table
    op.create_table(
        "lead_annotations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("lead_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("annotation_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_id", "lead_id", "user_id", "annotation_type", name="uq_lead_annotation"),
    )
    op.create_index("idx_lead_annotation_bucket_lead", "lead_annotations", ["bucket_id", "lead_id"], unique=False)
    op.create_index("idx_lead_annotation_user", "lead_annotations", ["user_id"], unique=False)
    op.create_index(op.f("ix_lead_annotations_lead_id"), "lead_annotations", ["lead_id"], unique=False)
    op.create_index(op.f("ix_lead_annotations_user_id"), "lead_annotations", ["user_id"], unique=False)

    # Create bucket_tag_definitions table
    op.create_table(
        "bucket_tag_definitions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create bucket_tags association table
    op.create_table(
        "bucket_tags",
        sa.Column("bucket_id", sa.String(), nullable=True),
        sa.Column("tag_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["bucket_tag_definitions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("bucket_id", "tag_id", name="uq_bucket_tag"),
    )

    # Create bucket_share_links table
    op.create_table(
        "bucket_share_links",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("share_token", sa.String(length=64), nullable=False),
        sa.Column(
            "permission",
            postgresql.ENUM(
                "owner", "admin", "editor", "viewer", "commenter", name="bucketpermission", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("current_uses", sa.Integer(), nullable=True, default=0),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
    )
    op.create_index("idx_share_link_token", "bucket_share_links", ["share_token"], unique=False)
    op.create_index("idx_share_link_bucket", "bucket_share_links", ["bucket_id"], unique=False)
    op.create_index(op.f("ix_bucket_share_links_is_active"), "bucket_share_links", ["is_active"], unique=False)

    # Create active_collaborations table
    op.create_table(
        "active_collaborations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("connection_type", sa.String(length=20), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("current_view", sa.String(length=50), nullable=True),
        sa.Column("is_editing", sa.Boolean(), nullable=True, default=False),
        sa.Column("connected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["collaborative_buckets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_id", "user_id", name="uq_bucket_user_active"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("idx_active_collab_bucket", "active_collaborations", ["bucket_id"], unique=False)
    op.create_index("idx_active_collab_user", "active_collaborations", ["user_id"], unique=False)
    op.create_index(op.f("ix_active_collaborations_user_id"), "active_collaborations", ["user_id"], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("active_collaborations")
    op.drop_table("bucket_share_links")
    op.drop_table("bucket_tags")
    op.drop_table("bucket_tag_definitions")
    op.drop_table("lead_annotations")
    op.drop_table("bucket_notifications")
    op.drop_table("bucket_versions")
    op.drop_table("bucket_comments")
    op.drop_table("bucket_activities")
    op.drop_table("bucket_permission_grants")
    op.drop_table("collaborative_buckets")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS bucketactivitytype")
    op.execute("DROP TYPE IF EXISTS bucketpermission")
