"""add_import_log_tables

Revision ID: b7b5e6f3a9f2
Revises: 9d2f8f2f7e1b
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7b5e6f3a9f2"
down_revision: Union[str, None] = "9d2f8f2f7e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "importlog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("customers_created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_importlog_tenant_id"), "importlog", ["tenant_id"], unique=False)

    op.create_table(
        "importlogdetail",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_log_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("skip_reason", sa.String(), nullable=True),
        sa.Column("created_repair_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_customer_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["import_log_id"], ["importlog.id"]),
        sa.ForeignKeyConstraint(["created_repair_job_id"], ["repairjob.id"]),
        sa.ForeignKeyConstraint(["created_customer_id"], ["customer.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_importlogdetail_import_log_id"), "importlogdetail", ["import_log_id"], unique=False)

    op.alter_column("importlog", "total_rows", server_default=None)
    op.alter_column("importlog", "imported_count", server_default=None)
    op.alter_column("importlog", "skipped_count", server_default=None)
    op.alter_column("importlog", "customers_created_count", server_default=None)
    op.alter_column("importlog", "status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_importlogdetail_import_log_id"), table_name="importlogdetail")
    op.drop_table("importlogdetail")

    op.drop_index(op.f("ix_importlog_tenant_id"), table_name="importlog")
    op.drop_table("importlog")
