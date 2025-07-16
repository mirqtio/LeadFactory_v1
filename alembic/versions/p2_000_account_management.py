"""P2-000: Add account management tables

Revision ID: p2_000_account_management
Revises: add_last_enriched_at
Create Date: 2025-07-16 09:44:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p2_000_account_management"
down_revision = "add_last_enriched_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended', 'deleted')")
    op.execute("CREATE TYPE teamrole AS ENUM ('owner', 'admin', 'member', 'viewer')")
    op.execute("CREATE TYPE permissionaction AS ENUM ('create', 'read', 'update', 'delete', 'execute')")
    op.execute("CREATE TYPE resourcetype AS ENUM ('lead', 'report', 'campaign', 'assessment', 'email', 'purchase', 'analytics', 'settings', 'user', 'team', 'organization', 'api_key', 'billing')")
    op.execute("CREATE TYPE authprovider AS ENUM ('local', 'google', 'github', 'saml')")

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('billing_email', sa.String(length=255), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('max_users', sa.Integer(), nullable=False),
        sa.Column('max_teams', sa.Integer(), nullable=False),
        sa.Column('max_api_keys', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('trial_ends_at', sa.Date(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.UniqueConstraint('stripe_customer_id')
    )
    op.create_index('ix_organizations_active', 'organizations', ['is_active'], unique=False)
    op.create_index('ix_organizations_stripe_customer', 'organizations', ['stripe_customer_id'], unique=False)

    # Create account_users table
    op.create_table(
        'account_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('auth_provider', postgresql.ENUM('local', 'google', 'github', 'saml', name='authprovider', create_type=False), nullable=False),
        sa.Column('auth_provider_id', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'suspended', 'deleted', name='userstatus', create_type=False), nullable=False),
        sa.Column('email_verified', sa.Boolean(), nullable=False),
        sa.Column('email_verified_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False),
        sa.Column('mfa_secret', sa.String(length=255), nullable=True),
        sa.Column('last_login_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_login_ip', sa.String(length=45), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index('ix_account_users_email', 'account_users', ['email'], unique=False)
    op.create_index('ix_account_users_username', 'account_users', ['username'], unique=False)
    op.create_index('ix_users_auth_provider', 'account_users', ['auth_provider', 'auth_provider_id'], unique=False)
    op.create_index('ix_users_organization_status', 'account_users', ['organization_id', 'status'], unique=False)

    # Create teams table
    op.create_table(
        'teams',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_team_org_slug')
    )
    op.create_index('ix_teams_organization', 'teams', ['organization_id'], unique=False)
    op.create_index('ix_teams_slug', 'teams', ['slug'], unique=False)

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'organization_id', name='uq_role_name_org')
    )
    op.create_index('ix_roles_organization', 'roles', ['organization_id'], unique=False)
    op.create_index('ix_roles_system', 'roles', ['is_system'], unique=False)

    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('resource', postgresql.ENUM('lead', 'report', 'campaign', 'assessment', 'email', 'purchase', 'analytics', 'settings', 'user', 'team', 'organization', 'api_key', 'billing', name='resourcetype', create_type=False), nullable=False),
        sa.Column('action', postgresql.ENUM('create', 'read', 'update', 'delete', 'execute', name='permissionaction', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource', 'action', name='uq_permission_resource_action')
    )
    op.create_index('ix_permissions_resource', 'permissions', ['resource'], unique=False)

    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=10), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('last_used_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_used_ip', sa.String(length=45), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=False)
    op.create_index('ix_api_keys_organization_active', 'api_keys', ['organization_id', 'is_active'], unique=False)
    op.create_index('ix_api_keys_user', 'api_keys', ['user_id'], unique=False)

    # Create user_sessions table
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_token_hash', sa.String(length=255), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('device_id', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('refresh_expires_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_activity_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refresh_token_hash'),
        sa.UniqueConstraint('session_token_hash')
    )
    op.create_index('ix_sessions_expires', 'user_sessions', ['expires_at'], unique=False)
    op.create_index('ix_sessions_user_active', 'user_sessions', ['user_id', 'is_active'], unique=False)

    # Create account_audit_logs table
    op.create_table(
        'account_audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_organization_created', 'account_audit_logs', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_audit_logs_resource', 'account_audit_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('ix_audit_logs_user', 'account_audit_logs', ['user_id'], unique=False)
    op.create_index('ix_account_audit_logs_action', 'account_audit_logs', ['action'], unique=False)
    op.create_index('ix_account_audit_logs_created_at', 'account_audit_logs', ['created_at'], unique=False)

    # Create email_verification_tokens table
    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_verification_tokens_expires', 'email_verification_tokens', ['expires_at'], unique=False)
    op.create_index('ix_verification_tokens_user', 'email_verification_tokens', ['user_id'], unique=False)

    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_reset_tokens_expires', 'password_reset_tokens', ['expires_at'], unique=False)
    op.create_index('ix_reset_tokens_user', 'password_reset_tokens', ['user_id'], unique=False)

    # Create association tables
    op.create_table(
        'team_users',
        sa.Column('team_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('role', postgresql.ENUM('owner', 'admin', 'member', 'viewer', name='teamrole', create_type=False), nullable=False),
        sa.Column('joined_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_team_users')
    )

    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.String(), nullable=True),
        sa.Column('permission_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permissions')
    )

    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('role_id', sa.String(), nullable=True),
        sa.Column('organization_id', sa.String(), nullable=True),
        sa.Column('team_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['account_users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'role_id', 'organization_id', 'team_id', name='uq_user_roles')
    )


def downgrade() -> None:
    # Drop association tables
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('team_users')
    
    # Drop main tables
    op.drop_table('password_reset_tokens')
    op.drop_table('email_verification_tokens')
    op.drop_table('account_audit_logs')
    op.drop_table('user_sessions')
    op.drop_table('api_keys')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('teams')
    op.drop_table('account_users')
    op.drop_table('organizations')
    
    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS authprovider')
    op.execute('DROP TYPE IF EXISTS resourcetype')
    op.execute('DROP TYPE IF EXISTS permissionaction')
    op.execute('DROP TYPE IF EXISTS teamrole')
    op.execute('DROP TYPE IF EXISTS userstatus')