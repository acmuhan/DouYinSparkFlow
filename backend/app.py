from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .crypto import encrypt_secret
from .db import Base, engine, get_db
from .models import Account, ApiKey, AuditLog, AuthSession, Order, Plan, Run, Subscription, Task, User
from .schemas import (
    AccountIn, AccountOut, AdminUserOut, ApiKeyIn, ApiKeyOut, CheckoutIn, LoginIn, OrderOut,
    PlanOut, PlanUpdateIn, RegisterIn, RunOut, SubscriptionOut, TaskIn, TaskOut, UserOut,
)
from .security import create_session_token, hash_api_key, hash_password, session_expiry, verify_password
from .services.audit import record_audit
from .services.billing import activate_order, create_order, ensure_can_create, seed_plans
from .services.epay import verify_callback
from .services.errors import PaymentError, QuotaError

settings = get_settings()
app = FastAPI(title="SparkFlow API", version="0.1.0", docs_url="/api/docs" if not settings.production else None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


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


def current_user(session: Annotated[str | None, Cookie(alias="sf_session")] = None, db: Session = Depends(get_db)) -> User:
    return _session_user(db, session)


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        api_error(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


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
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or user.status != "ACTIVE" or not verify_password(payload.password, user.password_hash):
        api_error(401, "邮箱或密码错误")
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
    response.set_cookie("sf_session", raw, httponly=True, secure=settings.production, samesite="lax", max_age=settings.session_days * 86400, path="/")


@app.get("/api/v1/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _user_out(user)


@app.get("/api/v1/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return list(db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order)))


@app.get("/api/v1/subscription", response_model=SubscriptionOut | None)
def get_subscription(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalar(select(Subscription).where(Subscription.user_id == user.id))


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
        order = activate_order(
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
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if not account:
        api_error(404, "账号不存在")
    account.status = "DELETED"
    account.updated_at = datetime.utcnow()
    db.commit()


@app.post("/api/v1/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        ensure_can_create(db, user_id=user.id, resource="task")
    except QuotaError as exc:
        api_error(402, str(exc))
    if not db.scalar(select(Account.id).where(Account.id == payload.account_id, Account.user_id == user.id, Account.status != "DELETED")):
        api_error(404, "账号不存在")
    task = Task(id=str(uuid4()), user_id=user.id, account_id=payload.account_id, name=payload.name.strip(), targets=payload.targets, message=payload.message, hitokoto_types=payload.hitokoto_types, schedule_time=payload.schedule_time, timezone=payload.timezone, enabled=payload.enabled, archived=False, updated_at=datetime.utcnow())
    db.add(task)
    db.commit()
    record_audit(db, actor_id=user.id, action="task.created", target_id=task.id, detail={"name": task.name})
    db.commit()
    return task


@app.get("/api/v1/tasks", response_model=list[TaskOut])
def list_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Task).where(Task.user_id == user.id, Task.archived.is_(False)).order_by(Task.created_at.desc())))


@app.patch("/api/v1/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id, Task.archived.is_(False)))
    if not task:
        api_error(404, "任务不存在")
    if not db.scalar(select(Account.id).where(Account.id == payload.account_id, Account.user_id == user.id, Account.status != "DELETED")):
        api_error(404, "账号不存在")
    for key, value in payload.model_dump().items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()
    db.commit()
    record_audit(db, actor_id=user.id, action="task.updated", target_id=task.id)
    db.commit()
    return task


@app.delete("/api/v1/tasks/{task_id}", status_code=204)
def archive_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id, Task.archived.is_(False)))
    if not task:
        api_error(404, "任务不存在")
    task.archived = True
    task.enabled = False
    task.updated_at = datetime.utcnow()
    db.commit()


@app.post("/api/v1/tasks/{task_id}/run", response_model=RunOut, status_code=201)
def run_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id, Task.archived.is_(False)))
    if not task:
        api_error(404, "任务不存在")
    try:
        ensure_can_create(db, user_id=user.id, resource="run")
    except QuotaError as exc:
        api_error(402, str(exc))
    run = Run(id=str(uuid4()), user_id=user.id, task_id=task.id, status="QUEUED", trigger_type="MANUAL", snapshot={"task_id": task.id, "name": task.name, "targets": task.targets}, created_at=datetime.utcnow())
    db.add(run)
    db.commit()
    record_audit(db, actor_id=user.id, action="run.queued", target_id=run.id, detail={"task_id": task.id})
    db.commit()
    return run


@app.get("/api/v1/runs", response_model=list[RunOut])
def list_runs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Run).where(Run.user_id == user.id).order_by(Run.created_at.desc()).limit(100)))


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
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "active_users": db.scalar(select(func.count(User.id)).where(User.status == "ACTIVE")) or 0,
        "paid_orders": db.scalar(select(func.count(Order.id)).where(Order.status == "PAID")) or 0,
        "gross_cents": db.scalar(select(func.coalesce(func.sum(Order.amount_cents), 0)).where(Order.status == "PAID")) or 0,
        "queued_runs": db.scalar(select(func.count(Run.id)).where(Run.status.in_(["QUEUED", "RUNNING"]))) or 0,
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
def admin_user_status(user_id: str, payload: dict[str, str], actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    if payload.get("status") not in {"ACTIVE", "SUSPENDED", "BANNED"}:
        api_error(400, "无效账户状态")
    user = db.get(User, user_id)
    if not user:
        api_error(404, "用户不存在")
    user.status = payload["status"]
    record_audit(db, actor_id=actor.id, action="admin.user_status", target_id=user.id, detail={"status": user.status})
    db.commit()
    return user


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


@app.get("/api/v1/admin/audit-logs")
def admin_audit_logs(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)))
    return [{"id": item.id, "actor_id": item.actor_id, "action": item.action, "target_id": item.target_id, "detail": item.detail, "created_at": item.created_at.isoformat()} for item in logs]


def create_app() -> FastAPI:
    return app
