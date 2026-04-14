"""merge heads e1f2a3b4c5d6 and z1a2b3c4d5e6

Revision ID: 20260414_merge_e1f2_z1a2
Revises: e1f2a3b4c5d6, z1a2b3c4d5e6
Create Date: 2026-04-14

"""
from alembic import op

revision = "20260414_merge_e1f2_z1a2"
down_revision = ("e1f2a3b4c5d6", "z1a2b3c4d5e6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
