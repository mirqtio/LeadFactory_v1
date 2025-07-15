"""Add missing tables and columns

Revision ID: fix_missing_tables_001
Revises: add_lead_explorer_001
Create Date: 2025-07-15 17:10:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_missing_tables_001"
down_revision = "add_lead_explorer_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create fct_api_cost table
    op.create_table(
        "fct_api_cost",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column(
            "timestamp", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_api_cost_provider", "fct_api_cost", ["provider"], unique=False)
    op.create_index("idx_api_cost_timestamp", "fct_api_cost", ["timestamp"], unique=False)
    op.create_index("idx_api_cost_lead", "fct_api_cost", ["lead_id"], unique=False)
    op.create_index("idx_api_cost_campaign", "fct_api_cost", ["campaign_id"], unique=False)
    op.create_index("idx_api_cost_provider_timestamp", "fct_api_cost", ["provider", "timestamp"], unique=False)

    # Check if campaigns table exists before creating campaign_batches
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "campaigns" not in tables:
        # Create campaigns table first
        op.create_table(
            "campaigns",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create campaign_batches table
    op.create_table(
        "campaign_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("targets_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("targets_contacted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("targets_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], name="fk_campaign_batches_campaign"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "batch_number", name="uq_campaign_batches"),
    )
    op.create_index("idx_campaign_batches_status", "campaign_batches", ["campaign_id", "status"], unique=False)
    op.create_index("idx_campaign_batches_schedule", "campaign_batches", ["scheduled_at", "status"], unique=False)

    # Create experiment_variants table
    # First check if experiments table has experiment_id or id column
    if "experiments" in tables:
        columns = [col["name"] for col in inspector.get_columns("experiments")]
        experiment_id_col = "experiment_id" if "experiment_id" in columns else "id"
    else:
        experiment_id_col = "id"

    op.create_table(
        "experiment_variants",
        sa.Column("variant_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column("variant_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "variant_type",
            sa.Enum("CONTROL", "TREATMENT", name="varianttype"),
            nullable=False,
            server_default="TREATMENT",
        ),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_control", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("feature_overrides", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], name="fk_experiment_variants_experiment"),
        sa.PrimaryKeyConstraint("variant_id"),
        sa.UniqueConstraint("experiment_id", "variant_key", name="uq_experiment_variant_key"),
        sa.CheckConstraint("weight >= 0", name="check_weight_positive"),
    )
    op.create_index(
        "idx_variants_experiment_type", "experiment_variants", ["experiment_id", "variant_type"], unique=False
    )

    # Add missing columns to businesses table
    if "businesses" in tables:
        columns = [col["name"] for col in inspector.get_columns("businesses")]
        if "geo_bucket" not in columns:
            op.add_column("businesses", sa.Column("geo_bucket", sa.String(length=80), nullable=True))
            op.create_index("idx_businesses_geo_bucket", "businesses", ["geo_bucket"], unique=False)
        if "vert_bucket" not in columns:
            op.add_column("businesses", sa.Column("vert_bucket", sa.String(length=80), nullable=True))
            op.create_index("idx_businesses_vert_bucket", "businesses", ["vert_bucket"], unique=False)

    # Add missing columns to targets table if it exists
    if "targets" in tables:
        columns = [col["name"] for col in inspector.get_columns("targets")]
        if "geo_bucket" not in columns:
            op.add_column("targets", sa.Column("geo_bucket", sa.String(length=80), nullable=True))
            op.create_index("idx_targets_geo_bucket", "targets", ["geo_bucket"], unique=False)
        if "vert_bucket" not in columns:
            op.add_column("targets", sa.Column("vert_bucket", sa.String(length=80), nullable=True))
            op.create_index("idx_targets_vert_bucket", "targets", ["vert_bucket"], unique=False)


def downgrade() -> None:
    # Drop indexes and columns from targets table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "targets" in tables:
        columns = [col["name"] for col in inspector.get_columns("targets")]
        if "vert_bucket" in columns:
            op.drop_index("idx_targets_vert_bucket", table_name="targets")
            op.drop_column("targets", "vert_bucket")
        if "geo_bucket" in columns:
            op.drop_index("idx_targets_geo_bucket", table_name="targets")
            op.drop_column("targets", "geo_bucket")

    # Drop indexes and columns from businesses table
    if "businesses" in tables:
        columns = [col["name"] for col in inspector.get_columns("businesses")]
        if "vert_bucket" in columns:
            op.drop_index("idx_businesses_vert_bucket", table_name="businesses")
            op.drop_column("businesses", "vert_bucket")
        if "geo_bucket" in columns:
            op.drop_index("idx_businesses_geo_bucket", table_name="businesses")
            op.drop_column("businesses", "geo_bucket")

    # Drop tables
    op.drop_table("experiment_variants")
    op.drop_table("campaign_batches")
    if "campaigns" in tables and not any(t.startswith("campaign") and t != "campaigns" for t in tables):
        # Only drop campaigns if we created it and no other campaign tables depend on it
        op.drop_table("campaigns")
    op.drop_table("fct_api_cost")
