from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, PLAN_FEATURES, get_auth_context, require_owner
from ..limiter import limiter
from ..models import (
    AuthSessionResponse,
    AuthSessionSiteOption,
    ActiveSiteSwitchRequest,
    ActiveSiteSwitchResponse,
    BootstrapResponse,
    LoginRequest,
    MultiSiteLoginRequest,
    MultiSiteLoginResponse,
    ParentAccount,
    ParentAccountEventLog,
    ParentAccountMembership,
    PublicUser,
    RepairJob,
    TenantEventLog,
    TenantSignupRequest,
    TenantPlanUpdateRequest,
    TenantSignupResponse,
    Tenant,
    TenantBootstrap,
    TokenResponse,
    User,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])

VALID_PLAN_CODES = {"shoe", "watch", "auto_key", "enterprise"}


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_slug(value: str) -> str:
    return value.strip().lower()


def _normalize_plan_code(value: str | None) -> str:
    if value is None:
        return "enterprise"
    plan_code = value.strip().lower()
    if plan_code not in VALID_PLAN_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{value}'")
    return plan_code


def _validate_password_strength(value: str) -> None:
    password = value or ""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")


def _build_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


def _get_or_create_parent_account(session: Session, owner_email: str, owner_name: str) -> ParentAccount:
    parent = session.exec(
        select(ParentAccount).where(ParentAccount.owner_email == owner_email)
    ).first()
    if parent:
        return parent
    parent = ParentAccount(name=f"{owner_name} Group", owner_email=owner_email)
    session.add(parent)
    session.flush()
    return parent


def _ensure_parent_membership(session: Session, parent: ParentAccount, user: User) -> None:
    existing = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent.id)
        .where(ParentAccountMembership.user_id == user.id)
    ).first()
    if existing:
        return
    session.add(
        ParentAccountMembership(
            parent_account_id=parent.id,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
    )


def _build_available_sites_for_email(session: Session, email: str) -> list[AuthSessionSiteOption]:
    parents = session.exec(select(ParentAccount).where(ParentAccount.owner_email == email)).all()
    if not parents:
        return []

    parent_ids = [p.id for p in parents]
    memberships = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id.in_(parent_ids))
        .order_by(ParentAccountMembership.created_at)
    ).all()

    sites: list[AuthSessionSiteOption] = []
    seen: set[UUID] = set()
    for membership in memberships:
        user = session.get(User, membership.user_id)
        if not user or not user.is_active or user.email != email:
            continue
        tenant = session.get(Tenant, membership.tenant_id)
        if not tenant:
            continue
        if tenant.id in seen:
            continue
        seen.add(tenant.id)
        sites.append(
            AuthSessionSiteOption(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                user_id=user.id,
                role=user.role,
            )
        )

    return sorted(sites, key=lambda s: (s.tenant_name.lower(), s.tenant_slug.lower()))


