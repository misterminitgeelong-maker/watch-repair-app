"""move performance indexes to migration

Revision ID: bed1e400718f
Revises: r8n9m0o1b2l3
Create Date: 2026-03-24 21:58:45.323094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bed1e400718f'
down_revision: Union[str, None] = 'r8n9m0o1b2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    statements_by_table = {
        "repairjob": [
            "CREATE INDEX IF NOT EXISTS idx_repairjob_tenant_created ON repairjob (tenant_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_repairjob_tenant_status_created ON repairjob (tenant_id, status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_repairjob_tenant_customer_account_status ON repairjob (tenant_id, customer_account_id, status)",
        ],
        "shoerepairjob": [
            "CREATE INDEX IF NOT EXISTS idx_shoerepairjob_tenant_created ON shoerepairjob (tenant_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_shoerepairjob_tenant_status_created ON shoerepairjob (tenant_id, status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_shoerepairjob_tenant_customer_account_status ON shoerepairjob (tenant_id, customer_account_id, status)",
        ],
        "autokeyjob": [
            "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_scheduled_created ON autokeyjob (tenant_id, scheduled_at, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_status_scheduled ON autokeyjob (tenant_id, status, scheduled_at)",
            "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_assigned_scheduled ON autokeyjob (tenant_id, assigned_user_id, scheduled_at)",
        ],
        "quote": [
            "CREATE INDEX IF NOT EXISTS idx_quote_tenant_status_sent ON quote (tenant_id, status, sent_at)",
        ],
        "invoice": [
            "CREATE INDEX IF NOT EXISTS idx_invoice_tenant_status_created ON invoice (tenant_id, status, created_at DESC)",
        ],
        "payment": [
            "CREATE INDEX IF NOT EXISTS idx_payment_tenant_status_created ON payment (tenant_id, status, created_at DESC)",
        ],
        "tenanteventlog": [
            "CREATE INDEX IF NOT EXISTS idx_tenanteventlog_tenant_type_created ON tenanteventlog (tenant_id, event_type, created_at DESC)",
        ],
        "customeraccountmembership": [
            "CREATE INDEX IF NOT EXISTS idx_customeraccountmembership_tenant_account_created ON customeraccountmembership (tenant_id, customer_account_id, created_at)",
        ],
        "customeraccountinvoice": [
            "CREATE INDEX IF NOT EXISTS idx_customeraccountinvoice_tenant_account_created ON customeraccountinvoice (tenant_id, customer_account_id, created_at DESC)",
        ],
        "customeraccountinvoiceline": [
            "CREATE INDEX IF NOT EXISTS idx_customeraccountinvoiceline_tenant_invoice_created ON customeraccountinvoiceline (tenant_id, customer_account_invoice_id, created_at)",
        ],
    }
    for table_name, statements in statements_by_table.items():
        if not inspector.has_table(table_name):
            continue
        for statement in statements:
            op.execute(statement)


def downgrade() -> None:
    index_names = [
        "idx_customeraccountinvoiceline_tenant_invoice_created",
        "idx_customeraccountinvoice_tenant_account_created",
        "idx_customeraccountmembership_tenant_account_created",
        "idx_tenanteventlog_tenant_type_created",
        "idx_payment_tenant_status_created",
        "idx_invoice_tenant_status_created",
        "idx_quote_tenant_status_sent",
        "idx_autokeyjob_tenant_assigned_scheduled",
        "idx_autokeyjob_tenant_status_scheduled",
        "idx_autokeyjob_tenant_scheduled_created",
        "idx_shoerepairjob_tenant_customer_account_status",
        "idx_shoerepairjob_tenant_status_created",
        "idx_shoerepairjob_tenant_created",
        "idx_repairjob_tenant_customer_account_status",
        "idx_repairjob_tenant_status_created",
        "idx_repairjob_tenant_created",
    ]
    for index_name in index_names:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
