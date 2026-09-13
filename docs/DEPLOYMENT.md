# 部署与运维

## 配置

生产部署前设置以下变量：

| 变量 | 用途与注意事项 |
| --- | --- |
| `DATABASE_URL` | MySQL 连接；API、Worker、迁移必须指向同一数据库 |
| `ENVIRONMENT` | 生产设为 `production` |
| `AUTO_CREATE_TABLES` | 生产设为 `false`，发布前应用迁移 |
| `ENCRYPTION_KEY` | API/Worker 使用同一独立随机密钥；保管好备份 |
| `APP_URL` | 对外 HTTPS 站点地址，用于支付通知和同步回跳 |
| `WEB_ORIGIN` | 浏览器访问的准确源地址 |
| `BACKEND_URL` | Next.js 可访问的 Python API 内网地址 |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 首次创建管理员，不负责已有账号密码重置 |
| `EPAY_*` | 旧部署兼容回退；新配置优先使用管理端支付设置 |

加密密钥变化会导致旧账号凭据无法正常解密，不要无迁移地轮换。
数据库备份与密钥备份应分开存储，恢复演练需验证两者配套可用。

注册开关、Worker 开关和超时、SMTP、支付配置在管理控制台维护，
加密保存在 `system_settings`。这些配置无需逐项添加到环境变量。
`DATABASE_URL`、主密钥、站点地址和首次管理员凭据仍是启动配置。

## 从旧版本升级

1. 停止 API 和 Worker，备份 MySQL 数据及独立保管的主加密密钥。
2. 安装当前依赖，在同一数据库上执行 `npm run db:migrate`。
   本次新增 `0002` 至 `0009` 迁移，不要手工跳过迁移或修改已应用 SQL。
3. 执行 `npm run build`，重启 API、Web、Worker。
4. 在管理端检查套餐权限、SMTP 和支付配置；新套餐默认不授予插件或操作权限。
5. 用测试用户确认资源检查、任务排队、运行日志和公告已读状态。

旧订阅通过快照保留既有抖音权益，不自动获得后来新增插件。
编辑套餐不会追溯修改已购买订阅的快照。SQLite 冒烟测试不验证 MySQL
的锁行为或迁移 SQL，必须在发布数据库副本上另做升级演练。

## Docker 的当前限制

`docker compose up -d --build` 是开发基线，不是加固后的生产配置。
Compose 插值不会默认读取 `.env.local`；可显式使用：

```powershell
docker compose --env-file .env.local up -d --build
```

但是 `--env-file` 只提供插值变量，不会把所有变量注入容器。
当前 Compose 的 API 没有传入 `EPAY_*`、`ENVIRONMENT`，且
`AUTO_CREATE_TABLES` 写死为 `"true"`；Worker 也缺少生产环境标志。
正式部署必须通过经过审阅的 Compose override 或部署平台显式配置这些项。
同时修改默认数据库密码，并确保 `MYSQL_PASSWORD` 与连接字符串一致。

## 入口与支付代理

HTTPS 网关至少需要以下路由：

- `/` 转发到 Next.js（3000）。
- `/api/v1/billing/epay/callback` 转发到 FastAPI（8000），保留请求体和方法。

订单生成的通知地址使用 `APP_URL/api/v1/billing/epay/callback`，
不是 Next.js 的 `/api/backend/...` 路径。只暴露 Next.js 会导致回调不可达。
限制数据库及 API 端口的公网访问，生产只开放所需入口。

## 发布验收

先备份数据库，应用迁移，再启动 API、Worker 和 Web。
确认 API 健康响应中的 `database=ok`、管理员可登录、Worker 有心跳。
用授权测试账号验证任务与租户隔离；用支付平台测试环境验证通知和重放。
没有商户及抖音测试授权时，不应宣称端到端验收完成。

故障排查使用 `docker compose logs --tail=100 api worker web`，
分享日志前删除凭据和个人信息。不要用删除数据库卷解决迁移问题；
应用版本回退也不会自动回滚数据库结构。
