"""State conversations and announcements; never grants access to shop business data."""
from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from urllib.parse import quote
from pydantic import BaseModel, Field
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context
from ..models import NetworkMessage, ParentAccount, Region, Tenant, User
from ..models.network_community import AnnouncementReceipt, NetworkAnnouncement, StateHubMessage, StateHubRead, NetworkMessageAttachment
from ..parent_network import (
    parent_region_scope, parent_role_for_user, parents_for_user, sites_for_parent, sites_for_tenant,
)
from .network_messages import _label, _own_context, _attachments, _attachments_by_message, _get_mine, _prepare_direct, SendBody

router = APIRouter(prefix="/v1/network-community", tags=["network-community"])
STATES = {
    "VIC": "Victoria", "NSW": "New South Wales", "QLD": "Queensland",
    "WA": "Western Australia", "SA": "South Australia", "TAS": "Tasmania",
    "ACT": "Australian Capital Territory", "NT": "Northern Territory", "NZ": "New Zealand",
}


def state_code(value):
    value = re.sub(r"\s+", " ", (value or "").strip().upper())
    if value in {name.upper(): code for code, name in STATES.items()}:
        return next(code for code, name in STATES.items() if name.upper() == value)
    match = re.match(r"^(VIC|NSW|QLD|WA|SA|TAS|ACT|NT|NZ)(?:$|[\s_-])", value)
    return match.group(1) if match else None


def _site_state(session, site):
    region = session.get(Region, site.region_id) if site.region_id else None
    tenant = session.get(Tenant, site.tenant_id)
    return state_code(region.code if region else (tenant.minit_region if tenant else None))


def _context(session, auth, parent_id):
    _own_context(auth)
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant or not tenant.is_active or tenant.merged_into_tenant_id:
        raise HTTPException(403, "This shop is not active")
    user = session.get(User, auth.user_id)
    parent = session.get(ParentAccount, parent_id)
    if not user or not user.is_active or not parent:
        raise HTTPException(404, "Network not found")
    site = next((s for s in sites_for_tenant(session, auth.tenant_id) if s.parent_account_id == parent_id), None)
    role = parent_role_for_user(session, parent, user)
    if not site and not role:
        raise HTTPException(404, "Network not found")
    scope = parent_region_scope(session, parent, user) if role else None
    region = session.get(Region, scope) if scope else None
    manager_state = state_code(region.code) if region else None
    own_state = _site_state(session, site) if site else None
    admin = role == "hq_admin"
    # Regional grants take precedence over an HQ tenant's site identity.
    allowed = set(STATES) if role and scope is None else {manager_state if scope else own_state} - {None}
    can_post = admin or bool(manager_state) or bool(site and site.network_role != "hq")
    return parent, user, own_state, allowed, admin, manager_state, can_post


def _hub_context(session, auth, parent_id, code, write=False):
    ctx = _context(session, auth, parent_id)
    if code not in STATES or code not in ctx[3]:
        raise HTTPException(403, "This state hub is not available to your account")
    if write and not (ctx[4] or ctx[5] == code or (ctx[6] and ctx[2] == code)):
        raise HTTPException(403, "Your network role cannot post in this hub")
    return ctx


def _messages_read(session, rows, auth, parent_id):
    """Serialise hub messages with a fixed number of queries, however many rows there are."""
    if not rows:
        return []
    ctx = _context(session, auth, parent_id)
    user_ids = {r.sender_user_id for r in rows if r.sender_user_id}
    tenant_ids = {r.sender_tenant_id for r in rows}
    reply_ids = {r.reply_to_id for r in rows if r.reply_to_id}
    users = {u.id: u for u in session.exec(select(User).where(col(User.id).in_(user_ids))).all()} if user_ids else {}
    tenants = {t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()}
    replies = {m.id: m for m in session.exec(select(StateHubMessage).where(col(StateHubMessage.id).in_(reply_ids))).all()} if reply_ids else {}
    files = _attachments_by_message(session, [r.id for r in rows], hub=True)
    out = []
    for message in rows:
        user = users.get(message.sender_user_id)
        reply = replies.get(message.reply_to_id)
        out.append({
            "can_moderate": message.sender_tenant_id == auth.tenant_id or ctx[4] or ctx[5] == message.state_code,
            "attachments": files.get(message.id, []),
            "id": message.id, "body": message.body, "created_at": message.created_at,
            "sender_name": user.full_name if user else "Former staff member", "shop_name": _label(tenants.get(message.sender_tenant_id)),
            "mine": message.sender_tenant_id == auth.tenant_id,
            "kind": message.kind, "resolved_at": message.resolved_at, "pinned": message.pinned_at is not None,
            "reply_to_id": message.reply_to_id, "reply_preview": reply.body[:160] if reply else None,
        })
    return out


