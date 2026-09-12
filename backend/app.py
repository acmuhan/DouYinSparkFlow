from __future__ import annotations

import secrets
import logging
import time
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .crypto import encrypt_secret
from .db import Base, engine, get_db
from .models import Account, ApiKey, AuditLog, AuthSession, Order, Plan, RateLimit, Refund, Run, Subscription, Task, Usage, User, Worker
from .schemas import (
    AccountIn, AccountOut, AdminRunStatusIn, AdminUserOut, ApiKeyIn, ApiKeyOut, CheckoutIn, LoginIn, OrderOut,
    AdminSubscriptionIn, PasswordUpdateIn, PlanOut, PlanUpdateIn, ProfileUpdateIn, QuotaAdjustmentIn,
    ReconcileIn, RefundCompleteIn, RefundIn, RefundOut, RegisterIn, RunOut, SubscriptionOut, TaskIn,
    TaskOut, UsageOut, UserOut, UserStatusIn,
)
from .security import create_session_token, hash_api_key, hash_password, session_expiry, verify_password
from .services.audit import record_audit
from .services.billing import activate_order, adjust_quota, create_order, ensure_can_create, expire_pending_orders, override_subscription, seed_plans, settle_order_callback
from .services.epay import verify_callback
from .services.errors import PaymentError, QuotaError, TaskError
from .services.jobs import cancel_run, enqueue_run, owned_task
from .services.scheduling import next_daily_run, utc_now

