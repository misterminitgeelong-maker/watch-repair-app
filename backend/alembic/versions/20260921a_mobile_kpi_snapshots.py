"""add mobile KPI daily/weekly snapshots + HQ recipient flag

Revision ID: 20260921a_mobile_kpi_snapshots
Revises: 20260917c_revenue_followup
Create Date: 2026-09-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260921a_mobile_kpi_snapshots"
down_revision: Union[str, None] = "20260917c_revenue_followup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_kpi_daily_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("operator_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("compiled_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["operator_tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_account_id",
            "operator_tenant_id",
            "trade_date",
            name="uq_mobile_kpi_daily_parent_op_date",
        ),
    )
    op.create_index(
        op.f("ix_mobile_kpi_daily_snapshot_parent_account_id"),
        "mobile_kpi_daily_snapshot",
        ["parent_account_id"],
    )
    op.create_index(
        op.f("ix_mobile_kpi_daily_snapshot_operator_tenant_id"),
        "mobile_kpi_daily_snapshot",
        ["operator_tenant_id"],
    )
    op.create_index(
        op.f("ix_mobile_kpi_daily_snapshot_trade_date"),
        "mobile_kpi_daily_snapshot",
        ["trade_date"],
    )

    op.create_table(
        "mobile_kpi_weekly_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("week_start_ymd", sa.String(length=10), nullable=False),
        sa.Column("week_end_ymd", sa.String(length=10), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("csv_sha256", sa.String(length=64), nullable=True),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compiled_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "week_start_ymd", name="uq_mobile_kpi_weekly_parent_week"),
    )
    op.create_index(
        op.f("ix_mobile_kpi_weekly_snapshot_parent_account_id"),
        "mobile_kpi_weekly_snapshot",
        ["parent_account_id"],
    )
    op.create_index(
        op.f("ix_mobile_kpi_weekly_snapshot_week_start_ymd"),
        "mobile_kpi_weekly_snapshot",
        ["week_start_ymd"],
    )

    with op.batch_alter_table("parentaccountuser") as batch:
        batch.add_column(
            sa.Column(
                "email_mobile_kpi_report",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("parentaccountuser") as batch:
        batch.drop_column("email_mobile_kpi_report")
    op.drop_index(op.f("ix_mobile_kpi_weekly_snapshot_week_start_ymd"), table_name="mobile_kpi_weekly_snapshot")
    op.drop_index(op.f("ix_mobile_kpi_weekly_snapshot_parent_account_id"), table_name="mobile_kpi_weekly_snapshot")
    op.drop_table("mobile_kpi_weekly_snapshot")
    op.drop_index(op.f("ix_mobile_kpi_daily_snapshot_trade_date"), table_name="mobile_kpi_daily_snapshot")
    op.drop_index(op.f("ix_mobile_kpi_daily_snapshot_operator_tenant_id"), table_name="mobile_kpi_daily_snapshot")
    op.drop_index(op.f("ix_mobile_kpi_daily_snapshot_parent_account_id"), table_name="mobile_kpi_daily_snapshot")
    op.drop_table("mobile_kpi_daily_snapshot")
