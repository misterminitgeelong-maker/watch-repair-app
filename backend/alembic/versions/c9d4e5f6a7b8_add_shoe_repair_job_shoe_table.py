"""add_shoe_repair_job_shoe_table

Revision ID: c9d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shoerepairjobshoe",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=False),
        sa.Column("shoe_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shoerepairjobshoe_tenant_id", "shoerepairjobshoe", ["tenant_id"])
    op.create_index("ix_shoerepairjobshoe_shoe_repair_job_id", "shoerepairjobshoe", ["shoe_repair_job_id"])

    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_shoerepairjobshoe_job_id",
            "shoerepairjobshoe", "shoerepairjob",
            ["shoe_repair_job_id"], ["id"],
        )
        op.create_foreign_key(
            "fk_shoerepairjobshoe_shoe_id",
            "shoerepairjobshoe", "shoe",
            ["shoe_id"], ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_shoerepairjobshoe_job_id", "shoerepairjobshoe", type_="foreignkey")
        op.drop_constraint("fk_shoerepairjobshoe_shoe_id", "shoerepairjobshoe", type_="foreignkey")
    op.drop_index("ix_shoerepairjobshoe_shoe_repair_job_id", table_name="shoerepairjobshoe")
    op.drop_index("ix_shoerepairjobshoe_tenant_id", table_name="shoerepairjobshoe")
    op.drop_table("shoerepairjobshoe")
