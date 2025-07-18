"""Add d2_companies table

Revision ID: a41430908e80
Revises: add_last_enriched_at
Create Date: 2025-07-16 18:39:51.649936

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a41430908e80"
down_revision = "add_last_enriched_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create d2_companies table
    op.create_table(
        "d2_companies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop d2_companies table
    op.drop_table("d2_companies")
