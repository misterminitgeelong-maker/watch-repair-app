"""Per-site messaging hub override.

Revision ID: 20261104_site_messaging_state
Revises: 20261103_network_community
"""
import sqlalchemy as sa
from alembic import op

revision = "20261104_site_messaging_state"
down_revision = "20261103_network_community"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("parentaccountsite", sa.Column("messaging_state", sa.String(8), nullable=True))


def downgrade():
    op.drop_column("parentaccountsite", "messaging_state")
