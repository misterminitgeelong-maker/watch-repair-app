"""
Cross-tenant by design: login and site switching, which resolve a user before a tenant is known.

Endpoints here take ``unscoped_session`` rather than ``get_session`` so the ORM
tenant filter in app/tenant_scope.py does not apply. That is deliberate and is
meant to be visible: an endpoint crossing the tenant boundary says so in its
signature, and these modules are the complete list of places that do.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, col, func, select

from ..config import settings
from ..database import get_session, unscoped_session
from ..dependencies import (
    AuthContext,
    LOWEST_PLAN_CODE,
    PLAN_FEATURES,
    VALID_PLAN_CODES,
    get_auth_context,
    normalize_plan_code,
    require_owner,
    stripe_billing_configured,
)
from ..limiter import limiter
from ..models import (
    AuthSessionResponse,
    AuthSessionSiteOption,
    ActiveSiteSwitchRequest,
    ActiveSiteSwitchResponse,
    BootstrapResponse,
    Customer,
    Invoice,
    LoginRequest,
    MultiSiteLoginRequest,
    MultiSiteLoginResponse,
    ParentAccount,
    RefreshRequest,
    RefreshSession,
    ParentAccountEventLog,
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
    Watch,
)
from ..parent_network import (
    PARENT_ROLE_HQ_ADMIN,
    grant_parent_role,
    is_hq_viewer_or_admin,
    link_site,
    parent_role_for_user,
    parents_for_user,
    sites_for_parent,
)
from ..security import create_access_token, create_refresh_token, decode_refresh_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])

def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_slug(value: str) -> str:
    return value.strip().lower()


def _normalize_plan_code(value: str | None, default_if_empty: str = "pro") -> str:
    plan_code = normalize_plan_code(value, default_if_empty=default_if_empty)
    if plan_code not in VALID_PLAN_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{value}'")
    return plan_code


def _validate_password_strength(value: str) -> None:
    password = value or ""
    min_len = settings.password_min_length
    if len(password) < min_len:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {min_len} characters",
        )
    if settings.password_require_number and not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one number",
        )
    if settings.password_require_special:
        special = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
        if not any(c in special for c in password):
            raise HTTPException(
                status_code=400,
                detail="Password must contain at least one special character (!@#$%^&* etc.)",
            )


def _build_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        mobile_commission_rules_json=getattr(user, "mobile_commission_rules_json", None),
    )


def _get_or_create_parent_account(session: Session, owner_email: str, owner_name: str) -> ParentAccount:
    parent = session.exec(
        select(ParentAccount)
        .where(ParentAccount.owner_email == owner_email)
        .order_by(col(ParentAccount.created_at).asc(), col(ParentAccount.id).asc())
    ).first()
    if parent:
        return parent
    parent = ParentAccount(name=f"{owner_name} Group", owner_email=owner_email)
    session.add(parent)
    session.flush()
    return parent


def _ensure_parent_membership(session: Session, parent: ParentAccount, user: User) -> None:
    """Put the user's tenant in the network and make the user an HQ admin of it.

    Called for every fresh signup/bootstrap: a single-shop owner is the admin
    of their own one-site network, which is what lets them add a second shop
    later without any migration of access.
    """
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is not None:
        link_site(session, parent_id=parent.id, tenant=tenant)
    grant_parent_role(session, parent_id=parent.id, user_id=user.id, role=PARENT_ROLE_HQ_ADMIN)


def _hq_parents_for_email(session: Session, email: str) -> list[ParentAccount]:
    """Networks any login with this email may switch sites within.

    A person with the same email in several tenants is one human; the site
    switcher is theirs if any of those logins holds an HQ role on the network
    (explicitly, or as the account owner).
    """
    users = session.exec(
        select(User)
        .where(User.email == email)
        .where(User.is_active == True)  # noqa: E712
        .order_by(col(User.created_at).asc(), col(User.id).asc())
    ).all()
    ordered: list[ParentAccount] = []
    seen: set[UUID] = set()
    for user in users:
        for parent in parents_for_user(session, user):
            if parent.id in seen:
                continue
            if not is_hq_viewer_or_admin(parent_role_for_user(session, parent, user)):
                continue
            seen.add(parent.id)
            ordered.append(parent)
    return ordered


def _build_available_sites_for_email(session: Session, email: str) -> list[AuthSessionSiteOption]:
    """Sites this email can switch into: every tenant in a network it holds an
    HQ role on, where a login with the same email exists."""
    parents = _hq_parents_for_email(session, email)
    if not parents:
        return []

    tenant_ids: list[UUID] = []
    for parent in parents:
        for site in sites_for_parent(session, parent.id):
            if site.tenant_id not in tenant_ids:
                tenant_ids.append(site.tenant_id)
    if not tenant_ids:
        return []

    users_by_tenant = {
        u.tenant_id: u
        for u in session.exec(
            select(User)
            .where(col(User.tenant_id).in_(tenant_ids))
            .where(User.email == email)
            .where(User.is_active == True)  # noqa: E712
            .order_by(col(User.created_at).desc())
        ).all()
    }
    tenants_by_id = {
        t.id: t
        for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()
    }

    sites: list[AuthSessionSiteOption] = []
    for tenant_id in tenant_ids:
        tenant = tenants_by_id.get(tenant_id)
        user = users_by_tenant.get(tenant_id)
        if not tenant or not user:
            continue
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


def _site_option_for_tenant_user(tenant: Tenant, user: User) -> AuthSessionSiteOption:
    return AuthSessionSiteOption(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        user_id=user.id,
        role=user.role,
    )


def _session_available_sites(session: Session, tenant: Tenant, user: User) -> list[AuthSessionSiteOption]:
    """HQ logins only need the active site in session — full network is on parent-account APIs."""
    from ..minit_branding import is_minit_hq_ui

    if is_minit_hq_ui(tenant):
        return [_site_option_for_tenant_user(tenant, user)]
    sites = _build_available_sites_for_email(session, user.email)
    if not sites:
        return [_site_option_for_tenant_user(tenant, user)]
    return sites


def _get_site_option_for_email_tenant(
    session: Session,
    email: str,
    tenant_id: UUID,
) -> AuthSessionSiteOption | None:
    for site in _build_available_sites_for_email(session, email):
        if site.tenant_id == tenant_id:
            return site
    return None


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
    from ..minit_branding import ensure_minit_tenant_plan, effective_plan_code, is_minit_hq_ui, tenant_product

    before_plan = tenant.plan_code
    tenant = ensure_minit_tenant_plan(session, tenant)
    if tenant.plan_code != before_plan:
        session.commit()
        session.refresh(tenant)

    normalized_plan = effective_plan_code(tenant)
    enabled = sorted(PLAN_FEATURES.get(normalized_plan, PLAN_FEATURES[LOWEST_PLAN_CODE]))
    product = tenant_product(tenant.slug)
    available_sites = _session_available_sites(session, tenant, user)
    cal_tz = settings.schedule_calendar_timezone
    now_shop = datetime.now(ZoneInfo(cal_tz))
    shop_today = now_shop.strftime("%Y-%m-%d")
    return AuthSessionResponse(
        user=_build_public_user(user),
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        product=product,
        is_minit_hq_ui=is_minit_hq_ui(tenant),
        plan_code=normalized_plan,
        enabled_features=enabled,
        active_site_tenant_id=tenant.id,
        available_sites=available_sites,
        schedule_calendar_timezone=cal_tz,
        shop_calendar_today_ymd=shop_today,
        signup_payment_pending=bool(getattr(tenant, "signup_payment_pending", False)),
        subscription_status=getattr(tenant, "subscription_status", None),
        trial_end=(
            getattr(tenant, "trial_end", None).isoformat()
            if getattr(tenant, "trial_end", None) is not None
            else None
        ),
        mobile_services_customer_sms_enabled=bool(getattr(tenant, "mobile_services_customer_sms_enabled", True)),
        tenant_business_address=getattr(tenant, "business_address", None),
    )


def _seed_demo_data_for_tenant(session: Session, tenant: Tenant, actor: User) -> dict[str, int]:
    from ..demo_shop import reset_and_seed_demo_shop

    return reset_and_seed_demo_shop(session, tenant, actor)


@router.post("/signup", response_model=TenantSignupResponse)
@limiter.limit("10/minute")
def signup(request: Request, payload: TenantSignupRequest, session: Session = Depends(unscoped_session)):
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

    plan_code = _normalize_plan_code(payload.plan_code, default_if_empty="basic_all_tabs")

    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code=plan_code,
        signup_payment_pending=stripe_billing_configured(),
    )
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

    # Auto-create a Stripe Connect Express account so invoice payments flow
    # through the tenant's own Stripe account from day one.
    if stripe_billing_configured():
        try:
            import stripe as _stripe  # type: ignore[import]
            _stripe.api_key = settings.stripe_secret_key
            country = (settings.stripe_connect_default_country or "AU").strip().upper()[:2]
            connect_acct = _stripe.Account.create(
                type="express",
                country=country,
                capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
                metadata={"tenant_id": str(tenant.id), "tenant_slug": tenant.slug},
                business_profile={"name": (tenant.name or "Shop")[:100]},
            )
            tenant.stripe_connect_account_id = connect_acct["id"]
            tenant.stripe_connect_charges_enabled = bool(connect_acct.get("charges_enabled"))
            tenant.stripe_connect_payouts_enabled = bool(connect_acct.get("payouts_enabled"))
            tenant.stripe_connect_details_submitted = bool(connect_acct.get("details_submitted"))
            session.add(tenant)
            session.add(TenantEventLog(
                tenant_id=tenant.id,
                entity_type="tenant",
                event_type="stripe_connect_account_created",
                event_summary="Stripe Express account auto-created at signup",
            ))
            session.commit()
        except Exception:
            logging.getLogger(__name__).exception(
                "signup.stripe_connect_create_failed tenant=%s", tenant.id
            )

    token, expires = create_access_token(tenant.id, owner.id, owner.role)
    refresh_token, refresh_expires = create_refresh_token(tenant.id, owner.id, owner.role)
    return TenantSignupResponse(
        tenant_id=tenant.id,
        user=_build_public_user(owner),
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(unscoped_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled")

    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.owner_email)
    _validate_password_strength(payload.owner_password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    plan_code = _normalize_plan_code(payload.plan_code, default_if_empty="basic_all_tabs")

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



# Dynamically set rate limit based on environment
def get_login_rate_limit():
    return settings.rate_limit_auth_login_test if settings.app_env == "test" else settings.rate_limit_auth_login

def _issue_session_tokens(
    session: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    role: str,
    request: Request | None = None,
) -> tuple[str, int, str, int]:
    """Create an access+refresh token pair backed by a persisted RefreshSession.

    Returns ``(access_token, access_expires, refresh_token, refresh_expires)``.
    The session id (``sid``) is shared by both tokens and is the RefreshSession
    primary key; the refresh token also carries a ``jti`` matching the row, so the
    session can be revoked per-device via ``/auth/sessions/revoke-others``.
    """
    sid = uuid4()
    jti = uuid4().hex
    now = datetime.now(timezone.utc)
    access, access_exp = create_access_token(tenant_id, user_id, role, sid=str(sid))
    refresh, refresh_exp = create_refresh_token(tenant_id, user_id, role, sid=str(sid), jti=jti)
    user_agent = None
    if request is not None:
        user_agent = (request.headers.get("user-agent") or "")[:400] or None
    session.add(
        RefreshSession(
            id=sid,
            tenant_id=tenant_id,
            user_id=user_id,
            jti=jti,
            created_at=now,
            last_used_at=now,
            expires_at=now + timedelta(seconds=refresh_exp),
            user_agent=user_agent,
        )
    )
    session.commit()
    return access, access_exp, refresh, refresh_exp


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_login_rate_limit)
def login(request: Request, payload: LoginRequest, session: Session = Depends(unscoped_session)):
    return _login_impl(request, payload, session)

def _login_impl(request: Request, payload: LoginRequest, session: Session = Depends(unscoped_session)):
    tenant = session.exec(select(Tenant).where(Tenant.slug == _normalize_slug(payload.tenant_slug))).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="Shop is suspended. Contact platform admin.")

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

    token, expires, refresh_token, refresh_expires = _issue_session_tokens(
        session, tenant_id=tenant.id, user_id=user.id, role=user.role, request=request
    )
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/multi-site-login", response_model=MultiSiteLoginResponse)
@limiter.limit("20/minute")
def multi_site_login(request: Request, payload: MultiSiteLoginRequest, session: Session = Depends(unscoped_session)):
    email = _normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    sites = _build_available_sites_for_email(session, email)
    if not sites:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    candidate = session.exec(
        select(User).where(User.email == email).where(User.is_active == True)  # noqa: E712
    ).first()
    if not candidate or not verify_password(payload.password, candidate.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    valid_sites = sites
    from ..minit_branding import is_minit_hq_ui

    selected = valid_sites[0]
    for site in valid_sites:
        tenant = session.get(Tenant, site.tenant_id)
        if tenant and is_minit_hq_ui(tenant):
            selected = site
            break
    hq_parents = _hq_parents_for_email(session, email)
    parent = hq_parents[0] if hq_parents else None
    if parent:
        session.add(
            ParentAccountEventLog(
                parent_account_id=parent.id,
                tenant_id=selected.tenant_id,
                actor_user_id=selected.user_id,
                actor_email=email,
                event_type="multi_site_login",
                event_summary=f"{email} logged in with {len(valid_sites)} accessible sites",
            )
        )
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

    token, expires, refresh_token, refresh_expires = _issue_session_tokens(
        session,
        tenant_id=selected.tenant_id,
        user_id=selected.user_id,
        role=selected.role,
        request=request,
    )
    selected_tenant = session.get(Tenant, selected.tenant_id)
    selected_user = session.get(User, selected.user_id)
    response_sites = (
        _session_available_sites(session, selected_tenant, selected_user)
        if selected_tenant and selected_user
        else valid_sites
    )
    return MultiSiteLoginResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
        active_site_tenant_id=selected.tenant_id,
        available_sites=response_sites,
    )


@router.post("/demo-seed")
def seed_demo_data(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # This used to only top a shop up with extra sample rows, so restricting it
    # in production alone was enough. It now wipes the tenant's jobs, customers,
    # invoices and bookings before reseeding, and a destructive endpoint that any
    # owner can call against their own live shop is not something to gate on
    # APP_ENV — a staging or local shop is somebody's work too. The allow-list
    # applies everywhere now.
    allowed = [
        _normalize_slug(settings.startup_seed_tenant_slug),
        *([_normalize_slug(s) for s in [settings.testing_tenant_slug] if (s or "").strip()]),
    ]
    if tenant.slug not in [a for a in allowed if a]:
        raise HTTPException(
            status_code=403,
            detail="Demo seeding rebuilds the shop from scratch and is only available for the configured demo or testing tenant",
        )

    created = _seed_demo_data_for_tenant(session, tenant, user)
    return {"ok": True, "created": created}


@router.post("/ensure-testing-tenant")
def ensure_testing_tenant_endpoint(session: Session = Depends(unscoped_session)):
    """Force-create/update the testing tenant from env vars. Use when login fails with 'Invalid credentials'.
    Enable with ALLOW_ENSURE_TESTING_TENANT=true or when APP_ENV is not production."""
    if settings.app_env.lower() == "production" and not settings.allow_ensure_testing_tenant:
        raise HTTPException(status_code=403, detail="Set ALLOW_ENSURE_TESTING_TENANT=true in .env to enable")
    from ..startup_seed import ensure_testing_tenant

    result = ensure_testing_tenant(session)
    if not result:
        return {
            "ok": False,
            "detail": "Testing tenant not configured. Set TESTING_TENANT_SLUG, TESTING_OWNER_EMAIL, TESTING_OWNER_PASSWORD in .env",
        }
    return {"ok": True, "tenant_slug": result.slug, "detail": "Testing tenant ready. Try signing in."}


@router.post("/ensure-minit-pilot")
def ensure_minit_pilot_endpoint(session: Session = Depends(unscoped_session)):
    """Create or refresh Mister Minit HQ + pilot shops from MINIT_* env vars.

    Use when Minit login returns 'Invalid credentials' because the pilot was never seeded on this database.
    Enable with ALLOW_ENSURE_MINIT_PILOT=true (set false again after seeding).
    """
    if settings.app_env.lower() == "production" and not settings.allow_ensure_minit_pilot:
        raise HTTPException(status_code=403, detail="Set ALLOW_ENSURE_MINIT_PILOT=true to enable on production")
    password = settings.minit_hq_owner_password or ""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="MINIT_HQ_OWNER_PASSWORD must be at least 8 characters")
    from ..minit_provision import ensure_minit_pilot_account

    result = ensure_minit_pilot_account(
        session,
        parent_name=settings.minit_parent_account_name,
        hq_tenant_slug=settings.minit_hq_tenant_slug.strip().lower(),
        hq_tenant_name=settings.minit_hq_tenant_name,
        hq_owner_email=settings.minit_hq_owner_email,
        hq_owner_password=password,
    )
    return {
        "ok": True,
        "hq_tenant_slug": result.hq_tenant_slug,
        "hq_owner_email": result.hq_owner_email,
        "created_tenant_slugs": result.created_tenant_slugs,
        "skipped_shop_numbers": result.skipped_shop_numbers,
        "detail": (
            f"Log in with Shop ID '{result.hq_tenant_slug}', email {result.hq_owner_email}, "
            "and MINIT_HQ_OWNER_PASSWORD. Retail: minit-3269. Operator: minit-mobile-3904."
        ),
    }


@router.post("/dev-auto-login", response_model=TokenResponse)
def dev_auto_login(session: Session = Depends(unscoped_session)):
    if settings.app_env.lower() == "production" or not settings.allow_dev_auto_login:
        raise HTTPException(status_code=403, detail="Dev auto-login is disabled")

    tenants = session.exec(select(Tenant)).all()
    if not tenants:
        tenant = Tenant(name=settings.startup_seed_tenant_name, slug=settings.startup_seed_tenant_slug)
        session.add(tenant)
        session.flush()
        user = _create_default_owner(session, tenant)
        token, expires = create_access_token(tenant.id, user.id, user.role)
        refresh_token, refresh_expires = create_refresh_token(tenant.id, user.id, user.role)
        return TokenResponse(
            access_token=token,
            expires_in_seconds=expires,
            refresh_token=refresh_token,
            refresh_expires_in_seconds=refresh_expires,
        )

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

    token, expires = create_access_token(selected_tenant.id, user.id, user.role)
    refresh_token, refresh_expires = create_refresh_token(selected_tenant.id, user.id, user.role)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshRequest, session: Session = Depends(unscoped_session)):
    try:
        claims = decode_refresh_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    tenant_id = claims.tenant_id
    user_id = claims.user_id

    user = session.get(User, user_id)
    if not user or user.tenant_id != tenant_id or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not tenant.is_active and claims.role != "platform_admin":
        raise HTTPException(status_code=403, detail="Shop is suspended. Contact platform admin.")
    revoked_at = tenant.auth_revoked_at
    if revoked_at and revoked_at.tzinfo is None:
        revoked_at = revoked_at.replace(tzinfo=timezone.utc)
    if revoked_at and claims.issued_at and claims.issued_at < revoked_at:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")

    # Tracked refresh token (carries a jti): validate the persisted session so a
    # revoked device can no longer mint access tokens. The session id (sid) is
    # kept stable across refreshes so the "current device" stays identifiable.
    if claims.jti:
        rs = session.exec(
            select(RefreshSession).where(RefreshSession.jti == claims.jti)
        ).first()
        if rs is None:
            # A missing session row is exactly what revocation looks like, so it
            # has to mean "sign in again" for every tenant. Minting fresh tokens
            # here for the demo let a leaked demo refresh token keep working for
            # ever and put revoking a device beyond reach. Demo convenience is
            # not worth an auth path that cannot be closed.
            raise HTTPException(status_code=401, detail="Session has been revoked. Please sign in again.")
        if rs.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Session has been revoked. Please sign in again.")
        rs_expires = rs.expires_at
        if rs_expires.tzinfo is None:
            rs_expires = rs_expires.replace(tzinfo=timezone.utc)
        if rs_expires < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")

        rs.last_used_at = datetime.now(timezone.utc)
        session.add(rs)
        session.commit()

        sid = str(rs.id)
        token, expires = create_access_token(tenant_id, user_id, user.role, sid=sid)
        refresh_token, refresh_expires = create_refresh_token(
            tenant_id, user_id, user.role, sid=sid, jti=rs.jti
        )
        return TokenResponse(
            access_token=token,
            expires_in_seconds=expires,
            refresh_token=refresh_token,
            refresh_expires_in_seconds=refresh_expires,
        )

    # Legacy untracked refresh token (issued before per-session tracking).
    token, expires = create_access_token(tenant_id, user_id, user.role)
    refresh_token, refresh_expires = create_refresh_token(tenant_id, user_id, user.role)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.get("/export-my-data", summary="Export tenant data for portability (GDPR-style)")
def export_my_data(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Returns a JSON snapshot of the tenant's data (customers, watches, jobs, quotes, invoices) for backup or portability."""
    customers = session.exec(select(Customer).where(Customer.tenant_id == auth.tenant_id)).all()
    watches = session.exec(select(Watch).where(Watch.tenant_id == auth.tenant_id)).all()
    jobs = session.exec(select(RepairJob).where(RepairJob.tenant_id == auth.tenant_id)).all()
    from ..models import Quote, Invoice
    quotes = session.exec(select(Quote).where(Quote.tenant_id == auth.tenant_id)).all()
    invoices = session.exec(select(Invoice).where(Invoice.tenant_id == auth.tenant_id)).all()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "customers": [{"id": str(c.id), "full_name": c.full_name, "email": c.email, "phone": c.phone, "created_at": c.created_at.isoformat() if c.created_at else None} for c in customers],
        "watches": [{"id": str(w.id), "customer_id": str(w.customer_id), "brand": w.brand, "model": w.model, "created_at": w.created_at.isoformat() if w.created_at else None} for w in watches],
        "repair_jobs": [{"id": str(j.id), "job_number": j.job_number, "watch_id": str(j.watch_id), "title": j.title, "status": j.status, "created_at": j.created_at.isoformat() if j.created_at else None} for j in jobs],
        "quotes": [{"id": str(q.id), "repair_job_id": str(q.repair_job_id), "status": q.status, "total_cents": q.total_cents, "created_at": q.created_at.isoformat() if q.created_at else None} for q in quotes],
        "invoices": [{"id": str(i.id), "invoice_number": i.invoice_number, "status": i.status, "total_cents": i.total_cents, "created_at": i.created_at.isoformat() if i.created_at else None} for i in invoices],
    }


