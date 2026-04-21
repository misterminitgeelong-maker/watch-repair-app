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
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Add quote approval fields to shoerepairjob. Wrap in batch_alter_table
    # so the subsequent alter_column (NOT NULL) works on SQLite too.
    with op.batch_alter_table("shoerepairjob") as batch_op:
        batch_op.add_column(sa.Column("quote_approval_token", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("quote_approval_token_expires_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("quote_status", sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Backfill: generate unique tokens for existing rows. Postgres uses its
    # native UUID function; SQLite uses the hex() of random bytes (CI-only
    # path — prod runs on Postgres).
    if dialect == "postgresql":
        op.execute("UPDATE shoerepairjob SET quote_approval_token = gen_random_uuid()::text WHERE quote_approval_token IS NULL")
    else:
        op.execute("UPDATE shoerepairjob SET quote_approval_token = lower(hex(randomblob(16))) WHERE quote_approval_token IS NULL")
    op.execute("UPDATE shoerepairjob SET quote_status = 'none' WHERE quote_status IS NULL")

    with op.batch_alter_table("shoerepairjob") as batch_op:
        batch_op.alter_column("quote_approval_token", nullable=False)
        batch_op.alter_column("quote_status", nullable=False)
        batch_op.create_index(
            batch_op.f("ix_shoerepairjob_quote_approval_token"),
            ["quote_approval_token"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_shoerepairjob_quote_approval_token_expires_at"),
            ["quote_approval_token_expires_at"],
            unique=False,
        )

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

    with op.batch_alter_table("shoerepairjob") as batch_op:
        batch_op.drop_index(batch_op.f("ix_shoerepairjob_quote_approval_token_expires_at"))
        batch_op.drop_index(batch_op.f("ix_shoerepairjob_quote_approval_token"))
        batch_op.drop_column("quote_status")
        batch_op.drop_column("quote_approval_token_expires_at")
        batch_op.drop_column("quote_approval_token")
