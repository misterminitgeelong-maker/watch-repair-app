"""add mobile lead ingest and suburb routing for parent accounts

Revision ID: r8n9m0o1b2l3
Revises: q0a1b2c3d4e5
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r8n9m0o1b2l3"
down_revision: Union[str, None] = "q0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parentaccount", sa.Column("mobile_lead_ingest_public_id", sa.Uuid(), nullable=True))
    op.add_column("parentaccount", sa.Column("mobile_lead_webhook_secret_hash", sa.String(), nullable=True))
    op.add_column("parentaccount", sa.Column("mobile_lead_default_tenant_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_parentaccount_mobile_lead_ingest_public_id"),
        "parentaccount",
        ["mobile_lead_ingest_public_id"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_parentaccount_mobile_lead_default_tenant_id_tenant",
        "parentaccount",
        "tenant",
        ["mobile_lead_default_tenant_id"],
        ["id"],
    )

    op.create_table(
        "mobilesuburbroute",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("state_code", sa.String(length=8), nullable=False),
        sa.Column("suburb_normalized", sa.String(length=200), nullable=False),
        sa.Column("target_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["target_tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "state_code", "suburb_normalized", name="uq_mobile_suburb_route_parent_state_suburb"),
    )
    op.create_index(op.f("ix_mobilesuburbroute_parent_account_id"), "mobilesuburbroute", ["parent_account_id"], unique=False)
    op.create_index(op.f("ix_mobilesuburbroute_state_code"), "mobilesuburbroute", ["state_code"], unique=False)
    op.create_index(op.f("ix_mobilesuburbroute_suburb_normalized"), "mobilesuburbroute", ["suburb_normalized"], unique=False)
    op.create_index(op.f("ix_mobilesuburbroute_target_tenant_id"), "mobilesuburbroute", ["target_tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mobilesuburbroute_target_tenant_id"), table_name="mobilesuburbroute")
    op.drop_index(op.f("ix_mobilesuburbroute_suburb_normalized"), table_name="mobilesuburbroute")
    op.drop_index(op.f("ix_mobilesuburbroute_state_code"), table_name="mobilesuburbroute")
    op.drop_index(op.f("ix_mobilesuburbroute_parent_account_id"), table_name="mobilesuburbroute")
    op.drop_table("mobilesuburbroute")

    op.drop_constraint("fk_parentaccount_mobile_lead_default_tenant_id_tenant", "parentaccount", type_="foreignkey")
    op.drop_index(op.f("ix_parentaccount_mobile_lead_ingest_public_id"), table_name="parentaccount")
    op.drop_column("parentaccount", "mobile_lead_default_tenant_id")
    op.drop_column("parentaccount", "mobile_lead_webhook_secret_hash")
    op.drop_column("parentaccount", "mobile_lead_ingest_public_id")
