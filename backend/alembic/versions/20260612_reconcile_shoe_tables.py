"""Reconcile shoe tables with models.

The shoe feature's base tables (shoe, shoerepairjob, shoerepairjobitem,
shoejobstatushistory) and smslog.shoe_repair_job_id were historically created
by SQLModel create_all at runtime, never by a migration — so a fresh database
built with `alembic upgrade head` was missing all of them (and the guarded
shoe migrations earlier in the chain silently skipped their ALTERs).

Every operation here is existence-guarded: on databases that already have the
tables (production) this is a no-op. scripts/check_migrations.py verifies the
chain stays equivalent to the models from now on.

Revision ID: 20260612_reconcile_shoe_tables
Revises: 20260611_third_party_statuses
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "20260612_reconcile_shoe_tables"
down_revision: Union[str, None] = "20260611_third_party_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def _has_column(table: str, column: str) -> bool:
    return any(c["name"] == column for c in _insp().get_columns(table))


def upgrade() -> None:
    if not _has_table("shoe"):
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
        op.create_index(op.f("ix_shoe_tenant_id"), "shoe", ["tenant_id"])
        op.create_index(op.f("ix_shoe_customer_id"), "shoe", ["customer_id"])

    if not _has_table("shoerepairjob"):
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
            sa.Column("priority", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("salesperson", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("collection_date", sa.Date(), nullable=True),
            sa.Column("deposit_cents", sa.Integer(), nullable=False),
            sa.Column("cost_cents", sa.Integer(), nullable=False),
            sa.Column("quote_approval_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("quote_approval_token_expires_at", sa.DateTime(), nullable=True),
            sa.Column("quote_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("custom_fields_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["shoe_id"], ["shoe.id"]),
            sa.ForeignKeyConstraint(["assigned_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["customer_account_id"], ["customeraccount.id"]),
            sa.ForeignKeyConstraint(["claimed_by_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_shoerepairjob_tenant_id"), "shoerepairjob", ["tenant_id"])
        op.create_index(op.f("ix_shoerepairjob_shoe_id"), "shoerepairjob", ["shoe_id"])
        op.create_index(op.f("ix_shoerepairjob_customer_account_id"), "shoerepairjob", ["customer_account_id"])
        op.create_index(op.f("ix_shoerepairjob_job_number"), "shoerepairjob", ["job_number"])
        op.create_index(op.f("ix_shoerepairjob_status_token"), "shoerepairjob", ["status_token"], unique=True)
        op.create_index(
            op.f("ix_shoerepairjob_quote_approval_token"), "shoerepairjob", ["quote_approval_token"], unique=True
        )
        op.create_index(
            op.f("ix_shoerepairjob_quote_approval_token_expires_at"),
            "shoerepairjob",
            ["quote_approval_token_expires_at"],
        )

    if not _has_table("shoerepairjobitem"):
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
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["shoe_repair_job_id"], ["shoerepairjob.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_shoerepairjobitem_tenant_id"), "shoerepairjobitem", ["tenant_id"])
        op.create_index(op.f("ix_shoerepairjobitem_shoe_repair_job_id"), "shoerepairjobitem", ["shoe_repair_job_id"])

    if not _has_table("shoejobstatushistory"):
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
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["shoe_repair_job_id"], ["shoerepairjob.id"]),
            sa.ForeignKeyConstraint(["changed_by_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_shoejobstatushistory_tenant_id"), "shoejobstatushistory", ["tenant_id"])
        op.create_index(
            op.f("ix_shoejobstatushistory_shoe_repair_job_id"), "shoejobstatushistory", ["shoe_repair_job_id"]
        )

    if _has_table("smslog") and not _has_column("smslog", "shoe_repair_job_id"):
        with op.batch_alter_table("smslog") as batch_op:
            batch_op.add_column(sa.Column("shoe_repair_job_id", sa.Uuid(), nullable=True))
        op.create_index(op.f("ix_smslog_shoe_repair_job_id"), "smslog", ["shoe_repair_job_id"])


def downgrade() -> None:
    # Reconcile migration — tables may pre-date this revision on production,
    # so downgrade intentionally leaves them in place.
    pass
