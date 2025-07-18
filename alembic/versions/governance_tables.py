"""Create governance tables for RBAC and audit logging

Revision ID: governance_tables_001
Revises: lead_explorer_001
Create Date: 2024-01-13 12:00:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


def get_enum_type(enum_name: str, values: list):
    """Get database-appropriate column type for enums"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=enum_name, create_type=False)
    else:
        # For SQLite and other databases, use VARCHAR
        return sa.String(50)


def get_timestamp_default():
    """Get database-appropriate timestamp default"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text("now()")
    else:
        # For SQLite and other databases, use CURRENT_TIMESTAMP
        return sa.text("CURRENT_TIMESTAMP")


# revision identifiers, used by Alembic.
revision = "governance_tables_001"
down_revision = "01dbf243d224"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE TYPE userrole AS ENUM ('admin', 'viewer')")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", get_enum_type("userrole", ["admin", "viewer"]), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("deactivated_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("deactivated_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_index("idx_users_email_active", "users", ["email", "is_active"], unique=False)

    # Create audit_log_global table
    op.create_table(
        "audit_log_global",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("user_role", sa.String(length=20), nullable=False),  # Use string instead of enum
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for audit_log_global
    op.create_index("idx_audit_global_timestamp", "audit_log_global", ["timestamp"], unique=False)
    op.create_index("idx_audit_global_user", "audit_log_global", ["user_id", "timestamp"], unique=False)
    op.create_index("idx_audit_global_action", "audit_log_global", ["action", "timestamp"], unique=False)
    op.create_index("idx_audit_global_endpoint", "audit_log_global", ["endpoint", "timestamp"], unique=False)
    op.create_index("idx_audit_global_request_id", "audit_log_global", ["request_id"], unique=False)

    # Create role_change_log table
    op.create_table(
        "role_change_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("changed_by_id", sa.String(), nullable=False),
        sa.Column("old_role", sa.String(length=20), nullable=False),
        sa.Column("new_role", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
        ),
    )

    # Create indexes for role_change_log
    op.create_index("idx_role_change_user", "role_change_log", ["user_id", "timestamp"], unique=False)
    op.create_index("idx_role_change_timestamp", "role_change_log", ["timestamp"], unique=False)


def downgrade() -> None:
    # Drop role_change_log table and indexes
    op.drop_index("idx_role_change_timestamp", table_name="role_change_log")
    op.drop_index("idx_role_change_user", table_name="role_change_log")
    op.drop_table("role_change_log")

    # Drop audit_log_global table and indexes
    op.drop_index("idx_audit_global_request_id", table_name="audit_log_global")
    op.drop_index("idx_audit_global_endpoint", table_name="audit_log_global")
    op.drop_index("idx_audit_global_action", table_name="audit_log_global")
    op.drop_index("idx_audit_global_user", table_name="audit_log_global")
    op.drop_index("idx_audit_global_timestamp", table_name="audit_log_global")
    op.drop_table("audit_log_global")

    # Drop users table and indexes
    op.drop_index("idx_users_email_active", table_name="users")
    op.drop_table("users")

    # Drop enum type (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS userrole")