def _create_default_owner(session: Session, tenant: Tenant) -> User:
    owner = User(
        tenant_id=tenant.id,
        email=settings.startup_seed_owner_email,
        full_name="Admin",
        role="owner",
        password_hash=hash_password(settings.startup_seed_owner_password),
        is_active=True,
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    return owner


def _build_auth_session_response(session: Session, tenant: Tenant, user: User) -> AuthSessionResponse:
    normalized_plan = _normalize_plan_code(tenant.plan_code)
    enabled = sorted(PLAN_FEATURES.get(normalized_plan, PLAN_FEATURES["enterprise"]))
    available_sites = _build_available_sites_for_email(session, user.email)
    if not available_sites:
        available_sites = [
            AuthSessionSiteOption(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                user_id=user.id,
                role=user.role,
            )
        ]
    return AuthSessionResponse(
        user=_build_public_user(user),
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        plan_code=normalized_plan,
        enabled_features=enabled,
        active_site_tenant_id=tenant.id,
        available_sites=available_sites,
    )


@router.post("/signup", response_model=TenantSignupResponse)
def signup(payload: TenantSignupRequest, session: Session = Depends(get_session)):
    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.email)
    owner_name = payload.full_name.strip()
    tenant_name = payload.tenant_name.strip()

    if not tenant_slug:
        raise HTTPException(status_code=400, detail="Tenant slug is required")
    if not tenant_name:
        raise HTTPException(status_code=400, detail="Tenant name is required")
    if not owner_name:
        raise HTTPException(status_code=400, detail="Full name is required")
    if not owner_email or "@" not in owner_email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    _validate_password_strength(payload.password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    plan_code = _normalize_plan_code(payload.plan_code)

    tenant = Tenant(name=tenant_name, slug=tenant_slug, plan_code=plan_code)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=owner_email,
        full_name=owner_name,
        role="owner",
        password_hash=hash_password(payload.password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    parent = _get_or_create_parent_account(session, owner_email, owner_name)
    _ensure_parent_membership(session, parent, owner)
    session.commit()

    token_subject = f"{tenant.id}:{owner.id}:{owner.role}"
    token, expires = create_access_token(token_subject)
    return TenantSignupResponse(
        tenant_id=tenant.id,
        user=_build_public_user(owner),
        access_token=token,
        expires_in_seconds=expires,
    )


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(get_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled")

    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.owner_email)
    _validate_password_strength(payload.owner_password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    plan_code = _normalize_plan_code(payload.plan_code)

    tenant = Tenant(name=payload.tenant_name.strip(), slug=tenant_slug, plan_code=plan_code)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=owner_email,
        full_name=payload.owner_full_name.strip(),
        role="owner",
        password_hash=hash_password(payload.owner_password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    parent = _get_or_create_parent_account(session, owner_email, payload.owner_full_name.strip())
    _ensure_parent_membership(session, parent, owner)
    session.commit()

    return BootstrapResponse(tenant_id=tenant.id, owner_user=_build_public_user(owner))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
def login(request: Request, payload: LoginRequest, session: Session = Depends(get_session)):
    tenant = session.exec(select(Tenant).where(Tenant.slug == _normalize_slug(payload.tenant_slug))).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = session.exec(
        select(User).where(User.tenant_id == tenant.id).where(User.email == _normalize_email(payload.email))
    ).first()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_user_id=user.id,
            actor_email=user.email,
            entity_type="session",
            event_type="login",
            event_summary=f"{user.email} logged in",
        )
    )
    session.commit()

    token_subject = f"{tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    return TokenResponse(access_token=token, expires_in_seconds=expires)


@router.post("/multi-site-login", response_model=MultiSiteLoginResponse)
@limiter.limit("20/minute")
def multi_site_login(request: Request, payload: MultiSiteLoginRequest, session: Session = Depends(get_session)):
    email = _normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    sites = _build_available_sites_for_email(session, email)
    if not sites:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    valid_sites: list[AuthSessionSiteOption] = []
    for site in sites:
        user = session.get(User, site.user_id)
        if user and verify_password(payload.password, user.password_hash):
            valid_sites.append(site)

    if not valid_sites:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    selected = valid_sites[0]
    # Log login event for the active site
    session.add(
        TenantEventLog(
            tenant_id=selected.tenant_id,
            actor_user_id=selected.user_id,
            actor_email=email,
            entity_type="session",
            event_type="login",
            event_summary=f"{email} logged in via multi-site login",
        )
    )
    session.commit()

    token_subject = f"{selected.tenant_id}:{selected.user_id}:{selected.role}"
    token, expires = create_access_token(token_subject)
    return MultiSiteLoginResponse(
        access_token=token,
        expires_in_seconds=expires,
        active_site_tenant_id=selected.tenant_id,
        available_sites=valid_sites,
    )


@router.post("/dev-auto-login", response_model=TokenResponse)
def dev_auto_login(session: Session = Depends(get_session)):
    if settings.app_env.lower() == "production" or not settings.allow_dev_auto_login:
        raise HTTPException(status_code=403, detail="Dev auto-login is disabled")

    tenants = session.exec(select(Tenant)).all()
    if not tenants:
        tenant = Tenant(name=settings.startup_seed_tenant_name, slug=settings.startup_seed_tenant_slug)
        session.add(tenant)
        session.flush()
        user = _create_default_owner(session, tenant)
        token_subject = f"{tenant.id}:{user.id}:{user.role}"
        token, expires = create_access_token(token_subject)
        return TokenResponse(access_token=token, expires_in_seconds=expires)

    selected_tenant = tenants[0]
    selected_count = -1
    for tenant in tenants:
        tenant_job_count = session.exec(
            select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant.id)
        ).one()
        count = int(tenant_job_count)
        if count > selected_count:
            selected_count = count
            selected_tenant = tenant

    user = session.exec(
        select(User)
        .where(User.tenant_id == selected_tenant.id)
        .where(User.email == settings.startup_seed_owner_email)
        .where(User.is_active)
    ).first()

    if not user:
        user = session.exec(
            select(User)
            .where(User.tenant_id == selected_tenant.id)
            .where(User.is_active)
            .order_by(User.created_at)
        ).first()

    if not user:
        user = _create_default_owner(session, selected_tenant)

    token_subject = f"{selected_tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    return TokenResponse(access_token=token, expires_in_seconds=expires)


@router.get("/session", response_model=AuthSessionResponse)
def get_session_info(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return _build_auth_session_response(session, tenant, user)


@router.patch("/session/site", response_model=ActiveSiteSwitchResponse)
def switch_active_site(
    payload: ActiveSiteSwitchRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    sites = _build_available_sites_for_email(session, current_user.email)
    target = next((s for s in sites if s.tenant_id == payload.tenant_id), None)
    if not target:
        raise HTTPException(status_code=403, detail="Target site is not available for this login")

    parent = session.exec(
        select(ParentAccount).where(ParentAccount.owner_email == current_user.email)
    ).first()
    if parent:
        source_tenant = session.get(Tenant, auth.tenant_id)
        target_tenant = session.get(Tenant, target.tenant_id)
        source_label = source_tenant.slug if source_tenant else str(auth.tenant_id)
        target_label = target_tenant.slug if target_tenant else str(target.tenant_id)
        session.add(
            ParentAccountEventLog(
                parent_account_id=parent.id,
                tenant_id=target.tenant_id,
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                event_type="switch_site",
                event_summary=f"Switched active site from '{source_label}' to '{target_label}'",
            )
        )
        session.commit()

    token_subject = f"{target.tenant_id}:{target.user_id}:{target.role}"
    token, expires = create_access_token(token_subject)
    return ActiveSiteSwitchResponse(
        access_token=token,
        expires_in_seconds=expires,
        active_site_tenant_id=target.tenant_id,
        available_sites=sites,
    )


@router.patch("/session/plan", response_model=AuthSessionResponse)
def update_session_plan(
    payload: TenantPlanUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    old_plan = tenant.plan_code
    tenant.plan_code = _normalize_plan_code(payload.plan_code)
    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_user_id=user.id,
            actor_email=user.email,
            entity_type="tenant",
            event_type="plan_changed",
            event_summary=f"Plan changed from '{old_plan}' to '{tenant.plan_code}' by {user.email}",
        )
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    return _build_auth_session_response(session, tenant, user)
