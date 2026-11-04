"""Site entitlements and MV number.

One site per franchisee shop; access is a set of entitlements with a payer.

Revision ID: 20261104_site_entitlements
Revises: 20261104_site_messaging_state
"""
import sqlalchemy as sa
from alembic import op

revision = "20261104_site_entitlements"
down_revision = "20261104_site_messaging_state"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("parentaccountsite", sa.Column("mv_number", sa.String(16), nullable=True))
    op.create_index("ix_parentaccountsite_mv_number", "parentaccountsite", ["mv_number"])
    op.create_table(
        "siteentitlement",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("parentaccountsite.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payer", sa.String(16), nullable=False, server_default="parent"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_siteentitlement_site_id", "siteentitlement", ["site_id"])
    op.create_index("ix_siteentitlement_parent_account_id", "siteentitlement", ["parent_account_id"])
    op.create_index("ix_siteentitlement_site_kind", "siteentitlement", ["site_id", "kind"])


def downgrade():
    op.drop_table("siteentitlement")
    op.drop_index("ix_parentaccountsite_mv_number", table_name="parentaccountsite")
    op.drop_column("parentaccountsite", "mv_number")
