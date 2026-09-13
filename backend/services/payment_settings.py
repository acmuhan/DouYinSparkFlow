from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crypto import decrypt_secret, encrypt_secret
from ..models import Order, SystemSetting
from .scheduling import utc_now


class PaymentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    epay_url: str = Field(default="", max_length=512)
    epay_version: Literal["V1", "V2"] = "V1"
    epay_pid: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    epay_timestamp_tolerance: int = Field(default=300, ge=30, le=3600)

    @field_validator("epay_url")
    @classmethod
    def gateway_url(cls, value: str) -> str:
        if value:
            url = urlparse(value)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError("gateway must be an HTTPS base URL")
        return value.rstrip("/")


class PaymentUpdate(PaymentSettings):
    epay_key: str | None = Field(default=None, max_length=1024)
    epay_private_key: str | None = Field(default=None, max_length=16384)
    epay_public_key: str | None = Field(default=None, max_length=16384)


class PaymentOut(PaymentSettings):
    key_configured: bool
    private_key_configured: bool
    public_key_configured: bool


SECRETS = {"epay_key", "epay_private_key", "epay_public_key"}


def payment_public(config: PaymentUpdate) -> PaymentOut:
    return PaymentOut(**config.model_dump(exclude=SECRETS), key_configured=bool(config.epay_key),
                      private_key_configured=bool(config.epay_private_key), public_key_configured=bool(config.epay_public_key))


def load_payment(db: Session) -> PaymentUpdate:
    row = db.get(SystemSetting, "payment")
    if row:
        return PaymentUpdate.model_validate_json(decrypt_secret(row.value_encrypted))
    env = get_settings()
    return PaymentUpdate(
        enabled=bool(env.epay_url and env.epay_pid), epay_url=env.epay_url,
        epay_version=env.epay_version.upper(), epay_pid=env.epay_pid, epay_key=env.epay_key,
        epay_private_key=env.epay_private_key, epay_public_key=env.epay_public_key,
        epay_timestamp_tolerance=env.epay_timestamp_tolerance,
    )


def save_payment(db: Session, payload: PaymentUpdate) -> PaymentOut:
    old = load_payment(db)
    changed = (payload.epay_url, payload.epay_pid, payload.epay_version) != (old.epay_url, old.epay_pid, old.epay_version)
    values = payload.model_dump()
    for key in SECRETS:
        if values[key] is None:
            if changed:
                values[key] = ""
            else:
                values[key] = getattr(old, key)
    config = PaymentUpdate(**values)
    if config.enabled:
        if not config.epay_url or not config.epay_pid:
            raise ValueError("gateway and merchant ID required")
        if config.epay_version == "V1" and not config.epay_key:
            raise ValueError("V1 merchant key required")
        if config.epay_version == "V2":
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
            try:
                private = serialization.load_pem_private_key((config.epay_private_key or "").encode(), password=None)
                public = serialization.load_pem_public_key((config.epay_public_key or "").encode())
                if not isinstance(private, RSAPrivateKey) or not isinstance(public, RSAPublicKey):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError("valid RSA private and gateway public keys required") from None
    row = db.get(SystemSetting, "payment")
    if row is None:
        row = SystemSetting(key="payment")
        db.add(row)
    row.value_encrypted = encrypt_secret(config.model_dump_json())
    row.updated_at = utc_now()
    return payment_public(config)


def callback_snapshot(config: PaymentUpdate) -> str:
    # Order snapshots need verification material only, never the signing private key.
    return encrypt_secret(config.model_copy(update={"epay_private_key": None}).model_dump_json())


def order_payment_config(order: Order):
    if order.payment_config_encrypted:
        return PaymentUpdate.model_validate_json(decrypt_secret(order.payment_config_encrypted))
    # Pre-migration orders were signed with the original deployment environment.
    return get_settings()
