"""add_suburbs_table

Revision ID: p9a0b1c2d3e4
Revises: o8a9b0c1d2e3
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "p9a0b1c2d3e4"
down_revision: Union[str, None] = "o8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suburb",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state_code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suburb_name"), "suburb", ["name"], unique=False)
    op.create_index(op.f("ix_suburb_state_code"), "suburb", ["state_code"], unique=False)
    op.create_index(
        "ix_suburb_state_name",
        "suburb",
        ["state_code", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_suburb_state_name", table_name="suburb")
    op.drop_index(op.f("ix_suburb_state_code"), table_name="suburb")
    op.drop_index(op.f("ix_suburb_name"), table_name="suburb")
    op.drop_table("suburb")
