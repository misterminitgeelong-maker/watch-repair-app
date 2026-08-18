"""Phone normalisation used by inbound SMS routing and the phone_normalized backfill."""
from app.phone_utils import normalize_phone


def test_normalize_phone_au_mobile_forms():
    assert normalize_phone("+61412345678") == "0412345678"
    assert normalize_phone("0412 345 678") == "0412345678"
    assert normalize_phone("412345678") == "0412345678"
    assert normalize_phone("03 5221 1234") == "0352211234"
    assert normalize_phone("") is None
    assert normalize_phone("123") is None
