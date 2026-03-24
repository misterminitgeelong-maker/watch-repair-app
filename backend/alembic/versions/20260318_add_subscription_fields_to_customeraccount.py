"""
Add subscription fields to CustomerAccount

Revision ID: 20260318_subscription_cust
Revises: 20260318_fleet_customeraccount
Create Date: 2026-03-18
"""

# revision identifiers, used by Alembic. (Keep <= 32 chars for alembic_version.version_num)
revision = '20260318_subscription_cust'
down_revision = '20260318_fleet_customeraccount'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('customeraccount', sa.Column('subscription_plan', sa.String(), nullable=False, server_default='none'))
    op.add_column('customeraccount', sa.Column('subscription_active', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('customeraccount', sa.Column('subscription_start_date', sa.Date(), nullable=True))

def downgrade():
    op.drop_column('customeraccount', 'subscription_start_date')
    op.drop_column('customeraccount', 'subscription_active')
    op.drop_column('customeraccount', 'subscription_plan')
