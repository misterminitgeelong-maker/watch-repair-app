"""The approved payer repair is narrow, auditable and safe to repeat."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa


def test_chadstone_payer_repair(monkeypatch):
    path = Path(__file__).parents[1] / "alembic/versions/20261104_chadstone_comp.py"
    spec = importlib.util.spec_from_file_location("chadstone_comp_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    ent = sa.Table("siteentitlement", metadata,
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("site_id", sa.Uuid()),
        sa.Column("parent_account_id", sa.Uuid()), sa.Column("kind", sa.String()),
        sa.Column("payer", sa.String()), sa.Column("ended_at", sa.DateTime()))
    events = sa.Table("parentaccounteventlog", metadata,
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("parent_account_id", sa.Uuid()),
        sa.Column("tenant_id", sa.Uuid()), sa.Column("event_type", sa.String()),
        sa.Column("event_summary", sa.String()), sa.Column("details_json", sa.String()),
        sa.Column("created_at", sa.DateTime()))
    metadata.create_all(engine)
    target_id = uuid4()
    base = dict(site_id=migration.SITE_ID, parent_account_id=migration.PARENT_ID,
                kind="pro", payer="tenant", ended_at=None)
    controls = [
        dict(base, id=uuid4(), site_id=uuid4()),
        dict(base, id=uuid4(), parent_account_id=uuid4()),
        dict(base, id=uuid4(), kind="booking"),
        dict(base, id=uuid4(), payer="parent"),
        dict(base, id=uuid4(), payer="comp"),
        dict(base, id=uuid4(), ended_at=datetime(2026, 11, 1)),
    ]
    with engine.begin() as connection:
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        connection.execute(ent.insert(), [dict(base, id=target_id)] + controls)
        migration.upgrade()
        migration.upgrade()
        result = {r.id: r.payer for r in connection.execute(sa.select(ent))}
        assert result[target_id] == "comp"
        assert all(result[r["id"]] == r["payer"] for r in controls)
        logs = connection.execute(sa.select(events)).mappings().all()
        assert len(logs) == 1
        manifest = json.loads(logs[0]["details_json"])
        assert manifest["entitlement_ids"] == [str(target_id)]
        assert manifest["before"] == {"payer": "tenant"}
        assert manifest["after"] == {"payer": "comp"}
        migration.downgrade()
        assert connection.scalar(sa.select(ent.c.payer).where(ent.c.id == target_id)) == "comp"
