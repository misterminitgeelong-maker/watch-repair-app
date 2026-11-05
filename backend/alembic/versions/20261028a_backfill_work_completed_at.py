"""backfill work_completed_at for jobs already in a completed or paid status

Revision ID: 20261028a_backfill_completed_at
Revises: 20261024a_auto_key_quote_options
"""
import sqlalchemy as sa
from alembic import op

revision = "20261028a_backfill_completed_at"
down_revision = "20261024a_auto_key_quote_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "autokeyjob" not in inspector.get_table_names():
        return
    bind.execute(
        sa.text(
            "UPDATE autokeyjob "
            "SET work_completed_at = COALESCE(updated_at, created_at) "
            "WHERE work_completed_at IS NULL "
            "AND status IN ('work_completed', 'booking_completed', 'completed', 'awaiting_collection', 'invoice_paid', 'collected')"
        )
    )


def downgrade() -> None:
    pass
