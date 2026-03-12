"""add_auto_key_quote_invoice_tables

Revision ID: a6e8d2f4c1b9
Revises: f7c2d9a1b3e6
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "a6e8d2f4c1b9"
down_revision: Union[str, None] = "f7c2d9a1b3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autokeyquote",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("auto_key_job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["auto_key_job_id"], ["autokeyjob.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_autokeyquote_tenant_id"), "autokeyquote", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_autokeyquote_auto_key_job_id"), "autokeyquote", ["auto_key_job_id"], unique=False)

    op.create_table(
        "autokeyquotelineitem",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("auto_key_quote_id", sa.Uuid(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("total_price_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["auto_key_quote_id"], ["autokeyquote.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_autokeyquotelineitem_tenant_id"), "autokeyquotelineitem", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_autokeyquotelineitem_auto_key_quote_id"), "autokeyquotelineitem", ["auto_key_quote_id"], unique=False)

    op.create_table(
        "autokeyinvoice",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("auto_key_job_id", sa.Uuid(), nullable=False),
        sa.Column("auto_key_quote_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["auto_key_job_id"], ["autokeyjob.id"]),
        sa.ForeignKeyConstraint(["auto_key_quote_id"], ["autokeyquote.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_autokeyinvoice_tenant_id"), "autokeyinvoice", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_autokeyinvoice_auto_key_job_id"), "autokeyinvoice", ["auto_key_job_id"], unique=False)
    op.create_index(op.f("ix_autokeyinvoice_invoice_number"), "autokeyinvoice", ["invoice_number"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_autokeyinvoice_invoice_number"), table_name="autokeyinvoice")
    op.drop_index(op.f("ix_autokeyinvoice_auto_key_job_id"), table_name="autokeyinvoice")
    op.drop_index(op.f("ix_autokeyinvoice_tenant_id"), table_name="autokeyinvoice")
    op.drop_table("autokeyinvoice")

    op.drop_index(op.f("ix_autokeyquotelineitem_auto_key_quote_id"), table_name="autokeyquotelineitem")
    op.drop_index(op.f("ix_autokeyquotelineitem_tenant_id"), table_name="autokeyquotelineitem")
    op.drop_table("autokeyquotelineitem")

    op.drop_index(op.f("ix_autokeyquote_auto_key_job_id"), table_name="autokeyquote")
    op.drop_index(op.f("ix_autokeyquote_tenant_id"), table_name="autokeyquote")
    op.drop_table("autokeyquote")
