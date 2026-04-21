import os
from uuid import uuid4

import pytest
from jose import jwt

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.config import settings
from app.security import create_access_token, decode_access_token


def test_valid_token_decodes_structured_claims():
    tenant_id = uuid4()
    user_id = uuid4()
    token, _ = create_access_token(tenant_id, user_id, "owner")
    claims = decode_access_token(token)
    assert claims.tenant_id == tenant_id
    assert claims.user_id == user_id
    assert claims.role == "owner"
    assert claims.sub == str(user_id)


def test_invalid_token_rejected():
    with pytest.raises(ValueError):
        decode_access_token("not-a-jwt")


def test_missing_claims_rejected():
    token = jwt.encode(
        {"sub": str(uuid4())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(ValueError):
        decode_access_token(token)


def test_malformed_claims_rejected():
    token = jwt.encode(
        {
            "sub": "user",
            "tenant_id": "not-a-uuid",
            "user_id": "also-not-a-uuid",
            "role": "owner",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(ValueError):
        decode_access_token(token)


def test_download_typ_token_rejected_as_access_token():
    """Regression for B-H5: a token minted for attachment download must not be
    accepted on auth paths even though it was signed with the same secret.
    """
    tenant_id = uuid4()
    user_id = uuid4()
    token = jwt.encode(
        {
            "sub": f"{tenant_id}:{user_id}",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "role": "owner",
            "typ": "attachment_download",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(ValueError):
        decode_access_token(token)
