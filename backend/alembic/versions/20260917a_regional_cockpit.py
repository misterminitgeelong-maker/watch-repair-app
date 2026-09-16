"""regional cockpit: region-scoped HQ roles, region week notes, baseline exclusions

* parentaccountuser.region_id — an hq_viewer grant pinned to one region is a
  regional manager: they see that region's sites and cockpit, nothing else.
* region.weekly_report_opt_in / last_weekly_report_sent_at — the Monday email
  to the regional manager.
* vswt_week_annotation.exclude_from_baselines — a shop's own bad week can be
  kept out of its rolling baselines.
* vswt_region_week_annotation — one note for a whole region's week, shown on
  every shop in it and optionally excluded from every shop's baselines.

Revision ID: 20260917a_regional_cockpit
Revises: 20260916_vswt_cockpit
Create Date: 2026-09-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260917a_regional_cockpit"
down_revision: Union[str, None] = "20260916_vswt_cockpit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "parentaccountuser" in tables and "region_id" not in _columns(inspector, "parentaccountuser"):
        with op.batch_alter_table("parentaccountuser") as batch:
            batch.add_column(sa.Column("region_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_parentaccountuser_region_id_region", "region", ["region_id"], ["id"])
        op.create_index(op.f("ix_parentaccountuser_region_id"), "parentaccountuser", ["region_id"], unique=False)

    if "region" in tables:
        existing = _columns(inspector, "region")
        with op.batch_alter_table("region") as batch:
            if "weekly_report_opt_in" not in existing:
                batch.add_column(
                    sa.Column("weekly_report_opt_in", sa.Boolean(), nullable=False, server_default=sa.false())
                )
            if "last_weekly_report_sent_at" not in existing:
                batch.add_column(sa.Column("last_weekly_report_sent_at", sa.DateTime(), nullable=True))

    if "vswt_week_annotation" in tables and "exclude_from_baselines" not in _columns(inspector, "vswt_week_annotation"):
        with op.batch_alter_table("vswt_week_annotation") as batch:
            batch.add_column(
                sa.Column("exclude_from_baselines", sa.Boolean(), nullable=False, server_default=sa.false())
            )

    if "vswt_region_week_annotation" not in tables:
        op.create_table(
            "vswt_region_week_annotation",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("parent_account_id", sa.Uuid(), nullable=False),
            sa.Column("region_id", sa.Uuid(), nullable=False),
            sa.Column("week_seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("note", sa.String(length=500), nullable=False),
            sa.Column("exclude_from_baselines", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
            sa.ForeignKeyConstraint(["region_id"], ["region.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region_id", "week_seq", name="uq_vswt_region_annotation_region_week"),
        )
        op.create_index(
            op.f("ix_vswt_region_week_annotation_parent_account_id"),
            "vswt_region_week_annotation",
            ["parent_account_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_vswt_region_week_annotation_region_id"), "vswt_region_week_annotation", ["region_id"], unique=False
        )
        op.create_index(
            op.f("ix_vswt_region_week_annotation_week_seq"), "vswt_region_week_annotation", ["week_seq"], unique=False
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "vswt_region_week_annotation" in tables:
        op.drop_table("vswt_region_week_annotation")

    if "vswt_week_annotation" in tables and "exclude_from_baselines" in _columns(inspector, "vswt_week_annotation"):
        with op.batch_alter_table("vswt_week_annotation") as batch:
            batch.drop_column("exclude_from_baselines")

    if "region" in tables:
        existing = _columns(inspector, "region")
        with op.batch_alter_table("region") as batch:
            if "last_weekly_report_sent_at" in existing:
                batch.drop_column("last_weekly_report_sent_at")
            if "weekly_report_opt_in" in existing:
                batch.drop_column("weekly_report_opt_in")

    if "parentaccountuser" in tables and "region_id" in _columns(inspector, "parentaccountuser"):
        op.drop_index(op.f("ix_parentaccountuser_region_id"), table_name="parentaccountuser")
        with op.batch_alter_table("parentaccountuser") as batch:
            batch.drop_constraint("fk_parentaccountuser_region_id_region", type_="foreignkey")
            batch.drop_column("region_id")
