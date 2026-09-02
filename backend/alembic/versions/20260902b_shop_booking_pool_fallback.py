"""shop mobile booking: 15-min offer timeout + fallback into the shared Dispatch Pool

Revision ID: 20260902b_shop_booking_pool
Revises: 20260902_mobile_lead_accept
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902b_shop_booking_pool"
down_revision: Union[str, None] = "20260902_mobile_lead_accept"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shopmobilebookingrequest",
        sa.Column("offer_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "shopmobilebookingrequest",
        sa.Column("job_lat", sa.Float(), nullable=True),
    )
    op.add_column(
        "shopmobilebookingrequest",
        sa.Column("job_lng", sa.Float(), nullable=True),
    )
    op.add_column(
        "shopmobilebookingrequest",
        sa.Column("pool_intake_job_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_shopmobilebookingrequest_offer_expires_at"),
        "shopmobilebookingrequest",
        ["offer_expires_at"],
        unique=False,
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_shopmobilebookingrequest_pool_intake_job_id_intakejob",
            "shopmobilebookingrequest",
            "intakejob",
            ["pool_intake_job_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_shopmobilebookingrequest_pool_intake_job_id_intakejob",
            "shopmobilebookingrequest",
            type_="foreignkey",
        )
    op.drop_index(
        op.f("ix_shopmobilebookingrequest_offer_expires_at"),
        table_name="shopmobilebookingrequest",
    )
    op.drop_column("shopmobilebookingrequest", "pool_intake_job_id")
    op.drop_column("shopmobilebookingrequest", "job_lng")
    op.drop_column("shopmobilebookingrequest", "job_lat")
    op.drop_column("shopmobilebookingrequest", "offer_expires_at")
