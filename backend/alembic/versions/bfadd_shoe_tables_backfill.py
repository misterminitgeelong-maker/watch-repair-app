"""Backfill shoe tables (shoe, shoerepairjob, shoerepairjobitem) that were
created via create_all() but never got an explicit migration, so
\`alembic upgrade head\` against a fresh DB (CI) previously failed at the
first migration that tried to add a column to one of them.

This migration runs IF NOT EXISTS-style via create_table with
batch_alter_table where needed. On databases where the tables already
exist (every production deploy that came up via create_all()), we just
stamp the revision by no-op'ing the create_table calls through a
Postgres-or-SQLite-compatible "check first" helper.

Revision ID: bfadd_shoe_tables
Revises: de9f6ccfac01
Create Date: 2026-04-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "bfadd_shoe_tables"
down_revision: Union[str, None] = "de9f6ccfac01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """True if the table already exists in the live DB.

    Used to make this backfill idempotent against production DBs that
    were created via create_all() and already contain the tables.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table_name)


def upgrade() -> None:
    # --- shoe ---
    if not _table_exists("shoe"):
        op.create_table(
            "shoe",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("customer_id", sa.Uuid(), nullable=False),
            sa.Column("shoe_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("brand", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("color", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("description_notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_shoe_tenant_id"), "shoe", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_shoe_customer_id"), "shoe", ["customer_id"], unique=False)

    # --- shoerepairjob ---
    # Includes customer_account_id because no later migration adds it
    # (the column was only ever present via create_all()). Later migrations
    # DO add: quote_approval_token, quote_approval_token_expires_at,
    # quote_status (c3d4e5f6a7b8), and claimed_by_user_id (20260414_add_claimed_by).
    # Those are deliberately omitted here so the subsequent migrations find
    # the same "absent" state in both fresh-CI and existing-prod databases.
    if not _table_exists("shoerepairjob"):
        op.create_table(
            "shoerepairjob",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("shoe_id", sa.Uuid(), nullable=False),
            sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
            sa.Column("customer_account_id", sa.Uuid(), nullable=True),
            sa.Column("job_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("priority", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="normal"),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="awaiting_go_ahead"),
            sa.Column("salesperson", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("collection_date", sa.Date(), nullable=True),
            sa.Column("deposit_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["shoe_id"], ["shoe.id"]),
            sa.ForeignKeyConstraint(["assigned_user_id"], ["user.id"]),
            # customer_account_id is nullable and has no FK here — the
            # customeraccount table is created by a LATER migration
            # (b1c4d6e8f9a2). Production DBs that used create_all() also
            # don't declare this FK, so matching that behaviour here keeps
            # the two environments consistent.
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_shoerepairjob_tenant_id"), "shoerepairjob", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_shoerepairjob_shoe_id"), "shoerepairjob", ["shoe_id"], unique=False)
        op.create_index(op.f("ix_shoerepairjob_customer_account_id"), "shoerepairjob", ["customer_account_id"], unique=False)
        op.create_index(op.f("ix_shoerepairjob_job_number"), "shoerepairjob", ["job_number"], unique=False)
        op.create_index(op.f("ix_shoerepairjob_status_token"), "shoerepairjob", ["status_token"], unique=True)

    # --- shoerepairjobitem ---
    if not _table_exists("shoerepairjobitem"):
        op.create_table(
            "shoerepairjobitem",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=False),
            sa.Column("catalogue_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("catalogue_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("item_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("pricing_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("unit_price_cents", sa.Integer(), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=False, server_default="1"),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["shoe_repair_job_id"], ["shoerepairjob.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_shoerepairjobitem_tenant_id"), "shoerepairjobitem", ["tenant_id"], unique=False)
        op.create_index(
            op.f("ix_shoerepairjobitem_shoe_repair_job_id"),
            "shoerepairjobitem",
            ["shoe_repair_job_id"],
            unique=False,
        )


def downgrade() -> None:
    # Best-effort: only drop if present (mirrors the upgrade's idempotency).
    if _table_exists("shoerepairjobitem"):
        op.drop_index(op.f("ix_shoerepairjobitem_shoe_repair_job_id"), table_name="shoerepairjobitem")
        op.drop_index(op.f("ix_shoerepairjobitem_tenant_id"), table_name="shoerepairjobitem")
        op.drop_table("shoerepairjobitem")
    if _table_exists("shoerepairjob"):
        op.drop_index(op.f("ix_shoerepairjob_status_token"), table_name="shoerepairjob")
        op.drop_index(op.f("ix_shoerepairjob_job_number"), table_name="shoerepairjob")
        op.drop_index(op.f("ix_shoerepairjob_shoe_id"), table_name="shoerepairjob")
        op.drop_index(op.f("ix_shoerepairjob_tenant_id"), table_name="shoerepairjob")
        op.drop_table("shoerepairjob")
    if _table_exists("shoe"):
        op.drop_index(op.f("ix_shoe_customer_id"), table_name="shoe")
        op.drop_index(op.f("ix_shoe_tenant_id"), table_name="shoe")
        op.drop_table("shoe")
