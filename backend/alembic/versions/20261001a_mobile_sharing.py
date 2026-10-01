"""Opt-in Mobile Services reporting for retail sites, separate from dispatch."""
import sqlalchemy as sa
from alembic import op

revision = "20261001a_mobile_sharing"
down_revision = "20260930a_mv_merge_safety"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("parentaccountsite", sa.Column("mobile_reporting_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("parentaccountsite", "mobile_reporting_enabled")
