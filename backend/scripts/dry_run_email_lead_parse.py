"""Dry-run the Mister Minit BCC email-lead parser against real captured emails.

Read-only: this never writes to the database, never sends SMS/email, and
never creates a job. It exists to answer one question before anything is
wired into the live dispatch cascade — "if we auto-routed the captured
email leads right now, would each one land on the correct operator?"

Usage (run with the same DATABASE_URL as the environment you want to check,
e.g. production, the same way other backend/scripts/*.py scripts do):

    python scripts/dry_run_email_lead_parse.py --owner-email owner@example.com
    python scripts/dry_run_email_lead_parse.py --owner-email owner@example.com --status new
    python scripts/dry_run_email_lead_parse.py --owner-email owner@example.com --csv out.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.minit_email_lead_parser import match_operator_for_lead, parse_powerfulform_body
from app.models import InboundEmail, ParentAccount


def _get_parent(session: Session, owner_email: str) -> ParentAccount:
    parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == owner_email)).first()
    if not parent:
        raise SystemExit(f"No ParentAccount found for owner_email={owner_email!r}")
    return parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--owner-email", required=True, help="Owner email of the HQ parent account (e.g. Minit HQ login).")
    ap.add_argument("--status", default=None, help="Only rows with this InboundEmail.status (new|processed|dismissed).")
    ap.add_argument("--csv", default=None, help="Optional path to also write results as CSV.")
    args = ap.parse_args()

    rows_out: list[dict[str, str]] = []
    counts = {"matched": 0, "matched_loose": 0, "unmatched": 0, "no_provider_field": 0, "no_fields_found": 0}

    with Session(engine) as session:
        parent = _get_parent(session, args.owner_email)
        query = select(InboundEmail).where(InboundEmail.parent_account_id == parent.id)
        if args.status:
            query = query.where(InboundEmail.status == args.status)
        emails = session.exec(query.order_by(InboundEmail.created_at.desc())).all()

        print(f"Parent account: {parent.name} ({parent.owner_email})")
        print(f"Inbound emails checked: {len(emails)}\n")

        header = f"{'created':<12} {'subject':<55} {'customer':<22} {'nearest provider (raw)':<38} {'match':<16} {'operator'}"
        print(header)
        print("-" * len(header))

        for email in emails:
            parsed = parse_powerfulform_body(email.text_body)
            if not parsed.fields_found:
                counts["no_fields_found"] += 1
                match_label = "no_fields_found"
                operator_name = ""
            else:
                match = match_operator_for_lead(session, parent_id=parent.id, parsed=parsed)
                counts[match.confidence] = counts.get(match.confidence, 0) + 1
                match_label = match.confidence
                operator_name = match.tenant.name if match.tenant else ""

            subject = (email.subject or "")[:55]
            customer = (parsed.customer_name or "")[:22]
            provider_raw = (parsed.nearest_provider_raw or "")[:38]
            created = email.created_at.strftime("%Y-%m-%d")
            print(f"{created:<12} {subject:<55} {customer:<22} {provider_raw:<38} {match_label:<16} {operator_name}")

            rows_out.append(
                {
                    "inbound_email_id": str(email.id),
                    "created_at": email.created_at.isoformat(),
                    "status": email.status,
                    "subject": email.subject or "",
                    "customer_name": parsed.customer_name or "",
                    "nearest_provider_raw": parsed.nearest_provider_raw or "",
                    "match": match_label,
                    "matched_operator": operator_name,
                    "service_required": parsed.service_required or "",
                }
            )

    print("\nSummary:")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    routable = counts["matched"] + counts["matched_loose"]
    print(f"\n{routable}/{len(rows_out)} would route cleanly to an operator if triggered today.")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()) if rows_out else [])
            writer.writeheader()
            writer.writerows(rows_out)
        print(f"\nWrote {len(rows_out)} rows to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
