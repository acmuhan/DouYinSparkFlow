from __future__ import annotations

import base64
import hashlib
import hmac
import time
from decimal import Decimal, InvalidOperation
from typing import Mapping
from urllib.parse import urlencode

from .errors import PaymentError
from ..config import get_settings


def _signing_string(params: Mapping[str, str]) -> str:
    pairs = [
        (key, str(value))
        for key, value in sorted(params.items())
        if key not in {"sign", "sign_type"} and value not in ("", None)
    ]
    return "&".join(f"{key}={value}" for key, value in pairs)


def v1_sign(params: Mapping[str, str], key: str) -> str:
    return hashlib.md5(f"{_signing_string(params)}{key}".encode("utf-8")).hexdigest()


def verify_v1(params: Mapping[str, str], key: str) -> bool:
    expected = v1_sign(params, key)
    return hmac.compare_digest(expected.lower(), str(params.get("sign", "")).lower())


def v2_sign(params: Mapping[str, str], private_key_pem: str) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    signature = private_key.sign(
        _signing_string(params).encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def verify_v2(params: Mapping[str, str], public_key_pem: str) -> bool:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        public_key.verify(
            base64.b64decode(str(params.get("sign", ""))),
            _signing_string(params).encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def validate_money(actual_cents: int, provider_money: str) -> None:
    try:
        cents = int((Decimal(provider_money) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        raise PaymentError("provider amount is invalid")
    if cents != actual_cents:
        raise PaymentError("provider amount does not match order")


def build_checkout(
    *,
    trade_no: str,
    name: str,
    amount_cents: int,
    payment_method: str,
    notify_url: str,
    return_url: str,
    custom_param: str,
) -> dict[str, str]:
    settings = get_settings()
    params = {
        "pid": settings.epay_pid,
        "type": payment_method,
        "out_trade_no": trade_no,
        "notify_url": notify_url,
        "return_url": return_url,
        "name": name,
        "money": f"{amount_cents / 100:.2f}",
        "param": custom_param,
    }
    if settings.epay_version.upper() == "V2":
        params["timestamp"] = str(int(time.time()))
        params["sign_type"] = "RSA-SHA256"
        params["sign"] = v2_sign(params, settings.epay_private_key) if settings.epay_private_key else ""
    else:
        params["sign_type"] = "MD5"
        params["sign"] = v1_sign(params, settings.epay_key) if settings.epay_key else ""
    endpoint = settings.epay_url.rstrip("/") + "/submit.php" if settings.epay_url else ""
    return {"endpoint": endpoint, "method": "GET", "params": params, "url": f"{endpoint}?{urlencode(params)}" if endpoint else ""}


def verify_callback(params: Mapping[str, str]) -> None:
    settings = get_settings()
    version = str(params.get("sign_type", settings.epay_version)).upper()
    valid = verify_v2(params, settings.epay_public_key) if version in {"RSA", "RSA-SHA256"} else verify_v1(params, settings.epay_key)
    if not valid:
        raise PaymentError("invalid payment signature")
    if version in {"RSA", "RSA-SHA256"}:
        timestamp = int(params.get("timestamp", "0"))
        if abs(int(time.time()) - timestamp) > settings.epay_timestamp_tolerance:
            raise PaymentError("payment callback timestamp expired")
