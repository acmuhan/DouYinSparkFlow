from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str = Field(min_length=5, max_length=254)
    name: str
    role: Literal["USER", "ADMIN"]
    status: str
    last_login_at: datetime | None = None


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("invalid email")
        return value


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


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
    active: bool
    sort_order: int


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    plan_id: str
    snapshot: dict
    expires_at: datetime | None
    updated_at: datetime


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    unique_id: str = Field(min_length=1, max_length=80)
    cookies: list[dict]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    unique_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class TaskIn(BaseModel):
    account_id: str
    name: str = Field(min_length=1, max_length=80)
    targets: list[str] = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    hitokoto_types: list[str] = Field(default_factory=list, max_length=20)
    schedule_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    enabled: bool = False

    @field_validator("targets")
    @classmethod
    def strip_targets(cls, value: list[str]) -> list[str]:
        result = [target.strip() for target in value if target.strip()]
        if not result:
            raise ValueError("targets must contain at least one non-empty value")
        return result


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
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AdminUserOut(UserOut):
    subscription: SubscriptionOut | None = None


class PlanUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(max_length=255)
    monthly_cents: int = Field(gt=0)
    quarterly_cents: int = Field(gt=0)
    yearly_cents: int = Field(gt=0)
    account_limit: int = Field(gt=0)
    task_limit: int = Field(gt=0)
    run_limit: int = Field(gt=0)
    features: list[str] = Field(max_length=30)
    active: bool = True
    sort_order: int = Field(default=0, ge=0)
