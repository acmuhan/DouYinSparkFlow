from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from utils import norm
from .plugins import PLUGINS
from .permissions import PERMISSIONS


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str = Field(min_length=5, max_length=254)
    name: str
    role: Literal["USER", "ADMIN"]
    status: str
    last_login_at: datetime | None = None


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or value.startswith("@") or value.endswith("@") or any(char.isspace() for char in value):
            raise ValueError("invalid email")
        return value


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AdminUserCreateIn(RegisterIn):
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("name must contain at least two visible characters")
        return value


class AdminUserEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return RegisterIn.valid_email(value)


class ProfileUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class PasswordUpdateIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserStatusIn(BaseModel):
    status: Literal["ACTIVE", "SUSPENDED", "BANNED"]


class AdminRunStatusIn(BaseModel):
    status: Literal["QUEUED", "CANCELLED"]
    reason: str = Field(min_length=1, max_length=255)


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name: str
    description: str
    monthly_cents: int
    quarterly_cents: int
    yearly_cents: int
    account_limit: int
    task_limit: int
    run_limit: int
    features: list[str]
    plugin_permissions: list[str] | None = None
    permissions: list[str] | None = None
    active: bool
    sort_order: int


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    plan_id: str
    snapshot: dict
    expires_at: datetime | None
    updated_at: datetime


