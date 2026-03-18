"""
Add subscription fields to CustomerAccount

Revision ID: 20260318_add_subscription_fields_to_customeraccount
Revises: 20260318_add_fleet_fields_to_customeraccount
Create Date: 2026-03-18
"""

# revision identifiers, used by Alembic.
revision = '20260318_add_subscription_fields_to_customeraccount'
down_revision = '20260318_add_fleet_fields_to_customeraccount'
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
