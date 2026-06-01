"""QoL: notification prefs, webhooks, API keys, portal notify flags, custom fields

Revision ID: 20260602_qol_features
Revises: 20260601_mobile_services_pricing
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_qol_features"
down_revision = "20260601_mobile_services_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usernotificationpreference",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("email_quote_approved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_invoice_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_sms_reply", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_daily_digest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_usernotifpref_tenant_user"),
    )
    op.create_table(
        "tenantapikey",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tenantwebhooksubscription",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("event_types", sa.String(512), nullable=False),
        sa.Column("secret", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("portalsession") as batch:
        batch.add_column(sa.Column("status_notify_email", sa.Boolean(), server_default=sa.false()))
        batch.add_column(sa.Column("status_notify_sms", sa.Boolean(), server_default=sa.false()))
    for table in ("repairjob", "shoerepairjob", "autokeyjob"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("custom_fields_json", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in ("autokeyjob", "shoerepairjob", "repairjob"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("custom_fields_json")
    with op.batch_alter_table("portalsession") as batch:
        batch.drop_column("status_notify_sms")
        batch.drop_column("status_notify_email")
    op.drop_table("tenantwebhooksubscription")
    op.drop_table("tenantapikey")
    op.drop_table("usernotificationpreference")
