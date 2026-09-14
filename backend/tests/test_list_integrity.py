"""List endpoints must not silently drop rows, and must not accept unbounded pages."""
from sqlmodel import Session

from app.database import engine
from app.models import AutoKeyJob, Customer
from app.security import decode_access_token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_auto_key_jobs(token: str, count: int) -> None:
    ctx = decode_access_token(token)
    with Session(engine) as session:
        customer = Customer(tenant_id=ctx.tenant_id, full_name="List Bulk", phone="0400000000")
        session.add(customer)
        session.commit()
        session.refresh(customer)
        session.add_all(
            [
                AutoKeyJob(
                    tenant_id=ctx.tenant_id,
                    customer_id=customer.id,
                    job_number=f"AK-{i:05d}",
                    title=f"Bulk {i}",
                )
                for i in range(count)
            ]
        )
        session.commit()


def test_auto_key_list_exposes_total_when_page_is_capped(client, bootstrap_and_login):
    token = bootstrap_and_login(password="supersecret123", plan_code="enterprise")
    headers = _headers(token)
    _seed_auto_key_jobs(token, 501)

    first = client.get("/v1/auto-key-jobs", headers=headers)
    assert first.status_code == 200, first.text
    assert len(first.json()) == 500
    assert first.headers.get("x-total-count") == "501"

    rest = client.get("/v1/auto-key-jobs", headers=headers, params={"skip": 500, "limit": 500})
    assert rest.status_code == 200, rest.text
    assert len(rest.json()) == 1
    assert rest.headers.get("x-total-count") == "501"


def test_repair_jobs_and_quotes_reject_unbounded_limit(client, bootstrap_and_login):
    token = bootstrap_and_login(password="supersecret123")
    headers = _headers(token)

    jobs = client.get("/v1/repair-jobs", headers=headers, params={"limit": 20000})
    assert jobs.status_code == 422

    quotes = client.get("/v1/quotes", headers=headers, params={"limit": 20000})
    assert quotes.status_code == 422

    ok_jobs = client.get("/v1/repair-jobs", headers=headers, params={"limit": 500})
    assert ok_jobs.status_code == 200, ok_jobs.text
    assert "x-total-count" in {k.lower() for k in ok_jobs.headers.keys()}

    ok_quotes = client.get("/v1/quotes", headers=headers, params={"limit": 500})
    assert ok_quotes.status_code == 200, ok_quotes.text
    assert "x-total-count" in {k.lower() for k in ok_quotes.headers.keys()}
