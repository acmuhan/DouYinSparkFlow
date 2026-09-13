PERMISSIONS = {
    "accounts.create": "创建执行资源",
    "accounts.validate": "更新凭据、验证资源和同步好友",
    "tasks.create": "创建和编辑任务",
    "tasks.manual": "手动执行任务",
    "tasks.schedule": "定时执行任务",
    "api.access": "创建 API 密钥并通过 API 访问",
}

# Freeze compatibility grants so future permissions are never granted by default.
LEGACY_PERMISSIONS = (
    "accounts.create", "accounts.validate", "tasks.create",
    "tasks.manual", "tasks.schedule", "api.access",
)


def effective_permissions(snapshot: dict) -> list[str]:
    value = snapshot.get("permissions")
    return list(LEGACY_PERMISSIONS) if value is None else value
