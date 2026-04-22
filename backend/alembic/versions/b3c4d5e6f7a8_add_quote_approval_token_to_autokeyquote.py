"""add quote_approval_token to autokeyquote

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('autokeyquote', sa.Column('quote_approval_token', sa.String(), nullable=True))
    # Backfill existing rows with unique tokens
    op.execute(
        "UPDATE autokeyquote SET quote_approval_token = gen_random_uuid()::text WHERE quote_approval_token IS NULL"
    )
    op.alter_column('autokeyquote', 'quote_approval_token', nullable=False)
    op.create_index('ix_autokeyquote_quote_approval_token', 'autokeyquote', ['quote_approval_token'], unique=True)


def downgrade():
    op.drop_index('ix_autokeyquote_quote_approval_token', 'autokeyquote')
    op.drop_column('autokeyquote', 'quote_approval_token')
