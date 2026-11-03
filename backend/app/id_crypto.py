"""Encrypt customer ID numbers at rest (Fernet; key from ID_CAPTURE_KEY, else JWT_SECRET)."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _fernet() -> Fernet:
    material = (settings.id_capture_key or settings.jwt_secret).encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"mainspring-id-capture:" + material).digest()))


def encrypt_id_number(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_id_number(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None
