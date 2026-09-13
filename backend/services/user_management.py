import secrets

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import Account, ApiKey, AuthSession, Run, Task, User
from ..security import hash_password
from .jobs import ACTIVE_RUN_STATES, cancel_run
from .scheduling import utc_now


def revoke_user_credentials(db: Session, user_id: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.execute(update(ApiKey).where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None)).values(revoked_at=utc_now()))


def retire_user(db: Session, user: User) -> None:
    """Caller locks the user; preserve financial foreign keys, revoke execution."""
    now = utc_now()
    user.status = "DELETED"
    user.name = "Deleted user"
    user.email = f"deleted-{user.id}@users.invalid"
    user.password_hash = hash_password(secrets.token_urlsafe(48))
    revoke_user_credentials(db, user.id)
    tasks = list(db.scalars(select(Task).where(Task.user_id == user.id).with_for_update()))
    for task in tasks:
        task.archived = True
        task.enabled = False
        task.next_run_at = None
        task.updated_at = now
    accounts = list(db.scalars(select(Account).where(Account.user_id == user.id).with_for_update()))
    for account in accounts:
        account.status = "DELETED"
        account.cookies_encrypted = ""
        account.updated_at = now
    runs = list(db.scalars(select(Run).where(Run.user_id == user.id, Run.status.in_(ACTIVE_RUN_STATES)).with_for_update()))
    for run in runs:
        cancel_run(db, run_id=run.id, user_id=user.id)
