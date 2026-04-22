"""add signature fields to autokeyquote

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('autokeyquote', sa.Column('signature_storage_key', sa.String(), nullable=True))
    op.add_column('autokeyquote', sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('autokeyquote', sa.Column('signer_name', sa.String(), nullable=True))


def downgrade():
    op.drop_column('autokeyquote', 'signer_name')
    op.drop_column('autokeyquote', 'signed_at')
    op.drop_column('autokeyquote', 'signature_storage_key')
