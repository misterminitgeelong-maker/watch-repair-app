"""Remap retired watch statuses to the new 3rd-party-repairer pipeline.

parts_to_order      -> at_third_party_for_quoting  (slot renamed)
sent_to_labanda     -> third_party_quote_approved  (slot renamed)
quoted_by_labanda   -> third_party_quote_approved  (status removed)
service             -> working_on                  (status removed)

Watch repair jobs only — shoe repairs keep parts_to_order/service.

Revision ID: 20260611_third_party_statuses
Revises: 20260610_quote_reminders
"""
from alembic import op

revision = "20260611_third_party_statuses"
down_revision = "20260610_quote_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE repairjob SET status = 'at_third_party_for_quoting' WHERE status = 'parts_to_order'"
    )
    op.execute(
        "UPDATE repairjob SET status = 'third_party_quote_approved' "
        "WHERE status IN ('sent_to_labanda', 'quoted_by_labanda')"
    )
    op.execute(
        "UPDATE repairjob SET status = 'working_on' WHERE status = 'service'"
    )


def downgrade() -> None:
    # Best-effort reverse: quoted_by_labanda and service rows can't be
    # distinguished after upgrade, so they stay on the nearest old status.
    op.execute(
        "UPDATE repairjob SET status = 'parts_to_order' WHERE status = 'at_third_party_for_quoting'"
    )
    op.execute(
        "UPDATE repairjob SET status = 'sent_to_labanda' WHERE status = 'third_party_quote_approved'"
    )
