"""Which messaging state hub a site belongs to. Shared by messaging and the shop admin screens."""
import re

STATES = {
    "VIC": "Victoria", "NSW": "New South Wales", "QLD": "Queensland",
    "WA": "Western Australia", "SA": "South Australia", "TAS": "Tasmania",
    "ACT": "Australian Capital Territory", "NT": "Northern Territory", "NZ": "New Zealand",
}
#: Stored in ``ParentAccountSite.messaging_state`` to keep a site out of every hub.
HUB_NONE = "NONE"


def state_code(value):
    value = re.sub(r"\s+", " ", (value or "").strip().upper())
    if value in {name.upper(): code for code, name in STATES.items()}:
        return next(code for code, name in STATES.items() if name.upper() == value)
    match = re.match(r"^(VIC|NSW|QLD|WA|SA|TAS|ACT|NT|NZ)(?:$|[\s_-])", value)
    return match.group(1) if match else None


def valid_hub_setting(value):
    return value in STATES or value == HUB_NONE


def hub_for(site, tenant, region):
    """Hub code for a site, or None.

    Order: the shop's own override (a state, or NONE to exclude it), then its area
    (so a SW-region shop in SOUTH AUSTRALIA lands in SA), then its region code.
    """
    setting = getattr(site, "messaging_state", None) if site else None
    if setting:
        return None if setting == HUB_NONE else setting
    area = state_code(tenant.minit_area) if tenant else None
    return area or state_code(region.code if region else (tenant.minit_region if tenant else None))


#: Areas deliberately outside the AU/NZ messaging hubs (so they are not listed as "missing a state").
EXCLUDED_AREAS = frozenset({"MALAYSIA", "SINGAPORE"})


def intentionally_excluded(site, tenant, region):
    if site is not None and getattr(site, "messaging_state", None) == HUB_NONE:
        return True
    area = (tenant.minit_area or "").strip().upper() if tenant else ""
    return area in EXCLUDED_AREAS or (region is not None and (region.code or "").strip().upper() == "SEA")
