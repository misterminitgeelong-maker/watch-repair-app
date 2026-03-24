"""add quote approval token expiry

Revision ID: 534bf5c52bfa
Revises: b15045375be3
Create Date: 2026-03-24 22:59:29.904267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '534bf5c52bfa'
down_revision: Union[str, None] = 'b15045375be3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("quote", sa.Column("approval_token_expires_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_quote_approval_token_expires_at"), "quote", ["approval_token_expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quote_approval_token_expires_at"), table_name="quote")
    op.drop_column("quote", "approval_token_expires_at")
