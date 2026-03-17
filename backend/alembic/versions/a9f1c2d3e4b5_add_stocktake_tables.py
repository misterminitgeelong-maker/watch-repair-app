"""add_stocktake_tables

Revision ID: a9f1c2d3e4b5
Revises: g2b3c4d5e6f7
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9f1c2d3e4b5"
down_revision: Union[str, None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stockitem",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("item_code", sa.String(), nullable=False),
        sa.Column("group_code", sa.String(), nullable=False, server_default=""),
        sa.Column("group_name", sa.String(), nullable=True),
        sa.Column("item_description", sa.String(), nullable=True),
        sa.Column("description2", sa.String(), nullable=True),
        sa.Column("description3", sa.String(), nullable=True),
        sa.Column("full_description", sa.String(), nullable=True),
        sa.Column("unit_description", sa.String(), nullable=True),
        sa.Column("pack_description", sa.String(), nullable=True),
        sa.Column("pack_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retail_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("system_stock_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stockitem_item_code"), "stockitem", ["item_code"], unique=False)
    op.create_index(op.f("ix_stockitem_group_code"), "stockitem", ["group_code"], unique=False)
    op.create_index(op.f("ix_stockitem_tenant_id"), "stockitem", ["tenant_id"], unique=False)

    op.create_table(
        "stocktakesession",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("group_code_filter", sa.String(), nullable=True),
        sa.Column("group_name_filter", sa.String(), nullable=True),
        sa.Column("search_filter", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stocktakesession_status"), "stocktakesession", ["status"], unique=False)
    op.create_index(op.f("ix_stocktakesession_tenant_id"), "stocktakesession", ["tenant_id"], unique=False)

    op.create_table(
        "stocktakeline",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("stocktake_session_id", sa.Uuid(), nullable=False),
        sa.Column("stock_item_id", sa.Uuid(), nullable=False),
        sa.Column("expected_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("counted_qty", sa.Float(), nullable=True),
        sa.Column("variance_qty", sa.Float(), nullable=True),
        sa.Column("variance_value_cents", sa.Integer(), nullable=True),
        sa.Column("counted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("counted_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["counted_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["stock_item_id"], ["stockitem.id"]),
        sa.ForeignKeyConstraint(["stocktake_session_id"], ["stocktakesession.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stocktakeline_stock_item_id"), "stocktakeline", ["stock_item_id"], unique=False)
    op.create_index(op.f("ix_stocktakeline_stocktake_session_id"), "stocktakeline", ["stocktake_session_id"], unique=False)
    op.create_index(op.f("ix_stocktakeline_tenant_id"), "stocktakeline", ["tenant_id"], unique=False)

    op.create_table(
        "stockadjustment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("stock_item_id", sa.Uuid(), nullable=False),
        sa.Column("stocktake_session_id", sa.Uuid(), nullable=False),
        sa.Column("old_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("variance_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("variance_value_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["stock_item_id"], ["stockitem.id"]),
        sa.ForeignKeyConstraint(["stocktake_session_id"], ["stocktakesession.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stockadjustment_stock_item_id"), "stockadjustment", ["stock_item_id"], unique=False)
    op.create_index(op.f("ix_stockadjustment_stocktake_session_id"), "stockadjustment", ["stocktake_session_id"], unique=False)
    op.create_index(op.f("ix_stockadjustment_tenant_id"), "stockadjustment", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stockadjustment_tenant_id"), table_name="stockadjustment")
    op.drop_index(op.f("ix_stockadjustment_stocktake_session_id"), table_name="stockadjustment")
    op.drop_index(op.f("ix_stockadjustment_stock_item_id"), table_name="stockadjustment")
    op.drop_table("stockadjustment")

    op.drop_index(op.f("ix_stocktakeline_tenant_id"), table_name="stocktakeline")
    op.drop_index(op.f("ix_stocktakeline_stocktake_session_id"), table_name="stocktakeline")
    op.drop_index(op.f("ix_stocktakeline_stock_item_id"), table_name="stocktakeline")
    op.drop_table("stocktakeline")

    op.drop_index(op.f("ix_stocktakesession_tenant_id"), table_name="stocktakesession")
    op.drop_index(op.f("ix_stocktakesession_status"), table_name="stocktakesession")
    op.drop_table("stocktakesession")

    op.drop_index(op.f("ix_stockitem_tenant_id"), table_name="stockitem")
    op.drop_index(op.f("ix_stockitem_group_code"), table_name="stockitem")
    op.drop_index(op.f("ix_stockitem_item_code"), table_name="stockitem")
    op.drop_table("stockitem")