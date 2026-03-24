"""add repair job counters and uniqueness

Revision ID: 7a2503368f72
Revises: 0406c6048b60
Create Date: 2026-03-24 22:22:05.298785

"""
import logging
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

_log = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = '7a2503368f72'
down_revision: Union[str, None] = '0406c6048b60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dedupe_repair_job_numbers(bind) -> int:
    """
    Assign unique job_number values for duplicate (tenant_id, job_number) rows.
    Keeps the oldest row (created_at, id) per group; others become DEDUP-{uuid}.
    """
    dup_groups = bind.execute(
        sa.text(
            """
            SELECT tenant_id, job_number
            FROM repairjob
            GROUP BY tenant_id, job_number
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    updated = 0
    for tenant_id, job_number in dup_groups:
        rows = bind.execute(
            sa.text(
                """
                SELECT id FROM repairjob
                WHERE tenant_id = :tenant_id AND job_number = :job_number
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"tenant_id": tenant_id, "job_number": job_number},
        ).fetchall()
        for row in rows[1:]:
            job_id = row[0]
            for _ in range(24):
                new_number = f"DEDUP-{uuid4()}"
                taken = bind.execute(
                    sa.text(
                        "SELECT 1 FROM repairjob WHERE tenant_id = :t AND job_number = :jn LIMIT 1"
                    ),
                    {"t": tenant_id, "jn": new_number},
                ).first()
                if not taken:
                    break
            else:
                raise RuntimeError(
                    "repair job dedupe: could not allocate unique job_number after retries "
                    f"(tenant_id={tenant_id})"
                )
            bind.execute(
                sa.text("UPDATE repairjob SET job_number = :jn WHERE id = :id"),
                {"jn": new_number, "id": job_id},
            )
            updated += 1
        if len(rows) > 1:
            _log.warning(
                "repair job dedupe: tenant_id=%s had %s rows for job_number=%r; "
                "kept one, renumbered %s",
                tenant_id,
                len(rows),
                job_number,
                len(rows) - 1,
            )
    return updated


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
    n_deduped = _dedupe_repair_job_numbers(bind)
    if n_deduped:
        _log.warning("repair job dedupe: total rows renumbered: %s", n_deduped)

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
            "Cannot add repair job uniqueness constraint: duplicate (tenant_id, job_number) rows remain "
            "after automated dedupe (unexpected); inspect repairjob manually."
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
