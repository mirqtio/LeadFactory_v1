"""Add PRD v1.2 assessment columns

Revision ID: 005
Revises: 004
Create Date: 2025-06-13

Adds columns for new assessment stack:
- domain_hash and phone_hash to businesses
- New assessment data columns to assessment_results
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "e3ab105c6555"  # Points to initial schema
branch_labels = None
depends_on = None


def upgrade():
    # Get the context to determine database type
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Use appropriate JSON type based on database
    if dialect_name == "postgresql":
        json_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        # For SQLite and other databases, use Text type
        json_type = sa.Text()

    # Add columns to businesses table
    op.add_column("businesses", sa.Column("domain_hash", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("phone_hash", sa.Text(), nullable=True))

    # Add columns to assessment_results table (note: table name from initial migration)
    op.add_column(
        "assessment_results",
        sa.Column("bsoup_json", json_type, nullable=True),
    )
    op.add_column(
        "assessment_results",
        sa.Column("semrush_json", json_type, nullable=True),
    )
    op.add_column(
        "assessment_results",
        sa.Column("yelp_json", json_type, nullable=True),
    )
    op.add_column(
        "assessment_results",
        sa.Column("gbp_profile_json", json_type, nullable=True),
    )
    op.add_column("assessment_results", sa.Column("screenshot_url", sa.Text(), nullable=True))
    op.add_column(
        "assessment_results",
        sa.Column("screenshot_thumb_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "assessment_results",
        sa.Column("visual_scores_json", json_type, nullable=True),
    )
    op.add_column(
        "assessment_results",
        sa.Column("visual_warnings", json_type, nullable=True),
    )
    op.add_column(
        "assessment_results",
        sa.Column("visual_quickwins", json_type, nullable=True),
    )

    # Create index on domain_hash for faster lookups
    op.create_index("idx_business_domain_hash", "businesses", ["domain_hash"], unique=False)


def downgrade():
    # Drop index
    op.drop_index("idx_business_domain_hash", table_name="businesses")

    # Drop columns from assessment_results
    op.drop_column("assessment_results", "visual_quickwins")
    op.drop_column("assessment_results", "visual_warnings")
    op.drop_column("assessment_results", "visual_scores_json")
    op.drop_column("assessment_results", "screenshot_thumb_url")
    op.drop_column("assessment_results", "screenshot_url")
    op.drop_column("assessment_results", "gbp_profile_json")
    op.drop_column("assessment_results", "yelp_json")
    op.drop_column("assessment_results", "semrush_json")
    op.drop_column("assessment_results", "bsoup_json")

    # Drop columns from businesses
    op.drop_column("businesses", "phone_hash")
    op.drop_column("businesses", "domain_hash")
