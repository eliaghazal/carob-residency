"""Authentication for the two audiences: customers (API tokens) and staff (signed tokens)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, Header
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from carob.db import get_session
from carob.errors import Forbidden, Unauthorized
from carob.models import ApiToken, Customer, Staff
from carob.security import decode_staff_token, hash_api_token


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("send your token as: Authorization: Bearer <token>")
    return authorization.split(" ", 1)[1].strip()


def current_customer(
    authorization: str | None = Header(default=None), session: Session = Depends(get_session)
) -> Customer:
    token = _bearer(authorization)
    row = session.execute(
        select(ApiToken, Customer)
        .join(Customer, Customer.id == ApiToken.customer_id)
        .where(ApiToken.token_hash == hash_api_token(token), ApiToken.revoked_at.is_(None))
    ).first()
    if row is None:
        raise Unauthorized("unknown or revoked API token")
    api_token, customer = row
    session.execute(
        update(ApiToken).where(ApiToken.id == api_token.id).values(last_used_at=datetime.now(UTC))
    )
    session.commit()
    return customer


def current_staff(
    authorization: str | None = Header(default=None), session: Session = Depends(get_session)
) -> Staff:
    claims = decode_staff_token(_bearer(authorization))
    staff = session.get(Staff, uuid.UUID(claims["sub"]))
    if staff is None or not staff.active:
        raise Unauthorized("this staff account is not active")
    return staff


def require_role(*roles: str) -> Callable[[Staff], Staff]:
    def check(staff: Staff = Depends(current_staff)) -> Staff:
        if staff.role not in roles:
            raise Forbidden(f"this needs one of these roles: {', '.join(roles)}")
        return staff

    return check
