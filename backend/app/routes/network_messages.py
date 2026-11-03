"""Direct messages between sites (shops, operators, HQ) that share a network.

Only the two participants can read a thread: HQ staff cannot read other sites'
conversations, including when they open a shop through a support session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, col, func, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context
from ..models import NetworkConversation, NetworkMessage, Tenant, TenantEventLog, User
from ..parent_network import sites_for_parent, sites_for_tenant
from ..shop_number import format_tenant_label

router = APIRouter(prefix="/v1/network-messages", tags=["network-messages"])

EVENT_TYPE = "network_message"


class ContactRead(BaseModel):
    tenant_id: UUID
    name: str
    network_role: str


class ConversationRead(BaseModel):
    id: UUID
    other_tenant_id: UUID
    other_name: str
    last_message_at: datetime
    last_body: str | None = None
    unread: int = 0


class MessageRead(BaseModel):
    id: UUID
    sender_tenant_id: UUID
    mine: bool
    sender_name: str | None = None
    body: str
    created_at: datetime


class SendBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _own_context(auth: AuthContext) -> None:
    if auth.support_actor_user_id is not None:
        raise HTTPException(status_code=403, detail="Support access cannot use site messaging")


def _label(t: Tenant | None) -> str:
    return format_tenant_label(t.name, t.shop_number) if t else "Site"


def _shared_parent(session: Session, me: UUID, other: UUID) -> UUID | None:
    mine = {s.parent_account_id for s in sites_for_tenant(session, me)}
    for site in sites_for_tenant(session, other):
        if site.parent_account_id in mine:
            return site.parent_account_id
    return None


def _pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


def _other(conv: NetworkConversation, me: UUID) -> UUID:
    return conv.tenant_high_id if conv.tenant_low_id == me else conv.tenant_low_id


def _get_mine(session: Session, conv_id: UUID, me: UUID) -> NetworkConversation:
    conv = session.get(NetworkConversation, conv_id)
    if not conv or me not in (conv.tenant_low_id, conv.tenant_high_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _clear_alerts(session: Session, tenant_id: UUID, conv_id: UUID) -> None:
    for ev in session.exec(
        select(TenantEventLog)
        .where(TenantEventLog.tenant_id == tenant_id)
        .where(TenantEventLog.event_type == EVENT_TYPE)
        .where(TenantEventLog.entity_id == conv_id)
    ).all():
        session.delete(ev)


@router.get("/contacts", response_model=list[ContactRead])
def list_contacts(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Every other active site in the networks this site belongs to."""
    _own_context(auth)
    found: dict[UUID, str] = {}
    for mine in sites_for_tenant(session, auth.tenant_id):
        for site in sites_for_parent(session, mine.parent_account_id):
            if site.tenant_id != auth.tenant_id:
                found.setdefault(site.tenant_id, site.network_role)
    out: list[ContactRead] = []
    for tid, role in found.items():
        t = session.get(Tenant, tid)
        if t and t.is_active and not t.merged_into_tenant_id:
            out.append(ContactRead(tenant_id=tid, name=_label(t), network_role=role))
    out.sort(key=lambda c: c.name.lower())
    return out


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    _own_context(auth)
    me = auth.tenant_id
    convs = session.exec(
        select(NetworkConversation)
        .where((NetworkConversation.tenant_low_id == me) | (NetworkConversation.tenant_high_id == me))
        .order_by(col(NetworkConversation.last_message_at).desc())
        .limit(200)
    ).all()
    out: list[ConversationRead] = []
    for c in convs:
        last = session.exec(
            select(NetworkMessage).where(NetworkMessage.conversation_id == c.id)
            .order_by(col(NetworkMessage.created_at).desc()).limit(1)
        ).first()
        unread = session.exec(
            select(func.count()).select_from(NetworkMessage)
            .where(NetworkMessage.conversation_id == c.id)
            .where(NetworkMessage.sender_tenant_id != me)
            .where(col(NetworkMessage.read_at).is_(None))
        ).one()
        other = session.get(Tenant, _other(c, me))
        out.append(ConversationRead(
            id=c.id, other_tenant_id=_other(c, me), other_name=_label(other),
            last_message_at=c.last_message_at, last_body=last.body[:140] if last else None, unread=int(unread),
        ))
    return out


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageRead])
def list_messages(
    conv_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Opening a thread marks the other site's messages as read and clears its Inbox alert."""
    _own_context(auth)
    me = auth.tenant_id
    conv = _get_mine(session, conv_id, me)
    rows = session.exec(
        select(NetworkMessage).where(NetworkMessage.conversation_id == conv.id)
        .order_by(col(NetworkMessage.created_at).desc()).limit(200)
    ).all()
    now = datetime.now(timezone.utc)
    for m in rows:
        if m.sender_tenant_id != me and m.read_at is None:
            m.read_at = now
            session.add(m)
    _clear_alerts(session, me, conv.id)
    session.commit()
    users = {u.id: u for u in session.exec(select(User).where(col(User.id).in_([m.sender_user_id for m in rows if m.sender_user_id]))).all()} if rows else {}
    return [
        MessageRead(
            id=m.id, sender_tenant_id=m.sender_tenant_id, mine=m.sender_tenant_id == me,
            sender_name=(users[m.sender_user_id].full_name or users[m.sender_user_id].email) if m.sender_user_id in users else None,
            body=m.body, created_at=m.created_at,
        )
        for m in reversed(rows)
    ]


@router.post("/with/{tenant_id}", response_model=MessageRead, status_code=201)
def send_message(
    tenant_id: UUID,
    body: SendBody,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Send a message to another site in a shared network, starting the thread if needed."""
    _own_context(auth)
    me = auth.tenant_id
    if tenant_id == me:
        raise HTTPException(status_code=400, detail="You cannot message your own site")
    other = session.get(Tenant, tenant_id)
    if not other or not other.is_active or other.merged_into_tenant_id:
        raise HTTPException(status_code=404, detail="Site not found")
    parent_id = _shared_parent(session, me, tenant_id)
    if parent_id is None:
        raise HTTPException(status_code=403, detail="You can only message sites in your own network")
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")

    low, high = _pair(me, tenant_id)
    conv = session.exec(
        select(NetworkConversation)
        .where(NetworkConversation.parent_account_id == parent_id)
        .where(NetworkConversation.tenant_low_id == low)
        .where(NetworkConversation.tenant_high_id == high)
    ).first()
    if conv is None:
        conv = NetworkConversation(parent_account_id=parent_id, tenant_low_id=low, tenant_high_id=high)
        session.add(conv)
        session.flush()
    msg = NetworkMessage(conversation_id=conv.id, sender_tenant_id=me, sender_user_id=auth.user_id, body=text)
    conv.last_message_at = msg.created_at
    session.add(msg)
    session.add(conv)

    sender = session.get(Tenant, me)
    user = session.get(User, auth.user_id)
    # One alert per thread: replace the previous one so a chatty thread can't bury the Inbox.
    _clear_alerts(session, tenant_id, conv.id)
    session.add(TenantEventLog(
        tenant_id=tenant_id,
        actor_user_id=auth.user_id,
        actor_email=user.email if user else None,
        entity_type="network_message",
        entity_id=conv.id,
        event_type=EVENT_TYPE,
        event_summary=f"Message from {_label(sender)}: {text[:200]}",
    ))
    session.commit()
    session.refresh(msg)
    return MessageRead(
        id=msg.id, sender_tenant_id=me, mine=True,
        sender_name=(user.full_name or user.email) if user else None, body=msg.body, created_at=msg.created_at,
    )
