"""split parentaccountmembership into sites, users and regions

parentaccountmembership conflated two questions — which tenants are in a
network, and which users can reach it — in one table with no unique
constraint, so every reader had to dedupe and nothing stopped a duplicate
row. It also left a shop's role in the network to be inferred from its
billing plan, and region to be a free-text string.

This replaces it with:

* parentaccountsite (parent_account_id, tenant_id) UNIQUE — the org chart,
  carrying network_role (hq | retail | operator) and an optional region_id.
  A tenant may still sit in more than one network on purpose: the directory
  import links a franchisee's shops to both their own group and HQ's.
* parentaccountuser (parent_account_id, user_id) UNIQUE — the access list,
  carrying role (hq_admin | hq_viewer). Shop-level users have no row.
* region (parent_account_id, code) UNIQUE — named regions with a manager and
  escalation contact, backfilled from the distinct tenant.minit_region strings
  in each network.

Backfill rules (preserve today's effective access exactly):

* every distinct (parent, tenant) pair becomes one site; network_role from the
  tenant's plan at migration time (minit_hq → hq, operator plans → operator,
  else retail); region_id from the normalised minit_region string.
* no user rows: access for logins inside the HQ tenant (owners → hq_admin,
  others → hq_viewer, exactly who could reach the dashboards before) and for
  the account owner's email is implicit; explicit rows are only written when
  HQ grants or changes a role deliberately.

Revision ID: 20260916a_parent_network
Revises: 20260915b_idem_state
Create Date: 2026-09-16

"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "20260916a_parent_network"
down_revision: Union[str, None] = "20260915b_idem_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "parentaccountmembership"
_HQ_SLUG = "mmsupport"
_HQ_PLAN = "minit_hq"
_OPERATOR_PLANS = {"basic_auto_key", "basic_shoe_auto_key", "basic_watch_auto_key", "basic_all_tabs"}
_PLAN_ALIASES = {"watch": "basic_watch", "shoe": "basic_shoe", "auto_key": "basic_auto_key", "enterprise": "pro"}


def _norm_plan(value: str | None) -> str:
    plan = (value or "").strip().lower()
    return _PLAN_ALIASES.get(plan, plan) or "pro"


def _network_role(slug: str | None, plan: str | None) -> str:
    if (slug or "").strip().lower() == _HQ_SLUG or _norm_plan(plan) == _HQ_PLAN:
        return "hq"
    if _norm_plan(plan) in _OPERATOR_PLANS:
        return "operator"
    return "retail"


def _region_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = " ".join(value.strip().upper().split())
    return code[:40] or None


def _create_tables() -> None:
    op.create_table(
        "region",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("manager_name", sa.String(length=200), nullable=True),
        sa.Column("manager_email", sa.String(length=320), nullable=True),
        sa.Column("manager_phone", sa.String(length=80), nullable=True),
        sa.Column("escalation_email", sa.String(length=320), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "code", name="uq_region_parent_code"),
    )
    op.create_index(op.f("ix_region_parent_account_id"), "region", ["parent_account_id"], unique=False)

    op.create_table(
        "parentaccountsite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("network_role", sa.String(length=16), nullable=False),
        sa.Column("region_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "tenant_id", name="uq_parentaccountsite_parent_tenant"),
    )
    op.create_index(op.f("ix_parentaccountsite_parent_account_id"), "parentaccountsite", ["parent_account_id"], unique=False)
    op.create_index(op.f("ix_parentaccountsite_tenant_id"), "parentaccountsite", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_parentaccountsite_network_role"), "parentaccountsite", ["network_role"], unique=False)
    op.create_index(op.f("ix_parentaccountsite_region_id"), "parentaccountsite", ["region_id"], unique=False)

    op.create_table(
        "parentaccountuser",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_account_id", "user_id", name="uq_parentaccountuser_parent_user"),
    )
    op.create_index(op.f("ix_parentaccountuser_parent_account_id"), "parentaccountuser", ["parent_account_id"], unique=False)
    op.create_index(op.f("ix_parentaccountuser_user_id"), "parentaccountuser", ["user_id"], unique=False)
    op.create_index(op.f("ix_parentaccountuser_role"), "parentaccountuser", ["role"], unique=False)


# Lightweight table handles so inserts get proper UUID/datetime binding on both dialects.
_region_t = sa.table(
    "region",
    sa.column("id", sa.Uuid()),
    sa.column("parent_account_id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("created_at", sa.DateTime()),
)
_site_t = sa.table(
    "parentaccountsite",
    sa.column("id", sa.Uuid()),
    sa.column("parent_account_id", sa.Uuid()),
    sa.column("tenant_id", sa.Uuid()),
    sa.column("network_role", sa.String()),
    sa.column("region_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime()),
)
_old_t = sa.table(
    _OLD,
    sa.column("parent_account_id", sa.Uuid()),
    sa.column("tenant_id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime()),
)
_tenant_t = sa.table(
    "tenant",
    sa.column("id", sa.Uuid()),
    sa.column("slug", sa.String()),
    sa.column("plan_code", sa.String()),
    sa.column("minit_region", sa.String()),
)
_app_user_t = sa.table(
    "user",
    sa.column("id", sa.Uuid()),
    sa.column("tenant_id", sa.Uuid()),
    sa.column("email", sa.String()),
    sa.column("role", sa.String()),
    sa.column("is_active", sa.Boolean()),
)


def _backfill(bind) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    memberships = bind.execute(
        sa.select(_old_t.c.parent_account_id, _old_t.c.tenant_id, _old_t.c.user_id, _old_t.c.created_at)
        .order_by(_old_t.c.created_at, _old_t.c.parent_account_id, _old_t.c.tenant_id)
    ).all()
    if not memberships:
        return

    tenant_ids = list({m.tenant_id for m in memberships})
    tenants = {
        r.id: r
        for r in bind.execute(
            sa.select(_tenant_t.c.id, _tenant_t.c.slug, _tenant_t.c.plan_code, _tenant_t.c.minit_region)
            .where(_tenant_t.c.id.in_(tenant_ids))
        ).all()
    }

    # ── sites (dedup on (parent, tenant), first link wins for created_at) ────
    site_rows: dict[tuple[UUID, UUID], dict] = {}
    for m in memberships:
        key = (m.parent_account_id, m.tenant_id)
        if key in site_rows:
            continue
        t = tenants.get(m.tenant_id)
        if t is None:
            continue
        site_rows[key] = {
            "id": uuid4(),
            "parent_account_id": m.parent_account_id,
            "tenant_id": m.tenant_id,
            "network_role": _network_role(t.slug, t.plan_code),
            "region_id": None,
            "created_at": m.created_at or now,
            "_region_code": _region_code(t.minit_region),
        }

    # ── regions (one per parent per distinct normalised code) ────────────────
    region_ids: dict[tuple[UUID, str], UUID] = {}
    region_inserts: list[dict] = []
    for row in site_rows.values():
        code = row["_region_code"]
        if not code:
            continue
        key = (row["parent_account_id"], code)
        if key not in region_ids:
            rid = uuid4()
            region_ids[key] = rid
            region_inserts.append(
                {"id": rid, "parent_account_id": row["parent_account_id"], "code": code, "name": code, "created_at": now}
            )
        row["region_id"] = region_ids[key]
    if region_inserts:
        bind.execute(sa.insert(_region_t), region_inserts)

    site_inserts = [{k: v for k, v in row.items() if not k.startswith("_")} for row in site_rows.values()]
    if site_inserts:
        bind.execute(sa.insert(_site_t), site_inserts)

    # No user rows are backfilled: a login inside the network's HQ tenant, or
    # one matching the account's owner_email, has an implicit role (see
    # parent_network.parent_role_for_user). Explicit rows are only written
    # when HQ deliberately grants or changes someone's role.


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "parentaccountsite" not in existing:
        _create_tables()

    if _OLD in existing:
        _backfill(bind)
        op.drop_table(_OLD)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if _OLD not in existing:
        op.create_table(
            _OLD,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("parent_account_id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_parentaccountmembership_parent_account_id"), _OLD, ["parent_account_id"], unique=False)
        op.create_index(op.f("ix_parentaccountmembership_tenant_id"), _OLD, ["tenant_id"], unique=False)
        op.create_index(op.f("ix_parentaccountmembership_user_id"), _OLD, ["user_id"], unique=False)

        # Best-effort restore: one membership per site, anchored on the first
        # active owner of that tenant (the shape provisioning always wrote).
        if "parentaccountsite" in existing:
            old_full = sa.table(
                _OLD,
                sa.column("id", sa.Uuid()),
                sa.column("parent_account_id", sa.Uuid()),
                sa.column("tenant_id", sa.Uuid()),
                sa.column("user_id", sa.Uuid()),
                sa.column("created_at", sa.DateTime()),
            )
            sites = bind.execute(
                sa.select(_site_t.c.parent_account_id, _site_t.c.tenant_id, _site_t.c.created_at)
            ).all()
            owners: dict[UUID, UUID] = {}
            for u in bind.execute(
                sa.select(_app_user_t.c.id, _app_user_t.c.tenant_id)
                .where(_app_user_t.c.role == "owner")
                .where(_app_user_t.c.is_active == True)  # noqa: E712
            ).all():
                owners.setdefault(u.tenant_id, u.id)
            rows = [
                {
                    "id": uuid4(),
                    "parent_account_id": s.parent_account_id,
                    "tenant_id": s.tenant_id,
                    "user_id": owners[s.tenant_id],
                    "created_at": s.created_at,
                }
                for s in sites
                if s.tenant_id in owners
            ]
            if rows:
                bind.execute(sa.insert(old_full), rows)

    for table in ("parentaccountuser", "parentaccountsite", "region"):
        if table in existing:
            op.drop_table(table)
