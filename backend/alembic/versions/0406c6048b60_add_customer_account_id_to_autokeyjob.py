"""add customer_account_id to autokeyjob

Revision ID: 0406c6048b60
Revises: bed1e400718f
Create Date: 2026-03-24 22:08:45.893543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0406c6048b60'
down_revision: Union[str, None] = 'bed1e400718f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("autokeyjob")}
    if "customer_account_id" not in columns:
        op.add_column("autokeyjob", sa.Column("customer_account_id", sa.Uuid(), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_customer_account_status "
        "ON autokeyjob (tenant_id, customer_account_id, status)"
    )
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_autokeyjob_customer_account_id",
            "autokeyjob",
            "customeraccount",
            ["customer_account_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_autokeyjob_customer_account_id", "autokeyjob", type_="foreignkey")
    op.execute("DROP INDEX IF EXISTS idx_autokeyjob_tenant_customer_account_status")
    columns = {col["name"] for col in sa.inspect(bind).get_columns("autokeyjob")}
    if "customer_account_id" in columns:
        op.drop_column("autokeyjob", "customer_account_id")
