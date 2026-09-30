"""auto-route BCC'd website-form emails to the matched operator's Lead Inbox

Revision ID: 20260930a_email_auto_route
Revises: 20260927a_invite_reminder
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260930a_email_auto_route"
down_revision: Union[str, None] = "20260927a_invite_reminder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parentaccount",
        sa.Column("inbound_email_auto_route", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("inboundemail", sa.Column("prospect_lead_id", sa.Uuid(), nullable=True))
    op.add_column("inboundemail", sa.Column("routed_tenant_id", sa.Uuid(), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_inboundemail_routed_tenant_id",
            "inboundemail",
            "tenant",
            ["routed_tenant_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_inboundemail_routed_tenant_id", "inboundemail", type_="foreignkey")
    op.drop_column("inboundemail", "routed_tenant_id")
    op.drop_column("inboundemail", "prospect_lead_id")
    op.drop_column("parentaccount", "inbound_email_auto_route")
