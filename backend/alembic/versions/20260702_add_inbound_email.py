"""add inboundemail table for BCC'd enquiry-form email capture

Revision ID: 20260702_inbound_email
Revises: 20260622_shop_booking_routing
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260702_inbound_email"
down_revision: Union[str, None] = "20260622_shop_booking_routing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inboundemail",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=True),
        sa.Column("from_email", sa.String(length=500), nullable=True),
        sa.Column("to_email", sa.String(length=500), nullable=True),
        sa.Column("subject", sa.String(length=1000), nullable=True),
        sa.Column("text_body", sa.String(), nullable=True),
        sa.Column("html_body", sa.String(), nullable=True),
        sa.Column("raw_headers", sa.String(), nullable=True),
        sa.Column("spf_result", sa.String(length=200), nullable=True),
        sa.Column("dkim_result", sa.String(length=500), nullable=True),
        sa.Column("sender_ip", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("auto_key_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["auto_key_job_id"], ["autokeyjob.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "message_id", name="uq_inbound_email_parent_message_id"),
    )
    op.create_index(op.f("ix_inboundemail_parent_account_id"), "inboundemail", ["parent_account_id"], unique=False)
    op.create_index(op.f("ix_inboundemail_message_id"), "inboundemail", ["message_id"], unique=False)
    op.create_index(op.f("ix_inboundemail_status"), "inboundemail", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inboundemail_status"), table_name="inboundemail")
    op.drop_index(op.f("ix_inboundemail_message_id"), table_name="inboundemail")
    op.drop_index(op.f("ix_inboundemail_parent_account_id"), table_name="inboundemail")
    op.drop_table("inboundemail")
