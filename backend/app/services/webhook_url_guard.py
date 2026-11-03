"""SSRF guard for tenant-supplied outbound webhook URLs.

Rules: https only, no credentials in the URL, and every address the host resolves
to must be a public unicast address (no loopback, private, link-local incl. cloud
metadata 169.254.169.254, multicast, reserved, unspecified). The check runs when
the subscription is created and again at send time (DNS can change).

Test/ops hook: ``WEBHOOK_ALLOWED_HOSTS`` (comma-separated hostnames) bypasses the
address check for those exact hosts. https is still required.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit


class WebhookUrlError(ValueError):
    pass


def _allowed_hosts() -> set[str]:
    raw = os.environ.get("WEBHOOK_ALLOWED_HOSTS", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _resolve(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    ) and ip.is_global


def validate_webhook_url(url: str) -> str:
    """Return the normalised URL or raise WebhookUrlError."""
    url = (url or "").strip()
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        port = parts.port or 443
    except ValueError as exc:
        raise WebhookUrlError("Invalid webhook URL") from exc
    if parts.scheme != "https":
        raise WebhookUrlError("Webhook URL must use https")
    if not host:
        raise WebhookUrlError("Webhook URL must include a host")
    if parts.username or parts.password:
        raise WebhookUrlError("Webhook URL must not include credentials")
    if host in _allowed_hosts():
        return url
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".internal"):
        raise WebhookUrlError("Webhook URL host is not allowed")
    try:
        addrs = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            addrs = _resolve(host, port)
        except OSError as exc:
            raise WebhookUrlError("Webhook URL host could not be resolved") from exc
    if not addrs or not all(_is_public(a) for a in addrs):
        raise WebhookUrlError("Webhook URL must resolve to a public address")
    return url
