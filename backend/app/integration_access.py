"""Management belongs to an HQ workspace, never to a shop entered from HQ."""
from fastapi import HTTPException
from sqlmodel import Session, select

from .dependencies import AuthContext
from .models import ParentAccount, ParentAccountSite, User
from .parent_network import PARENT_ROLE_HQ_ADMIN, parent_role_for_user


def can_manage_tenant_integrations(session: Session, auth: AuthContext) -> bool:
    if not auth.sid or auth.support_actor_user_id is not None:
        return False
    user = session.get(User, auth.user_id)
    if user is None or not user.is_active or user.tenant_id != auth.tenant_id:
        return False
    # The org chart is authoritative. Brand, plan, slug, owner email and access
    # to other shops cannot turn the active shop into an HQ workspace.
    sites = session.exec(select(ParentAccountSite).where(
        ParentAccountSite.tenant_id == auth.tenant_id,
        ParentAccountSite.network_role == "hq",
    )).all()
    return any(
        (parent := session.get(ParentAccount, site.parent_account_id)) is not None
        and parent_role_for_user(session, parent, user) == PARENT_ROLE_HQ_ADMIN
        for site in sites
    )


def require_tenant_integration_management(session: Session, auth: AuthContext) -> None:
    if not can_manage_tenant_integrations(session, auth):
        raise HTTPException(status_code=403, detail="Manage API keys and webhooks from your own HQ account")
