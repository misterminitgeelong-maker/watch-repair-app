"""Messaging data shared only within an explicitly linked parent network."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, LargeBinary, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow():
    return datetime.now(timezone.utc)


class StateHubMessage(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id", ondelete="CASCADE")
    state_code: str = Field(index=True, max_length=8)
    sender_tenant_id: UUID = Field(index=True, foreign_key="tenant.id", ondelete="CASCADE")
    sender_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", ondelete="SET NULL")
    body: str = Field(max_length=2000)
    reply_to_id: Optional[UUID] = Field(default=None, foreign_key="statehubmessage.id", ondelete="SET NULL")
    kind: str = Field(default="message", max_length=20)
    resolved_at: Optional[datetime] = None
    pinned_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class StateHubRead(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("parent_account_id", "state_code", "tenant_id", name="uq_statehubread_site"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id", ondelete="CASCADE")
    state_code: str = Field(max_length=8)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id", ondelete="CASCADE")
    last_read_at: datetime = Field(default_factory=utcnow)
    last_message_id: Optional[UUID] = None


class NetworkAnnouncement(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id", ondelete="CASCADE")
    state_code: Optional[str] = Field(default=None, index=True, max_length=8)
    title: str = Field(max_length=200)
    body: str = Field(max_length=10000)
    category: str = Field(default="update", max_length=20)
    pinned: bool = False
    requires_confirmation: bool = False
    author_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=utcnow, index=True)


class AnnouncementReceipt(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("announcement_id", "tenant_id", name="uq_announcementreceipt_site"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    announcement_id: UUID = Field(index=True, foreign_key="networkannouncement.id", ondelete="CASCADE")
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id", ondelete="CASCADE")
    read_at: datetime = Field(default_factory=utcnow)
    confirmed_at: Optional[datetime] = None

class NetworkMessageAttachment(SQLModel, table=True):
    """Small chat files stored transactionally with their message."""
    __table_args__ = (
        CheckConstraint("(hub_message_id IS NOT NULL AND direct_message_id IS NULL) OR (hub_message_id IS NULL AND direct_message_id IS NOT NULL)", name="ck_networkattachment_one_message"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    hub_message_id: Optional[UUID] = Field(default=None, index=True, foreign_key="statehubmessage.id", ondelete="CASCADE")
    direct_message_id: Optional[UUID] = Field(default=None, index=True, foreign_key="networkmessage.id", ondelete="CASCADE")
    filename: str = Field(max_length=200)
    content_type: str = Field(max_length=80)
    size_bytes: int
    data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))


