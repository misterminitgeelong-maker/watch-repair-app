"""add VSWT comparison cockpit persistence

Revision ID: 20260916_vswt_cockpit
Revises: 20260916a_parent_network
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_vswt_cockpit"
down_revision: Union[str, None] = "20260916a_parent_network"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vswt_report_target",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_number", sa.String(length=10), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "shop_number", "metric_key", name="uq_vswt_target_tenant_shop_metric"),
    )
    op.create_index(op.f("ix_vswt_report_target_tenant_id"), "vswt_report_target", ["tenant_id"])
    op.create_index(op.f("ix_vswt_report_target_shop_number"), "vswt_report_target", ["shop_number"])

    op.create_table(
        "vswt_week_annotation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_number", sa.String(length=10), nullable=False),
        sa.Column("week_seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "shop_number", "week_seq", name="uq_vswt_annotation_tenant_shop_week"),
    )
    op.create_index(op.f("ix_vswt_week_annotation_tenant_id"), "vswt_week_annotation", ["tenant_id"])
    op.create_index(op.f("ix_vswt_week_annotation_shop_number"), "vswt_week_annotation", ["shop_number"])
    op.create_index(op.f("ix_vswt_week_annotation_week_seq"), "vswt_week_annotation", ["week_seq"])

    with op.batch_alter_table("usernotificationpreference") as batch:
        batch.add_column(sa.Column("email_weekly_regional_report", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("last_weekly_regional_report_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usernotificationpreference") as batch:
        batch.drop_column("last_weekly_regional_report_sent_at")
        batch.drop_column("email_weekly_regional_report")
    op.drop_index(op.f("ix_vswt_week_annotation_week_seq"), table_name="vswt_week_annotation")
    op.drop_index(op.f("ix_vswt_week_annotation_shop_number"), table_name="vswt_week_annotation")
    op.drop_index(op.f("ix_vswt_week_annotation_tenant_id"), table_name="vswt_week_annotation")
    op.drop_table("vswt_week_annotation")
    op.drop_index(op.f("ix_vswt_report_target_shop_number"), table_name="vswt_report_target")
    op.drop_index(op.f("ix_vswt_report_target_tenant_id"), table_name="vswt_report_target")
    op.drop_table("vswt_report_target")
