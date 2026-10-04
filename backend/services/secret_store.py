"""
Server-side secrets (cloud API keys) kept encrypted in app_settings.

- Encryption: Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from FLASK_SECRET_KEY
  by HKDF-SHA256, so no extra secret has to be managed. Rotating FLASK_SECRET_KEY makes
  stored secrets unreadable; they then count as "not set" and an admin re-enters them.
- Plaintext never leaves the backend: admin endpoints only get mask_secret() output
  ("••••abcd").
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

_SETTING_PREFIX = "secret:"
_HKDF_SALT = b"shadowrealms-ai/secret-store"
_HKDF_INFO = b"app_settings secrets v1"
_DEV_DEFAULT = "dev-secret-key-change-in-production"


def _master_secret() -> str:
    s = (os.environ.get("FLASK_SECRET_KEY") or "").strip()
    if not s:
        logger.warning("FLASK_SECRET_KEY is not set; secrets are encrypted with the dev default key")
        s = _DEV_DEFAULT
    return s


def fernet_for(master_secret: str) -> Fernet:
    """Fernet instance for a master secret (HKDF-SHA256 -> 32 bytes -> urlsafe b64)."""
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=_HKDF_SALT, info=_HKDF_INFO
    ).derive(master_secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plaintext: str, master_secret: Optional[str] = None) -> str:
    return fernet_for(master_secret or _master_secret()).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str, master_secret: Optional[str] = None) -> Optional[str]:
    """Plaintext, or None when the token can't be decrypted (wrong/rotated key, garbage)."""
    try:
        return fernet_for(master_secret or _master_secret()).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None


def mask_secret(plaintext: Optional[str]) -> str:
    """'••••' + last 4 characters; '' when unset. Short keys show only the dots."""
    if not plaintext:
        return ""
    tail = plaintext[-4:] if len(plaintext) >= 12 else ""
    return "••••" + tail


# --- app_settings-backed storage -------------------------------------------------------


def set_secret(name: str, plaintext: Optional[str]) -> None:
    """Store (encrypted) or, with None/'' , delete the secret `name`."""
    from services.ai_runtime_settings import set_app_setting

    value = (plaintext or "").strip()
    set_app_setting(_SETTING_PREFIX + name, encrypt_secret(value) if value else None)


def get_secret(name: str) -> Optional[str]:
    """Decrypted secret or None (unset, or unreadable after a FLASK_SECRET_KEY change)."""
    from services.ai_runtime_settings import get_app_setting

    token = get_app_setting(_SETTING_PREFIX + name)
    if not token:
        return None
    plain = decrypt_secret(token)
    if plain is None:
        logger.warning("Stored secret %r can't be decrypted (FLASK_SECRET_KEY changed?); treating as unset", name)
    return plain


def secret_status(name: str) -> dict:
    """What the admin UI may see: whether it's set and the masked tail. Never the key."""
    plain = get_secret(name)
    return {"set": bool(plain), "masked": mask_secret(plain)}
