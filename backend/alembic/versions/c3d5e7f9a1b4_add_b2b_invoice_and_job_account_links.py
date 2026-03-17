"""add_b2b_invoice_and_job_account_links

Revision ID: c3d5e7f9a1b4
Revises: b1c4d6e8f9a2
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c3d5e7f9a1b4"
down_revision: Union[str, None] = "b1c4d6e8f9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add customer_account_id columns to existing job tables if they exist
    # (Some tables may not exist in all environments)
    with op.batch_alter_table("repairjob", schema=None) as batch_op:
        batch_op.add_column(sa.Column("customer_account_id", sa.Uuid(), nullable=True))
        batch_op.create_index(op.f("ix_repairjob_customer_account_id"), ["customer_account_id"], unique=False)
    
    op.create_table(
        "customeraccountinvoice",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_account_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_account_id"], ["customeraccount.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customeraccountinvoice_tenant_id"), "customeraccountinvoice", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_customeraccountinvoice_customer_account_id"), "customeraccountinvoice", ["customer_account_id"], unique=False)
    op.create_index(op.f("ix_customeraccountinvoice_invoice_number"), "customeraccountinvoice", ["invoice_number"], unique=False)

    op.create_table(
        "customeraccountinvoiceline",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_account_invoice_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_job_id", sa.Uuid(), nullable=False),
        sa.Column("job_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_account_invoice_id"], ["customeraccountinvoice.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customeraccountinvoiceline_tenant_id"), "customeraccountinvoiceline", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_customeraccountinvoiceline_customer_account_invoice_id"), "customeraccountinvoiceline", ["customer_account_invoice_id"], unique=False)
    op.create_index(op.f("ix_customeraccountinvoiceline_source_job_id"), "customeraccountinvoiceline", ["source_job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customeraccountinvoiceline_source_job_id"), table_name="customeraccountinvoiceline")
    op.drop_index(op.f("ix_customeraccountinvoiceline_customer_account_invoice_id"), table_name="customeraccountinvoiceline")
    op.drop_index(op.f("ix_customeraccountinvoiceline_tenant_id"), table_name="customeraccountinvoiceline")
    op.drop_table("customeraccountinvoiceline")

    op.drop_index(op.f("ix_customeraccountinvoice_invoice_number"), table_name="customeraccountinvoice")
    op.drop_index(op.f("ix_customeraccountinvoice_customer_account_id"), table_name="customeraccountinvoice")
    op.drop_index(op.f("ix_customeraccountinvoice_tenant_id"), table_name="customeraccountinvoice")
    op.drop_table("customeraccountinvoice")

    with op.batch_alter_table("repairjob", schema=None) as batch_op:
        batch_op.drop_index(op.f("ix_repairjob_customer_account_id"))
        batch_op.drop_column("customer_account_id")
