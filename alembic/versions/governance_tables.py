"""Create governance tables for RBAC and audit logging

Revision ID: governance_tables
Revises: lead_explorer_tables
Create Date: 2024-01-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'governance_tables'
down_revision = 'lead_explorer_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user role enum
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'viewer')")
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'viewer', name='userrole'), nullable=False),
        sa.Column('api_key_hash', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deactivated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}$'", name='valid_email'),
    )
    op.create_index('idx_users_email_active', 'users', ['email', 'is_active'], unique=False)

    # Create audit_log_global table
    op.create_table('audit_log_global',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('user_role', postgresql.ENUM('admin', 'viewer', name='userrole'), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('endpoint', sa.String(length=255), nullable=False),
        sa.Column('object_type', sa.String(length=100), nullable=False),
        sa.Column('object_id', sa.String(length=255), nullable=True),
        sa.Column('request_data', sa.Text(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=False),
        sa.Column('response_data', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('false', name='no_update_allowed'),  # Prevent updates
    )
    op.create_index('idx_audit_user_timestamp', 'audit_log_global', ['user_id', 'timestamp'], unique=False)
    op.create_index('idx_audit_object', 'audit_log_global', ['object_type', 'object_id'], unique=False)
    op.create_index('idx_audit_timestamp', 'audit_log_global', ['timestamp'], unique=False)
    op.create_index('idx_audit_action', 'audit_log_global', ['action', 'timestamp'], unique=False)

    # Create role_change_log table
    op.create_table('role_change_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('changed_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_role', postgresql.ENUM('admin', 'viewer', name='userrole'), nullable=False),
        sa.Column('new_role', postgresql.ENUM('admin', 'viewer', name='userrole'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('false', name='no_update_allowed'),  # Prevent updates
    )
    op.create_index('idx_role_change_user', 'role_change_log', ['user_id', 'timestamp'], unique=False)

    # Insert default admin user
    op.execute("""
        INSERT INTO users (email, name, role, is_active)
        VALUES ('admin@leadfactory.com', 'Default Admin', 'admin', true)
    """)


def downgrade() -> None:
    op.drop_index('idx_role_change_user', table_name='role_change_log')
    op.drop_table('role_change_log')
    
    op.drop_index('idx_audit_action', table_name='audit_log_global')
    op.drop_index('idx_audit_timestamp', table_name='audit_log_global')
    op.drop_index('idx_audit_object', table_name='audit_log_global')
    op.drop_index('idx_audit_user_timestamp', table_name='audit_log_global')
    op.drop_table('audit_log_global')
    
    op.drop_index('idx_users_email_active', table_name='users')
    op.drop_table('users')
    
    op.execute('DROP TYPE userrole')