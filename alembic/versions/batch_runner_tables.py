"""Add BatchReport and BatchReportLead tables

Revision ID: batch_runner_001
Revises: lead_explorer_001
Create Date: 2025-07-12 20:30:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "batch_runner_001"
down_revision = "01dbf243d224"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create BatchReport and BatchReportLead tables"""

    # Create batch_reports table
    op.create_table(
        "batch_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="batchstatus"),
            nullable=False,
            default="PENDING",
        ),
        sa.Column("total_leads", sa.Integer(), nullable=False, default=0),
        sa.Column("processed_leads", sa.Integer(), nullable=False, default=0),
        sa.Column("successful_leads", sa.Integer(), nullable=False, default=0),
        sa.Column("failed_leads", sa.Integer(), nullable=False, default=0),
        sa.Column("estimated_cost", sa.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column("actual_cost", sa.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column("template_version", sa.String(length=50), nullable=True),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for batch_reports
    op.create_index("ix_batch_reports_status", "batch_reports", ["status"])
    op.create_index("ix_batch_reports_created_at", "batch_reports", ["created_at"])
    op.create_index("ix_batch_reports_created_by_status", "batch_reports", ["created_by", "status"])

    # Create batch_report_leads table
    op.create_table(
        "batch_report_leads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("lead_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", "SKIPPED", name="leadprocessingstatus"),
            nullable=False,
            default="PENDING",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("report_url", sa.String(length=500), nullable=True),
        sa.Column("cost", sa.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["batch_id"], ["batch_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for batch_report_leads
    op.create_index("ix_batch_report_leads_batch_id_status", "batch_report_leads", ["batch_id", "status"])
    op.create_index("ix_batch_report_leads_lead_id", "batch_report_leads", ["lead_id"])
    op.create_index("ix_batch_report_leads_created_at", "batch_report_leads", ["created_at"])
    op.create_index("ix_batch_report_leads_batch_id_created_at", "batch_report_leads", ["batch_id", "created_at"])


def downgrade() -> None:
    """Drop BatchReport and BatchReportLead tables"""

    # Drop indexes first
    op.drop_index("ix_batch_report_leads_batch_id_created_at", "batch_report_leads")
    op.drop_index("ix_batch_report_leads_created_at", "batch_report_leads")
    op.drop_index("ix_batch_report_leads_lead_id", "batch_report_leads")
    op.drop_index("ix_batch_report_leads_batch_id_status", "batch_report_leads")

    op.drop_index("ix_batch_reports_created_by_status", "batch_reports")
    op.drop_index("ix_batch_reports_created_at", "batch_reports")
    op.drop_index("ix_batch_reports_status", "batch_reports")

    # Drop tables
    op.drop_table("batch_report_leads")
    op.drop_table("batch_reports")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS leadprocessingstatus")
    op.execute("DROP TYPE IF EXISTS batchstatus")
