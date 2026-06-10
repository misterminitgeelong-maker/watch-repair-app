"""Add reminder_sent_at to quote and autokeyquote for no-decision reminder SMS

Revision ID: 20260610_quote_reminders
Revises: 20260602_qol_features
"""

from alembic import op
import sqlalchemy as sa

revision = "20260610_quote_reminders"
down_revision = "20260602_qol_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("quote", "autokeyquote"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in ("autokeyquote", "quote"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("reminder_sent_at")
