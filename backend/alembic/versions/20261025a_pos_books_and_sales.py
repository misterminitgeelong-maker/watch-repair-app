"""shop counter POS: price books (versioned), shop settings, and the sales ledger

Revision ID: 20261025a_pos_books_and_sales
Revises: 20261024a_auto_key_quote_options
"""
from alembic import op
import sqlalchemy as sa

revision = "20261025a_pos_books_and_sales"
down_revision = "20261024a_auto_key_quote_options"
branch_labels = None
depends_on = None


def _tenant_fk(nullable: bool = False) -> sa.Column:
    return sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=nullable)


def upgrade():
    op.create_table(
        "pospricebook",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id", ondelete="CASCADE"), nullable=True),
        _tenant_fk(nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("region", sa.String(length=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("gst_rate_bp", sa.Integer(), nullable=False),
        sa.Column("cash_rounding_cents", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("draft_json", sa.String(), nullable=False),
        sa.Column("draft_updated_at", sa.DateTime(), nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("(parent_account_id IS NULL) <> (tenant_id IS NULL)", name="ck_pospricebook_one_owner"),
    )
    op.create_index("ix_pospricebook_parent_account_id", "pospricebook", ["parent_account_id"])
    op.create_index("ix_pospricebook_tenant_id", "pospricebook", ["tenant_id"])

    op.create_table(
        "pospricebookversion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("price_book_id", sa.Uuid(), sa.ForeignKey("pospricebook.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.String(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("price_book_id", "version", name="uq_pospricebookversion_book_version"),
    )
    op.create_index("ix_pospricebookversion_price_book_id", "pospricebookversion", ["price_book_id"])

    op.create_table(
        "posshopsettings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("price_book_id", sa.Uuid(), sa.ForeignKey("pospricebook.id", ondelete="SET NULL"), nullable=True),
        sa.Column("overrides_json", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_posshopsettings_tenant_id", "posshopsettings", ["tenant_id"], unique=True)
    op.create_index("ix_posshopsettings_price_book_id", "posshopsettings", ["price_book_id"])

    op.create_table(
        "possale",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("client_sale_id", sa.String(length=64), nullable=False),
        sa.Column("till_id", sa.String(length=64), nullable=False),
        sa.Column("staff_user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("staff_name", sa.String(length=120), nullable=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customer.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("price_book_id", sa.Uuid(), sa.ForeignKey("pospricebook.id", ondelete="SET NULL"), nullable=True),
        sa.Column("price_book_version", sa.Integer(), nullable=True),
        sa.Column("gst_rate_bp", sa.Integer(), nullable=False),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("combo_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False),
        sa.Column("discount_reason", sa.String(length=200), nullable=True),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("gst_cents", sa.Integer(), nullable=False),
        sa.Column("rounding_cents", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=2000), nullable=True),
        sa.Column("refund_of_sale_id", sa.Uuid(), sa.ForeignKey("possale.id", ondelete="SET NULL"), nullable=True),
        sa.Column("loyalty_points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "client_sale_id", name="uq_possale_tenant_client_sale"),
    )
    op.create_index("ix_possale_tenant_id", "possale", ["tenant_id"])
    op.create_index("ix_possale_till_id", "possale", ["till_id"])
    op.create_index("ix_possale_customer_id", "possale", ["customer_id"])
    op.create_index("ix_possale_business_date", "possale", ["business_date"])

    op.create_table(
        "possaleline",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("sale_id", sa.Uuid(), sa.ForeignKey("possale.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("category_key", sa.String(length=120), nullable=True),
        sa.Column("category_name", sa.String(length=120), nullable=True),
        sa.Column("group_key", sa.String(length=120), nullable=True),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("combo_cents", sa.Integer(), nullable=False),
        sa.Column("combo_label", sa.String(length=120), nullable=True),
        sa.Column("gst_free", sa.Boolean(), nullable=False),
        sa.Column("is_service", sa.Boolean(), nullable=False),
        sa.Column("job_type", sa.String(length=16), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_possaleline_tenant_id", "possaleline", ["tenant_id"])
    op.create_index("ix_possaleline_sale_id", "possaleline", ["sale_id"])

    op.create_table(
        "postender",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("sale_id", sa.Uuid(), sa.ForeignKey("possale.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tender_type", sa.String(length=16), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("tendered_cents", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("auth_code", sa.String(length=32), nullable=True),
        sa.Column("card_type", sa.String(length=32), nullable=True),
        sa.Column("masked_pan", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_postender_tenant_id", "postender", ["tenant_id"])
    op.create_index("ix_postender_sale_id", "postender", ["sale_id"])


def downgrade():
    for table, indexes in (
        ("postender", ["ix_postender_sale_id", "ix_postender_tenant_id"]),
        ("possaleline", ["ix_possaleline_sale_id", "ix_possaleline_tenant_id"]),
        ("possale", ["ix_possale_business_date", "ix_possale_customer_id", "ix_possale_till_id", "ix_possale_tenant_id"]),
        ("posshopsettings", ["ix_posshopsettings_price_book_id", "ix_posshopsettings_tenant_id"]),
        ("pospricebookversion", ["ix_pospricebookversion_price_book_id"]),
        ("pospricebook", ["ix_pospricebook_tenant_id", "ix_pospricebook_parent_account_id"]),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
