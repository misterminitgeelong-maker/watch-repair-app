"""add blade_code chip_type tech_notes to autokeyjob, auto_key_job_id to attachment

Revision ID: o8a9b0c1d2e3
Revises: n9h0b1c2d3e4
Create Date: 2025-03-23

"""
from alembic import op
import sqlalchemy as sa


revision = 'o8a9b0c1d2e3'
down_revision = 'n9h0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("autokeyjob", sa.Column("blade_code", sa.String(), nullable=True))
    op.add_column("autokeyjob", sa.Column("chip_type", sa.String(), nullable=True))
    op.add_column("autokeyjob", sa.Column("tech_notes", sa.Text(), nullable=True))

    op.add_column("attachment", sa.Column("auto_key_job_id", sa.Uuid(), nullable=True))
    # SQLite cannot ALTER TABLE to add constraints; keep FK for non-SQLite.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_attachment_auto_key_job_id", "attachment", "autokeyjob", ["auto_key_job_id"], ["id"])
    op.create_index("ix_attachment_auto_key_job_id", "attachment", ["auto_key_job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attachment_auto_key_job_id", table_name="attachment")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_attachment_auto_key_job_id", "attachment", type_="foreignkey")
    op.drop_column("attachment", "auto_key_job_id")

    op.drop_column("autokeyjob", "tech_notes")
    op.drop_column("autokeyjob", "chip_type")
    op.drop_column("autokeyjob", "blade_code")
