"""Phone normalisation used by inbound SMS routing and the phone_normalized backfill."""
from app.phone_utils import normalize_phone


def test_normalize_phone_au_mobile_forms():
    assert normalize_phone("+61412345678") == "0412345678"
    assert normalize_phone("0412 345 678") == "0412345678"
    assert normalize_phone("412345678") == "0412345678"
    assert normalize_phone("03 5221 1234") == "0352211234"
    assert normalize_phone("") is None
    assert normalize_phone("123") is None


def test_normalize_phone_nz_forms():
    from app.phone_utils import phones_match, phone_lookup_variants

    assert normalize_phone("+64 21 123 4567") == "0211234567"
    assert normalize_phone("021 123 4567") == "0211234567"
    assert normalize_phone("+6493001234") == "093001234"
    assert phones_match("+64211234567", "021 123 4567")
    assert "+64211234567" in phone_lookup_variants("0211234567")
