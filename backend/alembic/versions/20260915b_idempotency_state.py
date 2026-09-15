"""track idempotency reservation state

The Idempotency-Key row is now inserted *before* the mutation runs, so the unique
constraint on (tenant_id, key) is what stops a concurrent replay executing twice.
That needs a state column to describe the window between reserving the key and
knowing the response, plus completed_at so the retention sweep can tell a finished
row from a reservation whose request never came back.

Existing rows were all written after their mutation completed, so they backfill to
"completed" with completed_at set from created_at.

Revision ID: 20260915b_idem_state
Revises: 20260915_smslog_fk
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260915b_idem_state"
down_revision: Union[str, None] = "20260915_smslog_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mutationidempotencykey"


def _columns(inspector) -> set[str]:
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    existing = _columns(inspector)

    if "state" not in existing:
        op.add_column(
            _TABLE,
            sa.Column("state", sa.String(length=16), nullable=False, server_default="completed"),
        )
    if "completed_at" not in existing:
        op.add_column(_TABLE, sa.Column("completed_at", sa.DateTime(), nullable=True))

    # Rows written by the old middleware only ever existed post-response.
    op.execute(
        sa.text(
            "UPDATE mutationidempotencykey "
            "SET completed_at = created_at "
            "WHERE completed_at IS NULL"
        )
    )

    # New rows are inserted as reservations; the server default was only there to
    # backfill the existing ones.
    if bind.dialect.name != "sqlite":
        op.alter_column(_TABLE, "state", server_default="in_progress")

    existing_indexes = {ix["name"] for ix in inspector.get_indexes(_TABLE)}
    if "ix_mutationidempotencykey_created_at" not in existing_indexes:
        op.create_index(
            "ix_mutationidempotencykey_created_at", _TABLE, ["created_at"], unique=False
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return

    existing_indexes = {ix["name"] for ix in inspector.get_indexes(_TABLE)}
    if "ix_mutationidempotencykey_created_at" in existing_indexes:
        op.drop_index("ix_mutationidempotencykey_created_at", table_name=_TABLE)

    existing = _columns(inspector)
    if "completed_at" in existing:
        op.drop_column(_TABLE, "completed_at")
    if "state" in existing:
        op.drop_column(_TABLE, "state")