def _message_read(session, message, auth):
    return _messages_read(session, [message], auth, message.parent_account_id)[0]


class HubSend(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    reply_to_id: UUID | None = None
    kind: str = "message"


class HubUpdate(BaseModel):
    pinned: bool | None = None
    resolved: bool | None = None


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    state_code: str | None = None
    category: str = "update"
    pinned: bool = False
    requires_confirmation: bool = False


class ReadBody(BaseModel):
    # Use the newest message actually rendered, never a request's wall-clock time.
    message_id: UUID


class ReceiptBody(BaseModel):
    confirm: bool = False


@router.get("/networks")
def networks(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _own_context(auth)
    user = session.get(User, auth.user_id)
    ids = list(dict.fromkeys(
        [s.parent_account_id for s in sites_for_tenant(session, auth.tenant_id)]
        + [p.id for p in parents_for_user(session, user)]
    ))
    out = []
    for pid in ids:
        parent, _, own, allowed, admin, manager, can_post = _context(session, auth, pid)
        out.append({"id": pid, "name": parent.name, "own_state": own, "allowed_states": sorted(allowed),
                    "can_publish_network": admin, "publish_states": list(STATES) if admin else ([manager] if manager else []),
                    "can_post": can_post})
    return out


@router.get("/{parent_id}/hubs")
def hubs(parent_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _, _, own, allowed, admin, manager, can_post = _context(session, auth, parent_id)
    out = []
    for code, name in STATES.items():
        accessible = code in allowed
        read = session.exec(select(StateHubRead).where(
            StateHubRead.parent_account_id == parent_id, StateHubRead.state_code == code,
            StateHubRead.tenant_id == auth.tenant_id,
        )).first() if accessible else None
        unread = 0
        if accessible:
            stmt = select(func.count()).select_from(StateHubMessage).where(
                StateHubMessage.parent_account_id == parent_id, StateHubMessage.state_code == code,
                StateHubMessage.sender_tenant_id != auth.tenant_id,
            )
            if read:
                stmt = stmt.where((StateHubMessage.created_at > read.last_read_at) | ((StateHubMessage.created_at == read.last_read_at) & (StateHubMessage.id > read.last_message_id))) if read.last_message_id else stmt.where(StateHubMessage.created_at > read.last_read_at)
            unread = session.exec(stmt).one()
        out.append({"code": code, "name": name, "mine": code == own, "accessible": accessible,
                    "can_post": accessible and can_post and (code == own or code == manager or admin), "unread": unread})
    return out


@router.get("/{parent_id}/hubs/{code}/messages")
def hub_messages(parent_id: UUID, code: str, before: UUID | None = None,
                 limit: int = Query(50, ge=1, le=100),
                 auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _hub_context(session, auth, parent_id, code)
    stmt = select(StateHubMessage).where(StateHubMessage.parent_account_id == parent_id, StateHubMessage.state_code == code)
    if before:
        cursor = session.get(StateHubMessage, before)
        if not cursor or cursor.parent_account_id != parent_id or cursor.state_code != code:
            raise HTTPException(404, "Message cursor not found")
        stmt = stmt.where((StateHubMessage.created_at < cursor.created_at) | ((StateHubMessage.created_at == cursor.created_at) & (StateHubMessage.id < cursor.id)))
    rows = session.exec(stmt.order_by(col(StateHubMessage.created_at).desc(), col(StateHubMessage.id).desc()).limit(limit + 1)).all()
    return {"messages": _messages_read(session, list(reversed(rows[:limit])), auth, parent_id),
            "has_more": len(rows) > limit, "next_before": rows[limit - 1].id if len(rows) > limit else None}


def _prepare_hub(session, auth, parent_id, code, body):
    _hub_context(session, auth, parent_id, code, write=True)
    if not body.body.strip() or body.kind not in {"message", "stock_request"}:
        raise HTTPException(400, "Enter a message and a valid message type")
    if body.reply_to_id:
        reply = session.get(StateHubMessage, body.reply_to_id)
        if not reply or reply.parent_account_id != parent_id or reply.state_code != code:
            raise HTTPException(404, "Reply message not found in this hub")
    row = StateHubMessage(parent_account_id=parent_id, state_code=code, sender_tenant_id=auth.tenant_id,
                          sender_user_id=auth.user_id, body=body.body.strip(), reply_to_id=body.reply_to_id, kind=body.kind)
    session.add(row)
    session.flush()
    return row


@router.post("/{parent_id}/hubs/{code}/messages", status_code=201)
def hub_send(parent_id: UUID, code: str, body: HubSend,
             auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    row = _prepare_hub(session, auth, parent_id, code, body)
    session.commit()
    session.refresh(row)
    return _message_read(session, row, auth)


@router.patch("/{parent_id}/hubs/{code}/messages/{message_id}")
def hub_update(parent_id: UUID, code: str, message_id: UUID, body: HubUpdate,
               auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    ctx = _hub_context(session, auth, parent_id, code, write=True)
    row = session.get(StateHubMessage, message_id)
    if not row or row.parent_account_id != parent_id or row.state_code != code:
        raise HTTPException(404, "Message not found")
    if body.pinned is not None:
        # A shop can pin its own posts; HQ admins/state managers can curate the hub.
        if row.sender_tenant_id != auth.tenant_id and not ctx[4] and ctx[5] != code:
            raise HTTPException(403, "Only the posting shop or state moderator can pin this message")
        row.pinned_at = datetime.now(timezone.utc) if body.pinned else None
    if body.resolved is not None:
        if row.kind != "stock_request":
            raise HTTPException(400, "Only stock requests can be resolved")
        if row.sender_tenant_id != auth.tenant_id and not ctx[4] and ctx[5] != code:
            raise HTTPException(403, "Only the requesting shop or state moderator can resolve this request")
        row.resolved_at = datetime.now(timezone.utc) if body.resolved else None
    session.add(row)
    session.commit()
    session.refresh(row)
    return _message_read(session, row, auth)


@router.post("/{parent_id}/hubs/{code}/read", status_code=204)
def hub_read(parent_id: UUID, code: str, body: ReadBody,
             auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _hub_context(session, auth, parent_id, code)
    message = session.get(StateHubMessage, body.message_id)
    if not message or message.parent_account_id != parent_id or message.state_code != code:
        raise HTTPException(404, "Message not found")
    def update():
        row = session.exec(select(StateHubRead).where(
            StateHubRead.parent_account_id == parent_id, StateHubRead.state_code == code,
            StateHubRead.tenant_id == auth.tenant_id,
        )).first()
        if row is None:
            row = StateHubRead(parent_account_id=parent_id, state_code=code, tenant_id=auth.tenant_id,
                               last_read_at=message.created_at, last_message_id=message.id)
            session.add(row)
        else:
            newer = (StateHubRead.last_read_at < message.created_at) | ((StateHubRead.last_read_at == message.created_at) & ((col(StateHubRead.last_message_id).is_(None)) | (StateHubRead.last_message_id < message.id)))
            session.exec(sql_update(StateHubRead).where(StateHubRead.id == row.id, newer).values(last_read_at=message.created_at, last_message_id=message.id))
        session.commit()
    try:
        update()
    except IntegrityError:
        session.rollback()
        update()


def _announcement_context(session, auth, parent_id, announcement_id):
    ctx = _context(session, auth, parent_id)
    row = session.get(NetworkAnnouncement, announcement_id)
    if not row or row.parent_account_id != parent_id or (row.state_code and row.state_code not in ctx[3]):
        raise HTTPException(404, "Announcement not found")
    return ctx, row


def _announcements_read(session, rows, auth, ctx):
    if not rows:
        return []
    ids = [r.id for r in rows]
    receipts = {r.announcement_id: r for r in session.exec(select(AnnouncementReceipt).where(
        col(AnnouncementReceipt.announcement_id).in_(ids), AnnouncementReceipt.tenant_id == auth.tenant_id)).all()}
    author_ids = {r.author_user_id for r in rows if r.author_user_id}
    users = {u.id: u for u in session.exec(select(User).where(col(User.id).in_(author_ids))).all()} if author_ids else {}
    out = []
    for row in rows:
        receipt = receipts.get(row.id)
        user = users.get(row.author_user_id)
        out.append({"id": row.id, "title": row.title, "body": row.body, "state_code": row.state_code,
                    "category": row.category, "pinned": row.pinned, "requires_confirmation": row.requires_confirmation,
                    "created_at": row.created_at, "author_name": user.full_name if user else "Support Office",
                    "read": receipt is not None, "confirmed": receipt is not None and receipt.confirmed_at is not None,
                    "can_view_receipts": _can_view_receipts(ctx, row)})
    return out


def _can_view_receipts(ctx, row):
    return bool(ctx[4] or (ctx[5] and row.state_code == ctx[5]))


def _announcement_read(session, row, auth, ctx=None):
    ctx = ctx or _context(session, auth, row.parent_account_id)
    return _announcements_read(session, [row], auth, ctx)[0]


@router.get("/{parent_id}/announcements")
def announcements(parent_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                  auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    ctx = _context(session, auth, parent_id)
    rows = session.exec(select(NetworkAnnouncement).where(
        NetworkAnnouncement.parent_account_id == parent_id,
        (col(NetworkAnnouncement.state_code).is_(None)) | col(NetworkAnnouncement.state_code).in_(list(ctx[3])),
    ).order_by(col(NetworkAnnouncement.pinned).desc(), col(NetworkAnnouncement.created_at).desc())
        .offset(offset).limit(limit + 1)).all()
    return {"announcements": _announcements_read(session, rows[:limit], auth, ctx), "has_more": len(rows) > limit}


@router.post("/{parent_id}/announcements", status_code=201)
def publish(parent_id: UUID, body: AnnouncementCreate,
            auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    ctx = _context(session, auth, parent_id)
    if not ctx[4] and (not ctx[5] or body.state_code != ctx[5]):
        raise HTTPException(403, "Only HQ admins or the assigned state manager can publish to this audience")
    if body.state_code is not None and body.state_code not in STATES:
        raise HTTPException(400, "Choose a valid state")
    if not body.title.strip() or not body.body.strip() or body.category not in {"update", "training", "important"}:
        raise HTTPException(400, "Enter a title, message and valid category")
    row = NetworkAnnouncement(parent_account_id=parent_id, author_user_id=auth.user_id,
                              **body.model_dump(exclude={"title", "body"}),
                              title=body.title.strip(), body=body.body.strip())
    session.add(row)
    session.commit()
    session.refresh(row)
    return _announcement_read(session, row, auth, ctx)


@router.post("/{parent_id}/announcements/{announcement_id}/receipt")
def receipt(parent_id: UUID, announcement_id: UUID, body: ReceiptBody,
            auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    ctx, announcement = _announcement_context(session, auth, parent_id, announcement_id)
    if body.confirm and not announcement.requires_confirmation:
        raise HTTPException(400, "This announcement does not request confirmation")
    def save():
        row = session.exec(select(AnnouncementReceipt).where(
            AnnouncementReceipt.announcement_id == announcement_id, AnnouncementReceipt.tenant_id == auth.tenant_id,
        )).first()
        if not row:
            row = AnnouncementReceipt(announcement_id=announcement_id, tenant_id=auth.tenant_id)
        if body.confirm and not row.confirmed_at:
            row.confirmed_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
    try:
        save()
    except IntegrityError:
        session.rollback()
        save()
    return _announcement_read(session, announcement, auth, ctx)


def _audience_sites(session, parent_id, state):
    """Active shop sites an announcement reaches (Support office sites are not an audience)."""
    sites = [x for x in sites_for_parent(session, parent_id) if x.network_role != "hq"]
    tenants = {t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_([x.tenant_id for x in sites]))).all()} if sites else {}
    regions = {r.id: r for r in session.exec(select(Region).where(col(Region.parent_account_id) == parent_id)).all()}
    out = []
    for site in sites:
        tenant = tenants.get(site.tenant_id)
        if not tenant or not tenant.is_active or tenant.merged_into_tenant_id:
            continue
        region = regions.get(site.region_id) if site.region_id else None
        code = state_code(region.code if region else tenant.minit_region)
        if state is None or code == state:
            out.append((site, tenant, code))
    return out


@router.get("/{parent_id}/announcements/{announcement_id}/receipts")
def announcement_receipts(parent_id: UUID, announcement_id: UUID, export: str | None = None,
                          auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Which shops have read or confirmed an announcement. Publishers only."""
    ctx, row = _announcement_context(session, auth, parent_id, announcement_id)
    if not _can_view_receipts(ctx, row):
        raise HTTPException(403, "Only the people who can publish this announcement can see receipts")
    audience = _audience_sites(session, parent_id, row.state_code)
    receipts = {r.tenant_id: r for r in session.exec(select(AnnouncementReceipt).where(AnnouncementReceipt.announcement_id == row.id)).all()}
    shops = []
    for _, tenant, code in audience:
        receipt = receipts.get(tenant.id)
        shops.append({"tenant_id": tenant.id, "name": _label(tenant), "state_code": code,
                      "read_at": receipt.read_at if receipt else None,
                      "confirmed_at": receipt.confirmed_at if receipt else None})
    shops.sort(key=lambda s: (s["confirmed_at"] is not None, s["read_at"] is not None, s["name"].lower()))
    summary = {"audience": len(shops), "read": sum(1 for s in shops if s["read_at"]),
               "confirmed": sum(1 for s in shops if s["confirmed_at"]),
               "requires_confirmation": row.requires_confirmation}
    if export == "csv":
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Shop", "State", "Read at (UTC)", "Confirmed at (UTC)"])
        for s in shops:
            writer.writerow([s["name"], s["state_code"] or "", s["read_at"].isoformat() if s["read_at"] else "",
                             s["confirmed_at"].isoformat() if s["confirmed_at"] else ""])
        return Response(buffer.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": 'attachment; filename="announcement-receipts.csv"', "Cache-Control": "private, no-store"})
    return {"summary": summary, "shops": shops}


@router.get("/{parent_id}/state-gaps")
def state_gaps(parent_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Shops whose state cannot be worked out, so they get no state hub. HQ admins only."""
    ctx = _context(session, auth, parent_id)
    if not ctx[4]:
        raise HTTPException(403, "Only HQ admins can see this list")
    shops = [{"tenant_id": tenant.id, "name": _label(tenant), "region_value": tenant.minit_region}
             for _, tenant, code in _audience_sites(session, parent_id, None) if code is None]
    shops.sort(key=lambda s: s["name"].lower())
    return {"shops": shops}


async def _files(files):
    if len(files) > 5:
        raise HTTPException(400, "Attach up to five files")
    out = []
    total = 0
    for upload in files:
        data = await upload.read(5 * 1024 * 1024 + 1)
        await upload.close()
        total += len(data)
        if not data or len(data) > 5 * 1024 * 1024 or total > 10 * 1024 * 1024:
            raise HTTPException(413, "Each file must be at most 5 MB, with 10 MB total")
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif data.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif data.startswith(b"%PDF-"):
            mime = "application/pdf"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            raise HTTPException(415, "Use a PNG, JPEG, WebP photo or PDF")
        name = (upload.filename or "attachment").replace("\\", "/").split("/")[-1]
        name = "".join(ch for ch in name if ord(ch) >= 32)[:200] or "attachment"
        out.append({"filename": name, "content_type": mime, "size_bytes": len(data), "data": data})
    return out


@router.post("/{parent_id}/hubs/{code}/posts", status_code=201)
async def hub_post(parent_id: UUID, code: str, body: str = Form("", max_length=2000),
                   kind: str = Form("message"), reply_to_id: UUID | None = Form(None),
                   files: list[UploadFile] = File(default=[]),
                   auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _hub_context(session, auth, parent_id, code, write=True)
    attachments = await _files(files)
    payload = HubSend(body=body.strip() or ("Attachment" if attachments else " "), kind=kind, reply_to_id=reply_to_id)
    row = _prepare_hub(session, auth, parent_id, code, payload)
    for data in attachments:
        session.add(NetworkMessageAttachment(hub_message_id=row.id, **data))
    session.commit()
    session.refresh(row)
    return _message_read(session, row, auth)


@router.post("/{parent_id}/direct/{tenant_id}/posts", status_code=201)
async def direct_post(parent_id: UUID, tenant_id: UUID, body: str = Form("", max_length=2000),
                      files: list[UploadFile] = File(default=[]),
                      auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _context(session, auth, parent_id)
    attachments = await _files(files)
    msg, user = _prepare_direct(session, auth, tenant_id, SendBody(body=body.strip() or ("Attachment" if attachments else " ")), parent_id)
    for data in attachments:
        session.add(NetworkMessageAttachment(direct_message_id=msg.id, **data))
    session.commit()
    session.refresh(msg)
    return {"id": msg.id, "conversation_id": msg.conversation_id, "sender_tenant_id": auth.tenant_id,
            "mine": True, "sender_name": user.full_name if user else None, "body": msg.body,
            "created_at": msg.created_at, "attachments": _attachments(session, msg.id)}


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: UUID, auth: AuthContext = Depends(get_auth_context),
                        session: Session = Depends(unscoped_session)):
    _own_context(auth)
    row = session.get(NetworkMessageAttachment, attachment_id)
    if not row:
        raise HTTPException(404, "Attachment not found")
    if row.hub_message_id:
        message = session.get(StateHubMessage, row.hub_message_id)
        if not message:
            raise HTTPException(404, "Message not found")
        _hub_context(session, auth, message.parent_account_id, message.state_code)
    else:
        message = session.get(NetworkMessage, row.direct_message_id)
        if not message:
            raise HTTPException(404, "Message not found")
        _get_mine(session, message.conversation_id, auth.tenant_id)
    return Response(row.data, media_type=row.content_type, headers={
        "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.filename, safe=""),
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
    })


