"""add vswt_weekly_shop_metric table

Revision ID: 20260819_vswt_weekly_metrics
Revises: 20260818_shoe_job_counter
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_vswt_weekly_metrics"
down_revision: Union[str, None] = "20260818_shoe_job_counter"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FLOAT_METRIC_COLUMNS = [
    "budget_sales_target",
    "sales_ty", "sales_ly", "sales_pct_change",
    "customer_ty", "customer_ly", "customer_pct_change",
    "jobs_ty", "jobs_ly", "jobs_pct_change",
    "jobs_per_100", "keys_per_100", "engrave_per_100", "auto_remote_per_100",
    "sharpen_per_100", "shoe_per_100", "jewellery_repairs_per_100",
    "shoe_sales_ty", "shoe_jobs_ty",
    "key_sales_ty", "key_jobs_ty",
    "engrave_sales_ty", "engrave_jobs_ty",
    "watch_sales_ty", "watch_jobs_ty",
    "merch_sales_ty", "merch_jobs_ty",
    "auto_key_jobs_ty", "gg_remotes_jobs_ty",
    "watch_batt_fitted_jobs_ty", "watch_band_jobs_ty",
    "third_party_watch_repair_jobs_ty", "watch_repair_jobs_ty",
    "sharpening_jobs_ty", "jewellery_serv_jobs_ty",
]


def upgrade() -> None:
    op.create_table(
        "vswt_weekly_shop_metric",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("week_seq", sa.Integer(), nullable=False),
        sa.Column("shop_number", sa.String(length=10), nullable=False),
        sa.Column("shop_name", sa.String(), nullable=True),
        sa.Column("area_num", sa.String(), nullable=True),
        sa.Column("area_name", sa.String(), nullable=True),
        sa.Column("store_format", sa.String(), nullable=True),
        sa.Column("comp_status", sa.String(), nullable=True),
        *[sa.Column(name, sa.Float(), nullable=True) for name in _FLOAT_METRIC_COLUMNS],
        sa.Column("source_filename", sa.String(), nullable=True),
        sa.Column("uploaded_by_tenant_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("week_seq", "shop_number", name="uq_vswtweeklyshopmetric_week_shop"),
    )
    op.create_index(
        op.f("ix_vswt_weekly_shop_metric_week_seq"), "vswt_weekly_shop_metric", ["week_seq"]
    )
    op.create_index(
        op.f("ix_vswt_weekly_shop_metric_shop_number"), "vswt_weekly_shop_metric", ["shop_number"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vswt_weekly_shop_metric_shop_number"), table_name="vswt_weekly_shop_metric")
    op.drop_index(op.f("ix_vswt_weekly_shop_metric_week_seq"), table_name="vswt_weekly_shop_metric")
    op.drop_table("vswt_weekly_shop_metric")
