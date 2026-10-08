"""one-time texted codes for phone + ticket customer portal sign-in"""
from alembic import op
import sqlalchemy as sa

revision = "20261008b_portal_access_code"
down_revision = "20261008a_portal_session_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portalaccesscode",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_portalaccesscode_customer_id", "portalaccesscode", ["customer_id"])
    op.create_index("ix_portalaccesscode_tenant_id", "portalaccesscode", ["tenant_id"])


def downgrade():
    op.drop_index("ix_portalaccesscode_tenant_id", table_name="portalaccesscode")
    op.drop_index("ix_portalaccesscode_customer_id", table_name="portalaccesscode")
    op.drop_table("portalaccesscode")
