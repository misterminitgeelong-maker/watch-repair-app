"""Add gst_enabled/gst_inclusive toggle fields to quote and invoice

Revision ID: 20260802_gst_toggle
Revises: 20260713_sales_report_prefs
"""

from alembic import op
import sqlalchemy as sa

revision = "20260802_gst_toggle"
down_revision = "20260713_sales_report_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("quote", "invoice", "autokeyquote", "autokeyinvoice"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("gst_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
            batch.add_column(sa.Column("gst_inclusive", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for table in ("autokeyinvoice", "autokeyquote", "invoice", "quote"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("gst_inclusive")
            batch.drop_column("gst_enabled")
