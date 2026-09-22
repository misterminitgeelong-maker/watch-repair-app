"""Which failures on the customer-facing link paths are worth alerting on.

The middleware treats a set of paths as critical customer workflows and raises a
``CRITICAL_WORKFLOW_FAILURE`` (logged at error, captured by Sentry) for any 4xx/5xx
on them. The single-use SMS links are the exception: their tokens are cleared on
use, so a 404 is the designed outcome for a link that was already used, and a
customer re-tapping one must not page anybody.
"""

import logging

from fastapi.testclient import TestClient

from app.main import _classify_critical_workflow, _is_spent_public_link

PUBLIC_LINK_PATHS = (
    "/v1/public/auto-key-intake/6a1af8e368194cbcb4336ae269c4dbc9",
    "/v1/public/auto-key-booking/6a1af8e368194cbcb4336ae269c4dbc9",
    "/v1/public/auto-key-invoice/6a1af8e368194cbcb4336ae269c4dbc9",
)

REQUEST_LOGGER = "mainspring.requests"


def test_spent_public_link_is_a_404_on_a_customer_link():
    for path in PUBLIC_LINK_PATHS:
        assert _is_spent_public_link(path, 404) is True


def test_server_errors_on_a_customer_link_still_alert():
    for path in PUBLIC_LINK_PATHS:
        assert _is_spent_public_link(path, 500) is False
        assert _is_spent_public_link(path, 502) is False


def test_the_4xx_that_mean_something_still_alert():
    """422 is a broken request contract, 429 is a customer being rate-limited."""
    path = PUBLIC_LINK_PATHS[0]
    for status in (400, 422, 429):
        assert _is_spent_public_link(path, status) is False


def test_404_on_the_operator_and_cron_paths_still_alerts():
    """Only the public single-use links are exempt — these have no spent-token case."""
    assert _is_spent_public_link("/v1/auto-key-jobs/day-before-reminders", 404) is False
    assert _is_spent_public_link("/v1/auto-key-jobs/invoices/abc", 404) is False
    assert _is_spent_public_link("/v1/auto-key-jobs", 404) is False


def test_classification_is_unchanged():
    """The exemption gates the alert; it must not reclassify what an alert is."""
    assert _classify_critical_workflow(PUBLIC_LINK_PATHS[0], "GET") == "quick_intake_failure"
    assert _classify_critical_workflow(PUBLIC_LINK_PATHS[1], "GET") == "public_booking_failure"
    assert _classify_critical_workflow(PUBLIC_LINK_PATHS[2], "GET") == "public_invoice_failure"
    assert (
        _classify_critical_workflow("/v1/auto-key-jobs/day-before-reminders", "POST")
        == "day_before_reminder_failure"
    )
    assert _classify_critical_workflow("/v1/auto-key-jobs/invoices/abc", "PATCH") == "invoice_update_failure"
    assert _classify_critical_workflow("/v1/customers", "GET") is None


def test_reopening_a_spent_intake_link_does_not_alert(client: TestClient, caplog):
    """The regression: an unknown/used intake token 404s without paging anybody."""
    with caplog.at_level(logging.INFO, logger=REQUEST_LOGGER):
        res = client.get("/v1/public/auto-key-intake/6a1af8e368194cbcb4336ae269c4dbc9")

    assert res.status_code == 404
    messages = [r.getMessage() for r in caplog.records if r.name == REQUEST_LOGGER]
    assert not any("CRITICAL_WORKFLOW_FAILURE" in m for m in messages), messages
    assert any("PUBLIC_LINK_SPENT" in m for m in messages), messages


def test_a_real_failure_on_a_critical_path_still_alerts(client: TestClient, caplog):
    """Contrast case — an unauthenticated cron call is still an alert."""
    with caplog.at_level(logging.INFO, logger=REQUEST_LOGGER):
        res = client.post("/v1/auto-key-jobs/day-before-reminders")

    assert res.status_code >= 400
    messages = [r.getMessage() for r in caplog.records if r.name == REQUEST_LOGGER]
    assert any("CRITICAL_WORKFLOW_FAILURE" in m for m in messages), messages
    assert any("day_before_reminder_failure" in m for m in messages), messages
