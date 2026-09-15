"""Make tenant isolation a property of the session rather than of 325 memories.

Before this, isolation was enforced by hand at every call site: a
``session.get(Model, id)`` followed by ``if row.tenant_id != auth.tenant_id:
raise 404``, repeated across 327 lookups and 325 explicit ``tenant_id ==``
filters in ``app/routes/``. Every one of them was correct. That is not the
point — correctness depended on 325 independent acts of remembering, and the
326th endpoint gets written in a hurry.

Here a session can carry the tenant it is allowed to see. A ``do_orm_execute``
listener then adds ``tenant_id = :tenant`` to every ORM statement touching a
tenant-scoped model, so forgetting is safe by default instead of silent.

Three things were measured rather than assumed before settling on this design:

* ``with_loader_criteria`` intercepts ``session.get()``, not just ``select()``.
  That is what makes this worth doing: the 327 primary-key lookups are covered
  without editing any of them.
* It also blocks a cross-tenant bulk ``UPDATE``, so this is not read-only
  protection.
* The scope lives in ``session.info``, **not** in a ``ContextVar``. A ContextVar
  set inside a sync FastAPI dependency does not propagate back to the request
  context — and ``get_auth_context`` is sync, so a ContextVar design would have
  produced a security mechanism that silently did nothing. ``session.info``
  has no such failure mode: it is an attribute of the object being protected,
  with exactly the right lifetime.

What this does **not** cover, and still needs care:

* raw ``text()`` SQL, which bypasses the ORM entirely
* writing a *new* row with the wrong ``tenant_id`` — a different bug, since
  there is no existing row to filter
* ``session.exec(select(...))`` against a model with no ``tenant_id`` column

Cross-tenant access stays possible where the product genuinely needs it — the
login flow, platform admin, parent-account operations, billing webhooks and the
background sweeps all legitimately span tenants. Those use an unscoped session,
which is visible in the endpoint's signature rather than hidden in its body.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterable, Iterator
from uuid import UUID

from sqlalchemy import event, orm
from sqlmodel import Session, SQLModel

logger = logging.getLogger(__name__)

#: Key under which a session records the tenant it is restricted to.
SCOPE_KEY = "tenant_scope_id"

_MISSING = object()


def tenant_scoped_models() -> list[type[SQLModel]]:
    """Every mapped table carrying a ``tenant_id`` column.

    Derived from the metadata rather than hand-listed, so a new tenant-scoped
    table is protected the moment it exists. A hand-maintained list is the same
    kind of "remember to add it" problem this module exists to remove.
    """
    found: list[type[SQLModel]] = []
    seen: set[str] = set()

    def walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            walk(sub)
            table = getattr(sub, "__tablename__", None)
            if not table or table in seen:
                continue
            if "tenant_id" in getattr(sub, "model_fields", {}) or hasattr(sub, "tenant_id"):
                if getattr(sub, "__table__", None) is not None:
                    seen.add(table)
                    found.append(sub)

    walk(SQLModel)
    return found


def scope_to_tenant(session: Session, tenant_id: UUID) -> None:
    """Restrict every subsequent ORM statement on ``session`` to ``tenant_id``."""
    session.info[SCOPE_KEY] = tenant_id


def clear_scope(session: Session) -> None:
    session.info.pop(SCOPE_KEY, None)


def current_scope(session: Session) -> UUID | None:
    return session.info.get(SCOPE_KEY)


def is_scoped(session: Session) -> bool:
    return SCOPE_KEY in session.info


@contextmanager
def without_scope(session: Session) -> Iterator[None]:
    """Temporarily lift the tenant restriction on ``session``.

    For the narrow lookups inside an otherwise tenant-scoped request that have
    to see sibling tenants — "which other shops in this parent account use this
    shop number?" being the motivating case.

    This lifts the scope on the caller's own session rather than opening a
    second one. That matters: objects loaded on a different session belong to a
    different identity map, and attaching them to the caller's session raises
    "another instance with key ... is already present". Keep the lifted block
    as small as the query it exists for.
    """
    previous = session.info.get(SCOPE_KEY, _MISSING)
    session.info.pop(SCOPE_KEY, None)
    try:
        yield
    finally:
        if previous is not _MISSING:
            session.info[SCOPE_KEY] = previous


_scoped_by_table: dict[str, type[SQLModel]] = {}


def _scoped_lookup() -> dict[str, type[SQLModel]]:
    # Built once, after the models package has finished importing.
    if not _scoped_by_table:
        for model in tenant_scoped_models():
            _scoped_by_table[model.__tablename__] = model
    return _scoped_by_table


def _entities_in_statement(state: orm.ORMExecuteState) -> Iterable[type[SQLModel]]:
    """Only the tenant-scoped models this statement actually touches.

    Attaching criteria for all 52 scoped models to every statement would work,
    but it makes SQLAlchemy consider 52 options per query for no reason.
    """
    lookup = _scoped_lookup()
    for mapper in state.all_mappers:
        table = getattr(mapper.class_, "__tablename__", None)
        model = lookup.get(table) if table else None
        if model is not None:
            yield model


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_scope(state: orm.ORMExecuteState) -> None:
    tenant_id = state.session.info.get(SCOPE_KEY)
    if tenant_id is None:
        return
    for model in _entities_in_statement(state):
        state.statement = state.statement.options(
            orm.with_loader_criteria(
                model,
                model.tenant_id == tenant_id,  # type: ignore[attr-defined]
                include_aliases=True,
            )
        )
