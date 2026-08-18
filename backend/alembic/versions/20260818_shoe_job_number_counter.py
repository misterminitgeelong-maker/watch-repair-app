"""compare-and-set counter for shoe repair job numbers

Revision ID: 20260818_shoe_job_counter
Revises: 20260818_phone_normalized
Create Date: 2026-08-18

"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_shoe_job_counter"
down_revision: Union[str, None] = "20260818_phone_normalized"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shoerepairjobnumbercounter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_shoerepairjobnumbercounter_tenant_id"),
        "shoerepairjobnumbercounter",
        ["tenant_id"],
        unique=True,
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT tenant_id, job_number FROM shoerepairjob")).fetchall()
    max_by_tenant: dict[object, int] = {}
    for tenant_id, job_number in rows:
        parsed = 0
        if isinstance(job_number, str) and job_number.startswith("SHO-"):
            suffix = job_number[4:]
            if suffix.isdigit():
                parsed = int(suffix)
        if parsed > max_by_tenant.get(tenant_id, 0):
            max_by_tenant[tenant_id] = parsed
    for tenant_id, max_number in max_by_tenant.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO shoerepairjobnumbercounter (id, tenant_id, next_number, created_at, updated_at)
                VALUES (:id, :tenant_id, :next_number, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(uuid4()), "tenant_id": tenant_id, "next_number": max_number + 1},
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_shoerepairjobnumbercounter_tenant_id"), table_name="shoerepairjobnumbercounter")
    op.drop_table("shoerepairjobnumbercounter")
