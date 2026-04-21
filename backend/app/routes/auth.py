import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..dependencies import (
    AuthContext,
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
    Watch,
)
from ..security import create_access_token, create_refresh_token, decode_refresh_token, hash_password, verify_password
from ._auth_demo_seed import seed_demo_data_for_tenant

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
    enabled = sorted(PLAN_FEATURES.get(normalized_plan, PLAN_FEATURES["pro"]))
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
    cal_tz = settings.schedule_calendar_timezone
    now_shop = datetime.now(ZoneInfo(cal_tz))
    shop_today = now_shop.strftime("%Y-%m-%d")
    return AuthSessionResponse(
        user=_build_public_user(user),
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
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
    )



@router.post("/signup", response_model=TenantSignupResponse)
@limiter.limit("10/minute")
def signup(request: Request, payload: TenantSignupRequest, session: Session = Depends(get_session)):
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

    plan_code = _normalize_plan_code(payload.plan_code, default_if_empty="basic_watch")

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
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(get_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled")

    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.owner_email)
    _validate_password_strength(payload.owner_password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    plan_code = _normalize_plan_code(payload.plan_code, default_if_empty="basic_watch")

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

@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_login_rate_limit)
def login(request: Request, payload: LoginRequest, session: Session = Depends(get_session)):
    return _login_impl(request, payload, session)

def _login_impl(request: Request, payload: LoginRequest, session: Session = Depends(get_session)):
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

    token, expires = create_access_token(tenant.id, user.id, user.role)
    refresh_token, refresh_expires = create_refresh_token(tenant.id, user.id, user.role)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


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
    parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == email)).first()
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

    token, expires = create_access_token(selected.tenant_id, selected.user_id, selected.role)
    refresh_token, refresh_expires = create_refresh_token(selected.tenant_id, selected.user_id, selected.role)
    return MultiSiteLoginResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
        active_site_tenant_id=selected.tenant_id,
        available_sites=valid_sites,
    )


@router.post("/demo-seed")
def seed_demo_data(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    if settings.app_env.lower() == "production":
        allowed = [
            _normalize_slug(settings.startup_seed_tenant_slug),
            *([_normalize_slug(s) for s in [settings.testing_tenant_slug] if (s or "").strip()]),
        ]
        if tenant.slug not in [a for a in allowed if a]:
            raise HTTPException(status_code=403, detail="Demo seeding is only available for the configured demo or testing tenant")

    created = seed_demo_data_for_tenant(session, tenant, user)
    return {"ok": True, "created": created}


@router.post("/ensure-testing-tenant")
def ensure_testing_tenant_endpoint(session: Session = Depends(get_session)):
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
def refresh_tokens(payload: RefreshRequest, session: Session = Depends(get_session)):
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
    session: Session = Depends(get_session),
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
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return _build_auth_session_response(session, tenant, user)


@router.get("/sessions", summary="List known sessions for current user")
def list_sessions(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """
    Return the currently authenticated session shape.
    Until refresh-token persistence is introduced, we can only reliably surface
    the active token context rather than a full device/session inventory.
    """
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "sessions": [
            {
                "session_id": f"active:{auth.tenant_id}:{auth.user_id}",
                "tenant_id": str(auth.tenant_id),
                "user_id": str(auth.user_id),
                "role": auth.role,
                "email": user.email,
                "is_current": True,
            }
        ]
    }


@router.post("/sessions/revoke-others", summary="Revoke all other sessions for current user")
def revoke_other_sessions(auth: AuthContext = Depends(get_auth_context)):
    """
    Refresh tokens are not persisted yet, so there are currently no server-tracked
    "other sessions" to revoke. Returning a deterministic result avoids a silent stub.
    """
    return {"revoked": 0, "message": "No persisted secondary sessions found"}


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
    return ActiveSiteSwitchResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
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
