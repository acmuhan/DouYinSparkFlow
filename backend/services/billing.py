from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Order, Plan, Run, Subscription, Task, Account, Usage
from .epay import build_checkout, validate_money
from .errors import PaymentError, QuotaError

CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}
CYCLE_PRICE = {"monthly": "monthly_cents", "quarterly": "quarterly_cents", "yearly": "yearly_cents"}


def add_months(value: datetime, months: int) -> datetime:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def seed_plans(db: Session) -> None:
    if db.scalar(select(func.count(Plan.id))) != 0:
        return
    plans = [
        Plan(id=str(uuid4()), slug="starter", name="Starter", description="个人轻量续火花", monthly_cents=1900, quarterly_cents=4900, yearly_cents=15900, account_limit=1, task_limit=5, run_limit=300, features=["基础任务", "定时运行", "运行日志"], sort_order=1),
        Plan(id=str(uuid4()), slug="pro", name="Pro", description="适合稳定运营的进阶方案", monthly_cents=4900, quarterly_cents=12900, yearly_cents=39900, account_limit=5, task_limit=30, run_limit=3000, features=["多账号", "API Keys", "优先队列", "运行日志"], sort_order=2),
        Plan(id=str(uuid4()), slug="studio", name="Studio", description="团队与高频任务工作区", monthly_cents=12900, quarterly_cents=33900, yearly_cents=99900, account_limit=20, task_limit=200, run_limit=20000, features=["多账号", "团队审计", "API Keys", "优先队列", "高级报表"], sort_order=3),
    ]
    db.add_all(plans)
    db.commit()


def create_order(db: Session, *, user_id: str, data, app_url: str) -> Order:
    existing = db.scalar(select(Order).where(Order.user_id == user_id, Order.idempotency_key == data.idempotency_key))
    if existing:
        return existing
    plan = db.scalar(select(Plan).where(Plan.id == data.plan_id, Plan.active.is_(True)))
    if not plan:
        raise ValueError("plan not found or inactive")
    months = CYCLE_MONTHS[data.cycle]
    amount_cents = int(getattr(plan, CYCLE_PRICE[data.cycle]))
    now = datetime.utcnow()
    order_id = str(uuid4())
    checkout = build_checkout(
        trade_no=order_id,
        name=f"SparkFlow {plan.name} / {data.cycle}",
        amount_cents=amount_cents,
        payment_method=data.payment_method,
        notify_url=f"{app_url.rstrip('/')}/api/v1/billing/epay/callback",
        return_url=f"{app_url.rstrip('/')}/billing/result?order={order_id}",
        custom_param=user_id,
    )
    order = Order(
        id=order_id,
        user_id=user_id,
        plan_id=plan.id,
        snapshot={"slug": plan.slug, "name": plan.name, "features": plan.features, "account_limit": plan.account_limit, "task_limit": plan.task_limit, "run_limit": plan.run_limit},
        cycle=data.cycle,
        months=months,
        amount_cents=amount_cents,
        status="PENDING",
        provider_version=get_settings().epay_version.upper(),
        merchant_id=get_settings().epay_pid or "local",
        payment_method=data.payment_method,
        idempotency_key=data.idempotency_key,
        checkout=checkout,
        expires_at=now + timedelta(minutes=30),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def activate_order(db: Session, *, order_id: str, provider_trade_no: str, provider_money: str, status: str) -> Order:
    if status not in {"TRADE_SUCCESS", "SUCCESS", "PAID"}:
        raise PaymentError("payment is not successful")
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise PaymentError("order not found")
    if order.status == "PAID":
        return order
    if order.status != "PENDING":
        raise PaymentError(f"order cannot be paid from {order.status}")
    if order.expires_at < datetime.utcnow():
        order.status = "EXPIRED"
        db.commit()
        raise PaymentError("order expired")
    validate_money(order.amount_cents, provider_money)
    order.status = "PAID"
    order.provider_trade_no = provider_trade_no
    order.paid_at = datetime.utcnow()
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == order.user_id).with_for_update())
    now = datetime.utcnow()
    current_expiry = subscription.expires_at if subscription and subscription.expires_at and subscription.expires_at > now else now
    new_expiry = add_months(current_expiry, order.months)
    if subscription:
        subscription.plan_id = order.plan_id
        subscription.snapshot = order.snapshot
        subscription.expires_at = new_expiry
        subscription.last_order_id = order.id
        subscription.updated_at = now
    else:
        db.add(Subscription(id=str(uuid4()), user_id=order.user_id, plan_id=order.plan_id, snapshot=order.snapshot, expires_at=new_expiry, last_order_id=order.id, updated_at=now))
    db.commit()
    db.refresh(order)
    return order


def ensure_can_create(db: Session, *, user_id: str, resource: str) -> None:
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    if not subscription or not subscription.expires_at or subscription.expires_at <= datetime.utcnow():
        raise QuotaError("an active subscription is required")
    limits = subscription.snapshot
    if resource == "account":
        count = db.scalar(select(func.count(Account.id)).where(Account.user_id == user_id, Account.status != "DELETED")) or 0
        limit = int(limits.get("account_limit", 0))
    elif resource == "task":
        count = db.scalar(select(func.count(Task.id)).where(Task.user_id == user_id, Task.archived.is_(False))) or 0
        limit = int(limits.get("task_limit", 0))
    else:
        period = datetime.utcnow().strftime("%Y-%m")
        count = db.scalar(select(func.coalesce(Usage.used, 0) + func.coalesce(Usage.adjustment, 0)).where(Usage.user_id == user_id, Usage.period == period)) or 0
        limit = int(limits.get("run_limit", 0))
    if count >= limit:
        raise QuotaError(f"{resource} quota exceeded")
