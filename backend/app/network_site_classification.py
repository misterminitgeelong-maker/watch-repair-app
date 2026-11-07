"""Reviewed Minit presentation/targeting rules, separate from billing and dispatch.

Never change stored roles, memberships, reporting consent or dispatch readiness here.
Rules are scoped to the reviewed parent so unrelated networks keep their identities.
"""
from uuid import UUID

MINIT_PARENT_ID = UUID("f3bb646e-b7f5-44e0-9f7d-8ad2c347dd87")
HIDDEN_NUMBERS = frozenset({"0101", "01111", "3904"})
HIDDEN_SLUGS = frozenset({"minit-mobile-2311", "minit-mobile-6441", "minit-mobile-8829", "minit-mobile-8833"})
REVIEWED_VAN_NUMBERS = frozenset({"2915", "4903", "6902", "6903", "8901", "8905"})


def excluded_site_reason(parent_id, tenant):
    if parent_id != MINIT_PARENT_ID or tenant is None:
        return None
    if (tenant.slug or "").strip().lower() in HIDDEN_SLUGS:
        return "Imported Mobile Services placeholder; replacement operator requires review"
    if (tenant.shop_number or "").strip() in HIDDEN_NUMBERS:
        return "Test or excluded account; not a shop messaging target"
    return None


def display_network_role(parent_id, site, tenant):
    """Correct the six reviewed van labels without modifying stored roles."""
    if (parent_id == MINIT_PARENT_ID and site.network_role == "retail" and tenant is not None
            and (tenant.shop_number or "").strip() in REVIEWED_VAN_NUMBERS):
        return "operator"
    return site.network_role
