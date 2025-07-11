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
    # Check if we're using SQLite
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    if dialect_name == 'sqlite':
        # SQLite doesn't support dropping columns well, especially with constraints
        # For testing purposes, we'll skip this migration on SQLite
        print("Skipping yelp_id column drop on SQLite (not supported)")
        return
    
    # Drop unique constraint first (if exists)
    try:
        op.drop_constraint('businesses_yelp_id_key', 'businesses', type_='unique')
    except:
        pass  # Constraint might not exist
    
    # Drop the yelp_id column
    op.drop_column('businesses', 'yelp_id')
    
    # Also drop yelp_json column from assessment results if it exists
    try:
        op.drop_column('assessment_results', 'yelp_json')
    except:
        pass  # Column might not exist


def downgrade() -> None:
    # Check if we're using SQLite
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    if dialect_name == 'sqlite':
        # SQLite doesn't support dropping columns well, so we also skip adding them back
        print("Skipping yelp_id column re-add on SQLite (not supported)")
        return
        
    # Re-add yelp_id column
    op.add_column('businesses', sa.Column('yelp_id', sa.String(100), nullable=True))
    
    # Re-add unique constraint
    op.create_unique_constraint('businesses_yelp_id_key', 'businesses', ['yelp_id'])
    
    # Re-add yelp_json column to assessment results
    op.add_column('assessment_results', 
                  sa.Column('yelp_json', sa.JSON(), nullable=True))
