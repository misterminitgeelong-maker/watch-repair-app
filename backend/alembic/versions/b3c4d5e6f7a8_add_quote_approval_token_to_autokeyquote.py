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
    with op.batch_alter_table('autokeyquote') as batch_op:
        batch_op.add_column(sa.Column('quote_approval_token', sa.String(), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM autokeyquote WHERE quote_approval_token IS NULL")).fetchall()
    for (row_id,) in rows:
        bind.execute(
            sa.text("UPDATE autokeyquote SET quote_approval_token = :tok WHERE id = :id"),
            {"tok": uuid.uuid4().hex, "id": row_id},
        )
    with op.batch_alter_table('autokeyquote') as batch_op:
        batch_op.alter_column('quote_approval_token', nullable=False)
        batch_op.create_index(
            'ix_autokeyquote_quote_approval_token',
            ['quote_approval_token'],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table('autokeyquote') as batch_op:
        batch_op.drop_index('ix_autokeyquote_quote_approval_token')
        batch_op.drop_column('quote_approval_token')
