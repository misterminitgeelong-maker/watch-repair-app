"""Global search endpoint."""


def test_global_search_finds_repair_job(client, auth_headers, make_customer, make_watch):
    headers = auth_headers
    customer_id = make_customer(headers, full_name="Search Test", email="search-unique@test.com")
    watch_id = make_watch(headers, customer_id, brand="Omega", model="Speedmaster")
    create = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={
            "watch_id": watch_id,
            "title": "Unique Searchable Title XYZ",
            "status": "awaiting_go_ahead",
        },
    )
    assert create.status_code in (200, 201), create.text

    r = client.get("/v1/search", params={"q": "Unique Searchable"}, headers=headers)
    assert r.status_code == 200
    kinds = {h["kind"] for h in r.json()["hits"]}
    assert "repair_job" in kinds
