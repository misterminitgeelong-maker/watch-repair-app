"""merge heads: loyalty tables and autokey signature fields

Revision ID: 20260423_merge_heads
Revises: 20260423_loyalty, c4d5e6f7a8b9
Create Date: 2026-04-23

"""
from alembic import op

revision = "20260423_merge_heads"
down_revision = ("20260423_loyalty", "c4d5e6f7a8b9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
