"""Add bucket columns for geo and vertical segmentation

Revision ID: 004_bucket_columns
Revises: 003_cost_tracking
Create Date: 2025-06-11

Phase 0.5 - Task TG-06
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_bucket_columns'
down_revision = '003_cost_tracking'
branch_labels = None
depends_on = None


def upgrade():
    """Add bucket columns to businesses and targets tables"""
    
    # Add bucket columns to businesses table
    op.add_column('businesses', 
        sa.Column('geo_bucket', sa.String(80), nullable=True, 
                  comment='Geo bucket: {affluence}-{density}-{broadband}')
    )
    op.add_column('businesses',
        sa.Column('vert_bucket', sa.String(80), nullable=True,
                  comment='Vertical bucket: {urgency}-{ticket}-{maturity}')
    )
    
    # Add bucket columns to targets table for aggregation
    op.add_column('targets',
        sa.Column('geo_bucket', sa.String(80), nullable=True,
                  comment='Geo bucket for this target segment')
    )
    op.add_column('targets', 
        sa.Column('vert_bucket', sa.String(80), nullable=True,
                  comment='Vertical bucket for this target segment')
    )
    
    # Create indexes for bucket queries
    op.create_index('idx_businesses_geo_bucket', 'businesses', ['geo_bucket'])
    op.create_index('idx_businesses_vert_bucket', 'businesses', ['vert_bucket'])
    op.create_index('idx_businesses_buckets', 'businesses', ['geo_bucket', 'vert_bucket'])
    
    op.create_index('idx_targets_geo_bucket', 'targets', ['geo_bucket'])
    op.create_index('idx_targets_vert_bucket', 'targets', ['vert_bucket'])
    op.create_index('idx_targets_buckets', 'targets', ['geo_bucket', 'vert_bucket'])


def downgrade():
    """Remove bucket columns"""
    
    # Drop indexes
    op.drop_index('idx_businesses_geo_bucket', 'businesses')
    op.drop_index('idx_businesses_vert_bucket', 'businesses')
    op.drop_index('idx_businesses_buckets', 'businesses')
    
    op.drop_index('idx_targets_geo_bucket', 'targets')
    op.drop_index('idx_targets_vert_bucket', 'targets')
    op.drop_index('idx_targets_buckets', 'targets')
    
    # Drop columns
    op.drop_column('businesses', 'geo_bucket')
    op.drop_column('businesses', 'vert_bucket')
    
    op.drop_column('targets', 'geo_bucket') 
    op.drop_column('targets', 'vert_bucket')