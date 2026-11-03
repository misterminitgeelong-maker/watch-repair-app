"""Helpers that keep capability tokens and contact details out of logs."""
from __future__ import annotations

import re

_SEGMENT_CHARS = re.compile(r"^[A-Za-z0-9_\-=.~]+$")
_URL_IN_TEXT = re.compile(r"(https?://[^\s/]+)(/[^\s?#]*)")
_EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Routes whose path carries a bearer capability (token / status token / invite).
_TOKENISED_PREFIXES = ("/v1/public/",)


def _is_token_segment(seg: str) -> bool:
    """Route words are lowercase letters and hyphens; random tokens contain digits,
    capitals or underscores (and are long)."""
    if len(seg) < 8 or not _SEGMENT_CHARS.match(seg):
        return False
    return any(c.isdigit() or c.isupper() or c == "_" for c in seg)


def _redact_segments(path: str) -> str:
    return "/".join("[token]" if _is_token_segment(p) else p for p in path.split("/"))


def redact_path(path: str) -> str:
    """Replace token-looking segments of public/tokenised routes with ``[token]``."""
    if path and path.startswith(_TOKENISED_PREFIXES):
        return _redact_segments(path)
    return path


def mask_phone(value: str | None) -> str:
    """Keep only the last 3 digits: ``+61412345678`` -> ``***678``."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return f"***{digits[-3:]}" if len(digits) >= 3 else "***"


def mask_email(value: str | None) -> str:
    """Keep first character and domain: ``jane@example.com`` -> ``j***@example.com``."""
    if not value:
        return ""
    s = str(value)
    if "@" not in s:
        return "***"
    local, _, domain = s.rpartition("@")
    return f"{local[:1]}***@{domain}"


def redact_text(text: str | None) -> str:
    """Redact URL token segments and email addresses inside free text (message bodies)."""
    if not text:
        return ""
    s = _URL_IN_TEXT.sub(lambda m: m.group(1) + _redact_segments(m.group(2)), text)
    return _EMAIL_IN_TEXT.sub(lambda m: mask_email(m.group(0)), s)
