"""public lead dedupe refs + network scoping for the dispatch pool"""
import sqlalchemy as sa
from alembic import op

revision = "20261019a_lead_routing_integrity"
down_revision = "20261009a_hq_settings"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("prospectlead") as batch:
        batch.add_column(sa.Column("external_ref", sa.String(length=200), nullable=True))
        batch.create_unique_constraint("uq_prospectlead_external_ref", ["external_ref"])
    with op.batch_alter_table("intakejob") as batch:
        batch.add_column(sa.Column("parent_account_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("external_ref", sa.String(length=200), nullable=True))
        batch.create_foreign_key("fk_intakejob_parent_account", "parentaccount", ["parent_account_id"], ["id"])
        batch.create_index("ix_intakejob_parent_account_id", ["parent_account_id"])
        batch.create_unique_constraint("uq_intakejob_external_ref", ["external_ref"])

    # Backfill: with exactly one HQ network there is no ambiguity about who owns
    # existing pool jobs. With several, leave NULL (hidden) rather than guess.
    bind = op.get_bind()
    parents = bind.execute(sa.text("SELECT id FROM parentaccount")).fetchall()
    if len(parents) == 1:
        bind.execute(
            sa.text("UPDATE intakejob SET parent_account_id = :pid WHERE parent_account_id IS NULL"),
            {"pid": parents[0][0]},
        )


def downgrade():
    with op.batch_alter_table("intakejob") as batch:
        batch.drop_constraint("uq_intakejob_external_ref", type_="unique")
        batch.drop_index("ix_intakejob_parent_account_id")
        batch.drop_constraint("fk_intakejob_parent_account", type_="foreignkey")
        batch.drop_column("external_ref")
        batch.drop_column("parent_account_id")
    with op.batch_alter_table("prospectlead") as batch:
        batch.drop_constraint("uq_prospectlead_external_ref", type_="unique")
        batch.drop_column("external_ref")
