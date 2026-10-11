"""shoe model, size and proof-of-purchase fields (Birkenstock warranty and stock)"""
from alembic import op
import sqlalchemy as sa

revision = "20261011a_shoe_purchase_fields"
down_revision = "20261009a_hq_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shoe", sa.Column("model_name", sa.String(), nullable=True))
    op.add_column("shoe", sa.Column("size", sa.String(), nullable=True))
    op.add_column("shoe", sa.Column("purchase_date", sa.Date(), nullable=True))
    op.add_column("shoe", sa.Column("purchase_store", sa.String(), nullable=True))
    op.add_column("shoe", sa.Column("purchase_ref", sa.String(), nullable=True))


def downgrade():
    for col in ("purchase_ref", "purchase_store", "purchase_date", "size", "model_name"):
        op.drop_column("shoe", col)
