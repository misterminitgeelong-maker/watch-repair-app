"""Per-HQ settings: the one place that answers "how is this company's HQ set up".

Minit used to be special-cased by slug, flag and plan code across the backend.
A company is now an HQ with a settings row. Minit's row is seeded from
``MINIT_DEFAULTS``, which mirrors today's behaviour exactly; nothing reads
these settings for access decisions yet (that is the next step), so adding the
table changes no behaviour for Minit or anyone else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from .minit_branding import MINIT_ACCENT_COLOR, MINIT_HQ_SLUG, MINIT_SITE_PLANS
from .models import HqSettings

#: Modules an HQ can switch on. The HQ dashboard, nav and reports will be
#: built from these instead of assuming mobile services.
HQ_MODULES: tuple[str, ...] = (
    "mobile_services",
    "shoe",
    "watch",
    "stock",
    "lead_routing",
    "kpis",
    "regional_reports",
)

MINIT_PRODUCT_KEY = "minit"


@dataclass(frozen=True)
class HqConfig:
    product_key: str
    display_name: str
    logo_url: str | None
    brand_color: str | None
    modules: frozenset[str]
    site_plans: frozenset[str]

    def has_module(self, module: str) -> bool:
        return module in self.modules


#: What Minit's HQ does today, written down. Tests pin it against the code
#: that still enforces it, so the seeded row can't drift from real behaviour.
MINIT_DEFAULTS = HqConfig(
    product_key=MINIT_PRODUCT_KEY,
    display_name="Mister Minit",
    logo_url=None,  # the Minit logo is served by minit_branding
    brand_color=MINIT_ACCENT_COLOR,
    modules=frozenset({"mobile_services", "lead_routing", "kpis", "regional_reports"}),
    site_plans=frozenset(MINIT_SITE_PLANS),
)


def _config_from_row(row: HqSettings) -> HqConfig:
    return HqConfig(
        product_key=row.product_key,
        display_name=row.display_name,
        logo_url=row.logo_url,
        brand_color=row.brand_color,
        modules=frozenset(json.loads(row.modules_json or "[]")),
        site_plans=frozenset(json.loads(row.site_plans_json or "[]")),
    )


def get_hq_config(session: Session, parent_account_id: UUID) -> HqConfig | None:
    """The HQ's settings, or None when this parent account has no HQ row."""
    row = session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent_account_id)).first()
    return _config_from_row(row) if row else None


def upsert_hq_settings(session: Session, parent_account_id: UUID, config: HqConfig) -> HqSettings:
    unknown = config.modules - set(HQ_MODULES)
    if unknown:
        raise ValueError(f"Unknown HQ modules: {sorted(unknown)}")
    row = session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent_account_id)).first()
    if row is None:
        row = HqSettings(parent_account_id=parent_account_id, product_key=config.product_key, display_name=config.display_name)
    row.product_key = config.product_key
    row.display_name = config.display_name
    row.logo_url = config.logo_url
    row.brand_color = config.brand_color
    row.modules_json = json.dumps(sorted(config.modules))
    row.site_plans_json = json.dumps(sorted(config.site_plans))
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.flush()
    return row


def ensure_minit_hq_settings(session: Session, parent_account_id: UUID) -> HqSettings:
    """Seed Minit's row (idempotent). Leaves an existing row untouched so later
    edits made through the admin screen are never overwritten."""
    row = session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent_account_id)).first()
    if row is not None:
        return row
    return upsert_hq_settings(session, parent_account_id, MINIT_DEFAULTS)


__all__ = [
    "HQ_MODULES",
    "HqConfig",
    "MINIT_DEFAULTS",
    "MINIT_HQ_SLUG",
    "MINIT_PRODUCT_KEY",
    "ensure_minit_hq_settings",
    "get_hq_config",
    "upsert_hq_settings",
]
