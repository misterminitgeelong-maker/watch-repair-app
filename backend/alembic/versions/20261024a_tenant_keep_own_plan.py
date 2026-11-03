"""tenant.keep_own_plan: let a Minit-network shop keep a non-Minit plan"""
import sqlalchemy as sa
from alembic import op

revision = "20261024a_tenant_keep_own_plan"
down_revision = "20261019a_lead_routing_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tenant",
        sa.Column("keep_own_plan", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("tenant", "keep_own_plan")
