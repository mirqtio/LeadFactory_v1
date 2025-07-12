"""add report lineage tables

Revision ID: b05a0dd84dfc
Revises: lead_explorer_tables
Create Date: 2025-07-12 13:28:37.737513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b05a0dd84dfc'
down_revision: Union[str, None] = 'lead_explorer_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create report_lineage table
    op.create_table(
        'report_lineage',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('report_generation_id', sa.String(), nullable=False),
        sa.Column('lead_id', sa.String(), nullable=False),
        sa.Column('pipeline_run_id', sa.String(), nullable=False),
        sa.Column('template_version_id', sa.String(), nullable=False),
        sa.Column('pipeline_start_time', sa.DateTime(), nullable=False),
        sa.Column('pipeline_end_time', sa.DateTime(), nullable=False),
        sa.Column('pipeline_logs', sa.JSON(), nullable=True),
        sa.Column('raw_inputs_compressed', sa.LargeBinary(), nullable=True),
        sa.Column('raw_inputs_size_bytes', sa.Integer(), nullable=True),
        sa.Column('compression_ratio', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['report_generation_id'], ['d6_report_generations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('report_generation_id'),
        sa.CheckConstraint('raw_inputs_size_bytes >= 0', name='check_raw_inputs_size_non_negative'),
        sa.CheckConstraint('compression_ratio >= 0 AND compression_ratio <= 100', name='check_compression_ratio_range'),
        sa.CheckConstraint('access_count >= 0', name='check_access_count_non_negative')
    )
    
    # Create indexes for report_lineage
    op.create_index('idx_lineage_report_id', 'report_lineage', ['report_generation_id'])
    op.create_index('idx_lineage_lead_id', 'report_lineage', ['lead_id'])
    op.create_index('idx_lineage_pipeline_run', 'report_lineage', ['pipeline_run_id'])
    op.create_index('idx_lineage_created_at', 'report_lineage', ['created_at'])
    
    # Create report_lineage_audit table
    op.create_table(
        'report_lineage_audit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('lineage_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('accessed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['lineage_id'], ['report_lineage.id'], ondelete='CASCADE')
    )
    
    # Create indexes for report_lineage_audit
    op.create_index('idx_lineage_audit_lineage_id', 'report_lineage_audit', ['lineage_id'])
    op.create_index('idx_lineage_audit_user_id', 'report_lineage_audit', ['user_id'])
    op.create_index('idx_lineage_audit_accessed_at', 'report_lineage_audit', ['accessed_at'])


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('report_lineage_audit')
    op.drop_table('report_lineage')