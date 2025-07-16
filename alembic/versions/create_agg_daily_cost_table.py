"""Create agg_daily_cost table

Revision ID: create_agg_daily_cost
Revises: add_last_enriched_at
Create Date: 2025-07-16 10:50:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "create_agg_daily_cost"
down_revision = "add_last_enriched_at"
branch_labels = None
depends_on = None


def get_timestamp_default():
    """Get database-appropriate timestamp default"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text("now()")
    else:
        # For SQLite and other databases, use CURRENT_TIMESTAMP
        return sa.text("CURRENT_TIMESTAMP")


def get_timestamp_type():
    """Get database-appropriate timestamp type"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.TIMESTAMP(timezone=True)
    else:
        # For SQLite and other databases, use TIMESTAMP
        return sa.TIMESTAMP()


def upgrade():
    # Create agg_daily_cost table
    op.create_table(
        "agg_daily_cost",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            get_timestamp_type(),
            server_default=get_timestamp_default(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            get_timestamp_type(),
            server_default=get_timestamp_default(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create unique index for preventing duplicate aggregations
    op.create_index(
        "idx_daily_cost_unique",
        "agg_daily_cost",
        ["date", "provider", "operation", "campaign_id"],
        unique=True,
    )

    # Create additional indexes for performance
    op.create_index("idx_agg_daily_cost_date", "agg_daily_cost", ["date"])
    op.create_index("idx_agg_daily_cost_provider", "agg_daily_cost", ["provider"])
    op.create_index("idx_agg_daily_cost_campaign_id", "agg_daily_cost", ["campaign_id"])


def downgrade():
    # Drop indexes
    op.drop_index("idx_agg_daily_cost_campaign_id", table_name="agg_daily_cost")
    op.drop_index("idx_agg_daily_cost_provider", table_name="agg_daily_cost")
    op.drop_index("idx_agg_daily_cost_date", table_name="agg_daily_cost")
    op.drop_index("idx_daily_cost_unique", table_name="agg_daily_cost")

    # Drop table
    op.drop_table("agg_daily_cost")
