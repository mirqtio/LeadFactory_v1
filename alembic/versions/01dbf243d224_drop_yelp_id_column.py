"""drop yelp_id column

Revision ID: 01dbf243d224
Revises: c9f6c90ad153
Create Date: 2025-07-10 20:02:55.435309

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '01dbf243d224'
down_revision = 'c9f6c90ad153'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop unique constraint first (if exists)
    try:
        op.drop_constraint('businesses_yelp_id_key', 'businesses', type_='unique')
    except:
        pass  # Constraint might not exist
    
    # Drop the yelp_id column
    op.drop_column('businesses', 'yelp_id')
    
    # Also drop yelp_json column from assessment results if it exists
    try:
        op.drop_column('d3_assessment_results', 'yelp_json')
    except:
        pass  # Column might not exist


def downgrade() -> None:
    # Re-add yelp_id column
    op.add_column('businesses', sa.Column('yelp_id', sa.String(100), nullable=True))
    
    # Re-add unique constraint
    op.create_unique_constraint('businesses_yelp_id_key', 'businesses', ['yelp_id'])
    
    # Re-add yelp_json column to assessment results
    op.add_column('d3_assessment_results', 
                  sa.Column('yelp_json', sa.JSON(), nullable=True))
