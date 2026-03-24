"""add repair job counters and uniqueness

Revision ID: 7a2503368f72
Revises: 0406c6048b60
Create Date: 2026-03-24 22:22:05.298785

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2503368f72'
down_revision: Union[str, None] = '0406c6048b60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repairjobnumbercounter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_repairjobnumbercounter_tenant_id"),
        "repairjobnumbercounter",
        ["tenant_id"],
        unique=True,
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT tenant_id, job_number, COUNT(*) AS c
            FROM repairjob
            GROUP BY tenant_id, job_number
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if rows:
        raise RuntimeError(
            "Cannot add repair job uniqueness constraint: duplicate (tenant_id, job_number) rows exist."
        )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("repairjob") as batch_op:
            batch_op.create_unique_constraint(
                "uq_repairjob_tenant_job_number",
                ["tenant_id", "job_number"],
            )
    else:
        op.create_unique_constraint(
            "uq_repairjob_tenant_job_number",
            "repairjob",
            ["tenant_id", "job_number"],
        )

    existing_jobs = bind.execute(
        sa.text("SELECT tenant_id, job_number FROM repairjob")
    ).fetchall()
    max_by_tenant: dict[object, int] = {}
    for tenant_id, job_number in existing_jobs:
        parsed = 0
        if isinstance(job_number, str) and job_number.startswith("JOB-"):
            suffix = job_number[4:]
            if suffix.isdigit():
                parsed = int(suffix)
        if parsed > max_by_tenant.get(tenant_id, 0):
            max_by_tenant[tenant_id] = parsed

    for tenant_id, max_number in max_by_tenant.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO repairjobnumbercounter (id, tenant_id, next_number, created_at, updated_at)
                VALUES (:id, :tenant_id, :next_number, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "next_number": max_number + 1,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("repairjob") as batch_op:
            batch_op.drop_constraint("uq_repairjob_tenant_job_number", type_="unique")
    else:
        op.drop_constraint("uq_repairjob_tenant_job_number", "repairjob", type_="unique")
    op.drop_index(op.f("ix_repairjobnumbercounter_tenant_id"), table_name="repairjobnumbercounter")
    op.drop_table("repairjobnumbercounter")
