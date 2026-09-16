"""The regional manager's Monday email.

One email per region with ``weekly_report_opt_in`` and a manager address:
the region's week against the previous one, its rank among regions, the
shops that moved most either way, the exceptions, and the narrative — with
the per-shop table attached as a CSV. Sent once per ISO week, and only once
a new reporting week has appeared since the last send, so a quiet upload
schedule does not produce a duplicate.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from .. import email_client
from ..models import ParentAccount, Region

logger = logging.getLogger(__name__)


def _is_due(last_sent_at: datetime | None, today: date) -> bool:
    if last_sent_at is None:
        return True
    last_date = last_sent_at.astimezone(timezone.utc).date() if last_sent_at.tzinfo else last_sent_at.date()
    return last_date.isocalendar()[:2] != today.isocalendar()[:2]


def _csv_bytes(data: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Shop #", "Shop", "Area", "Sales", "Previous", "Change", "Change %", "Customers", "Jobs",
            "Avg sale", "Rank in region", "Rank in network", "Z-score", "Target", "Target variance",
        ]
    )
    for r in data.get("shops", []):
        writer.writerow(
            [
                r["shop_number"], r["shop_name"], r.get("area_name"), r["sales"], r["previous_sales"], r["delta"],
                r["delta_pct"], r["customers"], r["jobs"], r["avg_sale"], r["rank_in_region"], r["rank_in_network"],
                r["zscore"], r["target"], r["target_variance"],
            ]
        )
    return buf.getvalue().encode("utf-8")


def send_region_report(session: Session, *, parent: ParentAccount, region: Region) -> bool:
    """Build and send the region's report now. Stamps the region even when
    delivery is not configured, matching the other report sweeps, so a
    missing provider never turns into a retry storm."""
    from ..routes.parent_regions import build_region_cockpit

    to_email = (region.manager_email or "").strip()
    if not to_email:
        return False
    data = build_region_cockpit(session, parent=parent, region=region, comparison="previous")
    if not data.get("available"):
        return False
    sales = next((r for r in data["rows"] if r["key"] == "sales_ty"), {})
    customers = next((r for r in data["rows"] if r["key"] == "customer_ty"), {})
    sent, _error = email_client.send_region_manager_report_email(
        to_email=to_email,
        manager_name=region.manager_name,
        region_name=region.name,
        week=data["week"],
        sales=sales.get("current"),
        sales_delta_pct=sales.get("delta_pct"),
        customers=customers.get("current"),
        region_rank=sales.get("rank"),
        region_count=data["region_count"],
        shops_reported=data["shops_reported"],
        shop_count=data["shop_count"],
        narrative=data["narrative"],
        movers_up=data["movers"]["up"],
        movers_down=data["movers"]["down"],
        alerts=data["alerts"],
        attainment=data["target_attainment"],
        csv_bytes=_csv_bytes(data),
        csv_filename=f"{region.code.lower().replace(' ', '-')}-week-{data['week']}.csv",
    )
    region.last_weekly_report_sent_at = datetime.now(timezone.utc)
    session.add(region)
    session.commit()
    return sent


def send_due_region_reports(session: Session, parent_id: UUID | None = None) -> dict[str, int]:
    today = datetime.now(timezone.utc).date()
    summary = {"sent": 0, "skipped": 0}
    query = select(Region).where(Region.weekly_report_opt_in.is_(True))  # type: ignore[attr-defined]
    if parent_id:
        query = query.where(Region.parent_account_id == parent_id)
    for region in session.exec(query).all():
        if not (region.manager_email or "").strip() or not _is_due(region.last_weekly_report_sent_at, today):
            summary["skipped"] += 1
            continue
        parent = session.get(ParentAccount, region.parent_account_id)
        if parent is None:
            summary["skipped"] += 1
            continue
        try:
            if send_region_report(session, parent=parent, region=region):
                summary["sent"] += 1
            else:
                summary["skipped"] += 1
        except Exception:
            logger.exception("regional_manager_report.send_failed region=%s", region.id)
            summary["skipped"] += 1
    return summary
