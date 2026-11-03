"""State hubs, announcements and per-shop read/receipt markers.

Revision ID: 20261103_network_community
Revises: 20261103_engraving_payments
"""
import sqlalchemy as sa
from alembic import op

revision = "20261103_network_community"
down_revision = "20261103_engraving_payments"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _fk(name, target, nullable=False, ondelete="CASCADE"):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade():
    op.create_table(
        "statehubmessage", _id(), _fk("parent_account_id", "parentaccount.id"),
        sa.Column("state_code", sa.String(8), nullable=False),
        _fk("sender_tenant_id", "tenant.id"),
        _fk("sender_user_id", "user.id", True, "SET NULL"),
        sa.Column("body", sa.String(2000), nullable=False),
        _fk("reply_to_id", "statehubmessage.id", True, "SET NULL"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("pinned_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("parent_account_id", "state_code", "sender_tenant_id", "created_at"):
        op.create_index("ix_statehubmessage_" + column, "statehubmessage", [column])
    op.create_table(
        "statehubread", _id(), _fk("parent_account_id", "parentaccount.id"),
        sa.Column("state_code", sa.String(8), nullable=False), _fk("tenant_id", "tenant.id"),
        sa.Column("last_read_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_id", sa.Uuid(), nullable=True),
        sa.UniqueConstraint("parent_account_id", "state_code", "tenant_id", name="uq_statehubread_site"),
    )
    for column in ("parent_account_id", "tenant_id"):
        op.create_index("ix_statehubread_" + column, "statehubread", [column])
    op.create_table(
        "networkannouncement", _id(), _fk("parent_account_id", "parentaccount.id"),
        sa.Column("state_code", sa.String(8), nullable=True),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("body", sa.String(10000), nullable=False),
        sa.Column("category", sa.String(20), nullable=False), sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        _fk("author_user_id", "user.id", True, "SET NULL"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("parent_account_id", "state_code", "created_at"):
        op.create_index("ix_networkannouncement_" + column, "networkannouncement", [column])
    op.create_table(
        "announcementreceipt", _id(), _fk("announcement_id", "networkannouncement.id"),
        _fk("tenant_id", "tenant.id"),
        sa.Column("read_at", sa.DateTime(), nullable=False), sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("announcement_id", "tenant_id", name="uq_announcementreceipt_site"),
    )
    for column in ("announcement_id", "tenant_id"):
        op.create_index("ix_announcementreceipt_" + column, "announcementreceipt", [column])

    op.create_table(
        "networkmessageattachment", _id(),
        _fk("hub_message_id", "statehubmessage.id", True),
        _fk("direct_message_id", "networkmessage.id", True),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("(hub_message_id IS NOT NULL AND direct_message_id IS NULL) OR (hub_message_id IS NULL AND direct_message_id IS NOT NULL)", name="ck_networkattachment_one_message"),
    )
    for column in ("hub_message_id", "direct_message_id"):
        op.create_index("ix_networkmessageattachment_" + column, "networkmessageattachment", [column])


def downgrade():
    op.drop_table("networkmessageattachment")
    op.drop_table("announcementreceipt")
    op.drop_table("networkannouncement")
    op.drop_table("statehubread")
    op.drop_table("statehubmessage")

