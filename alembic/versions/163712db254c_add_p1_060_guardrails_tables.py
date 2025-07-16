"""Add P1-060 guardrails tables

Revision ID: 163712db254c
Revises: 11c6591e1a0d
Create Date: 2025-07-16 12:30:59.976553

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "163712db254c"
down_revision = "11c6591e1a0d"
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


def upgrade() -> None:
    # Create guardrail_limits table
    op.create_table(
        "guardrail_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("period", sa.String(length=50), nullable=False),
        sa.Column("limit_usd", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_guardrail_limits_provider", "guardrail_limits", ["provider"], unique=False)
    op.create_index("ix_guardrail_limits_campaign_id", "guardrail_limits", ["campaign_id"], unique=False)

    # Create guardrail_violations table
    op.create_table(
        "guardrail_violations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("limit_id", sa.Integer(), nullable=False),
        sa.Column("limit_name", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("current_spend", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("percentage_used", sa.Float(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["limit_id"],
            ["guardrail_limits.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guardrail_violations_timestamp", "guardrail_violations", ["timestamp"], unique=False)
    op.create_index("ix_guardrail_violations_severity", "guardrail_violations", ["severity"], unique=False)
    op.create_index("ix_guardrail_violations_provider", "guardrail_violations", ["provider"], unique=False)
    op.create_index(
        "ix_guardrail_violations_timestamp_severity", "guardrail_violations", ["timestamp", "severity"], unique=False
    )

    # Create rate_limits table
    op.create_table(
        "rate_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=True),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("burst_size", sa.Integer(), nullable=False),
        sa.Column("cost_per_minute_usd", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("cost_burst_usd", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rate_limits_provider_operation", "rate_limits", ["provider", "operation"], unique=True)

    # Create alert_history table
    op.create_table(
        "alert_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("violation_id", sa.Integer(), nullable=False),
        sa.Column("alert_channel", sa.String(length=50), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(), server_default=get_timestamp_default(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, default=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["violation_id"],
            ["guardrail_violations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_history_sent_at", "alert_history", ["sent_at"], unique=False)
    op.create_index("ix_alert_history_sent_at_channel", "alert_history", ["sent_at", "alert_channel"], unique=False)


def downgrade() -> None:
    # Drop alert_history table
    op.drop_index("ix_alert_history_sent_at_channel", table_name="alert_history")
    op.drop_index("ix_alert_history_sent_at", table_name="alert_history")
    op.drop_table("alert_history")

    # Drop rate_limits table
    op.drop_index("ix_rate_limits_provider_operation", table_name="rate_limits")
    op.drop_table("rate_limits")

    # Drop guardrail_violations table
    op.drop_index("ix_guardrail_violations_timestamp_severity", table_name="guardrail_violations")
    op.drop_index("ix_guardrail_violations_provider", table_name="guardrail_violations")
    op.drop_index("ix_guardrail_violations_severity", table_name="guardrail_violations")
    op.drop_index("ix_guardrail_violations_timestamp", table_name="guardrail_violations")
    op.drop_table("guardrail_violations")

    # Drop guardrail_limits table
    op.drop_index("ix_guardrail_limits_campaign_id", table_name="guardrail_limits")
    op.drop_index("ix_guardrail_limits_provider", table_name="guardrail_limits")
    op.drop_table("guardrail_limits")
