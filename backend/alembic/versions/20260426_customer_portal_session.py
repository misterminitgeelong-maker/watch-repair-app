"""add customer_portal_session table

Revision ID: 20260426_customer_portal_session
Revises: 20260425b_add_cust_acct_id
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = "20260426_customer_portal_session"
down_revision = "20260425b_add_cust_acct_id"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customerportalsession",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_customerportalsession_token", "customerportalsession", ["token"])
    op.create_index("ix_customerportalsession_tenant_id", "customerportalsession", ["tenant_id"])
    op.create_index("ix_customerportalsession_customer_id", "customerportalsession", ["customer_id"])


def downgrade():
    op.drop_index("ix_customerportalsession_customer_id", table_name="customerportalsession")
    op.drop_index("ix_customerportalsession_tenant_id", table_name="customerportalsession")
    op.drop_index("ix_customerportalsession_token", table_name="customerportalsession")
    op.drop_table("customerportalsession")
