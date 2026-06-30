import uuid
from typing import Any

from sqlalchemy.orm import Session

from carob.models import AuditLog


def record(
    session: Session,
    actor_type: str,
    actor_id: uuid.UUID | None,
    action: str,
    target: str | None = None,
    **details: Any,
) -> None:
    """Append to the audit log in the caller's transaction."""
    session.add(
        AuditLog(actor_type=actor_type, actor_id=actor_id, action=action, target=target, details=details)
    )
