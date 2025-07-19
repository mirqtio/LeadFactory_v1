"""Create missing fct_api_cost table for gateway cost tracking

Revision ID: 5186822f03ee
Revises: f5fa976855a3
Create Date: 2025-07-19 10:11:33.283958

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "5186822f03ee"
down_revision = "f5fa976855a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create fct_api_cost table for gateway cost tracking"""
    op.create_table(
        "fct_api_cost",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("lead_id", sa.String(length=100), nullable=True),  # String type as required by fix migration
        sa.Column("gateway_provider", sa.String(length=50), nullable=True),
        sa.Column("api_endpoint", sa.String(length=200), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create indices for common query patterns
    op.create_index("idx_api_cost_timestamp", "fct_api_cost", ["timestamp"])
    op.create_index("idx_api_cost_lead", "fct_api_cost", ["lead_id"])
    op.create_index("idx_api_cost_provider", "fct_api_cost", ["gateway_provider"])


def downgrade() -> None:
    """Drop fct_api_cost table"""
    op.drop_table("fct_api_cost")
