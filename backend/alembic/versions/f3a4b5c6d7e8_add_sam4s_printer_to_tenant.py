"""Add SAM4S network printer host/port to tenant.

Revision ID: f3a4b5c6d7e8
Revises: 20260713_sales_report_prefs
Create Date: 2026-07-22

"""
from alembic import op
import sqlalchemy as sa

revision = "f3a4b5c6d7e8"
down_revision = "20260713_sales_report_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("sam4s_printer_host", sa.String(length=255), nullable=True))
    op.add_column("tenant", sa.Column("sam4s_printer_port", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant", "sam4s_printer_port")
    op.drop_column("tenant", "sam4s_printer_host")
