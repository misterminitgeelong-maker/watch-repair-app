"""enforce one auto-key invoice per quote + one cost-based invoice per job

Closes the duplicate-invoice race on job completion without forbidding
multi-quote jobs:

  - UNIQUE(auto_key_quote_id): at most one invoice per quote. NULLs stay
    distinct, so cost-based (quoteless) invoices are unaffected. This makes the
    manual "from quote", portal quote-approval, and completion auto-create
    paths race-safe.
  - Partial UNIQUE index on (auto_key_job_id) WHERE auto_key_quote_id IS NULL:
    at most one cost-based invoice per job, closing the no-quote completion
    race while still allowing one invoice per quote on multi-quote jobs.

The dedup step is defensive (app-level guards have always prevented these
duplicates, so it is normally a no-op) and non-destructive: it detaches the
quote link from later duplicates rather than deleting any invoice row.

Revision ID: 20260621_aki_invoice_uniq
Revises: 20260612_reconcile_shoe_tables
"""
import sqlalchemy as sa
from alembic import op

revision = "20260621_aki_invoice_uniq"
down_revision = "20260612_reconcile_shoe_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Defensive, non-destructive dedup: for invoices sharing a quote, keep the
    # earliest and detach the quote link from the rest (no rows deleted).
    op.execute(
        """
        UPDATE autokeyinvoice SET auto_key_quote_id = NULL
        WHERE auto_key_quote_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM autokeyinvoice e
              WHERE e.auto_key_quote_id = autokeyinvoice.auto_key_quote_id
                AND (
                    e.created_at < autokeyinvoice.created_at
                    OR (e.created_at = autokeyinvoice.created_at AND e.id < autokeyinvoice.id)
                )
          )
        """
    )

    with op.batch_alter_table("autokeyinvoice") as batch:
        batch.create_unique_constraint("uq_autokeyinvoice_quote", ["auto_key_quote_id"])

    op.create_index(
        "uq_autokeyinvoice_costbased_per_job",
        "autokeyinvoice",
        ["auto_key_job_id"],
        unique=True,
        sqlite_where=sa.text("auto_key_quote_id IS NULL"),
        postgresql_where=sa.text("auto_key_quote_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_autokeyinvoice_costbased_per_job", table_name="autokeyinvoice")
    with op.batch_alter_table("autokeyinvoice") as batch:
        batch.drop_constraint("uq_autokeyinvoice_quote", type_="unique")
