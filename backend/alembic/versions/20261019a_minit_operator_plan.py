"""move Minit mobile-operator tenants from basic_auto_key to the uncapped minit_operator plan"""
import json

from alembic import op
import sqlalchemy as sa

revision = "20261019a_minit_operator_plan"
down_revision = "20261009a_hq_settings"
branch_labels = None
depends_on = None


# Mirrors app.minit_branding.MINIT_SITE_PLANS (inline so the migration is frozen).
_MINIT_SITE_PLANS = ["basic_auto_key", "booking_only", "minit_operator"]


def _set_hq_site_plans(plans_fn):
    """Minit's HqSettings row gates which plans HQ may assign (hq_access)."""
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, site_plans_json FROM hqsettings WHERE product_key = 'minit'")).fetchall()
    for row_id, raw in rows:
        plans = plans_fn(json.loads(raw or "[]"))
        bind.execute(
            sa.text("UPDATE hqsettings SET site_plans_json = :j WHERE id = :i"),
            {"j": json.dumps(sorted(plans)), "i": row_id},
        )


def upgrade():
    _set_hq_site_plans(lambda plans: set(plans) | {"minit_operator"})
    # Only Minit tenants that are operators (parentaccountsite.network_role) and
    # currently on basic_auto_key. Idempotent: a re-run matches nothing.
    op.execute(
        sa.text(
            "UPDATE tenant SET plan_code = 'minit_operator' "
            "WHERE is_minit = :t AND plan_code = 'basic_auto_key' "
            "AND id IN (SELECT tenant_id FROM parentaccountsite WHERE network_role = 'operator')"
        ).bindparams(sa.bindparam("t", True))
    )


def downgrade():
    _set_hq_site_plans(lambda plans: set(plans) - {"minit_operator"})
    op.execute(
        sa.text(
            "UPDATE tenant SET plan_code = 'basic_auto_key' "
            "WHERE is_minit = :t AND plan_code = 'minit_operator'"
        ).bindparams(sa.bindparam("t", True))
    )
