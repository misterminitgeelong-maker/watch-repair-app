"""Exercise the additive migration on populated legacy tables without touching app data."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_upgrade_preserves_existing_operators_and_downgrade_preserves_rows():
    path = Path(__file__).parents[1] / "alembic/versions/20260930a_mv_merge_safety.py"
    spec = importlib.util.spec_from_file_location("mv_merge_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    db = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    tenant = sa.Table("tenant", metadata, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String()))
    audit = sa.Table("parentaccounteventlog", metadata, sa.Column("id", sa.Uuid(), primary_key=True),
                     sa.Column("event_summary", sa.String()))
    metadata.create_all(db)
    tid = uuid4()
    with db.begin() as connection:
        connection.execute(tenant.insert().values(id=tid, name="Existing operator"))
        connection.execute(audit.insert().values(id=uuid4(), event_summary="Existing audit"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            result = connection.execute(sa.text("SELECT name, mobile_dispatch_paused, merged_into_tenant_id FROM tenant")).one()
            assert tuple(result) == ("Existing operator", 0, None)
            assert connection.execute(sa.text("SELECT details_json FROM parentaccounteventlog")).scalar() is None
            migration.downgrade()
        assert connection.execute(sa.select(tenant.c.name)).scalar_one() == "Existing operator"
        assert connection.execute(sa.select(audit.c.event_summary)).scalar_one() == "Existing audit"
