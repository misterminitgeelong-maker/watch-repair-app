"""support-access consent and ID capture

Adds tenant.support_access_until
(owner's time-boxed consent for HQ support access), tenant.require_id_capture,
tenanteventlog.support_actor_user_id (tags rows written in a support session),
and the autokeyidcapture / autokeyidaccesslog tables.

Revision ID: 20261103_operator_sms_consent_id
Revises: 20261101_engraving_events
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_operator_sms_consent_id"
down_revision: Union[str, None] = "20261101_engraving_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("support_access_until", sa.DateTime(), nullable=True))
    op.add_column(
        "tenant",
        sa.Column("require_id_capture", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    with op.batch_alter_table("tenanteventlog") as batch:
        batch.add_column(sa.Column("support_actor_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_tenanteventlog_support_actor_user", "user", ["support_actor_user_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_tenanteventlog_support_actor_user_id", "tenanteventlog", ["support_actor_user_id"])

    op.create_table(
        "autokeyidcapture",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auto_key_job_id", sa.Uuid(), sa.ForeignKey("autokeyjob.id"), nullable=False),
        sa.Column("id_type", sa.String(length=32), nullable=False),
        sa.Column("id_number_encrypted", sa.String(), nullable=False),
        sa.Column("id_number_last4", sa.String(length=8), nullable=False),
        sa.Column("id_issuer", sa.String(length=64), nullable=True),
        sa.Column("name_on_id", sa.String(length=200), nullable=False),
        sa.Column("proof_of_ownership_type", sa.String(length=32), nullable=False),
        sa.Column("proof_of_ownership_notes", sa.String(length=500), nullable=True),
        sa.Column("consent_text_version", sa.String(length=32), nullable=False),
        sa.Column("consent_given_at", sa.DateTime(), nullable=False),
        sa.Column("consent_method", sa.String(length=16), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("auto_key_job_id", name="uq_autokeyidcapture_job"),
    )
    op.create_index("ix_autokeyidcapture_tenant_id", "autokeyidcapture", ["tenant_id"])
    op.create_index("ix_autokeyidcapture_auto_key_job_id", "autokeyidcapture", ["auto_key_job_id"])

    op.create_table(
        "autokeyidaccesslog",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auto_key_job_id", sa.Uuid(), sa.ForeignKey("autokeyjob.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("support_actor_user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_autokeyidaccesslog_tenant_id", "autokeyidaccesslog", ["tenant_id"])
    op.create_index("ix_autokeyidaccesslog_auto_key_job_id", "autokeyidaccesslog", ["auto_key_job_id"])
    op.create_index("ix_autokeyidaccesslog_created_at", "autokeyidaccesslog", ["created_at"])


def downgrade() -> None:
    op.drop_table("autokeyidaccesslog")
    op.drop_table("autokeyidcapture")
    op.drop_index("ix_tenanteventlog_support_actor_user_id", table_name="tenanteventlog")
    with op.batch_alter_table("tenanteventlog") as batch:
        batch.drop_constraint("fk_tenanteventlog_support_actor_user", type_="foreignkey")
        batch.drop_column("support_actor_user_id")
    op.drop_column("tenant", "require_id_capture")
    op.drop_column("tenant", "support_access_until")
