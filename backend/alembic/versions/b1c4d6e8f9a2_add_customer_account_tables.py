"""add_customer_account_tables

Revision ID: b1c4d6e8f9a2
Revises: a6e8d2f4c1b9
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b1c4d6e8f9a2"
down_revision: Union[str, None] = "a6e8d2f4c1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customeraccount",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("account_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("contact_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("contact_email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("contact_phone", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("billing_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customeraccount_tenant_id"), "customeraccount", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_customeraccount_account_code"), "customeraccount", ["account_code"], unique=False)

    op.create_table(
        "customeraccountmembership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_account_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_account_id"], ["customeraccount.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customeraccountmembership_tenant_id"), "customeraccountmembership", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_customeraccountmembership_customer_account_id"), "customeraccountmembership", ["customer_account_id"], unique=False)
    op.create_index(op.f("ix_customeraccountmembership_customer_id"), "customeraccountmembership", ["customer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customeraccountmembership_customer_id"), table_name="customeraccountmembership")
    op.drop_index(op.f("ix_customeraccountmembership_customer_account_id"), table_name="customeraccountmembership")
    op.drop_index(op.f("ix_customeraccountmembership_tenant_id"), table_name="customeraccountmembership")
    op.drop_table("customeraccountmembership")

    op.drop_index(op.f("ix_customeraccount_account_code"), table_name="customeraccount")
    op.drop_index(op.f("ix_customeraccount_tenant_id"), table_name="customeraccount")
    op.drop_table("customeraccount")
