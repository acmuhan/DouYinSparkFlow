"""Explicit, trusted plugin registry; importing user-supplied code is not supported."""

from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel

from .douyin_streak import DouyinConfig, execute


@dataclass(frozen=True)
class Plugin:
    id: str
    name: str
    description: str
    execute: Callable
    config_model: type[BaseModel]
    requires_account: bool
    legacy_fields: tuple[str, ...] = ()


PLUGINS = {
    "douyin_streak": Plugin(
        id="douyin_streak", name="抖音续火花",
        description="使用已授权抖音账号维护好友火花",
        execute=execute,
        config_model=DouyinConfig,
        requires_account=True,
        legacy_fields=("targets", "message", "hitokoto_types"),
    ),
}


def get_plugin(plugin_id: str) -> Plugin:
    try:
        return PLUGINS[plugin_id]
    except KeyError:
        raise ValueError("Unknown plugin") from None


def allowed_plugins(snapshot: dict) -> list[str]:
    # Existing paid snapshots predate plugin permissions; preserve only the
    # one legacy entitlement, never grant future plugins implicitly.
    permissions = snapshot.get("plugin_permissions")
    return ["douyin_streak"] if permissions is None else permissions
