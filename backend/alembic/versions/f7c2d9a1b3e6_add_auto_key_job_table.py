"""add_auto_key_job_table

Revision ID: f7c2d9a1b3e6
Revises: e4a9b1c2d3f4
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "f7c2d9a1b3e6"
down_revision: Union[str, None] = "e4a9b1c2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autokeyjob",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("job_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("vehicle_make", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("vehicle_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("vehicle_year", sa.Integer(), nullable=True),
        sa.Column("registration_plate", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("vin", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("key_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("key_quantity", sa.Integer(), nullable=False),
        sa.Column("programming_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("priority", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("salesperson", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("deposit_cents", sa.Integer(), nullable=False),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_autokeyjob_tenant_id"), "autokeyjob", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_autokeyjob_customer_id"), "autokeyjob", ["customer_id"], unique=False)
    op.create_index(op.f("ix_autokeyjob_job_number"), "autokeyjob", ["job_number"], unique=False)
    op.create_index(op.f("ix_autokeyjob_status_token"), "autokeyjob", ["status_token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_autokeyjob_status_token"), table_name="autokeyjob")
    op.drop_index(op.f("ix_autokeyjob_job_number"), table_name="autokeyjob")
    op.drop_index(op.f("ix_autokeyjob_customer_id"), table_name="autokeyjob")
    op.drop_index(op.f("ix_autokeyjob_tenant_id"), table_name="autokeyjob")
    op.drop_table("autokeyjob")
