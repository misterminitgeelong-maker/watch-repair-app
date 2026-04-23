"""add loyalty tables (tiers, customer_loyalty, points_ledger)

Revision ID: 20260423_loyalty
Revises: z1a2b3c4d5e6
Create Date: 2026-04-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260423_loyalty"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loyaltytier",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("min_spend_cents", sa.Integer(), nullable=False),
        sa.Column("earn_multiplier_x100", sa.Integer(), nullable=False),
        sa.Column("points_expiry_months", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_loyaltytier_name"), "loyaltytier", ["name"], unique=True)

    # Seed the four tiers
    op.execute(
        "INSERT INTO loyaltytier (id, name, label, min_spend_cents, earn_multiplier_x100, points_expiry_months) VALUES "
        "(1, 'Bronze',   'Fixer',   0,     100, 24), "
        "(2, 'Silver',   'Regular', 10000, 125, 24), "
        "(3, 'Gold',     'Trusted', 30000, 150, NULL), "
        "(4, 'Platinum', 'Master',  75000, 200, NULL)"
    )

    op.create_table(
        "customerloyalty",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("tier_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("points_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["tier_id"], ["loyaltytier.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "customer_id", name="uq_customerloyalty_tenant_customer"),
    )
    op.create_index(op.f("ix_customerloyalty_tenant_id"), "customerloyalty", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_customerloyalty_customer_id"), "customerloyalty", ["customer_id"], unique=False)

    op.create_table(
        "pointsledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_loyalty_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("points_delta", sa.Integer(), nullable=False),
        sa.Column("source_invoice_id", sa.Uuid(), nullable=True),
        sa.Column("source_amount_cents", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["customer_loyalty_id"], ["customerloyalty.id"]),
        sa.ForeignKeyConstraint(["source_invoice_id"], ["invoice.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_pointsledger_idempotency"),
    )
    op.create_index(op.f("ix_pointsledger_tenant_id"), "pointsledger", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_pointsledger_customer_loyalty_id"), "pointsledger", ["customer_loyalty_id"], unique=False)
    op.create_index(op.f("ix_pointsledger_idempotency_key"), "pointsledger", ["idempotency_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pointsledger_idempotency_key"), table_name="pointsledger")
    op.drop_index(op.f("ix_pointsledger_customer_loyalty_id"), table_name="pointsledger")
    op.drop_index(op.f("ix_pointsledger_tenant_id"), table_name="pointsledger")
    op.drop_table("pointsledger")

    op.drop_index(op.f("ix_customerloyalty_customer_id"), table_name="customerloyalty")
    op.drop_index(op.f("ix_customerloyalty_tenant_id"), table_name="customerloyalty")
    op.drop_table("customerloyalty")

    op.drop_index(op.f("ix_loyaltytier_name"), table_name="loyaltytier")
    op.drop_table("loyaltytier")
