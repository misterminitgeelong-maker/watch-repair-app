"""Mister Minit shops show the Mister Minit logo wherever their customers look:
the customer portal, public status pages, and invoice/quote PDFs and emails."""

from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.minit_branding import (
    MINIT_DOCUMENT_COLOR,
    MINIT_LOGO_ASSET,
    MINIT_LOGO_PUBLIC_PATH,
    customer_brand_color,
    customer_logo_url,
    document_branding,
)
from app.models import Tenant
from app.pdf_invoice import build_invoice_pdf, build_quote_pdf
from tests.test_customer_portal_lookup import _bootstrap, _create_watch_job, _portal_view

_LINE_ITEMS = [
    {"description": "Key cut", "quantity": 2, "unit_price_cents": 1500, "total_price_cents": 3000},
]


def _mark_minit(slug: str) -> None:
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tenant.is_minit = True
        tenant.logo_url = "https://example.com/own-logo.png"
        session.add(tenant)
        session.commit()


def test_minit_tenant_gets_minit_logo_over_its_own():
    tenant = Tenant(name="Mister Minit Chadstone", slug="minit-3269", is_minit=True, logo_url="https://x/own.png")
    assert customer_logo_url(tenant).endswith(MINIT_LOGO_PUBLIC_PATH)
    assert customer_brand_color(tenant)  # falls back to Minit red

    branding = document_branding(tenant)
    assert branding["logo_path"] == str(MINIT_LOGO_ASSET)
    assert branding["logo_url"] is None
    assert branding["brand_color"] == MINIT_DOCUMENT_COLOR
    assert MINIT_LOGO_ASSET.is_file()


def test_non_minit_tenant_keeps_its_own_branding():
    tenant = Tenant(name="Geelong Watch Co", slug="gwc", logo_url="https://x/own.png", brand_color="#123456")
    assert customer_logo_url(tenant) == "https://x/own.png"
    assert customer_brand_color(tenant) == "#123456"
    assert document_branding(tenant) == {
        "logo_url": "https://x/own.png",
        "logo_path": None,
        "brand_color": "#123456",
    }


def test_minit_pdfs_embed_bundled_logo_without_fetching(monkeypatch):
    def _no_network(*_a, **_kw):
        raise AssertionError("Minit logo must come from the bundled file, not HTTP")

    monkeypatch.setattr(httpx, "Client", _no_network)
    minit = document_branding(Tenant(name="Mister Minit", slug="minit-1", is_minit=True))
    common = dict(customer_name="Alex", shop_name="Mister Minit", line_items=_LINE_ITEMS, total_cents=3000)

    plain = build_invoice_pdf(invoice_number="INV-1", job_number="1", **common)
    branded = build_invoice_pdf(invoice_number="INV-1", job_number="1", **common, **minit)
    quote = build_quote_pdf(job_number="1", **common, **minit)

    assert branded.startswith(b"%PDF") and quote.startswith(b"%PDF")
    # The logo image is embedded, so the branded PDF is materially larger.
    assert len(branded) > len(plain) + 10_000
    assert b"/Subtype /Image" in branded


def test_portal_and_status_page_flag_minit_shops(client: TestClient):
    headers = _bootstrap(client)
    slug = headers.pop("tenant_slug")
    email = f"minit-{uuid4().hex[:8]}@portal.test"
    job = _create_watch_job(client, headers, email, "Battery")
    # Flag it afterwards: Minit plans don't create repair jobs from this API.
    _mark_minit(slug)

    res = _portal_view(client, email)
    assert res.status_code == 200, res.text
    (shop,) = res.json()["shops"]
    assert shop["is_minit"] is True
    assert shop["logo_url"].endswith(MINIT_LOGO_PUBLIC_PATH)

    status = client.get(f"/v1/public/jobs/{job.status_token}")
    assert status.status_code == 200, status.text
    assert status.json()["shop"]["is_minit"] is True

    shop_info = client.get(f"/v1/public/portal/{slug}/shop")
    assert shop_info.status_code == 200, shop_info.text
    assert shop_info.json()["is_minit"] is True
    assert shop_info.json()["logo_url"].endswith(MINIT_LOGO_PUBLIC_PATH)


def test_portal_leaves_other_shops_alone(client: TestClient):
    headers = _bootstrap(client)
    headers.pop("tenant_slug")
    email = f"plain-{uuid4().hex[:8]}@portal.test"
    _create_watch_job(client, headers, email, "Service")

    (shop,) = _portal_view(client, email).json()["shops"]
    assert shop["is_minit"] is False
    assert shop["logo_url"] is None


def test_customer_emails_carry_minit_logo():
    from app.email_client import _customer_shop_info

    with Session(engine) as session:
        tenant = Tenant(name="Mister Minit Chadstone", slug=f"minit-{uuid4().hex[:6]}", is_minit=True)
        session.add(tenant)
        session.commit()
        info = _customer_shop_info("Mister Minit Chadstone", session, tenant.id)
        assert info.logo_url and info.logo_url.endswith(MINIT_LOGO_PUBLIC_PATH)
        assert info.brand_color

        # No session or tenant: just the name, as before.
        assert _customer_shop_info("Shop", None, None).logo_url is None


def test_shoe_status_page_flags_minit_shops(client: TestClient):
    from tests.test_customer_portal_lookup import _create_shoe_job

    headers = _bootstrap(client)
    slug = headers.pop("tenant_slug")
    job = _create_shoe_job(client, headers, f"shoe-{uuid4().hex[:8]}@portal.test", "Heels")
    _mark_minit(slug)

    res = client.get(f"/v1/public/shoe-jobs/{job.status_token}")
    assert res.status_code == 200, res.text
    assert res.json()["shop"]["is_minit"] is True
    assert res.json()["shop"]["logo_url"].endswith(MINIT_LOGO_PUBLIC_PATH)
