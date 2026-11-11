"""Idempotent multi-shop screenshot fixture; strictly the disposable localhost SQLite DB.

Run from any directory with the project's backend test interpreter. No HTTP/provider calls,
password output, migrations, production connections or HQ-site promotion are performed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from uuid import UUID


def seed() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    fixture_dir = (root / "artifacts/native-local-backend").resolve()
    connection = json.loads((fixture_dir / "connection.json").read_text(encoding="utf-8"))
    review = json.loads((fixture_dir / "screen-review-data.json").read_text(encoding="utf-8"))
    origin = urlsplit(connection["base_url"])
    if origin.scheme != "http" or origin.hostname != "127.0.0.1" or origin.port != 8716 or origin.username or origin.password or origin.path not in ("", "/") or origin.query or origin.fragment:
        raise ValueError("Only the disposable 127.0.0.1:8716 screenshot backend is allowed")
    database = Path(connection["database"]).resolve(strict=True)
    if database.parent != fixture_dir or not database.name.startswith("native-test-") or database.suffix != ".db":
        raise ValueError("Database must be a native-test SQLite file in this checkout's local fixture folder")
    if Path(review["database"]).resolve(strict=True) != database or review.get("source") != "disposable localhost synthetic data only":
        raise ValueError("Review metadata does not identify the same disposable database")
    main_id = UUID(connection["tenant_id"])
    if str(main_id) != review["tenant_id"] or not connection["slug"].startswith("native-qa-") or not connection["email"].endswith("@native.example.test"):
        raise ValueError("Unexpected main screenshot tenant metadata")
    partner_id = UUID(review["recipient_tenant_id"])
    parent_id = UUID(review["network_id"])
    if partner_id == main_id:
        raise ValueError("Partner must be a distinct fixture shop")

    # Set the validated SQLite target before importing app modules/configuration.
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    os.environ["APP_ENV"] = "test"
    os.environ["STARTUP_SEED_ENABLED"] = "false"
    os.environ["TWILIO_DRY_RUN"] = "true"
    sys.path.insert(0, str(root / "backend"))
    from sqlmodel import Session, create_engine, select
    from app.models import ParentAccount, ParentAccountSite, ParentAccountUser, Tenant, User
    from app.integration_access import can_manage_tenant_integrations
    from app.dependencies import AuthContext
    from app.routes.auth import _build_available_sites_for_user

    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        main = session.get(Tenant, main_id)
        partner = session.get(Tenant, partner_id)
        parent = session.get(ParentAccount, parent_id)
        if main is None or main.slug != connection["slug"] or partner is None or parent is None:
            raise ValueError("Expected screenshot tenant/network records do not exist")
        sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent_id,
            ParentAccountSite.tenant_id.in_([main_id, partner_id]))).all()
        if {s.tenant_id for s in sites} != {main_id, partner_id} or any(s.network_role == "hq" for s in sites):
            raise ValueError("Both fixture shops must already be linked, with neither an HQ workspace")
        owner = session.exec(select(User).where(User.tenant_id == main_id, User.email == connection["email"], User.is_active == True)).one()
        clone = session.exec(select(User).where(User.tenant_id == partner_id, User.email == owner.email)).first()
        if clone is None:
            clone = User(tenant_id=partner_id, email=owner.email, full_name=owner.full_name,
                role=owner.role, password_hash=owner.password_hash, is_active=True)
            session.add(clone); session.flush()
        elif not clone.is_active:
            raise ValueError("Existing partner fixture login is inactive; refusing to silently reactivate it")
        for user in (owner, clone):
            grant = session.exec(select(ParentAccountUser).where(ParentAccountUser.parent_account_id == parent_id,
                ParentAccountUser.user_id == user.id)).first()
            if grant is None:
                session.add(ParentAccountUser(parent_account_id=parent_id, user_id=user.id, role="hq_admin"))
            elif grant.role != "hq_admin" or grant.region_id is not None:
                grant.role = "hq_admin"; grant.region_id = None; session.add(grant)
        session.flush()
        for user in (owner, clone):
            choices = _build_available_sites_for_user(session, user)
            if not {main_id, partner_id}.issubset({x.tenant_id for x in choices}):
                raise AssertionError("Fixture login cannot switch both directions")
            auth = AuthContext(tenant_id=user.tenant_id, user_id=user.id, role=user.role, sid="fixture-direct-session")
            if can_manage_tenant_integrations(session, auth):
                raise AssertionError("Retail fixture unexpectedly gained integration management")
        session.commit()
    return {"source": "disposable localhost synthetic data only", "multi_site_ready": True,
        "site_count": len(choices), "retail_integrations_allowed": False}


if __name__ == "__main__":
    print(json.dumps(seed()))
