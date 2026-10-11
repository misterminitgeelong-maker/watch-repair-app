"""HQ shoe catalogue, parts, locations, stock levels, transfers, movements, job part use and purchase records"""
from alembic import op
import sqlalchemy as sa

revision = "20261011b_hq_stock"
down_revision = "20261011a_shoe_purchase_fields"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _parent():
    return sa.Column("parent_account_id", sa.Uuid(), sa.ForeignKey("parentaccount.id", ondelete="CASCADE"), nullable=False)


def upgrade():
    op.create_table(
        "stockpart", _id(), _parent(),
        sa.Column("sku", sa.String(80), nullable=False), sa.Column("name", sa.String(200), nullable=False),
        sa.Column("part_type", sa.String(40)), sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("reorder_level", sa.Integer(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("parent_account_id", "sku", name="uq_stockpart_parent_sku"),
    )
    op.create_index("ix_stockpart_parent_account_id", "stockpart", ["parent_account_id"])
    op.create_index("ix_stockpart_sku", "stockpart", ["sku"])

    op.create_table(
        "hqshoemodel", _id(), _parent(),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("category", sa.String(40)),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("parent_account_id", "name", name="uq_hqshoemodel_parent_name"),
    )
    op.create_index("ix_hqshoemodel_parent_account_id", "hqshoemodel", ["parent_account_id"])

    op.create_table(
        "hqshoemodelpart", _id(), _parent(),
        sa.Column("model_id", sa.Uuid(), sa.ForeignKey("hqshoemodel.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Uuid(), sa.ForeignKey("stockpart.id", ondelete="CASCADE"), nullable=False),
        sa.Column("size", sa.String(40)), sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_hqshoemodelpart_parent_account_id", "hqshoemodelpart", ["parent_account_id"])
    op.create_index("ix_hqshoemodelpart_model_id", "hqshoemodelpart", ["model_id"])
    op.create_index("ix_hqshoemodelpart_part_id", "hqshoemodelpart", ["part_id"])

    op.create_table(
        "stocklocation", _id(), _parent(),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id")), sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("parent_account_id", "name", name="uq_stocklocation_parent_name"),
    )
    op.create_index("ix_stocklocation_parent_account_id", "stocklocation", ["parent_account_id"])
    op.create_index("ix_stocklocation_tenant_id", "stocklocation", ["tenant_id"])

    op.create_table(
        "stocklevel", _id(), _parent(),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("stocklocation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Uuid(), sa.ForeignKey("stockpart.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("location_id", "part_id", name="uq_stocklevel_location_part"),
    )
    op.create_index("ix_stocklevel_parent_account_id", "stocklevel", ["parent_account_id"])
    op.create_index("ix_stocklevel_location_id", "stocklevel", ["location_id"])
    op.create_index("ix_stocklevel_part_id", "stocklevel", ["part_id"])

    op.create_table(
        "stocktransfer", _id(), _parent(),
        sa.Column("from_location_id", sa.Uuid(), sa.ForeignKey("stocklocation.id"), nullable=False),
        sa.Column("to_location_id", sa.Uuid(), sa.ForeignKey("stocklocation.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("note", sa.String()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("received_at", sa.DateTime()),
    )
    op.create_index("ix_stocktransfer_parent_account_id", "stocktransfer", ["parent_account_id"])
    op.create_index("ix_stocktransfer_from_location_id", "stocktransfer", ["from_location_id"])
    op.create_index("ix_stocktransfer_to_location_id", "stocktransfer", ["to_location_id"])
    op.create_index("ix_stocktransfer_status", "stocktransfer", ["status"])

    op.create_table(
        "stocktransferline", _id(),
        sa.Column("transfer_id", sa.Uuid(), sa.ForeignKey("stocktransfer.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Uuid(), sa.ForeignKey("stockpart.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("received_quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_stocktransferline_transfer_id", "stocktransferline", ["transfer_id"])

    op.create_table(
        "stockmovement", _id(), _parent(),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("stocklocation.id"), nullable=False),
        sa.Column("part_id", sa.Uuid(), sa.ForeignKey("stockpart.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), sa.ForeignKey("stocktransfer.id")),
        sa.Column("shoe_repair_job_id", sa.Uuid(), sa.ForeignKey("shoerepairjob.id")),
        sa.Column("note", sa.String()), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stockmovement_parent_account_id", "stockmovement", ["parent_account_id"])
    op.create_index("ix_stockmovement_location_id", "stockmovement", ["location_id"])
    op.create_index("ix_stockmovement_part_id", "stockmovement", ["part_id"])
    op.create_index("ix_stockmovement_kind", "stockmovement", ["kind"])
    op.create_index("ix_stockmovement_shoe_repair_job_id", "stockmovement", ["shoe_repair_job_id"])

    op.create_table(
        "shoejobpartuse", _id(),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shoe_repair_job_id", sa.Uuid(), sa.ForeignKey("shoerepairjob.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Uuid(), sa.ForeignKey("stockpart.id"), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("stocklocation.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_shoejobpartuse_tenant_id", "shoejobpartuse", ["tenant_id"])
    op.create_index("ix_shoejobpartuse_shoe_repair_job_id", "shoejobpartuse", ["shoe_repair_job_id"])

    op.create_table(
        "hqpurchaserecord", _id(), _parent(),
        sa.Column("purchase_ref", sa.String(120), nullable=False), sa.Column("purchase_date", sa.Date()),
        sa.Column("store", sa.String(120)), sa.Column("customer_name", sa.String(200)),
        sa.Column("customer_email", sa.String(254)), sa.Column("customer_phone", sa.String(40)),
        sa.Column("model_name", sa.String(120)), sa.Column("size", sa.String(40)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hqpurchaserecord_parent_account_id", "hqpurchaserecord", ["parent_account_id"])
    op.create_index("ix_hqpurchaserecord_purchase_ref", "hqpurchaserecord", ["purchase_ref"])
    op.create_index("ix_hqpurchaserecord_customer_name", "hqpurchaserecord", ["customer_name"])
    op.create_index("ix_hqpurchaserecord_customer_email", "hqpurchaserecord", ["customer_email"])
    op.create_index("ix_hqpurchaserecord_customer_phone", "hqpurchaserecord", ["customer_phone"])


def downgrade():
    for table in ("hqpurchaserecord", "shoejobpartuse", "stockmovement", "stocktransferline", "stocktransfer",
                  "stocklevel", "stocklocation", "hqshoemodelpart", "hqshoemodel", "stockpart"):
        op.drop_table(table)
