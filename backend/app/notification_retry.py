"""Shared retry policy for outbound SMS and email.

Inline retries cover timeouts and 5xx only. A 4xx is a permanent rejection
(bad number, bounced recipient) and must not be retried — that burns quota
and delays everything behind it.
"""
from __future__ import annotations

from .config import settings

RETRYABLE_HTTP_MIN = 500


def inline_retry_attempts() -> int:
    return max(int(settings.notification_inline_retry_attempts), 1)


def redelivery_max_attempts() -> int:
    return max(int(settings.notification_redelivery_max_attempts), 1)


def backoff_seconds(attempt_index: int) -> float:
    """Bounded exponential delay before attempt_index (0-based) is issued after a failure."""
    base = max(float(settings.notification_retry_backoff_seconds), 0.05)
    cap = max(float(settings.notification_retry_backoff_cap_seconds), base)
    return min(cap, base * (2**attempt_index))


def is_retryable_http_status(status: int | None) -> bool:
    if status is None:
        return False
    return status >= RETRYABLE_HTTP_MIN


def http_status_from_exc(exc: BaseException) -> int | None:
    raw = getattr(exc, "status", None)
    if isinstance(raw, int) and 100 <= raw <= 599:
        return raw
    raw = getattr(exc, "status_code", None)
    if isinstance(raw, int) and 100 <= raw <= 599:
        return raw
    return None


def is_timeout_exc(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    if "timeout" in name or "timedout" in name:
        return True
    if isinstance(exc, TimeoutError):
        return True
    return False


def is_transport_exc(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    return any(token in name for token in ("connection", "transport", "network", "connecterror"))


def should_retry_exc(exc: BaseException) -> bool:
    status = http_status_from_exc(exc)
    if status is not None:
        return is_retryable_http_status(status)
    return is_timeout_exc(exc) or is_transport_exc(exc)


def pin_attempts_if_permanent(attempt_count: int, *, permanent: bool) -> int:
    """On 4xx, jump to the cap so the out-of-band sweep will not pick the row up."""
    if permanent:
        return max(attempt_count, redelivery_max_attempts())
    return attempt_count
