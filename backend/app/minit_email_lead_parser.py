"""Parser for Mister Minit's own booking-enquiry form emails (BCC'd via powerfulform.com).

Capture-and-triage v1 (``backend/app/routes/inbound_email.py``) stores these
emails raw for manual HQ triage — nothing auto-parses them yet. This module
is a **read-only, non-persisting** parser + operator matcher used to preview
what automatic routing *would* do. It never sends SMS/email, never creates a
job, and never writes to the database — it exists so the routing decision
can be validated against real captured emails before anything is wired into
``mobile_lead_dispatch.py``'s live cascade.

The form itself already tells us the nearest operator (see
"Nearest Provider {STATE}: Mister Minit Mobile Services {name}" below) — we
match that string against the operator directory instead of re-deriving it
from the suburb/territory map, which is AU-only and would miss NZ leads.

Not every captured email can be parsed: some (observed for NZ regions such as
Sylvia Park/Auckland and Porirua/Wellington) arrive with no field data in
``text_body`` at all — just the generic "a customer submitted a form" notice.
``ParsedEmailLead.fields_found`` is False for those; they must stay in manual
HQ triage regardless of anything built here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlmodel import Session

from .minit_provision import _is_operator_plan
from .models import Tenant
from .shop_number import linked_tenants_for_parent

# Order matters: matched top-to-bottom against each stripped line.
_FIELD_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("location_state_raw", re.compile(r"^please select your location:\s*(.*)$", re.I)),
    ("nearest_provider_raw", re.compile(r"^nearest provider\b[^:]*:\s*(.*)$", re.I)),
    ("first_name", re.compile(r"^first name:\s*(.*)$", re.I)),
    ("last_name", re.compile(r"^last name:\s*(.*)$", re.I)),
    ("email", re.compile(r"^email:\s*(.*)$", re.I)),
    ("phone", re.compile(r"^phone:\s*(.*)$", re.I)),
    ("service_required", re.compile(r"^service required:\s*(.*)$", re.I)),
    ("vehicle_make", re.compile(r"^make:\s*(.*)$", re.I)),
    ("vehicle_model", re.compile(r"^model:\s*(.*)$", re.I)),
    ("vehicle_year", re.compile(r"^year:\s*(.*)$", re.I)),
    ("details", re.compile(r"^please provide details:\s*(.*)$", re.I)),
    ("contact_preference", re.compile(r"^how would you like to be contacted:\s*(.*)$", re.I)),
]

# The free-text box is the only field customers reliably wrap onto more than
# one line ("Please Provide Details: ...\nMy strata has been notified..."),
# so it's the only one we let continuation lines fold into.
_CONTINUABLE_FIELDS = frozenset({"details"})

_MISTER_MINIT_PREFIX_RE = re.compile(r"^mister minit\s+", re.I)


@dataclass
class ParsedEmailLead:
    raw_fields: dict[str, str] = field(default_factory=dict)
    #: False when no recognised "Label: value" lines were found at all — the
    #: email must stay in manual HQ triage; nothing below is trustworthy.
    fields_found: bool = False

    location_state_raw: str | None = None
    nearest_provider_raw: str | None = None
    #: nearest_provider_raw with the "Mister Minit " prefix stripped, ready
    #: to match against Tenant.name (e.g. "Mobile Services Burwood").
    nearest_provider_clean: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    service_required: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: str | None = None
    details: str | None = None
    contact_preference: str | None = None

    @property
    def customer_name(self) -> str | None:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts).strip() or None


def parse_powerfulform_body(text_body: str | None) -> ParsedEmailLead:
    """Extract the label:value field dump from a Mister Minit enquiry email body."""
    result = ParsedEmailLead()
    if not text_body:
        return result

    current_key: str | None = None
    for raw_line in text_body.splitlines():
        line = raw_line.strip()
        if not line:
            current_key = None
            continue

        matched_key: str | None = None
        for key, pattern in _FIELD_PATTERNS:
            m = pattern.match(line)
            if m:
                result.raw_fields[key] = m.group(1).strip()
                matched_key = key
                break

        if matched_key:
            current_key = matched_key if matched_key in _CONTINUABLE_FIELDS else None
        elif current_key:
            existing = result.raw_fields.get(current_key, "")
            result.raw_fields[current_key] = f"{existing} {line}".strip()

    if not result.raw_fields:
        return result

    result.fields_found = True
    result.location_state_raw = result.raw_fields.get("location_state_raw")
    result.nearest_provider_raw = result.raw_fields.get("nearest_provider_raw")
    if result.nearest_provider_raw:
        result.nearest_provider_clean = _MISTER_MINIT_PREFIX_RE.sub("", result.nearest_provider_raw).strip()
    result.first_name = result.raw_fields.get("first_name")
    result.last_name = result.raw_fields.get("last_name")
    result.email = result.raw_fields.get("email")
    result.phone = result.raw_fields.get("phone")
    result.service_required = result.raw_fields.get("service_required")
    result.vehicle_make = result.raw_fields.get("vehicle_make")
    result.vehicle_model = result.raw_fields.get("vehicle_model")
    result.vehicle_year = result.raw_fields.get("vehicle_year")
    result.details = result.raw_fields.get("details")
    result.contact_preference = result.raw_fields.get("contact_preference")
    return result


def _normalize_operator_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _loose_operator_key(name: str) -> str:
    """Drop spacing/punctuation entirely — catches 'Smithfield/Cairns' vs 'Smithfield / Cairns'."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


