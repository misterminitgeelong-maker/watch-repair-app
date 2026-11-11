"""Shared display/storage names for manual mobile payments, including older apps."""
def normalise_payment_method(value: str | None) -> str | None:
    cleaned = (value or "").strip().lower()
    return {"card": "eftpos", "bank_transfer": "bank"}.get(cleaned, cleaned) or None
