"""Add guardrail configuration tables

Revision ID: add_guardrail_tables
Revises: 1527a20d59ab
Create Date: 2025-01-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_guardrail_tables"
down_revision: Union[str, None] = "1527a20d59ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create guardrail_limits table
    op.create_table(
        "guardrail_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("period", sa.String(50), nullable=False),
        sa.Column("limit_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(100), nullable=True),
        sa.Column("warning_threshold", sa.Float(), nullable=False),
        sa.Column("critical_threshold", sa.Float(), nullable=False),
        sa.Column("actions", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("circuit_breaker_enabled", sa.Boolean(), nullable=False),
        sa.Column("circuit_breaker_failure_threshold", sa.Integer(), nullable=False),
        sa.Column("circuit_breaker_recovery_timeout", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_guardrail_limits_provider"), "guardrail_limits", ["provider"], unique=False)
    op.create_index(op.f("ix_guardrail_limits_campaign_id"), "guardrail_limits", ["campaign_id"], unique=False)

    # Create guardrail_violations table
    op.create_table(
        "guardrail_violations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("limit_name", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("current_spend", sa.Numeric(10, 4), nullable=False),
        sa.Column("limit_amount", sa.Numeric(10, 4), nullable=False),
        sa.Column("percentage_used", sa.Float(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(100), nullable=True),
        sa.Column("action_taken", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_guardrail_violations_timestamp"), "guardrail_violations", ["timestamp"], unique=False)
    op.create_index(op.f("ix_guardrail_violations_provider"), "guardrail_violations", ["provider"], unique=False)
    op.create_index(op.f("ix_guardrail_violations_severity"), "guardrail_violations", ["severity"], unique=False)

    # Create rate_limits table
    op.create_table(
        "rate_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("operation", sa.String(100), nullable=True),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("burst_size", sa.Integer(), nullable=False),
        sa.Column("cost_per_minute", sa.Numeric(10, 4), nullable=True),
        sa.Column("cost_burst_size", sa.Numeric(10, 4), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rate_limits_provider_operation"), "rate_limits", ["provider", "operation"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_rate_limits_provider_operation"), table_name="rate_limits")
    op.drop_table("rate_limits")
    op.drop_index(op.f("ix_guardrail_violations_severity"), table_name="guardrail_violations")
    op.drop_index(op.f("ix_guardrail_violations_provider"), table_name="guardrail_violations")
    op.drop_index(op.f("ix_guardrail_violations_timestamp"), table_name="guardrail_violations")
    op.drop_table("guardrail_violations")
    op.drop_index(op.f("ix_guardrail_limits_campaign_id"), table_name="guardrail_limits")
    op.drop_index(op.f("ix_guardrail_limits_provider"), table_name="guardrail_limits")
    op.drop_table("guardrail_limits")
