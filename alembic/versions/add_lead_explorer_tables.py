"""Add Lead and AuditLogLead tables for Lead Explorer

Revision ID: add_lead_explorer_001
Revises: c1cdcf290cb2
Create Date: 2025-07-13 12:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_lead_explorer_001"
down_revision = "c1cdcf290cb2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Lead and AuditLogLead tables"""

    # Use String types for all databases to avoid enum conflicts
    # The application models handle the enum validation
    enrichmentstatus_enum = sa.String(length=20)
    auditaction_enum = sa.String(length=10)

    # Create leads table
    op.create_table(
        "leads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=500), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("enrichment_status", enrichmentstatus_enum, nullable=False, server_default="PENDING"),
        sa.Column("enrichment_task_id", sa.String(length=255), nullable=True),
        sa.Column("enrichment_error", sa.Text(), nullable=True),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("deleted_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_leads_email"),
        sa.UniqueConstraint("domain", name="uq_leads_domain"),
    )

    # Create indexes for leads table
    op.create_index("ix_leads_email_domain", "leads", ["email", "domain"])
    op.create_index("ix_leads_enrichment_lookup", "leads", ["enrichment_status", "enrichment_task_id"])
    op.create_index("ix_leads_active_manual", "leads", ["is_deleted", "is_manual"])
    op.create_index("ix_leads_created_status", "leads", ["created_at", "enrichment_status"])
    op.create_index(op.f("ix_leads_email"), "leads", ["email"], unique=False)
    op.create_index(op.f("ix_leads_domain"), "leads", ["domain"], unique=False)
    op.create_index(op.f("ix_leads_enrichment_status"), "leads", ["enrichment_status"], unique=False)
    op.create_index(op.f("ix_leads_enrichment_task_id"), "leads", ["enrichment_task_id"], unique=False)
    op.create_index(op.f("ix_leads_is_manual"), "leads", ["is_manual"], unique=False)
    op.create_index(op.f("ix_leads_is_deleted"), "leads", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_leads_created_at"), "leads", ["created_at"], unique=False)

    # Create audit_log_leads table
    op.create_table(
        "audit_log_leads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("lead_id", sa.String(), nullable=False),
        sa.Column("action", auditaction_enum, nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("user_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("old_values", sa.Text(), nullable=True),
        sa.Column("new_values", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for audit_log_leads table
    op.create_index("ix_audit_leads_lead_id_timestamp", "audit_log_leads", ["lead_id", "timestamp"])
    op.create_index("ix_audit_leads_action_timestamp", "audit_log_leads", ["action", "timestamp"])
    op.create_index("ix_audit_leads_user_timestamp", "audit_log_leads", ["user_id", "timestamp"])
    op.create_index(op.f("ix_audit_log_leads_lead_id"), "audit_log_leads", ["lead_id"], unique=False)
    op.create_index(op.f("ix_audit_log_leads_action"), "audit_log_leads", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_leads_timestamp"), "audit_log_leads", ["timestamp"], unique=False)


def downgrade() -> None:
    """Drop Lead and AuditLogLead tables"""

    # Drop audit_log_leads table and indexes
    op.drop_index(op.f("ix_audit_log_leads_timestamp"), table_name="audit_log_leads")
    op.drop_index(op.f("ix_audit_log_leads_action"), table_name="audit_log_leads")
    op.drop_index(op.f("ix_audit_log_leads_lead_id"), table_name="audit_log_leads")
    op.drop_index("ix_audit_leads_user_timestamp", table_name="audit_log_leads")
    op.drop_index("ix_audit_leads_action_timestamp", table_name="audit_log_leads")
    op.drop_index("ix_audit_leads_lead_id_timestamp", table_name="audit_log_leads")
    op.drop_table("audit_log_leads")

    # Drop leads table and indexes
    op.drop_index(op.f("ix_leads_created_at"), table_name="leads")
    op.drop_index(op.f("ix_leads_is_deleted"), table_name="leads")
    op.drop_index(op.f("ix_leads_is_manual"), table_name="leads")
    op.drop_index(op.f("ix_leads_enrichment_task_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_enrichment_status"), table_name="leads")
    op.drop_index(op.f("ix_leads_domain"), table_name="leads")
    op.drop_index(op.f("ix_leads_email"), table_name="leads")
    op.drop_index("ix_leads_created_status", table_name="leads")
    op.drop_index("ix_leads_active_manual", table_name="leads")
    op.drop_index("ix_leads_enrichment_lookup", table_name="leads")
    op.drop_index("ix_leads_email_domain", table_name="leads")
    op.drop_table("leads")
