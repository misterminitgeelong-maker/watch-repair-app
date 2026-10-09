"""per-HQ settings table; Minit's HQ seeded to match current behaviour"""
import json
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "20261009a_hq_settings"
down_revision = "20261008b_portal_access_code"
branch_labels = None
depends_on = None

# Mirrors app.hq_settings.MINIT_DEFAULTS (kept inline so the migration never
# changes if app code does).
_MINIT_MODULES = ["kpis", "lead_routing", "mobile_services", "regional_reports"]
_MINIT_SITE_PLANS = ["basic_auto_key", "booking_only"]


def upgrade():
    table = op.create_table(
        "hqsettings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_key", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("logo_url", sa.String(length=2000), nullable=True),
        sa.Column("brand_color", sa.String(length=20), nullable=True),
        sa.Column("modules_json", sa.String(), nullable=False),
        sa.Column("site_plans_json", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hqsettings_parent_account_id", "hqsettings", ["parent_account_id"], unique=True)
    op.create_index("ix_hqsettings_product_key", "hqsettings", ["product_key"])

    # Seed Minit's row: the parent account that holds the mmsupport HQ tenant.
    bind = op.get_bind()
    parent_id = bind.execute(
        sa.text(
            "SELECT s.parent_account_id FROM parentaccountsite s "
            "JOIN tenant t ON t.id = s.tenant_id "
            "WHERE t.slug = 'mmsupport' AND t.is_minit = :yes LIMIT 1"
        ),
        {"yes": True},
    ).scalar()
    if parent_id is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        op.bulk_insert(table, [{
            "id": uuid.uuid4(),
            "parent_account_id": parent_id if isinstance(parent_id, uuid.UUID) else uuid.UUID(str(parent_id)),
            "product_key": "minit",
            "display_name": "Mister Minit",
            "logo_url": None,
            "brand_color": "#E31837",
            "modules_json": json.dumps(_MINIT_MODULES),
            "site_plans_json": json.dumps(_MINIT_SITE_PLANS),
            "created_at": now,
            "updated_at": now,
        }])


def downgrade():
    op.drop_index("ix_hqsettings_product_key", table_name="hqsettings")
    op.drop_index("ix_hqsettings_parent_account_id", table_name="hqsettings")
    op.drop_table("hqsettings")
