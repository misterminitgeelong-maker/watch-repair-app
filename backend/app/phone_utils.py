"""Phone normalisation shared by inbound SMS routing and message-thread merging."""
import re


def normalize_phone(raw: str) -> str | None:
    if not raw or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw.strip())
    if not digits:
        return None
    # AU international → local (e.g. +61412345678 → 0412345678)
    if digits.startswith("61") and len(digits) >= 11:
        digits = "0" + digits[2:11]
    # NZ international → local (e.g. +64211234567 → 0211234567). National numbers are
    # 9-11 digits with the trunk 0, so the international form is 64 + 8-10 digits.
    elif digits.startswith("64") and 10 <= len(digits) <= 12:
        digits = "0" + digits[2:]
    if len(digits) == 9 and digits[0] in ("4", "3"):
        digits = "0" + digits
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) < 8:
        return None
    return digits


def phones_match(a: str | None, b: str | None) -> bool:
    left = normalize_phone(a or "")
    right = normalize_phone(b or "")
    return bool(left and right and left == right)


def phone_lookup_variants(raw: str) -> list[str]:
    """Exact plus normalized AU forms so SmsLog.to_phone can be queried without a scan."""
    variants: set[str] = set()
    stripped = (raw or "").strip()
    if stripped:
        variants.add(stripped)
    normalized = normalize_phone(raw or "")
    if normalized:
        variants.add(normalized)
        if normalized.startswith("0") and len(normalized) == 10:
            variants.add("+61" + normalized[1:])
            variants.add("61" + normalized[1:])
        if normalized.startswith("0") and 9 <= len(normalized) <= 11:
            variants.add("+64" + normalized[1:])
            variants.add("64" + normalized[1:])
    return [v for v in variants if v]
