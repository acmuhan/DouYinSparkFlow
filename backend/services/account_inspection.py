import json
from datetime import timedelta

from sqlalchemy import select

from ..crypto import decrypt_secret
from ..db import SessionLocal
from ..models import Account, User
from ..plugins.douyin_inspection import InspectionResult, inspect_cookies
from .scheduling import utc_now
from .plugin_access import ensure_permission
from .errors import QuotaError


def claim_inspection(db) -> str | None:
    expired = utc_now() - timedelta(minutes=3)
    account = db.scalar(select(Account).join(User, Account.user_id == User.id).where(
        Account.status != "DELETED", User.status == "ACTIVE",
        (Account.inspection_status == "QUEUED") |
        ((Account.inspection_status == "CHECKING") & (Account.checked_at < expired)),
    ).order_by(Account.updated_at).limit(1).with_for_update(skip_locked=True))
    if not account:
        return None
    try:
        ensure_permission(db, account.user_id, "accounts.validate")
    except QuotaError:
        account.inspection_status = "FAILED"
        account.inspection_message = "当前订阅未授权资源检测"
        return None
    account.inspection_status = "CHECKING"
    account.checked_at = utc_now()
    return account.id


def execute_inspection(account_id: str, *, session_factory=SessionLocal, inspector=inspect_cookies):
    with session_factory() as db:
        account = db.get(Account, account_id)
        if not account or account.status == "DELETED" or account.inspection_status != "CHECKING":
            return
        encrypted = account.cookies_encrypted
        claimed_at = account.checked_at
    try:
        result = inspector(json.loads(decrypt_secret(encrypted)))
    except Exception:
        result = InspectionResult("UNVERIFIED", "资源检测失败，请检查 Cookie 格式及 Worker 环境")
    with session_factory() as db:
        account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
        user = db.get(User, account.user_id) if account else None
        if (not account or not user or user.status != "ACTIVE" or account.status == "DELETED"
                or account.cookies_encrypted != encrypted or account.checked_at != claimed_at
                or account.inspection_status != "CHECKING"):
            return
        account.status = result.status
        account.inspection_status = "SUCCEEDED" if result.status == "READY" else "FAILED"
        account.inspection_message = result.message
        account.friends = result.friends
        account.checked_at = utc_now()
        db.commit()
