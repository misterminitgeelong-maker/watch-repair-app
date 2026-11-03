"""direct messages between sites of one network

Adds networkconversation (one thread per pair of sites per network) and
networkmessage.

Revision ID: 20261102_network_messages
Revises: 20261101_engraving_events
Create Date: 2026-11-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_network_messages"
down_revision: Union[str, None] = "20261101_engraving_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "networkconversation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_low_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_high_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("parent_account_id", "tenant_low_id", "tenant_high_id", name="uq_networkconversation_pair"),
    )
    op.create_index("ix_networkconversation_parent_account_id", "networkconversation", ["parent_account_id"])
    op.create_index("ix_networkconversation_tenant_low_id", "networkconversation", ["tenant_low_id"])
    op.create_index("ix_networkconversation_tenant_high_id", "networkconversation", ["tenant_high_id"])

    op.create_table(
        "networkmessage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("networkconversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_networkmessage_conversation_id", "networkmessage", ["conversation_id"])
    op.create_index("ix_networkmessage_sender_tenant_id", "networkmessage", ["sender_tenant_id"])


def downgrade() -> None:
    op.drop_table("networkmessage")
    op.drop_table("networkconversation")
