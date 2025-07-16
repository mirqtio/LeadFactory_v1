"""Add last_enriched_at to Business model

Revision ID: add_last_enriched_at
Revises: fix_missing_tables_and_columns
Create Date: 2025-07-16 09:30:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_last_enriched_at"
down_revision = "fix_missing_tables_and_columns"
branch_labels = None
depends_on = None


def upgrade():
    # Add last_enriched_at column to businesses table
    op.add_column("businesses", sa.Column("last_enriched_at", sa.TIMESTAMP(), nullable=True))

    # Create index for better query performance
    op.create_index("ix_businesses_last_enriched_at", "businesses", ["last_enriched_at"])


def downgrade():
    # Drop index first
    op.drop_index("ix_businesses_last_enriched_at", table_name="businesses")

    # Drop column
    op.drop_column("businesses", "last_enriched_at")
