"""add db integrity constraints

Revision ID: f62d271a3526
Revises: 9a7c6e5a8642
Create Date: 2026-03-24 22:34:15.632273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f62d271a3526'
down_revision: Union[str, None] = '9a7c6e5a8642'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Quote "user": in PostgreSQL `user` is reserved; unquoted FROM user targets the wrong relation.
    duplicate_users = bind.execute(
        sa.text(
            """
            SELECT tenant_id, email, COUNT(*) AS c
            FROM "user"
            GROUP BY tenant_id, email
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if duplicate_users:
        raise RuntimeError(
            "Cannot add user uniqueness constraint: duplicate (tenant_id, email) rows exist."
        )

    # Enforce tenant-scoped user identity uniqueness.
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("user") as batch_op:
            batch_op.create_unique_constraint("uq_user_tenant_email", ["tenant_id", "email"])
    else:
        op.create_unique_constraint("uq_user_tenant_email", "user", ["tenant_id", "email"])

    # Non-negative integrity checks for money/time/file-size fields.
    for table_name, checks in (
        ("repairjob", [("ck_repairjob_deposit_cents_non_negative", "deposit_cents >= 0")]),
        ("invoice", [
            ("ck_invoice_subtotal_cents_non_negative", "subtotal_cents >= 0"),
            ("ck_invoice_tax_cents_non_negative", "tax_cents >= 0"),
            ("ck_invoice_total_cents_non_negative", "total_cents >= 0"),
        ]),
        ("payment", [("ck_payment_amount_cents_non_negative", "amount_cents >= 0")]),
        ("worklog", [("ck_worklog_minutes_spent_non_negative", "minutes_spent >= 0")]),
        ("attachment", [("ck_attachment_file_size_bytes_non_negative", "file_size_bytes IS NULL OR file_size_bytes >= 0")]),
        ("autokeyinvoice", [
            ("ck_autokeyinvoice_subtotal_cents_non_negative", "subtotal_cents >= 0"),
            ("ck_autokeyinvoice_tax_cents_non_negative", "tax_cents >= 0"),
            ("ck_autokeyinvoice_total_cents_non_negative", "total_cents >= 0"),
        ]),
        ("customeraccountinvoice", [
            ("ck_customeraccountinvoice_subtotal_cents_non_negative", "subtotal_cents >= 0"),
            ("ck_customeraccountinvoice_tax_cents_non_negative", "tax_cents >= 0"),
            ("ck_customeraccountinvoice_total_cents_non_negative", "total_cents >= 0"),
        ]),
        ("customeraccountinvoiceline", [("ck_customeraccountinvoiceline_amount_cents_non_negative", "amount_cents >= 0")]),
    ):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table_name) as batch_op:
                for name, condition in checks:
                    batch_op.create_check_constraint(name, condition)
        else:
            for name, condition in checks:
                op.create_check_constraint(name, table_name, condition)


def downgrade() -> None:
    bind = op.get_bind()
    check_drops = (
        ("customeraccountinvoiceline", ["ck_customeraccountinvoiceline_amount_cents_non_negative"]),
        ("customeraccountinvoice", [
            "ck_customeraccountinvoice_total_cents_non_negative",
            "ck_customeraccountinvoice_tax_cents_non_negative",
            "ck_customeraccountinvoice_subtotal_cents_non_negative",
        ]),
        ("autokeyinvoice", [
            "ck_autokeyinvoice_total_cents_non_negative",
            "ck_autokeyinvoice_tax_cents_non_negative",
            "ck_autokeyinvoice_subtotal_cents_non_negative",
        ]),
        ("attachment", ["ck_attachment_file_size_bytes_non_negative"]),
        ("worklog", ["ck_worklog_minutes_spent_non_negative"]),
        ("payment", ["ck_payment_amount_cents_non_negative"]),
        ("invoice", [
            "ck_invoice_total_cents_non_negative",
            "ck_invoice_tax_cents_non_negative",
            "ck_invoice_subtotal_cents_non_negative",
        ]),
        ("repairjob", ["ck_repairjob_deposit_cents_non_negative"]),
    )
    for table_name, names in check_drops:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table_name) as batch_op:
                for name in names:
                    batch_op.drop_constraint(name, type_="check")
        else:
            for name in names:
                op.drop_constraint(name, table_name, type_="check")

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("user") as batch_op:
            batch_op.drop_constraint("uq_user_tenant_email", type_="unique")
    else:
        op.drop_constraint("uq_user_tenant_email", "user", type_="unique")
