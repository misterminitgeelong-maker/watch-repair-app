"""Follow-up state; business resolution remains on the source job/quote/invoice."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class RevenueFollowUp(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "issue_key", name="uq_revenue_followup_issue"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    issue_key: str = Field(max_length=100)
    auto_key_job_id: UUID = Field(index=True, foreign_key="autokeyjob.id")
    owner_user_id: UUID | None = Field(default=None, foreign_key="user.id")
    next_follow_up_at: datetime | None = None
    note: str = Field(default="", max_length=2000)
    last_contact_at: datetime | None = None
    version: int = 1
