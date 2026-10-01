"""Mobile-only reporting links for independent retail accounts."""
import sqlalchemy as sa
from alembic import op

revision = "20261001b_mobile_sources"
down_revision = "20261001a_mobile_sharing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "parentmobilereportingsource",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "tenant_id", name="uq_parent_mobile_source"),
    )
    op.create_index("ix_parentmobilereportingsource_parent_account_id", "parentmobilereportingsource", ["parent_account_id"])
    op.create_index("ix_parentmobilereportingsource_tenant_id", "parentmobilereportingsource", ["tenant_id"])


def downgrade():
    op.drop_table("parentmobilereportingsource")
