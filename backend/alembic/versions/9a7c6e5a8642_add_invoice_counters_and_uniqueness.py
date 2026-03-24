"""add invoice counters and uniqueness

Revision ID: 9a7c6e5a8642
Revises: 7a2503368f72
Create Date: 2026-03-24 22:29:20.323437

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a7c6e5a8642'
down_revision: Union[str, None] = '7a2503368f72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoicenumbercounter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_invoicenumbercounter_tenant_id"),
        "invoicenumbercounter",
        ["tenant_id"],
        unique=True,
    )

    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            """
            SELECT tenant_id, invoice_number, COUNT(*) AS c
            FROM invoice
            GROUP BY tenant_id, invoice_number
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if duplicates:
        raise RuntimeError(
            "Cannot add invoice uniqueness constraint: duplicate (tenant_id, invoice_number) rows exist."
        )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("invoice") as batch_op:
            batch_op.create_unique_constraint(
                "uq_invoice_tenant_invoice_number",
                ["tenant_id", "invoice_number"],
            )
    else:
        op.create_unique_constraint(
            "uq_invoice_tenant_invoice_number",
            "invoice",
            ["tenant_id", "invoice_number"],
        )

    existing_invoices = bind.execute(
        sa.text("SELECT tenant_id, invoice_number FROM invoice")
    ).fetchall()
    max_by_tenant: dict[object, int] = {}
    for tenant_id, invoice_number in existing_invoices:
        parsed = 0
        if isinstance(invoice_number, str) and invoice_number.startswith("INV-"):
            suffix = invoice_number[4:]
            if suffix.isdigit():
                parsed = int(suffix)
        if parsed > max_by_tenant.get(tenant_id, 0):
            max_by_tenant[tenant_id] = parsed

    for tenant_id, max_number in max_by_tenant.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO invoicenumbercounter (id, tenant_id, next_number, created_at, updated_at)
                VALUES (:id, :tenant_id, :next_number, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(uuid4()), "tenant_id": tenant_id, "next_number": max_number + 1},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("invoice") as batch_op:
            batch_op.drop_constraint("uq_invoice_tenant_invoice_number", type_="unique")
    else:
        op.drop_constraint("uq_invoice_tenant_invoice_number", "invoice", type_="unique")
    op.drop_index(op.f("ix_invoicenumbercounter_tenant_id"), table_name="invoicenumbercounter")
    op.drop_table("invoicenumbercounter")
