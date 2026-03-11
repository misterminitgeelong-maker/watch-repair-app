"""add_shoe_repair_job_id_to_attachment

Revision ID: a1b2c3d4e5f6
Revises: 9d2f8f2f7e1b
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "de9f6ccfac01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attachment",
        sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_attachment_shoe_repair_job_id",
        "attachment",
        ["shoe_repair_job_id"],
    )
    # Foreign key only for non-SQLite (SQLite doesn't support ADD CONSTRAINT)
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_attachment_shoe_repair_job_id",
            "attachment",
            "shoerepairjob",
            ["shoe_repair_job_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_attachment_shoe_repair_job_id", "attachment", type_="foreignkey")
    op.drop_index("ix_attachment_shoe_repair_job_id", table_name="attachment")
    op.drop_column("attachment", "shoe_repair_job_id")
