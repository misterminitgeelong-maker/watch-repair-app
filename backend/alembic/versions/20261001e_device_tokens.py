"""Phone push notification device tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20261001e_device_tokens"
down_revision = "20261001d_hq_owner_invite"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "devicetoken",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_devicetoken_tenant_id", "devicetoken", ["tenant_id"])
    op.create_index("ix_devicetoken_user_id", "devicetoken", ["user_id"])
    op.create_index("ix_devicetoken_token", "devicetoken", ["token"], unique=True)


def downgrade():
    op.drop_table("devicetoken")
