"""shoe_status_history_and_smslog_shoe_fk

Revision ID: e8b9c0d1f2a3
Revises: b2c3d4e5f6a7
Branch Labels: None
Depends On: None

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "e8b9c0d1f2a3"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create shoe job status history table
    op.create_table(
        "shoejobstatushistory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=False),
        sa.Column("old_status", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("new_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("change_note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["shoe_repair_job_id"], ["shoerepairjob.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shoejobstatushistory_tenant_id"), "shoejobstatushistory", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_shoejobstatushistory_shoe_repair_job_id"),
        "shoejobstatushistory",
        ["shoe_repair_job_id"],
        unique=False,
    )

    # Add shoe_repair_job_id FK column to smslog
    op.add_column("smslog", sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_smslog_shoe_repair_job_id"), "smslog", ["shoe_repair_job_id"], unique=False)
    op.create_foreign_key(
        "fk_smslog_shoe_repair_job_id",
        "smslog",
        "shoerepairjob",
        ["shoe_repair_job_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_smslog_shoe_repair_job_id", "smslog", type_="foreignkey")
    op.drop_index(op.f("ix_smslog_shoe_repair_job_id"), table_name="smslog")
    op.drop_column("smslog", "shoe_repair_job_id")

    op.drop_index(op.f("ix_shoejobstatushistory_shoe_repair_job_id"), table_name="shoejobstatushistory")
    op.drop_index(op.f("ix_shoejobstatushistory_tenant_id"), table_name="shoejobstatushistory")
    op.drop_table("shoejobstatushistory")
