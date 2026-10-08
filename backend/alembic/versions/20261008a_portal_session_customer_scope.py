"""portal sessions opened by phone + ticket number are scoped to one customer"""
from alembic import op
import sqlalchemy as sa

revision = "20261008a_portal_session_scope"
down_revision = "20261001e_device_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("portalsession", sa.Column("customer_id", sa.Uuid(), nullable=True))
    op.add_column("portalsession", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.create_index("ix_portalsession_customer_id", "portalsession", ["customer_id"])
    op.create_index("ix_portalsession_tenant_id", "portalsession", ["tenant_id"])


def downgrade():
    op.drop_index("ix_portalsession_tenant_id", table_name="portalsession")
    op.drop_index("ix_portalsession_customer_id", table_name="portalsession")
    op.drop_column("portalsession", "tenant_id")
    op.drop_column("portalsession", "customer_id")
