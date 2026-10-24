"""two-outcome auto key quotes: option labels, selected option, line item option key

Revision ID: 20261024a_auto_key_quote_options
Revises: 20261019a_lead_routing_integrity
"""
from alembic import op
import sqlalchemy as sa

revision = "20261024a_auto_key_quote_options"
down_revision = "20261019a_lead_routing_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("autokeyquote", sa.Column("option_a_label", sa.String(), nullable=True))
    op.add_column("autokeyquote", sa.Column("option_b_label", sa.String(), nullable=True))
    op.add_column("autokeyquote", sa.Column("selected_option", sa.String(), nullable=True))
    op.add_column("autokeyquote", sa.Column("selected_at", sa.DateTime(), nullable=True))
    op.add_column("autokeyquotelineitem", sa.Column("option_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("autokeyquotelineitem", "option_key")
    op.drop_column("autokeyquote", "selected_at")
    op.drop_column("autokeyquote", "selected_option")
    op.drop_column("autokeyquote", "option_b_label")
    op.drop_column("autokeyquote", "option_a_label")
