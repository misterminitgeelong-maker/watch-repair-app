"""add tenant-scoped uniqueness for auto-key numbers

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f7
Create Date: 2026-04-13

"""

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("autokeyjob") as batch:
        batch.create_unique_constraint(
            "uq_autokeyjob_tenant_job_number",
            ["tenant_id", "job_number"],
        )
    with op.batch_alter_table("autokeyinvoice") as batch:
        batch.create_unique_constraint(
            "uq_autokeyinvoice_tenant_invoice_number",
            ["tenant_id", "invoice_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("autokeyinvoice") as batch:
        batch.drop_constraint("uq_autokeyinvoice_tenant_invoice_number", type_="unique")
    with op.batch_alter_table("autokeyjob") as batch:
        batch.drop_constraint("uq_autokeyjob_tenant_job_number", type_="unique")
