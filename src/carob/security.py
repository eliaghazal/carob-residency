"""Passwords, staff tokens and customer API tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from carob.config import get_settings
from carob.errors import Unauthorized

_hasher = PasswordHasher()
STAFF_ROLES = ("agent", "supervisor", "admin")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def issue_staff_token(staff_id: uuid.UUID, role: str, name: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": str(staff_id),
        "role": role,
        "name": name,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
        "iss": "carob-staff",
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_staff_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token, get_settings().jwt_secret, algorithms=["HS256"], issuer="carob-staff", leeway=30
        )
    except jwt.PyJWTError as exc:
        raise Unauthorized("invalid or expired staff token") from exc


def new_api_token() -> tuple[str, str, str]:
    """A customer API token: (token shown once, its prefix, its hash). Only the hash is stored."""
    secret = secrets.token_urlsafe(32)
    token = f"crb_{secret}"
    return token, token[:12], hash_api_token(token)


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
