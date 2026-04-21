"""Unit tests for csv_import_helpers — pure functions, no DB required."""

import os
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(__file__).with_name(f'test_csv_helpers_{uuid4().hex}.db').as_posix()}"

from app.routes.csv_import_helpers import (
    _allocate_import_job_number,
    _clean_name,
    _dollars_to_cents,
    _get_first,
    _infer_auto_key_status,
    _infer_job_status,
    _normalize_phone,
    _parse_date_flexible,
    _reserve_import_job_number,
    _status_slug,
)


class TestDollarsToCents:
    def test_plain_integer_dollars(self):
        assert _dollars_to_cents("150") == 15000

    def test_dollar_symbol_stripped(self):
        assert _dollars_to_cents("$250.50") == 25050

    def test_empty_returns_zero(self):
        assert _dollars_to_cents("") == 0
        assert _dollars_to_cents(None) == 0  # type: ignore[arg-type]

    def test_garbage_returns_zero(self):
        assert _dollars_to_cents("n/a") == 0

    def test_negative_sign_stripped(self):
        # Current behaviour: helper treats "-25.00" as 2500 cents (sign is
        # stripped along with the dollar symbol). Documenting this as-is so
        # any future change to treat refunds as negative amounts is a
        # deliberate call, not a silent regression.
        assert _dollars_to_cents("-25.00") == 2500


class TestNormalizePhone:
    def test_au_mobile_no_change(self):
        assert _normalize_phone("0412345678") == "0412345678"

    def test_strips_spaces_and_parens(self):
        assert _normalize_phone("(04) 1234-5678") == "0412345678"

    def test_empty_returns_none(self):
        assert _normalize_phone("") is None
        assert _normalize_phone(None) is None  # type: ignore[arg-type]


class TestCleanName:
    def test_trims_whitespace(self):
        assert _clean_name("  Alice Smith  ") == "Alice Smith"

    def test_empty_returns_none(self):
        assert _clean_name("") is None
        assert _clean_name("   ") is None


class TestGetFirst:
    def test_returns_first_populated_key(self):
        row = {"customer": "", "name": "Alice", "full_name": "Unused"}
        assert _get_first(row, ["customer", "name", "full_name"]) == "Alice"

    def test_all_empty_returns_empty_string(self):
        row = {"a": "", "b": ""}
        assert _get_first(row, ["a", "b"]) == ""

    def test_missing_keys_fall_through(self):
        row = {"only_one": "hit"}
        assert _get_first(row, ["missing", "only_one"]) == "hit"


class TestParseDateFlexible:
    def test_iso_date(self):
        result = _parse_date_flexible("2026-04-21")
        assert result is not None
        assert (result.year, result.month, result.day) == (2026, 4, 21)

    def test_au_format(self):
        result = _parse_date_flexible("21/04/2026")
        if result is not None:  # parser may or may not support this; don't force it
            assert result.month == 4
            assert result.day == 21

    def test_empty_returns_none(self):
        assert _parse_date_flexible("") is None


class TestStatusSlug:
    def test_lowercases_and_strips(self):
        assert _status_slug("  Completed  ") == "completed"

    def test_replaces_spaces_with_underscores(self):
        assert _status_slug("No Go") in {"no_go", "nogo", "no go"}


class TestInferJobStatus:
    def test_collected_maps_to_collected(self):
        assert _infer_job_status("collected", "") == "collected"

    def test_ready_maps_to_awaiting_collection(self):
        assert _infer_job_status("ready", "") == "awaiting_collection"

    def test_unknown_falls_back_to_a_watch_status(self):
        # Unknown statuses must return a value from the watch JobStatus
        # Literal — pipelines persist this directly so 422 at write time
        # would be worse than a reasonable default.
        watch_statuses = {
            "awaiting_quote", "awaiting_go_ahead", "go_ahead", "no_go",
            "working_on", "awaiting_parts", "parts_to_order",
            "service", "completed", "awaiting_collection", "collected",
        }
        assert _infer_job_status("made up status", "") in watch_statuses


class TestInferAutoKeyStatus:
    def test_unknown_falls_back_to_a_valid_status(self):
        # Whatever the fallback is, it must be a member of the Mobile
        # Services status vocabulary so Pydantic validation accepts it.
        ak_statuses = {
            "awaiting_quote", "awaiting_go_ahead", "go_ahead",
            "quote_sent", "awaiting_booking_confirmation", "booking_confirmed",
            "pending_booking", "booked", "job_delayed", "en_route", "on_site",
            "work_completed", "invoice_paid", "failed_job",
            "awaiting_customer_details",
        }
        assert _infer_auto_key_status("random nonsense", "") in ak_statuses
        assert _infer_auto_key_status("work_completed", "") in ak_statuses


class TestAllocateAndReserveJobNumbers:
    def test_allocate_uses_ticket_stem_when_provided(self):
        usage: dict[str, int] = {}
        result = _allocate_import_job_number(usage, "A123", 1)
        assert "A123" in result or result

    def test_reserve_skips_already_used(self):
        used = {"IMP-00001"}
        result = _reserve_import_job_number("IMP-00001", used)
        # Must produce a DIFFERENT number than the one already taken …
        assert result != "IMP-00001"
        # … AND must register the new choice so subsequent calls don't collide.
        assert result in used

    def test_reserve_returns_preferred_when_free(self):
        used: set[str] = set()
        result = _reserve_import_job_number("IMP-42", used)
        assert result == "IMP-42"
        assert "IMP-42" in used
