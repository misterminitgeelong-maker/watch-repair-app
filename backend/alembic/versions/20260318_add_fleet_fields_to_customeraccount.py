"""
Add fleet/dealer fields to CustomerAccount

Revision ID: 20260318_fleet_customeraccount
Revises: b1c4d6e8f9a2
Create Date: 2026-03-18
"""

# revision identifiers, used by Alembic. (Keep <= 32 chars for alembic_version.version_num)
revision = '20260318_fleet_customeraccount'
down_revision = 'b1c4d6e8f9a2'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('customeraccount', sa.Column('account_type', sa.String(), nullable=True))
    op.add_column('customeraccount', sa.Column('fleet_size', sa.Integer(), nullable=True))
    op.add_column('customeraccount', sa.Column('primary_contact_name', sa.String(), nullable=True))
    op.add_column('customeraccount', sa.Column('primary_contact_phone', sa.String(), nullable=True))
    op.add_column('customeraccount', sa.Column('billing_cycle', sa.String(), nullable=True))
    op.add_column('customeraccount', sa.Column('credit_limit', sa.Integer(), nullable=True))
    op.add_column('customeraccount', sa.Column('account_notes', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('customeraccount', 'account_notes')
    op.drop_column('customeraccount', 'credit_limit')
    op.drop_column('customeraccount', 'billing_cycle')
    op.drop_column('customeraccount', 'primary_contact_phone')
    op.drop_column('customeraccount', 'primary_contact_name')
    op.drop_column('customeraccount', 'fleet_size')
    op.drop_column('customeraccount', 'account_type')
