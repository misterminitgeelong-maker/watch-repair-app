"""Add weekly/monthly sales report email preferences to usernotificationpreference

Revision ID: 20260713_sales_report_prefs
Revises: 20260702_force_hq_testing
"""

from alembic import op
import sqlalchemy as sa

revision = "20260713_sales_report_prefs"
down_revision = "20260702_force_hq_testing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usernotificationpreference") as batch:
        batch.add_column(sa.Column("email_weekly_sales_report", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("email_monthly_sales_report", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("last_weekly_sales_report_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_monthly_sales_report_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usernotificationpreference") as batch:
        batch.drop_column("last_monthly_sales_report_sent_at")
        batch.drop_column("last_weekly_sales_report_sent_at")
        batch.drop_column("email_monthly_sales_report")
        batch.drop_column("email_weekly_sales_report")
