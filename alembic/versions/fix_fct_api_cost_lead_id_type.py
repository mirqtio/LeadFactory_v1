"""Fix fct_api_cost lead_id column type from Integer to String

Revision ID: fix_fct_api_cost_lead_id_type
Revises: 324616807570
Create Date: 2025-07-18 15:23:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_fct_api_cost_lead_id_type"
down_revision = "fix_unit_economics_table_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fix lead_id column type from Integer to String"""
    # Drop the existing index first
    op.drop_index("idx_api_cost_lead", table_name="fct_api_cost")

    # Change the column type from Integer to String
    op.alter_column(
        "fct_api_cost",
        "lead_id",
        existing_type=sa.Integer(),
        type_=sa.String(length=100),
        nullable=True,
    )

    # Recreate the index
    op.create_index("idx_api_cost_lead", "fct_api_cost", ["lead_id"], unique=False)


def downgrade() -> None:
    """Revert lead_id column type from String back to Integer"""
    # Drop the index first
    op.drop_index("idx_api_cost_lead", table_name="fct_api_cost")

    # Change the column type back from String to Integer
    op.alter_column(
        "fct_api_cost",
        "lead_id",
        existing_type=sa.String(length=100),
        type_=sa.Integer(),
        nullable=True,
    )

    # Recreate the index
    op.create_index("idx_api_cost_lead", "fct_api_cost", ["lead_id"], unique=False)
