from uuid import uuid4

from ..models import Run, RunEvent
from .scheduling import utc_now

MESSAGES = {
    "queued": "任务已进入执行队列",
    "started": "Worker 已开始执行",
    "progress": "发送进度已更新",
    "succeeded": "任务执行结束",
    "failed": "任务执行失败，请查看运行结果",
    "cancelled": "任务已取消，已提交的消息无法撤回",
    "cancel_requested": "已请求取消，等待 Worker 停止",
    "interrupted": "执行进程中断，部分操作可能已完成",
    "lease_expired": "Worker 租约过期，任务不会自动重放",
    "requeued": "管理员已将任务重新入队",
}


def add_run_event(db, run: Run, code: str) -> None:
    # Messages are selected from an allowlist, never copied from browser errors.
    db.add(RunEvent(id=str(uuid4()), run_id=run.id, code=code, message=MESSAGES[code],
                    sent_count=run.sent_count or 0, created_at=utc_now()))
