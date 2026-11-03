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
from sqlalchemy.exc import IntegrityError

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context
from ..models import NetworkConversation, NetworkMessage, Tenant, TenantEventLog, User
from ..models import Region
from ..models.network_community import NetworkMessageAttachment
from ..parent_network import site_for_tenant_in_parent
from ..parent_network import sites_for_parent, sites_for_tenant
from ..shop_number import format_tenant_label

router = APIRouter(prefix="/v1/network-messages", tags=["network-messages"])

EVENT_TYPE = "network_message"


class ContactRead(BaseModel):
    tenant_id: UUID
    name: str
    network_role: str
    state_code: str | None = None
    shop_number: str | None = None


class ConversationRead(BaseModel):
    id: UUID
    parent_account_id: UUID
    other_tenant_id: UUID
    other_name: str
    last_message_at: datetime
    last_body: str | None = None
    unread: int = 0


class NetworkAttachmentRead(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int


def _attachments(session, message_id, hub=False):
    column = NetworkMessageAttachment.hub_message_id if hub else NetworkMessageAttachment.direct_message_id
    rows = session.exec(select(NetworkMessageAttachment.id, NetworkMessageAttachment.filename, NetworkMessageAttachment.content_type, NetworkMessageAttachment.size_bytes).where(column == message_id)).all()
    return [NetworkAttachmentRead(id=row[0], filename=row[1], content_type=row[2], size_bytes=row[3]) for row in rows]


def _attachments_by_message(session, message_ids, hub=False):
    if not message_ids:
        return {}
    column = NetworkMessageAttachment.hub_message_id if hub else NetworkMessageAttachment.direct_message_id
    rows = session.exec(select(column, NetworkMessageAttachment.id, NetworkMessageAttachment.filename, NetworkMessageAttachment.content_type, NetworkMessageAttachment.size_bytes).where(col(column).in_(message_ids))).all()
    out: dict = {}
    for mid, aid, name, ctype, size in rows:
        out.setdefault(mid, []).append(NetworkAttachmentRead(id=aid, filename=name, content_type=ctype, size_bytes=size))
    return out


class MessageRead(BaseModel):
    id: UUID
    sender_tenant_id: UUID
    mine: bool
    sender_name: str | None = None
    body: str
    created_at: datetime
    conversation_id: UUID | None = None
    attachments: list[NetworkAttachmentRead] = Field(default_factory=list)


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
    if not site_for_tenant_in_parent(session, conv.parent_account_id, me):
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
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Every other active site in the networks this site belongs to."""
    _own_context(auth)
    found: dict[UUID, str] = {}
    mine_sites = sites_for_tenant(session, auth.tenant_id)
    if parent_account_id and not any(s.parent_account_id == parent_account_id for s in mine_sites):
        raise HTTPException(status_code=403, detail="Network not available")
    for mine in mine_sites:
        if parent_account_id and mine.parent_account_id != parent_account_id:
            continue
        for site in sites_for_parent(session, mine.parent_account_id):
            if site.tenant_id != auth.tenant_id:
                found.setdefault(site.tenant_id, site.network_role)
    live_ids = set(session.exec(select(User.tenant_id).where(User.is_active == True, col(User.tenant_id).in_(list(found)))).all())  # noqa: E712
    out: list[ContactRead] = []
    for tid, role in found.items():
        t = session.get(Tenant, tid)
        if t and t.is_active and not t.merged_into_tenant_id and tid in live_ids:
            from .network_community import state_code
            site = site_for_tenant_in_parent(session, parent_account_id, tid) if parent_account_id else None
            region = session.get(Region, site.region_id) if site and site.region_id else None
            out.append(ContactRead(tenant_id=tid, name=_label(t), network_role=role, shop_number=t.shop_number, state_code=state_code(region.code if region else t.minit_region)))
    out.sort(key=lambda c: c.name.lower())
    return out


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    parent_account_id: UUID | None = None,
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
    my_parents = {s.parent_account_id for s in sites_for_tenant(session, me)}
    if parent_account_id and parent_account_id not in my_parents:
        raise HTTPException(status_code=403, detail="Network not available")
    convs = [c for c in convs if c.parent_account_id in my_parents and (not parent_account_id or c.parent_account_id == parent_account_id)]
    ids = [c.id for c in convs]
    unread_by: dict = {}
    last_by: dict = {}
    if ids:
        unread_by = dict(session.exec(
            select(NetworkMessage.conversation_id, func.count()).where(col(NetworkMessage.conversation_id).in_(ids))
            .where(NetworkMessage.sender_tenant_id != me).where(col(NetworkMessage.read_at).is_(None))
            .group_by(NetworkMessage.conversation_id)
        ).all())
        newest = (select(NetworkMessage.conversation_id.label("cid"), func.max(NetworkMessage.created_at).label("m"))
                  .where(col(NetworkMessage.conversation_id).in_(ids)).group_by(NetworkMessage.conversation_id).subquery())
        for m in session.exec(select(NetworkMessage).join(newest, (NetworkMessage.conversation_id == newest.c.cid) & (NetworkMessage.created_at == newest.c.m))).all():
            last_by[m.conversation_id] = m
    other_ids = {_other(c, me) for c in convs}
    tenants = {t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_(other_ids))).all()} if other_ids else {}
    for c in convs:
        last = last_by.get(c.id)
        out.append(ConversationRead(
            id=c.id, parent_account_id=c.parent_account_id, other_tenant_id=_other(c, me), other_name=_label(tenants.get(_other(c, me))),
            last_message_at=c.last_message_at, last_body=last.body[:140] if last else None, unread=int(unread_by.get(c.id, 0)),
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
    files = _attachments_by_message(session, [m.id for m in rows])
    return [
        MessageRead(
            id=m.id, sender_tenant_id=m.sender_tenant_id, mine=m.sender_tenant_id == me,
            sender_name=(users[m.sender_user_id].full_name or users[m.sender_user_id].email) if m.sender_user_id in users else None,
            body=m.body, created_at=m.created_at, conversation_id=conv.id, attachments=files.get(m.id, []),
        )
        for m in reversed(rows)
    ]


def _prepare_direct(session, auth, tenant_id, body, parent_account_id=None):
    _own_context(auth)
    me = auth.tenant_id
    if tenant_id == me:
        raise HTTPException(status_code=400, detail="You cannot message your own site")
    other = session.get(Tenant, tenant_id)
    if not other or not other.is_active or other.merged_into_tenant_id or not session.exec(select(User.id).where(User.tenant_id == tenant_id, User.is_active == True)).first():  # noqa: E712
        raise HTTPException(status_code=404, detail="Site not found")
    parent_id = parent_account_id or _shared_parent(session, me, tenant_id)
    if parent_account_id and (not site_for_tenant_in_parent(session, parent_account_id, me) or not site_for_tenant_in_parent(session, parent_account_id, tenant_id)):
        raise HTTPException(status_code=403, detail="You can only message sites in your own network")
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
        try:
            with session.begin_nested():
                conv = NetworkConversation(parent_account_id=parent_id, tenant_low_id=low, tenant_high_id=high)
                session.add(conv)
                session.flush()
        except IntegrityError:
            conv = session.exec(select(NetworkConversation).where(
                NetworkConversation.parent_account_id == parent_id,
                NetworkConversation.tenant_low_id == low, NetworkConversation.tenant_high_id == high,
            )).first()
            if conv is None:
                raise
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
    session.flush()
    return msg, user


@router.post("/with/{tenant_id}", response_model=MessageRead, status_code=201)
def send_message(
    tenant_id: UUID,
    body: SendBody,
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Send a message to another site in a shared network, starting the thread if needed."""
    msg, user = _prepare_direct(session, auth, tenant_id, body, parent_account_id)
    session.commit()
    session.refresh(msg)
    return MessageRead(
        id=msg.id, sender_tenant_id=auth.tenant_id, mine=True,
        sender_name=(user.full_name or user.email) if user else None, body=msg.body, created_at=msg.created_at, conversation_id=msg.conversation_id, attachments=_attachments(session, msg.id),
    )

