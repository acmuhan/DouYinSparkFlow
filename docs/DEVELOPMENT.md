# 本地开发

## 进程与目录

浏览器访问 Next.js，`/api/backend/*` 代理到 FastAPI 的 `/api/v1/*`。
代理负责转发，不代表所有请求都经过 Zod 校验；Python 使用 Pydantic
执行请求校验与角色、租户权限检查。独立 Worker 执行浏览器任务。

`lib/` 定义 Drizzle 数据结构，`backend/models.py` 映射同一组表；
`backend/services/` 包含计费及 Runner 等服务。数据库变更需同时核对两端。

## 初始化

按根目录 README 安装依赖和浏览器。MySQL 默认连接
`127.0.0.1:3307/sparkflow`，如果本机使用 3306，请修改 `DATABASE_URL`。
可用 `docker compose up -d mysql` 仅启动开发数据库。

`.env.local` 同时供 Next.js、迁移脚本和 Python Settings 读取。
从仓库根目录启动命令，使用相同加密密钥启动 API 和 Worker。
不要提交环境文件、Cookie、密钥或日志。

首次启动先执行 `npm run db:migrate`，然后分别运行：

```powershell
uvicorn backend.app:app --reload --port 8000
python -m backend.worker
npm run dev
```

这三个命令各占一个终端。访问 `http://localhost:3000`；
API 文档在 `http://127.0.0.1:8000/docs`。
`/api/v1/health` 需检查 JSON 的 `database` 字段，而不是只看 HTTP 200。

## 修改数据库

1. 修改 Drizzle schema 并同步 SQLAlchemy 模型。
2. 执行 `npm run db:generate`，审阅生成 SQL。
3. 执行 `npm run db:check` 与 `npm run db:migrate`。
4. 在隔离 MySQL 实例验证升级、约束和事务行为后提交迁移文件。

现有迁移的正常部署只需 `db:migrate`，不需重新生成。
`AUTO_CREATE_TABLES=true` 仅用于开发，不替代版本化迁移。

## 回归检查

```powershell
npm run typecheck
npm run lint
npm run build
npm run db:check
python -m pytest backend/tests tests -q
python -m compileall -q backend core
```

测试通过不证明 MySQL 行锁、真实支付回调或抖音消息发送正确。
新增后端测试使用 `test_*.py`，重点覆盖越权访问、重复回调、
订阅延期、额度扣减和任务取消。视觉变更附桌面及移动端截图。
