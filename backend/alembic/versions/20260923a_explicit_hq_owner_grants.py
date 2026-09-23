"""Backfill explicit HQ grants for logins that reached HQ by owner_email match.

parents_for_user / parent_role_for_user no longer treat "this login's email
equals ParentAccount.owner_email" as HQ admin access, because email is
unverified and only unique per shop. Every login that had access that way AND
sits in a shop linked to that network gets an explicit hq_admin grant here,
so nobody legitimate loses access when the fallback goes.

Revision ID: 20260923a_explicit_hq_grants
Revises: 20260921a_mobile_kpi_snapshots
Create Date: 2026-09-23
"""
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260923a_explicit_hq_grants"
down_revision: Union[str, None] = "20260921a_mobile_kpi_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT p.id AS parent_id, u.id AS user_id
            FROM parentaccount p
            JOIN "user" u ON lower(u.email) = lower(p.owner_email) AND u.is_active = :active
            JOIN parentaccountsite s ON s.parent_account_id = p.id AND s.tenant_id = u.tenant_id
            WHERE NOT EXISTS (
                SELECT 1 FROM parentaccountuser g
                WHERE g.parent_account_id = p.id AND g.user_id = u.id
            )
            """
        ),
        {"active": True},
    ).fetchall()
    if not rows:
        return
    grants = sa.table(
        "parentaccountuser",
        sa.column("id", sa.Uuid()),
        sa.column("parent_account_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("role", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("region_id", sa.Uuid()),
        sa.column("email_mobile_kpi_report", sa.Boolean()),
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        grants,
        [
            {
                "id": uuid4(),
                "parent_account_id": UUID(str(r.parent_id)),
                "user_id": UUID(str(r.user_id)),
                "role": "hq_admin",
                "created_at": now,
                "region_id": None,
                "email_mobile_kpi_report": False,
            }
            for r in rows
        ],
    )


def downgrade() -> None:
    # The grants are indistinguishable from ones made through the app; leaving
    # them in place on downgrade keeps the same people with the same access.
    pass
