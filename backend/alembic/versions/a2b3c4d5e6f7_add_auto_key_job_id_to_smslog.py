"""add auto_key_job_id to smslog

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('smslog', sa.Column('auto_key_job_id', sa.Uuid(), nullable=True))
    op.create_index('ix_smslog_auto_key_job_id', 'smslog', ['auto_key_job_id'])
    op.create_foreign_key(
        'fk_smslog_auto_key_job_id',
        'smslog', 'autokeyjob',
        ['auto_key_job_id'], ['id'],
    )


def downgrade():
    op.drop_constraint('fk_smslog_auto_key_job_id', 'smslog', type_='foreignkey')
    op.drop_index('ix_smslog_auto_key_job_id', 'smslog')
    op.drop_column('smslog', 'auto_key_job_id')
