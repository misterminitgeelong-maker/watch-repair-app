"""The signed-in HQ's own settings, so its screens can show only what it has switched on."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..hq_access import hq_config_for_tenant, require_hq
from ..minit_branding import MINIT_LOGO_PUBLIC_PATH

router = APIRouter(prefix="/v1/parent-accounts", tags=["hq-config"])


@router.get("/me/hq-config")
def get_my_hq_config(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(get_session)):
    tenant = require_hq(auth, session)
    config = hq_config_for_tenant(session, tenant)
    assert config is not None  # require_hq already refused non-HQs
    return {
        "product_key": config.product_key,
        "display_name": config.display_name,
        # Minit's logo ships with the app, so its row stores none.
        "logo_url": config.logo_url or (MINIT_LOGO_PUBLIC_PATH if config.product_key == "minit" else None),
        "brand_color": config.brand_color,
        "modules": sorted(config.modules),
    }