@router.get("/session", response_model=AuthSessionResponse)
def get_session_info(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return _build_auth_session_response(session, tenant, user)


@router.get("/sessions", summary="List known sessions for current user")
def list_sessions(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """List the user's active (non-revoked, unexpired) persisted sessions.

    Sessions are tracked from the moment the user signs in with per-session
    tracking; tokens issued before that (or by endpoints that do not create a
    session) won't appear here. The session matching the current access token's
    ``sid`` is flagged ``is_current``.
    """
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    now = datetime.now(timezone.utc)
    rows = session.exec(
        select(RefreshSession)
        .where(RefreshSession.user_id == auth.user_id)
        .where(RefreshSession.revoked_at.is_(None))
        .order_by(RefreshSession.last_used_at.desc())
    ).all()

    sessions = []
    for r in rows:
        expires = r.expires_at if r.expires_at.tzinfo else r.expires_at.replace(tzinfo=timezone.utc)
        if expires < now:
            continue
        sessions.append(
            {
                "session_id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "user_id": str(r.user_id),
                "role": auth.role,
                "email": user.email,
                "user_agent": r.user_agent,
                "created_at": (r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)).isoformat(),
                "last_used_at": (r.last_used_at if r.last_used_at.tzinfo else r.last_used_at.replace(tzinfo=timezone.utc)).isoformat(),
                "is_current": auth.sid is not None and str(r.id) == auth.sid,
            }
        )

    return {"sessions": sessions}


@router.post("/sessions/revoke-others", summary="Revoke all other sessions for current user")
def revoke_other_sessions(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Revoke every persisted session for the user except the current device.

    Requires the current access token to be tracked (carry a ``sid``). Revoked
    sessions can no longer be used to refresh access tokens.
    """
    if not auth.sid:
        return {
            "revoked": 0,
            "message": "Current session is not tracked. Sign in again to enable per-device revocation.",
        }
    try:
        current_sid = UUID(auth.sid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session id")

    now = datetime.now(timezone.utc)
    rows = session.exec(
        select(RefreshSession)
        .where(RefreshSession.user_id == auth.user_id)
        .where(RefreshSession.revoked_at.is_(None))
        .where(RefreshSession.id != current_sid)
    ).all()
    for r in rows:
        r.revoked_at = now
        session.add(r)
    session.commit()

    return {"revoked": len(rows), "message": f"Revoked {len(rows)} other session(s)."}


@router.patch("/session/site", response_model=ActiveSiteSwitchResponse)
def switch_active_site(
    payload: ActiveSiteSwitchRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    target = _get_site_option_for_email_tenant(session, current_user.email, payload.tenant_id)
    if not target:
        raise HTTPException(status_code=403, detail="Target site is not available for this login")

    hq_parents = _hq_parents_for_email(session, current_user.email)
    parent = hq_parents[0] if hq_parents else None
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
    source_tenant = session.get(Tenant, auth.tenant_id)
    target_tenant = session.get(Tenant, target.tenant_id)
    source_label = source_tenant.slug if source_tenant else str(auth.tenant_id)
    target_label = target_tenant.slug if target_tenant else str(target.tenant_id)
    session.add(
        TenantEventLog(
            tenant_id=target.tenant_id,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            entity_type="session",
            event_type="switch_site",
            event_summary=f"{current_user.email} switched active site from '{source_label}' to '{target_label}'",
        )
    )
    session.commit()

    token, expires = create_access_token(target.tenant_id, target.user_id, target.role)
    refresh_token, refresh_expires = create_refresh_token(target.tenant_id, target.user_id, target.role)
    target_tenant = session.get(Tenant, target.tenant_id)
    target_user = session.get(User, target.user_id)
    response_sites = (
        _session_available_sites(session, target_tenant, target_user)
        if target_tenant and target_user
        else [target]
    )
    return ActiveSiteSwitchResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
        active_site_tenant_id=target.tenant_id,
        available_sites=response_sites,
    )


@router.patch("/session/plan", response_model=AuthSessionResponse)
def update_session_plan(
    payload: TenantPlanUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
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
