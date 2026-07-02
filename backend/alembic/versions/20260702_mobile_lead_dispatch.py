"""add mobile lead dispatch cascade + parent escalation settings

Revision ID: 20260702_mobile_lead_dispatch
Revises: 20260702_inbound_email
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260702_mobile_lead_dispatch"
down_revision: Union[str, None] = "20260702_inbound_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parentaccount",
        sa.Column("mobile_lead_escalation_tenant_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "parentaccount",
        sa.Column("mobile_lead_offer_timeout_minutes", sa.Integer(), nullable=False, server_default="30"),
    )
    op.add_column(
        "parentaccount",
        sa.Column("mobile_lead_max_operator_offers", sa.Integer(), nullable=False, server_default="3"),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_parentaccount_mobile_lead_escalation_tenant_id_tenant",
            "parentaccount",
            "tenant",
            ["mobile_lead_escalation_tenant_id"],
            ["id"],
        )

    op.create_table(
        "mobileleaddispatch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("suburb", sa.String(length=200), nullable=False),
        sa.Column("state_code", sa.String(length=8), nullable=False),
        sa.Column("suburb_normalized", sa.String(length=200), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("candidate_operator_ids_json", sa.String(), nullable=False),
        sa.Column("current_offer_index", sa.Integer(), nullable=False),
        sa.Column("current_operator_tenant_id", sa.Uuid(), nullable=True),
        sa.Column("offer_expires_at", sa.DateTime(), nullable=True),
        sa.Column("auto_key_job_id", sa.Uuid(), nullable=True),
        sa.Column("offer_timeout_minutes", sa.Integer(), nullable=False),
        sa.Column("max_operator_offers", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["current_operator_tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["auto_key_job_id"], ["autokeyjob.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_parent_account_id"),
        "mobileleaddispatch",
        ["parent_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_status"),
        "mobileleaddispatch",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_state_code"),
        "mobileleaddispatch",
        ["state_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_suburb_normalized"),
        "mobileleaddispatch",
        ["suburb_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_current_operator_tenant_id"),
        "mobileleaddispatch",
        ["current_operator_tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_offer_expires_at"),
        "mobileleaddispatch",
        ["offer_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mobileleaddispatch_auto_key_job_id"),
        "mobileleaddispatch",
        ["auto_key_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mobileleaddispatch_auto_key_job_id"), table_name="mobileleaddispatch")
    op.drop_index(op.f("ix_mobileleaddispatch_offer_expires_at"), table_name="mobileleaddispatch")
    op.drop_index(op.f("ix_mobileleaddispatch_current_operator_tenant_id"), table_name="mobileleaddispatch")
    op.drop_index(op.f("ix_mobileleaddispatch_suburb_normalized"), table_name="mobileleaddispatch")
    op.drop_index(op.f("ix_mobileleaddispatch_state_code"), table_name="mobileleaddispatch")
    op.drop_index(op.f("ix_mobileleaddispatch_status"), table_name="mobileleaddispatch")
    op.drop_index(op.f("ix_mobileleaddispatch_parent_account_id"), table_name="mobileleaddispatch")
    op.drop_table("mobileleaddispatch")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_parentaccount_mobile_lead_escalation_tenant_id_tenant",
            "parentaccount",
            type_="foreignkey",
        )
    op.drop_column("parentaccount", "mobile_lead_max_operator_offers")
    op.drop_column("parentaccount", "mobile_lead_offer_timeout_minutes")
    op.drop_column("parentaccount", "mobile_lead_escalation_tenant_id")
