"""Phone push notifications through Firebase Cloud Messaging (HTTP v1).

Sending is off unless ``FCM_SERVICE_ACCOUNT_JSON`` holds a Firebase service-account
key. New shop inbox alerts (``TenantEventLog`` rows of an inbox type) are pushed to
every registered device in that shop once the transaction that created them commits.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from uuid import UUID

import httpx
import jwt
from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession, object_session
from sqlmodel import Session, select

from .config import settings
from .database import engine
from .models import DeviceToken, TenantEventLog

logger = logging.getLogger(__name__)

PUSH_EVENT_TYPES = frozenset({
    "quote_approved",
    "quote_declined",
    "mobile_lead_quote_needed",
    "inbound_email_received",
    "shop_booking_pending",
    "invoice_paid",
    "customer_sms_reply",
    "portal_customer_message",
    "portal_booking_received",
    "card_payment_needs_attention",
})

_QUEUE_KEY = "push_queue"
_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_access: dict[str, float | str] = {"token": "", "expires_at": 0.0}
_access_lock = threading.Lock()


def _service_account() -> dict | None:
    raw = (settings.fcm_service_account_json or "").strip()
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("FCM_SERVICE_ACCOUNT_JSON is not valid JSON; push disabled")
        return None
    if not all(info.get(k) for k in ("client_email", "private_key", "project_id")):
        logger.warning("FCM_SERVICE_ACCOUNT_JSON is missing fields; push disabled")
        return None
    return info


def fcm_enabled() -> bool:
    return _service_account() is not None


def _access_token(info: dict) -> str:
    with _access_lock:
        if _access["token"] and float(_access["expires_at"]) - 60 > time.time():
            return str(_access["token"])
        now = int(time.time())
        token_uri = info.get("token_uri") or "https://oauth2.googleapis.com/token"
        assertion = jwt.encode(
            {"iss": info["client_email"], "scope": _SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
            info["private_key"],
            algorithm="RS256",
        )
        res = httpx.post(
            token_uri,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            timeout=10,
        )
        res.raise_for_status()
        body = res.json()
        _access["token"] = body["access_token"]
        _access["expires_at"] = now + int(body.get("expires_in", 3600))
        return str(_access["token"])


def send_to_tokens(tokens: list[str], title: str, body: str) -> list[str]:
    """Send one notification to each token; returns tokens FCM says are no longer valid."""
    info = _service_account()
    if not info or not tokens:
        return []
    url = f"https://fcm.googleapis.com/v1/projects/{info['project_id']}/messages:send"
    headers = {"Authorization": f"Bearer {_access_token(info)}"}
    dead: list[str] = []
    for token in tokens:
        payload = {"message": {"token": token, "notification": {"title": title, "body": body}}}
        try:
            res = httpx.post(url, json=payload, headers=headers, timeout=10)
        except httpx.HTTPError:
            logger.warning("FCM send failed", exc_info=True)
            continue
        if res.status_code == 404 or (res.status_code == 400 and "UNREGISTERED" in res.text):
            dead.append(token)
        elif res.status_code >= 400:
            logger.warning("FCM rejected a push: %s %s", res.status_code, res.text[:200])
    return dead


def notify_tenant(tenant_id: UUID, title: str, body: str) -> None:
    """Push to every registered device in a shop, pruning tokens FCM reports as dead."""
    if not fcm_enabled():
        return
    with Session(engine) as db:
        tokens = list(db.exec(select(DeviceToken.token).where(DeviceToken.tenant_id == tenant_id)).all())
        if not tokens:
            return
        dead = send_to_tokens(tokens, title, body)
        if dead:
            for row in db.exec(select(DeviceToken).where(DeviceToken.token.in_(dead))).all():
                db.delete(row)
            db.commit()


def _dispatch(items: list[tuple[UUID, str, str]]) -> None:
    def run() -> None:
        for tenant_id, title, body in items:
            try:
                notify_tenant(tenant_id, title, body)
            except Exception:
                logger.exception("Push notification failed")

    threading.Thread(target=run, daemon=True).start()


_installed = False


def install_push_hooks() -> None:
    """Queue a push for each new inbox alert and send it after the commit succeeds."""
    global _installed
    if _installed:
        return
    _installed = True

    @event.listens_for(TenantEventLog, "after_insert")
    def _queue(mapper, connection, target):  # noqa: ARG001
        if target.event_type not in PUSH_EVENT_TYPES:
            return
        session = object_session(target)
        if session is not None:
            session.info.setdefault(_QUEUE_KEY, []).append((target.tenant_id, "Mainspring", target.event_summary))

    @event.listens_for(OrmSession, "after_commit")
    def _send(session):
        items = session.info.pop(_QUEUE_KEY, None)
        if items and fcm_enabled():
            _dispatch(items)

    @event.listens_for(OrmSession, "after_rollback")
    def _drop(session):
        session.info.pop(_QUEUE_KEY, None)
