"""sms opt-out suppression list and inbound MessageSid receipts"""
from alembic import op
import sqlalchemy as sa

revision = "20261019a_sms_controls"
down_revision = "20261009a_hq_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "smssuppression",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("phone_normalized", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("keyword", sa.String(length=32), nullable=True),
        sa.Column("source_tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_smssuppression_phone_normalized", "smssuppression", ["phone_normalized"], unique=True)
    op.create_index("ix_smssuppression_active", "smssuppression", ["active"])
    op.create_table(
        "inboundsmsreceipt",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_sid", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inboundsmsreceipt_message_sid", "inboundsmsreceipt", ["message_sid"], unique=True)


def downgrade():
    op.drop_index("ix_inboundsmsreceipt_message_sid", table_name="inboundsmsreceipt")
    op.drop_table("inboundsmsreceipt")
    op.drop_index("ix_smssuppression_active", table_name="smssuppression")
    op.drop_index("ix_smssuppression_phone_normalized", table_name="smssuppression")
    op.drop_table("smssuppression")
