"""add_prospect_business_table

Revision ID: q0a1b2c3d4e5
Revises: p9a0b1c2d3e4
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "q0a1b2c3d4e5"
down_revision: Union[str, None] = "p9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prospectbusiness",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("place_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("address", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("website", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("suburb_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state_code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prospectbusiness_place_id"), "prospectbusiness", ["place_id"], unique=True)
    op.create_index(op.f("ix_prospectbusiness_category"), "prospectbusiness", ["category"], unique=False)
    op.create_index(op.f("ix_prospectbusiness_suburb_name"), "prospectbusiness", ["suburb_name"], unique=False)
    op.create_index(op.f("ix_prospectbusiness_state_code"), "prospectbusiness", ["state_code"], unique=False)
    op.create_index(
        "ix_prospectbusiness_category_state_suburb",
        "prospectbusiness",
        ["category", "state_code", "suburb_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_prospectbusiness_category_state_suburb", table_name="prospectbusiness")
    op.drop_index(op.f("ix_prospectbusiness_state_code"), table_name="prospectbusiness")
    op.drop_index(op.f("ix_prospectbusiness_suburb_name"), table_name="prospectbusiness")
    op.drop_index(op.f("ix_prospectbusiness_category"), table_name="prospectbusiness")
    op.drop_index(op.f("ix_prospectbusiness_place_id"), table_name="prospectbusiness")
    op.drop_table("prospectbusiness")
