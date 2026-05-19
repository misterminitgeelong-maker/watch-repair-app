"""Shop mobile operator booking requests and AutoKeyJob referral columns.

Revision ID: 20260519_shop_mobile_booking
Revises: 20260519_xero
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = "20260519_shop_mobile_booking"
down_revision = "20260519_xero"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopmobilebookingrequest",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("requesting_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("target_operator_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("customer_name", sa.String(length=300), nullable=False),
        sa.Column("phone", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("vehicle_make", sa.String(length=120), nullable=True),
        sa.Column("vehicle_model", sa.String(length=120), nullable=True),
        sa.Column("registration_plate", sa.String(length=32), nullable=True),
        sa.Column("visit_location_type", sa.String(length=32), nullable=False),
        sa.Column("job_address", sa.String(length=2000), nullable=False),
        sa.Column("preferred_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_type", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("operator_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_response_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decline_reason", sa.String(length=2000), nullable=True),
        sa.Column("resulting_auto_key_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["operator_response_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["requesting_tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["resulting_auto_key_job_id"], ["autokeyjob.id"]),
        sa.ForeignKeyConstraint(["target_operator_tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resulting_auto_key_job_id"),
    )
    op.create_index(
        "ix_shopmobilebookingrequest_requesting_tenant_id",
        "shopmobilebookingrequest",
        ["requesting_tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_shopmobilebookingrequest_target_operator_tenant_id",
        "shopmobilebookingrequest",
        ["target_operator_tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_shopmobilebookingrequest_requesting_tenant_id_status",
        "shopmobilebookingrequest",
        ["requesting_tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_shopmobilebookingrequest_target_operator_tenant_id_status",
        "shopmobilebookingrequest",
        ["target_operator_tenant_id", "status"],
        unique=False,
    )

    op.add_column("autokeyjob", sa.Column("referring_shop_tenant_id", sa.Uuid(), nullable=True))
    op.add_column("autokeyjob", sa.Column("shop_mobile_booking_request_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_autokeyjob_referring_shop_tenant_id",
        "autokeyjob",
        ["referring_shop_tenant_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_autokeyjob_referring_shop_tenant_id_tenant",
        "autokeyjob",
        "tenant",
        ["referring_shop_tenant_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_autokeyjob_shop_mobile_booking_request_id",
        "autokeyjob",
        "shopmobilebookingrequest",
        ["shop_mobile_booking_request_id"],
        ["id"],
    )
    op.create_index(
        "ix_autokeyjob_shop_mobile_booking_request_id",
        "autokeyjob",
        ["shop_mobile_booking_request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_autokeyjob_shop_mobile_booking_request_id", table_name="autokeyjob")
    op.drop_constraint("fk_autokeyjob_shop_mobile_booking_request_id", "autokeyjob", type_="foreignkey")
    op.drop_constraint("fk_autokeyjob_referring_shop_tenant_id_tenant", "autokeyjob", type_="foreignkey")
    op.drop_index("ix_autokeyjob_referring_shop_tenant_id", table_name="autokeyjob")
    op.drop_column("autokeyjob", "shop_mobile_booking_request_id")
    op.drop_column("autokeyjob", "referring_shop_tenant_id")

    op.drop_index("ix_shopmobilebookingrequest_target_operator_tenant_id_status", table_name="shopmobilebookingrequest")
    op.drop_index("ix_shopmobilebookingrequest_requesting_tenant_id_status", table_name="shopmobilebookingrequest")
    op.drop_index("ix_shopmobilebookingrequest_target_operator_tenant_id", table_name="shopmobilebookingrequest")
    op.drop_index("ix_shopmobilebookingrequest_requesting_tenant_id", table_name="shopmobilebookingrequest")
    op.drop_table("shopmobilebookingrequest")
