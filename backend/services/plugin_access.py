from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Subscription
from ..plugins import PLUGINS, allowed_plugins
from .errors import QuotaError
from .scheduling import utc_now
from ..permissions import PERMISSIONS, effective_permissions


def ensure_permission(db: Session, user_id: str, permission: str) -> None:
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    if (permission not in PERMISSIONS or not subscription or not subscription.expires_at
            or subscription.expires_at <= utc_now() or permission not in effective_permissions(subscription.snapshot)):
        raise QuotaError("当前订阅未授权此操作")


def ensure_plugin_access(db: Session, user_id: str, plugin_id: str) -> None:
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    if (plugin_id not in PLUGINS or not subscription or not subscription.expires_at
            or subscription.expires_at <= utc_now() or plugin_id not in allowed_plugins(subscription.snapshot)):
        raise QuotaError("当前订阅未授权此插件")
