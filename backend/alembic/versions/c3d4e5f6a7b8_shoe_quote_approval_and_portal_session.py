"""shoe_quote_approval_and_portal_session

Revision ID: c3d4e5f6a7b8
Revises: e8b9c0d1f2a3
Branch Labels: None
Depends On: None

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = "e8b9c0d1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add quote approval fields to shoerepairjob
    op.add_column('shoerepairjob', sa.Column('quote_approval_token', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('shoerepairjob', sa.Column('quote_approval_token_expires_at', sa.DateTime(), nullable=True))
    op.add_column('shoerepairjob', sa.Column('quote_status', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Backfill: generate unique tokens for existing rows
    op.execute("UPDATE shoerepairjob SET quote_approval_token = gen_random_uuid()::text WHERE quote_approval_token IS NULL")
    op.execute("UPDATE shoerepairjob SET quote_status = 'none' WHERE quote_status IS NULL")

    op.alter_column('shoerepairjob', 'quote_approval_token', nullable=False)
    op.alter_column('shoerepairjob', 'quote_status', nullable=False)

    op.create_index(op.f('ix_shoerepairjob_quote_approval_token'), 'shoerepairjob', ['quote_approval_token'], unique=True)
    op.create_index(op.f('ix_shoerepairjob_quote_approval_token_expires_at'), 'shoerepairjob', ['quote_approval_token_expires_at'], unique=False)

    # Create portal session table
    op.create_table(
        'portalsession',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portalsession_email'), 'portalsession', ['email'], unique=False)
    op.create_index(op.f('ix_portalsession_token'), 'portalsession', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_portalsession_token'), table_name='portalsession')
    op.drop_index(op.f('ix_portalsession_email'), table_name='portalsession')
    op.drop_table('portalsession')

    op.drop_index(op.f('ix_shoerepairjob_quote_approval_token_expires_at'), table_name='shoerepairjob')
    op.drop_index(op.f('ix_shoerepairjob_quote_approval_token'), table_name='shoerepairjob')
    op.drop_column('shoerepairjob', 'quote_status')
    op.drop_column('shoerepairjob', 'quote_approval_token_expires_at')
    op.drop_column('shoerepairjob', 'quote_approval_token')
