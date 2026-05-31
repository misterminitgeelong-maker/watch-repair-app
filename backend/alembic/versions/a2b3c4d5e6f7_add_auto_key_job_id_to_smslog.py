"""add auto_key_job_id to smslog

Revision ID: a2b3c4d5e6f7
Revises: 20260415_queue_day
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = '20260415_queue_day'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('smslog') as batch_op:
        batch_op.add_column(sa.Column('auto_key_job_id', sa.Uuid(), nullable=True))
        batch_op.create_index('ix_smslog_auto_key_job_id', ['auto_key_job_id'])
        batch_op.create_foreign_key(
            'fk_smslog_auto_key_job_id',
            'autokeyjob',
            ['auto_key_job_id'],
            ['id'],
        )


def downgrade():
    with op.batch_alter_table('smslog') as batch_op:
        batch_op.drop_constraint('fk_smslog_auto_key_job_id', type_='foreignkey')
        batch_op.drop_index('ix_smslog_auto_key_job_id')
        batch_op.drop_column('auto_key_job_id')
