"""Fix P2-000 timezone support for timestamp columns

Revision ID: fix_p2_000_timezone_support
Revises: p2_000_account_management
Create Date: 2025-07-16 12:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_p2_000_timezone_support"
down_revision = "p2_000_account_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add timezone support to all timestamp columns in account management tables"""

    # Organizations table
    op.alter_column(
        "organizations",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "organizations",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )

    # Account users table
    op.alter_column(
        "account_users",
        "email_verified_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "account_users",
        "last_login_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "account_users",
        "locked_until",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "account_users",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "account_users",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "account_users",
        "deleted_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )

    # Teams table
    op.alter_column(
        "teams", "created_at", type_=sa.TIMESTAMP(timezone=True), existing_type=sa.TIMESTAMP(), existing_nullable=False
    )
    op.alter_column(
        "teams", "updated_at", type_=sa.TIMESTAMP(timezone=True), existing_type=sa.TIMESTAMP(), existing_nullable=False
    )

    # Roles table
    op.alter_column(
        "roles", "created_at", type_=sa.TIMESTAMP(timezone=True), existing_type=sa.TIMESTAMP(), existing_nullable=False
    )
    op.alter_column(
        "roles", "updated_at", type_=sa.TIMESTAMP(timezone=True), existing_type=sa.TIMESTAMP(), existing_nullable=False
    )

    # API keys table
    op.alter_column(
        "api_keys",
        "last_used_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "api_keys",
        "expires_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "api_keys",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "api_keys",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "api_keys",
        "revoked_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )

    # User sessions table
    op.alter_column(
        "user_sessions",
        "expires_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "user_sessions",
        "refresh_expires_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "user_sessions",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "user_sessions",
        "last_activity_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "user_sessions",
        "revoked_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )

    # Account audit logs table
    op.alter_column(
        "account_audit_logs",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )

    # Email verification tokens table
    op.alter_column(
        "email_verification_tokens",
        "expires_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "email_verification_tokens",
        "used_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "email_verification_tokens",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )

    # Password reset tokens table
    op.alter_column(
        "password_reset_tokens",
        "expires_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        "password_reset_tokens",
        "used_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "password_reset_tokens",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
    )

    # Team users association table
    op.alter_column(
        "team_users",
        "joined_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Remove timezone support from timestamp columns (revert to plain TIMESTAMP)"""

    # Organizations table
    op.alter_column(
        "organizations",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "organizations",
        "updated_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )

    # Account users table
    op.alter_column(
        "account_users",
        "email_verified_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "account_users",
        "last_login_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "account_users",
        "locked_until",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "account_users",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "account_users",
        "updated_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "account_users",
        "deleted_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )

    # Teams table
    op.alter_column(
        "teams", "created_at", type_=sa.TIMESTAMP(), existing_type=sa.TIMESTAMP(timezone=True), existing_nullable=False
    )
    op.alter_column(
        "teams", "updated_at", type_=sa.TIMESTAMP(), existing_type=sa.TIMESTAMP(timezone=True), existing_nullable=False
    )

    # Roles table
    op.alter_column(
        "roles", "created_at", type_=sa.TIMESTAMP(), existing_type=sa.TIMESTAMP(timezone=True), existing_nullable=False
    )
    op.alter_column(
        "roles", "updated_at", type_=sa.TIMESTAMP(), existing_type=sa.TIMESTAMP(timezone=True), existing_nullable=False
    )

    # API keys table
    op.alter_column(
        "api_keys",
        "last_used_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "api_keys",
        "expires_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "api_keys",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "api_keys",
        "updated_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "api_keys",
        "revoked_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )

    # User sessions table
    op.alter_column(
        "user_sessions",
        "expires_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "user_sessions",
        "refresh_expires_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "user_sessions",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "user_sessions",
        "last_activity_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "user_sessions",
        "revoked_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )

    # Account audit logs table
    op.alter_column(
        "account_audit_logs",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )

    # Email verification tokens table
    op.alter_column(
        "email_verification_tokens",
        "expires_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "email_verification_tokens",
        "used_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "email_verification_tokens",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )

    # Password reset tokens table
    op.alter_column(
        "password_reset_tokens",
        "expires_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "password_reset_tokens",
        "used_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "password_reset_tokens",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )

    # Team users association table
    op.alter_column(
        "team_users",
        "joined_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
