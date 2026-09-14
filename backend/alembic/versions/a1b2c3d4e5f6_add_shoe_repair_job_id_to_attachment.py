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
    # Foreign key only for non-SQLite (SQLite doesn't support ADD CONSTRAINT).
    # shoerepairjob is created later in the chain (20260612_reconcile_shoe_tables)
    # on a fresh database; 20260914b_shoe_fk_backfill adds this FK afterwards.
    bind = op.get_bind()
    if bind.dialect.name != "sqlite" and sa.inspect(bind).has_table("shoerepairjob"):
        op.create_foreign_key(
            "fk_attachment_shoe_repair_job_id",
            "attachment",
            "shoerepairjob",
            ["shoe_repair_job_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite" and any(
        fk["name"] == "fk_attachment_shoe_repair_job_id" for fk in sa.inspect(bind).get_foreign_keys("attachment")
    ):
        op.drop_constraint("fk_attachment_shoe_repair_job_id", "attachment", type_="foreignkey")
    op.drop_index("ix_attachment_shoe_repair_job_id", table_name="attachment")
    op.drop_column("attachment", "shoe_repair_job_id")
