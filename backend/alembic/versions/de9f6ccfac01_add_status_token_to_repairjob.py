"""add_status_token_to_repairjob

Revision ID: de9f6ccfac01
Revises: c31dd0be9d6f
Create Date: 2026-03-10

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "de9f6ccfac01"
down_revision: Union[str, None] = "c31dd0be9d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repairjob", sa.Column("status_token", sa.String(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM repairjob")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE repairjob SET status_token = :token WHERE id = :id"),
            {"token": uuid4().hex, "id": row[0]},
        )

    op.alter_column("repairjob", "status_token", nullable=False)
    op.create_index(op.f("ix_repairjob_status_token"), "repairjob", ["status_token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_repairjob_status_token"), table_name="repairjob")
    op.drop_column("repairjob", "status_token")
