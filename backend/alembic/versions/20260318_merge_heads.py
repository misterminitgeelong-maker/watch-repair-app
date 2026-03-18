"""
Alembic merge migration to resolve multiple heads

Revision ID: 20260318_merge_heads
Revises: 20260318_add_fleet_fields_to_customeraccount, a9f1c2d3e4b5, i4d5e6f7a8b9c
Create Date: 2026-03-18
"""

# revision identifiers, used by Alembic.
revision = '20260318_merge_heads'
down_revision = ('20260318_add_fleet_fields_to_customeraccount', 'a9f1c2d3e4b5', 'i4d5e6f7a8b9c')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
