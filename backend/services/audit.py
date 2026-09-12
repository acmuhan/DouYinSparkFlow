from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import AuditLog


def record_audit(db: Session, *, actor_id: str | None, action: str, target_id: str | None = None, detail: dict[str, Any] | None = None) -> None:
    db.add(AuditLog(id=str(uuid4()), actor_id=actor_id, action=action, target_id=target_id, detail=detail or {}))