class UsageOut(BaseModel):
    period: str
    used: int
    adjustment: int
    limit: int
    remaining: int


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    unique_id: str = Field(min_length=1, max_length=80)
    cookies: list[dict] = Field(min_length=1, max_length=200)

    @field_validator("cookies")
    @classmethod
    def scoped_cookies(cls, value: list[dict]) -> list[dict]:
        clean = []
        for item in value:
            domain = item.get("domain", "")
            if not isinstance(domain, str) or domain.lstrip(".") not in {"douyin.com", "www.douyin.com"}:
                raise ValueError("cookies must be scoped to douyin.com")
            if not isinstance(item.get("name"), str) or not item["name"] or not isinstance(item.get("value"), str):
                raise ValueError("invalid cookie name or value")
            if len(item["value"]) > 16384 or len(item["name"]) > 256:
                raise ValueError("cookie too large")
            if not isinstance(item.get("path", "/"), str) or not item.get("path", "/").startswith("/"):
                raise ValueError("invalid cookie path")
            entry = {key: item[key] for key in ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite") if key in item}
            entry.setdefault("path", "/")
            if entry.get("sameSite") not in {None, "Strict", "Lax", "None"}:
                entry.pop("sameSite")
            clean.append(entry)
        return clean


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    unique_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    inspection_status: str | None = None
    inspection_message: str | None = None
    checked_at: datetime | None = None


class TaskIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    account_id: str | None = Field(default=None, min_length=1, max_length=36)
    plugin_id: str = Field(default="douyin_streak", max_length=80)
    name: str = Field(min_length=1, max_length=80)
    targets: list[str] = Field(default_factory=list, max_length=100)
    message: str = Field(default="", max_length=2000)
    plugin_config: dict | None = None
    hitokoto_types: list[str] = Field(default_factory=list, max_length=20)
    schedule_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    enabled: bool = False

    @model_validator(mode="after")
    def validate_plugin_configuration(self):
        plugin = PLUGINS[self.plugin_id]
        if plugin.requires_account and not self.account_id:
            raise ValueError("this plugin requires an account")
        if not plugin.requires_account and self.account_id:
            raise ValueError("this plugin does not accept account credentials")
        source = self.plugin_config
        if source is None:
            source = {key: getattr(self, key) for key in plugin.legacy_fields}
        self.plugin_config = plugin.config_model.model_validate(source).model_dump(mode="json")
        for key in plugin.legacy_fields:
            setattr(self, key, self.plugin_config[key])
        return self

    @field_validator("plugin_id")
    @classmethod
    def known_plugin(cls, value: str) -> str:
        if value not in PLUGINS:
            raise ValueError("unknown plugin")
        return value

    @field_validator("targets")
    @classmethod
    def strip_targets(cls, value: list[str]) -> list[str]:
        result = [norm(target) for target in value]
        if any(not target or len(target) > 128 for target in result):
            raise ValueError("targets must contain 1-128 visible characters")
        return list(dict.fromkeys(result))

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("unknown IANA timezone") from None
        return value


class RunSnapshot(TaskIn):
    version: Literal[1] = 1
    usage_period: str = Field(pattern=r"^\d{4}-\d{2}$")


class TaskOut(TaskIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    archived: bool
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CheckoutIn(BaseModel):
    plan_id: str
    cycle: Literal["monthly", "quarterly", "yearly"]
    payment_method: Literal["alipay", "wxpay", "qqpay"] = "alipay"
    idempotency_key: str = Field(min_length=8, max_length=64)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    plan_id: str
    cycle: str
    amount_cents: int
    status: str
    provider_version: str
    provider_trade_no: str | None
    payment_method: str
    checkout: dict | None
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    expires_days: int = Field(default=90, ge=1, le=730)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    prefix: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    token: str | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    status: str
    trigger_type: str
    sent_count: int
    result: str | None
    cancel_requested: bool
    worker_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class RunEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    message: str
    sent_count: int
    created_at: datetime


class AdminUserOut(UserOut):
    subscription: SubscriptionOut | None = None


class PlanUpdateIn(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(max_length=255)
    monthly_cents: int = Field(gt=0)
    quarterly_cents: int = Field(gt=0)
    yearly_cents: int = Field(gt=0)
    account_limit: int = Field(gt=0)
    task_limit: int = Field(gt=0)
    run_limit: int = Field(gt=0)
    features: list[str] = Field(max_length=30)
    plugin_permissions: list[str] | None = Field(default=None, max_length=100)
    permissions: list[str] | None = Field(default=None, max_length=100)
    active: bool = True
    sort_order: int = Field(default=0, ge=0)

    @field_validator("plugin_permissions")
    @classmethod
    def known_permissions(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(item not in PLUGINS for item in value):
            raise ValueError("unknown plugin permission")
        return list(dict.fromkeys(value)) if value is not None else None

    @field_validator("permissions")
    @classmethod
    def valid_actions(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(item not in PERMISSIONS for item in value):
            raise ValueError("unknown operation permission")
        return list(dict.fromkeys(value)) if value is not None else None


class PlanCreateIn(PlanUpdateIn):
    permissions: list[str] = Field(default_factory=list, max_length=100)
    plugin_permissions: list[str] = Field(default_factory=list, max_length=100)
    slug: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    id: str | None = Field(default=None, min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")


class SettingIn(BaseModel):
    value: str = Field(max_length=10000)


class GeneralSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration_enabled: bool = Field(strict=True)
    worker_enabled: bool | None = Field(default=None, strict=True)
    worker_timeout: int | None = Field(default=None, ge=10, le=3600, strict=True)


class AnnouncementIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=10000)
    active: bool = True


class AnnouncementOut(AnnouncementIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class AnnouncementNotificationOut(AnnouncementOut):
    read_at: datetime | None = None


class QuotaAdjustmentIn(BaseModel):
    period: str = Field(pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$")
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=1, max_length=255)


class AdminSubscriptionIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=36)
    months: int = Field(ge=1, le=120)
    reason: str = Field(min_length=1, max_length=255)


class RefundIn(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    order_id: str
    status: str
    amount_cents: int
    reason: str
    provider_refund_no: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class RefundCompleteIn(BaseModel):
    status: Literal["SUCCEEDED", "FAILED"]
    provider_refund_no: str | None = Field(default=None, max_length=128)
    error: str | None = Field(default=None, max_length=255)


class ReconcileIn(BaseModel):
    provider_trade_no: str = Field(min_length=1, max_length=128)
    provider_money: str = Field(pattern=r"^\d+(?:\.\d{1,2})?$")
    reason: str = Field(min_length=1, max_length=255)
