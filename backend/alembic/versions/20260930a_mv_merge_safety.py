"""Separate dispatch eligibility from identity and record MV merge provenance."""
import sqlalchemy as sa
from alembic import op

revision = "20260930a_mv_merge_safety"
down_revision = "20260927a_invite_reminder"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tenant") as batch:
        batch.add_column(sa.Column("mobile_dispatch_paused", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("merged_into_tenant_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_tenant_merged_into", "tenant", ["merged_into_tenant_id"], ["id"])
    op.add_column("parentaccounteventlog", sa.Column("details_json", sa.String(), nullable=True))


def downgrade():
    op.drop_column("parentaccounteventlog", "details_json")
    with op.batch_alter_table("tenant") as batch:
        batch.drop_constraint("fk_tenant_merged_into", type_="foreignkey")
        batch.drop_column("merged_into_tenant_id")
        batch.drop_column("mobile_dispatch_paused")
