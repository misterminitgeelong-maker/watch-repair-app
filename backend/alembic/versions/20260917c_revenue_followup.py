"""Persist revenue follow-ups without changing financial source records."""
from alembic import op
import sqlalchemy as sa

revision = "20260917c_revenue_followup"
down_revision = "20260917b_mobile_statuses"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revenuefollowup",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("issue_key", sa.String(100), nullable=False),
        sa.Column("auto_key_job_id", sa.Uuid(), sa.ForeignKey("autokeyjob.id"), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("next_follow_up_at", sa.DateTime()),
        sa.Column("note", sa.String(2000), nullable=False),
        sa.Column("last_contact_at", sa.DateTime()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "issue_key", name="uq_revenue_followup_issue"),
    )
    op.create_index("ix_revenuefollowup_tenant_id", "revenuefollowup", ["tenant_id"])
    op.create_index("ix_revenuefollowup_auto_key_job_id", "revenuefollowup", ["auto_key_job_id"])


def downgrade():
    op.drop_table("revenuefollowup")
