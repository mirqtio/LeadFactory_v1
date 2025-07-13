"""Create governance tables for RBAC and audit logging

Revision ID: governance_tables_001
Revises: lead_explorer_001
Create Date: 2024-01-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import String

# revision identifiers, used by Alembic.
revision = 'governance_tables_001'
down_revision = 'lead_explorer_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get the bind to check database type
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    # Check if tables already exist
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'users' in existing_tables:
        print("Governance tables already exist, skipping creation")
        return
    
    # Create users table
    if dialect_name == 'postgresql':
        # PostgreSQL specific: Create user role enum if it doesn't exist
        op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN CREATE TYPE userrole AS ENUM ('admin', 'viewer'); END IF; END$$;")
        
        # Create users table with PostgreSQL specific types
        op.create_table('users',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('role', sa.Enum('admin', 'viewer', name='userrole', create_type=False), nullable=False),
            sa.Column('api_key_hash', sa.String(length=255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('deactivated_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('deactivated_by', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email')
            # Email validation handled at application layer for cross-database compatibility
        )
    else:
        # SQLite and other databases: Use simple string for role
        op.create_table('users',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),  # Use string instead of enum
            sa.Column('api_key_hash', sa.String(length=255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('deactivated_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('deactivated_by', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
            # Skip email validation check constraint for SQLite
        )
    
    op.create_index('idx_users_email_active', 'users', ['email', 'is_active'], unique=False)

    # Create audit_log_global table
    op.create_table('audit_log_global',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('user_role', sa.String(length=20), nullable=False),  # Use string instead of enum
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('endpoint', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(length=36), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('request_body', sa.Text(), nullable=True),
        sa.Column('response_summary', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for audit_log_global
    op.create_index('idx_audit_global_timestamp', 'audit_log_global', ['timestamp'], unique=False)
    op.create_index('idx_audit_global_user', 'audit_log_global', ['user_id', 'timestamp'], unique=False)
    op.create_index('idx_audit_global_action', 'audit_log_global', ['action', 'timestamp'], unique=False)
    op.create_index('idx_audit_global_endpoint', 'audit_log_global', ['endpoint', 'timestamp'], unique=False)
    op.create_index('idx_audit_global_request_id', 'audit_log_global', ['request_id'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_index('idx_audit_global_request_id', table_name='audit_log_global')
    op.drop_index('idx_audit_global_endpoint', table_name='audit_log_global')
    op.drop_index('idx_audit_global_action', table_name='audit_log_global')
    op.drop_index('idx_audit_global_user', table_name='audit_log_global')
    op.drop_index('idx_audit_global_timestamp', table_name='audit_log_global')
    op.drop_table('audit_log_global')
    
    op.drop_index('idx_users_email_active', table_name='users')
    op.drop_table('users')
    
    # Drop enum type if PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP TYPE userrole")