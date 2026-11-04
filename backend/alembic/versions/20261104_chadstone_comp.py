"""Make the owner's Chadstone Pro complimentary, as approved by Sam.

Only the exact existing Minit shop entitlement is corrected. No grants are added.
Downgrade deliberately preserves this commercial decision instead of reintroducing
a charge when rolling application code back.
"""
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision = "20261104_chadstone_comp"
down_revision = "20261104_site_entitlements"
branch_labels = None
depends_on = None

PARENT_ID = UUID("f3bb646e-b7f5-44e0-9f7d-8ad2c347dd87")
SITE_ID = UUID("8d03dcd6-eee4-4a76-afbb-4068e0b0b9b4")
TENANT_ID = UUID("214f3906-466c-4ee1-b797-e4571eb00f36")


def upgrade():
    bind = op.get_bind()
    ent = sa.table("siteentitlement",
        sa.column("id", sa.Uuid()), sa.column("site_id", sa.Uuid()),
        sa.column("parent_account_id", sa.Uuid()), sa.column("kind", sa.String()),
        sa.column("payer", sa.String()), sa.column("ended_at", sa.DateTime()))
    events = sa.table("parentaccounteventlog",
        sa.column("id", sa.Uuid()), sa.column("parent_account_id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()), sa.column("event_type", sa.String()),
        sa.column("event_summary", sa.String()), sa.column("details_json", sa.String()),
        sa.column("created_at", sa.DateTime()))
    target = sa.and_(ent.c.parent_account_id == PARENT_ID, ent.c.site_id == SITE_ID,
                     ent.c.kind == "pro", ent.c.payer == "tenant", ent.c.ended_at.is_(None))
    ids = list(bind.execute(sa.select(ent.c.id).where(target)).scalars())
    if not ids:
        return
    bind.execute(ent.update().where(target).values(payer="comp"))
    bind.execute(events.insert().values(
        id=uuid4(), parent_account_id=PARENT_ID, tenant_id=TENANT_ID,
        event_type="entitlement_payer_corrected",
        event_summary="Chadstone Pro made complimentary: software owner's shop (Sam approved)",
        details_json=json.dumps({"migration": revision, "entitlement_ids": [str(i) for i in ids],
                                 "site_id": str(SITE_ID), "kind": "pro",
                                 "before": {"payer": "tenant"}, "after": {"payer": "comp"},
                                 "reason": "Owner's software and shop; complimentary Pro"}),
        created_at=datetime.now(timezone.utc)))


def downgrade():
    # A schema rollback is not authorization to start charging the owner's shop.
    pass