@dataclass
class OperatorMatch:
    tenant: Tenant | None
    #: "matched" | "matched_loose" | "unmatched" | "no_provider_field"
    confidence: str


def bookable_operators_for_parent(session: Session, parent_id: UUID) -> list[Tenant]:
    """Operator-plan tenants linked to the parent — the same pool website leads dispatch to."""
    return [t for t in linked_tenants_for_parent(session, parent_id) if _is_operator_plan(t.plan_code)]


def match_operator_for_lead(
    session: Session,
    *,
    parent_id: UUID,
    parsed: ParsedEmailLead,
) -> OperatorMatch:
    """Match the email's self-reported 'Nearest Provider' name to an operator tenant.

    The form already computes the nearest operator for us — we match its
    name against the operator directory rather than re-deriving it from the
    AU suburb/territory map (which would silently drop NZ leads).
    """
    if not parsed.nearest_provider_clean:
        return OperatorMatch(tenant=None, confidence="no_provider_field")

    operators = bookable_operators_for_parent(session, parent_id)

    target = _normalize_operator_name(parsed.nearest_provider_clean)
    for tenant in operators:
        if _normalize_operator_name(tenant.name) == target:
            return OperatorMatch(tenant=tenant, confidence="matched")

    loose_target = _loose_operator_key(parsed.nearest_provider_clean)
    for tenant in operators:
        if _loose_operator_key(tenant.name) == loose_target:
            return OperatorMatch(tenant=tenant, confidence="matched_loose")

    return OperatorMatch(tenant=None, confidence="unmatched")


@dataclass
class EmailLeadOperatorBucket:
    """Email-lead volume for one operator (or an unmatched/no-fields bucket)."""

    operator_tenant_id: UUID | None
    operator_name: str
    total_count: int = 0
    new_count: int = 0
    processed_count: int = 0
    dismissed_count: int = 0
    #: Oldest still-"new" email in this bucket — how stale the backlog is.
    oldest_new_at: object = None  # datetime | None; kept loosely typed to avoid importing datetime here


def bucket_email_leads_by_operator(
    session: Session,
    *,
    parent_id: UUID,
    emails: "list",
) -> list[EmailLeadOperatorBucket]:
    """Group already-queried InboundEmail rows by matched operator + status counts.

    Shared by the HTTP "email leads by shop" report and the weekly mobile
    network report email — kept in one place so both agree on what counts as
    "matched" vs "unmatched" vs "no fields extracted".
    """
    buckets: dict[str, EmailLeadOperatorBucket] = {}

    def _bucket(key: str, tenant_id: UUID | None, name: str) -> EmailLeadOperatorBucket:
        existing = buckets.get(key)
        if existing:
            return existing
        created = EmailLeadOperatorBucket(operator_tenant_id=tenant_id, operator_name=name)
        buckets[key] = created
        return created

    for email in emails:
        parsed = parse_powerfulform_body(email.text_body)
        if not parsed.fields_found:
            bucket = _bucket("no_fields", None, "No fields extracted (manual review needed)")
        else:
            match = match_operator_for_lead(session, parent_id=parent_id, parsed=parsed)
            if match.tenant:
                bucket = _bucket(str(match.tenant.id), match.tenant.id, match.tenant.name)
            else:
                label = parsed.nearest_provider_clean or "Unmatched operator"
                bucket = _bucket(f"unmatched:{label}", None, f"{label} (no matching operator)")

        bucket.total_count += 1
        if email.status == "new":
            bucket.new_count += 1
            if bucket.oldest_new_at is None or email.created_at < bucket.oldest_new_at:
                bucket.oldest_new_at = email.created_at
        elif email.status == "processed":
            bucket.processed_count += 1
        elif email.status == "dismissed":
            bucket.dismissed_count += 1

    return sorted(buckets.values(), key=lambda b: (-b.new_count, b.operator_name.lower()))