settings = get_settings()
logger = logging.getLogger("sparkflow.api")
app = FastAPI(title="SparkFlow API", version="0.1.0", docs_url="/api/docs" if not settings.production else None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id, request.method, request.url.path, response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


def api_error(status_code: int, detail: str):
    raise HTTPException(status_code=status_code, detail={"code": "REQUEST_ERROR", "message": detail})


def _session_user(db: Session, session_token: str | None) -> User:
    if not session_token:
        api_error(status.HTTP_401_UNAUTHORIZED, "登录状态已失效")
    token_hash = hash_api_key(session_token)
    session = db.scalar(select(AuthSession).where(AuthSession.id == token_hash))
    if not session or session.expires_at <= datetime.utcnow():
        api_error(status.HTTP_401_UNAUTHORIZED, "登录状态已失效")
    user = db.get(User, session.user_id)
    if not user or user.status != "ACTIVE":
        api_error(status.HTTP_403_FORBIDDEN, "账户不可用")
    return user


def current_user(
    session: Annotated[str | None, Cookie(alias="sf_session")] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    if authorization and authorization.lower().startswith("bearer "):
        raw_key = authorization[7:].strip()
        key = db.scalar(select(ApiKey).where(ApiKey.token_hash == hash_api_key(raw_key)).with_for_update())
        if not key or key.revoked_at or key.expires_at <= datetime.utcnow():
            api_error(status.HTTP_401_UNAUTHORIZED, "API Key 无效或已过期")
        user = db.get(User, key.user_id)
        if not user or user.status != "ACTIVE":
            api_error(status.HTTP_403_FORBIDDEN, "账户不可用")
        key.last_used_at = datetime.utcnow()
        db.commit()
        return user
    return _session_user(db, session)


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        api_error(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


LOGIN_ATTEMPT_LIMIT = 8
LOGIN_WINDOW_SECONDS = 15 * 60


def _login_rate_key(email: str, client_host: str) -> str:
    return hash_api_key(f"login:{email.lower()}:{client_host}")


def _consume_login_attempt(db: Session, key: str) -> RateLimit:
    now = datetime.utcnow()
    limit = db.scalar(select(RateLimit).where(RateLimit.id == key).with_for_update())
    if limit and limit.expires_at <= now:
        limit.attempts = 0
        limit.expires_at = now + timedelta(seconds=LOGIN_WINDOW_SECONDS)
    if not limit:
        limit = RateLimit(id=key, attempts=0, expires_at=now + timedelta(seconds=LOGIN_WINDOW_SECONDS))
        db.add(limit)
        db.flush()
    if limit.attempts >= LOGIN_ATTEMPT_LIMIT:
        api_error(429, "登录尝试过于频繁，请稍后再试")
    limit.attempts += 1
    return limit


@app.on_event("startup")
def startup():
    if settings.auto_create_tables:
        Base.metadata.create_all(engine)
    with next(get_db()) as db:
        seed_plans(db)
        if settings.admin_email and settings.admin_password:
            admin = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
            if not admin:
                db.add(User(id=str(uuid4()), email=settings.admin_email.lower(), name=settings.admin_name, password_hash=hash_password(settings.admin_password), role="ADMIN", status="ACTIVE"))
                db.commit()


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        database = "ok"
    except Exception:
        database = "error"
    return {"status": "ok", "database": database, "version": app.version}


@app.post("/api/v1/auth/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    if not settings.registration_enabled:
        api_error(403, "暂未开放注册")
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        api_error(409, "邮箱已注册")
    user = User(id=str(uuid4()), email=email, name=payload.name.strip(), password_hash=hash_password(payload.password), role="USER", status="ACTIVE")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        api_error(409, "邮箱已注册")
    _set_session(db, user, response)
    record_audit(db, actor_id=user.id, action="auth.register", target_id=user.id)
    db.commit()
    return _user_out(user)


@app.post("/api/v1/auth/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    client_host = request.client.host if request.client else "unknown"
    rate_limit = _consume_login_attempt(db, _login_rate_key(payload.email, client_host))
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or user.status != "ACTIVE" or not verify_password(payload.password, user.password_hash):
        db.commit()
        api_error(401, "邮箱或密码错误")
    db.delete(rate_limit)
    user.last_login_at = datetime.utcnow()
    _set_session(db, user, response)
    record_audit(db, actor_id=user.id, action="auth.login", target_id=user.id)
    db.commit()
    return _user_out(user)


@app.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response, session_token: Annotated[str | None, Cookie(alias="sf_session")] = None, db: Session = Depends(get_db)):
    if session_token:
        db.query(AuthSession).filter_by(id=hash_api_key(session_token)).delete()
        db.commit()
    response.delete_cookie("sf_session", path="/")


def _set_session(db: Session, user: User, response: Response) -> None:
    raw, token_hash = create_session_token()
    db.add(AuthSession(id=token_hash, user_id=user.id, expires_at=session_expiry()))
    # Secure cookies are required for HTTPS production, but must remain usable
    # when an isolated production-mode smoke test is served over plain HTTP.
    response.set_cookie(
        "sf_session",
        raw,
        httponly=True,
        secure=settings.app_url.lower().startswith("https://"),
        samesite="lax",
        max_age=settings.session_days * 86400,
        path="/",
    )


@app.get("/api/v1/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _user_out(user)


@app.patch("/api/v1/me", response_model=UserOut)
def update_profile(payload: ProfileUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = payload.name
    record_audit(db, actor_id=user.id, action="profile.updated", target_id=user.id)
    db.commit()
    return user


@app.patch("/api/v1/me/password", status_code=204)
def update_password(payload: PasswordUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        api_error(400, "当前密码不正确")
    user.password_hash = hash_password(payload.new_password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
    record_audit(db, actor_id=user.id, action="profile.password_changed", target_id=user.id)
    db.commit()


@app.get("/api/v1/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return list(db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order)))


@app.get("/api/v1/subscription", response_model=SubscriptionOut | None)
def get_subscription(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalar(select(Subscription).where(Subscription.user_id == user.id))


@app.get("/api/v1/usage", response_model=UsageOut)
def usage_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = utc_now()
    period = now.strftime("%Y-%m")
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    usage = db.scalar(select(Usage).where(Usage.user_id == user.id, Usage.period == period))
    used = usage.used if usage else 0
    adjustment = usage.adjustment if usage else 0
    limit = int((subscription.snapshot if subscription else {}).get("run_limit", 0))
    effective_limit = max(0, limit + adjustment)
    return UsageOut(period=period, used=used, adjustment=adjustment, limit=limit, remaining=max(0, effective_limit - used))


@app.post("/api/v1/billing/checkout", response_model=OrderOut, status_code=201)
def checkout(payload: CheckoutIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return create_order(db, user_id=user.id, data=payload, app_url=settings.app_url)
    except ValueError as exc:
        api_error(400, str(exc))


@app.post("/api/v1/billing/epay/callback", response_class=None)
async def epay_callback(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    raw: dict[str, Any] = dict(await request.form()) if "application/x-www-form-urlencoded" in content_type else dict(await request.json())
    try:
        verify_callback({key: str(value) for key, value in raw.items()})
        order = settle_order_callback(
            db,
            order_id=str(raw.get("out_trade_no", "")),
            provider_trade_no=str(raw.get("trade_no", "")),
            provider_money=str(raw.get("money", "0")),
            status=str(raw.get("trade_status", raw.get("status", ""))),
        )
    except PaymentError as exc:
        api_error(400, str(exc))
    record_audit(db, actor_id=None, action="billing.callback", target_id=order.id, detail={"trade_no": order.provider_trade_no})
    db.commit()
    return Response("success", media_type="text/plain")


@app.get("/api/v1/billing/orders", response_model=list[OrderOut])
def my_orders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(50)))


@app.post("/api/v1/accounts", response_model=AccountOut, status_code=201)
def create_account(payload: AccountIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        ensure_can_create(db, user_id=user.id, resource="account")
    except QuotaError as exc:
        api_error(402, str(exc))
    account = Account(id=str(uuid4()), user_id=user.id, name=payload.name.strip(), unique_id=payload.unique_id.strip(), cookies_encrypted=encrypt_secret(__import__("json").dumps(payload.cookies)), status="READY", updated_at=datetime.utcnow())
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        api_error(409, "该账号已存在")
    record_audit(db, actor_id=user.id, action="account.created", target_id=account.id, detail={"unique_id": account.unique_id})
    db.commit()
    return account


@app.get("/api/v1/accounts", response_model=list[AccountOut])
def list_accounts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Account).where(Account.user_id == user.id, Account.status != "DELETED").order_by(Account.created_at.desc())))


@app.delete("/api/v1/accounts/{account_id}", status_code=204)
def delete_account(account_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    tasks = list(db.scalars(select(Task).where(Task.account_id == account_id, Task.user_id == user.id).with_for_update()))
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id).with_for_update())
    if not account:
        api_error(404, "账号不存在")
    account.status = "DELETED"
    account.updated_at = datetime.utcnow()
    for task in tasks:
        task.enabled = False
        task.next_run_at = None
    record_audit(db, actor_id=user.id, action="account.deleted", target_id=account.id)
    db.commit()


@app.post("/api/v1/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        ensure_can_create(db, user_id=user.id, resource="task")
    except QuotaError as exc:
        api_error(402, str(exc))
    if not db.scalar(select(Account.id).where(Account.id == payload.account_id, Account.user_id == user.id, Account.status == "READY")):
        api_error(404, "账号不存在")
    task = Task(id=str(uuid4()), user_id=user.id, account_id=payload.account_id, name=payload.name.strip(), targets=payload.targets, message=payload.message, hitokoto_types=payload.hitokoto_types, schedule_time=payload.schedule_time, timezone=payload.timezone, enabled=payload.enabled, archived=False, updated_at=datetime.utcnow())
    task.next_run_at = next_daily_run(task.schedule_time, task.timezone, utc_now()) if task.enabled else None
    db.add(task)
    record_audit(db, actor_id=user.id, action="task.created", target_id=task.id, detail={"name": task.name})
    db.commit()
    return task


@app.get("/api/v1/tasks", response_model=list[TaskOut])
def list_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Task).where(Task.user_id == user.id, Task.archived.is_(False)).order_by(Task.created_at.desc())))


@app.patch("/api/v1/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        task = owned_task(db, user.id, task_id)
    except TaskError:
        api_error(404, "任务不存在")
    if not db.scalar(select(Account.id).where(Account.id == payload.account_id, Account.user_id == user.id, Account.status == "READY")):
        api_error(404, "账号不存在")
    schedule_changed = (task.enabled, task.schedule_time, task.timezone) != (payload.enabled, payload.schedule_time, payload.timezone)
    for key, value in payload.model_dump().items():
        setattr(task, key, value)
    if not task.enabled:
        task.next_run_at = None
    elif schedule_changed or not task.next_run_at:
        task.next_run_at = next_daily_run(task.schedule_time, task.timezone, utc_now())
    task.updated_at = datetime.utcnow()
    record_audit(db, actor_id=user.id, action="task.updated", target_id=task.id)
    db.commit()
    return task


@app.delete("/api/v1/tasks/{task_id}", status_code=204)
def archive_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        task = owned_task(db, user.id, task_id)
    except TaskError:
        api_error(404, "任务不存在")
    task.archived = True
    task.enabled = False
    task.next_run_at = None
    task.updated_at = datetime.utcnow()
    record_audit(db, actor_id=user.id, action="task.archived", target_id=task.id)
    db.commit()


@app.post("/api/v1/tasks/{task_id}/run", response_model=RunOut, status_code=201)
def run_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        task = owned_task(db, user.id, task_id)
    except TaskError:
        api_error(404, "任务不存在")
    try:
        run = enqueue_run(db, task=task, trigger_type="MANUAL")
    except QuotaError as exc:
        api_error(402, str(exc))
    except TaskError as exc:
        api_error(409, str(exc))
    db.commit()
    return run


@app.get("/api/v1/runs", response_model=list[RunOut])
def list_runs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Run).where(Run.user_id == user.id).order_by(Run.created_at.desc()).limit(100)))


@app.get("/api/v1/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    run = db.scalar(select(Run).where(Run.id == run_id, Run.user_id == user.id))
    if not run:
        api_error(404, "运行记录不存在")
    return run


@app.post("/api/v1/runs/{run_id}/cancel", response_model=RunOut)
def request_run_cancel(run_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        run = cancel_run(db, run_id=run_id, user_id=user.id)
    except TaskError:
        api_error(404, "运行记录不存在")
    db.commit()
    return run


@app.get("/api/v1/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())))


@app.post("/api/v1/api-keys", response_model=ApiKeyOut, status_code=201)
def create_api_key(payload: ApiKeyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    raw = "sf_live_" + secrets.token_urlsafe(30)
    now = datetime.utcnow()
    key = ApiKey(id=str(uuid4()), user_id=user.id, name=payload.name.strip(), prefix=raw[:14], token_hash=hash_api_key(raw), expires_at=now + timedelta(days=payload.expires_days), created_at=now)
    db.add(key)
    record_audit(db, actor_id=user.id, action="api_key.created", target_id=key.id, detail={"name": key.name})
    db.commit()
    return ApiKeyOut.model_validate(key).model_copy(update={"token": raw})


@app.delete("/api/v1/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    key = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if not key:
        api_error(404, "API Key 不存在")
    key.revoked_at = datetime.utcnow()
    db.commit()


@app.get("/api/v1/admin/overview")
def admin_overview(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    total_orders = db.scalar(select(func.count(Order.id))) or 0
    paid_orders = db.scalar(select(func.count(Order.id)).where(Order.status == "PAID")) or 0
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "active_users": db.scalar(select(func.count(User.id)).where(User.status == "ACTIVE")) or 0,
        "orders": total_orders,
        "paid_orders": paid_orders,
        "order_conversion_rate": round((paid_orders / total_orders) * 100, 2) if total_orders else 0,
        "gross_cents": db.scalar(select(func.coalesce(func.sum(Order.amount_cents), 0)).where(Order.status == "PAID")) or 0,
        "queued_runs": db.scalar(select(func.count(Run.id)).where(Run.status.in_(["QUEUED", "CLAIMED", "RUNNING"]))) or 0,
        "failed_runs": db.scalar(select(func.count(Run.id)).where(Run.status == "FAILED")) or 0,
    }


@app.get("/api/v1/admin/users", response_model=list[AdminUserOut])
def admin_users(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(200)))
    result = []
    for user in users:
        output = AdminUserOut.model_validate(user)
        subscription = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
        result.append(output.model_copy(update={"subscription": SubscriptionOut.model_validate(subscription) if subscription else None}))
    return result


@app.patch("/api/v1/admin/users/{user_id}/status", response_model=UserOut)
def admin_user_status(user_id: str, payload: UserStatusIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        api_error(404, "用户不存在")
    user.status = payload.status
    record_audit(db, actor_id=actor.id, action="admin.user_status", target_id=user.id, detail={"status": user.status})
    db.commit()
    return user


@app.patch("/api/v1/admin/users/{user_id}/subscription", response_model=SubscriptionOut)
def admin_user_subscription(user_id: str, payload: AdminSubscriptionIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    if not db.get(User, user_id):
        api_error(404, "用户不存在")
    try:
        subscription = override_subscription(db, user_id=user_id, plan_id=payload.plan_id, months=payload.months)
    except ValueError as exc:
        api_error(400, str(exc))
    record_audit(db, actor_id=actor.id, action="admin.subscription_override", target_id=user_id, detail={"plan_id": payload.plan_id, "months": payload.months, "reason": payload.reason})
    db.commit()
    return subscription


@app.post("/api/v1/admin/users/{user_id}/quota-adjustments", response_model=UsageOut)
def admin_quota_adjustment(user_id: str, payload: QuotaAdjustmentIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    if not db.get(User, user_id):
        api_error(404, "用户不存在")
    usage = adjust_quota(db, user_id=user_id, period=payload.period, amount=payload.amount, reason=payload.reason)
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    limit = int((subscription.snapshot if subscription else {}).get("run_limit", 0))
    record_audit(db, actor_id=actor.id, action="admin.quota_adjustment", target_id=user_id, detail={"period": payload.period, "amount": payload.amount, "reason": payload.reason})
    db.commit()
    effective_limit = max(0, limit + usage.adjustment)
    return UsageOut(period=usage.period, used=usage.used, adjustment=usage.adjustment, limit=limit, remaining=max(0, effective_limit - usage.used))


@app.get("/api/v1/admin/plans", response_model=list[PlanOut])
def admin_plans(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(Plan).order_by(Plan.sort_order)))


@app.patch("/api/v1/admin/plans/{plan_id}", response_model=PlanOut)
def admin_update_plan(plan_id: str, payload: PlanUpdateIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if not plan:
        api_error(404, "套餐不存在")
    for key, value in payload.model_dump().items():
        setattr(plan, key, value)
    record_audit(db, actor_id=actor.id, action="admin.plan_updated", target_id=plan.id, detail={"slug": plan.slug})
    db.commit()
    return plan


@app.get("/api/v1/admin/orders", response_model=list[OrderOut])
def admin_orders(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(Order).order_by(Order.created_at.desc()).limit(200)))


@app.post("/api/v1/admin/orders/{order_id}/reconcile", response_model=OrderOut)
def admin_reconcile_order(order_id: str, payload: ReconcileIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        api_error(404, "订单不存在")
    try:
        order = activate_order(db, order_id=order.id, provider_trade_no=payload.provider_trade_no, provider_money=payload.provider_money, status="PAID")
    except PaymentError as exc:
        api_error(400, str(exc))
    record_audit(db, actor_id=actor.id, action="admin.order_reconciled", target_id=order.id, detail={"reason": payload.reason, "trade_no": payload.provider_trade_no})
    db.commit()
    return order


@app.post("/api/v1/admin/orders/{order_id}/refund", response_model=RefundOut, status_code=201)
def admin_request_refund(order_id: str, payload: RefundIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        api_error(404, "订单不存在")
    if order.status != "PAID":
        api_error(409, "只有已支付订单可以退款")
    existing = db.scalar(select(Refund).where(Refund.order_id == order.id).with_for_update())
    if existing:
        return existing
    refund = Refund(
        id=str(uuid4()), order_id=order.id, status="PENDING",
        amount_cents=order.amount_cents, reason=payload.reason,
        updated_at=datetime.utcnow(),
    )
    db.add(refund)
    order.status = "REFUND_PENDING"
    record_audit(db, actor_id=actor.id, action="admin.refund_requested", target_id=order.id, detail={"amount_cents": refund.amount_cents, "reason": payload.reason})
    db.commit()
    return refund


@app.get("/api/v1/admin/refunds", response_model=list[RefundOut])
def admin_refunds(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(Refund).order_by(Refund.created_at.desc()).limit(200)))


@app.patch("/api/v1/admin/refunds/{refund_id}", response_model=RefundOut)
def admin_complete_refund(refund_id: str, payload: RefundCompleteIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    refund = db.scalar(select(Refund).where(Refund.id == refund_id).with_for_update())
    if not refund:
        api_error(404, "退款记录不存在")
    if refund.status != "PENDING":
        return refund
    if payload.status == "SUCCEEDED" and not payload.provider_refund_no:
        api_error(400, "退款成功必须提供支付网关退款单号")
    refund.status = payload.status
    refund.provider_refund_no = payload.provider_refund_no
    refund.error = payload.error
    refund.updated_at = datetime.utcnow()
    order = db.get(Order, refund.order_id)
    if order:
        order.status = "REFUNDED" if payload.status == "SUCCEEDED" else "PAID"
        if payload.status == "SUCCEEDED":
            before = order.subscription_before
            subscription = db.scalar(select(Subscription).where(Subscription.user_id == order.user_id).with_for_update())
            if before and subscription:
                subscription.plan_id = before["plan_id"]
                subscription.snapshot = before["snapshot"]
                subscription.expires_at = datetime.fromisoformat(before["expires_at"]) if before.get("expires_at") else None
                subscription.updated_at = datetime.utcnow()
            elif subscription:
                subscription.expires_at = datetime.utcnow()
                subscription.updated_at = datetime.utcnow()
    record_audit(db, actor_id=actor.id, action="admin.refund_completed", target_id=refund.id, detail={"status": payload.status})
    db.commit()
    return refund


@app.get("/api/v1/admin/audit-logs")
def admin_audit_logs(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)))
    return [{"id": item.id, "actor_id": item.actor_id, "action": item.action, "target_id": item.target_id, "detail": item.detail, "created_at": item.created_at.isoformat()} for item in logs]


@app.get("/api/v1/admin/runs", response_model=list[RunOut])
def admin_runs(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(Run).order_by(Run.created_at.desc()).limit(200)))


@app.patch("/api/v1/admin/runs/{run_id}", response_model=RunOut)
def admin_run_status(run_id: str, payload: AdminRunStatusIn, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
    if not run:
        api_error(404, "运行记录不存在")
    if payload.status == "QUEUED":
        if run.status not in {"FAILED", "CANCELLED"}:
            api_error(409, "只有失败或已取消运行可以重新入队")
        run.status = "QUEUED"
        run.cancel_requested = False
        run.finished_at = None
        run.result = None
        run.worker_id = None
        run.lease_until = None
    else:
        if run.status not in {"QUEUED", "CLAIMED", "RUNNING"}:
            api_error(409, "当前运行状态不可取消")
        run.cancel_requested = True
        if run.status == "QUEUED":
            run.status = "CANCELLED"
            run.finished_at = datetime.utcnow()
            run.result = "Admin cancelled before execution"
    record_audit(db, actor_id=actor.id, action="admin.run_status", target_id=run.id, detail={"status": payload.status, "reason": payload.reason})
    db.commit()
    return run


@app.get("/api/v1/admin/workers")
def admin_workers(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    now = utc_now()
    workers = list(db.scalars(select(Worker).order_by(Worker.heartbeat_at.desc()).limit(200)))
    return [{
        "id": worker.id, "heartbeat_at": worker.heartbeat_at.isoformat() + "Z",
        "status": worker.status if worker.heartbeat_at > now - timedelta(seconds=60) else "OFFLINE",
    } for worker in workers]


def create_app() -> FastAPI:
    return app
