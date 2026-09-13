from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..config import get_settings
from ..crypto import decrypt_secret, encrypt_secret
from ..models import SystemSetting
from .scheduling import utc_now


def registration_enabled(db: Session) -> bool:
    row = db.get(SystemSetting, "registration_enabled")
    if row is None:
        return get_settings().registration_enabled
    return decrypt_secret(row.value_encrypted) == "true"


def set_registration_enabled(db: Session, enabled: bool) -> None:
    row = db.get(SystemSetting, "registration_enabled")
    if row is None:
        row = SystemSetting(key="registration_enabled")
        db.add(row)
    row.value_encrypted = encrypt_secret("true" if enabled else "false")
    row.updated_at = utc_now()


class WorkerSettings(BaseModel):
    enabled: bool = Field(strict=True)
    timeout: int = Field(ge=10, le=3600, strict=True)


def worker_settings(db: Session) -> WorkerSettings:
    row = db.get(SystemSetting, "worker")
    if row:
        return WorkerSettings.model_validate_json(decrypt_secret(row.value_encrypted))
    config = get_settings()
    return WorkerSettings(enabled=config.worker_enabled, timeout=config.worker_timeout)


def set_worker_settings(db: Session, config: WorkerSettings) -> None:
    row = db.get(SystemSetting, "worker")
    if row is None:
        row = SystemSetting(key="worker")
        db.add(row)
    row.value_encrypted = encrypt_secret(config.model_dump_json())
    row.updated_at = utc_now()
