"""Platform-admin HQ owner invitations."""
from alembic import op
import sqlalchemy as sa

revision = "20261001d_hq_owner_invite"
down_revision = "20261001c_mobile_dispatch"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hqownerinvite",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    for column in ("parent_account_id", "tenant_id", "status", "token_hash"):
        op.create_index(f"ix_hqownerinvite_{column}", "hqownerinvite", [column], unique=column == "token_hash")


def downgrade():
    op.drop_table("hqownerinvite")
