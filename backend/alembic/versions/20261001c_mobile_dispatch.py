"""Dispatch opt-in for independent retail Mobile Services links."""
import sqlalchemy as sa
from alembic import op

revision = "20261001c_mobile_dispatch"
down_revision = "20261001b_mobile_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("parentmobilereportingsource", sa.Column("dispatch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("parentmobilereportingsource", "dispatch_enabled")
