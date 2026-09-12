# DouYin Spark Flow / SparkFlow

![项目封面](docs/images/cover.png)

![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6)
![Python](https://img.shields.io/badge/Python-FastAPI-009688)
![Next.js](https://img.shields.io/badge/Next.js-App_Router-black)
![MySQL](https://img.shields.io/badge/MySQL-8%2B-4479A1)
![License](https://img.shields.io/badge/License-MIT-green)

SparkFlow 是基于原 Douyin Playwright Runner 构建的多租户控制台：
Next.js App Router + TypeScript + Tailwind/shadcn 风格组件，Python FastAPI
负责认证、任务与计费，MySQL 8+ 通过 Drizzle Migration 管理结构。

> 当前是开发中的产品实现，不是已通过生产验收的发行版。真实 MySQL 并发、
> Docker 运行、易支付交易与授权抖音账号执行仍需集成验收。

## 文档导航

- [文档索引](docs/README.md)：平台教程与运维说明
- [本地开发](docs/DEVELOPMENT.md)：环境、迁移、启动、检查
- [部署与运维](docs/DEPLOYMENT.md)：生产配置、代理、备份、排错
- [支付与业务边界](docs/BILLING.md)：订单、回调、退款与验收
- [实现状态](docs/IMPLEMENTATION.md)：架构和待完成的验证
- [贡献指南](AGENTS.md)：代码规范与 PR 要求

## 本地快速开始

需要 Node.js 22.15+、可安装后端依赖的 Python 环境和 MySQL 8+。
以下命令在仓库根目录执行；不要覆盖已有 `.env.local`。

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m playwright install chromium
Copy-Item .env.platform.example .env.local
```

编辑 `.env.local`，设置数据库连接、独立随机 `ENCRYPTION_KEY`、
管理员账号密码，并将 `AUTO_CREATE_TABLES=false`。然后：

```powershell
npm run db:migrate
uvicorn backend.app:app --reload --port 8000
```

在另外两个终端分别运行 `npm run dev` 和 `python -m backend.worker`
（Worker 终端也需要激活虚拟环境）。访问 `http://localhost:3000`。
API 启动时会初始化套餐，并在配置的管理员邮箱尚不存在时创建管理员；
修改环境变量不会重置已有管理员密码或提升已有账号角色。

## 验证

```powershell
npm run typecheck
npm run lint
npm run build
npm run db:check
python -m pytest backend/tests tests -q
```

生产构建与独立类型检查应顺序运行，避免同时读写 `.next` 生成类型。
这些检查不等同于真实支付、浏览器执行或 MySQL 并发测试。

## 功能范围

用户侧包含个人资料、订阅及配额查看、加密账号资源、任务与运行记录、
API 密钥；管理员侧包含用户状态、套餐、配额调整、订单补单、退款登记、
审计记录和 Worker 状态。退款登记不会向支付平台自动发起退款。

DouYin Spark Flow is a Playwright-based automation project for maintaining
Douyin chat streaks. The repository now includes a commercial multi-tenant
console built with Next.js and a Python API.

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | TypeScript、Next.js App Router、React |
| 界面 | Tailwind CSS、Radix UI、shadcn 风格组件、Lucide |
| 服务端 | Python、FastAPI、Pydantic、SQLAlchemy |
| 数据库 | MySQL 8+、Drizzle ORM 与版本化 Migration |
| 自动化 | Playwright、独立 Python Worker |
| 认证 | HttpOnly Session、ADMIN/USER 权限、哈希 API 密钥 |

## 仓库结构

```text
app/ components/      Next.js 页面、代理和业务界面
lib/                  前端契约、数据库与 Drizzle schema
backend/              Python API、Worker、服务和测试
core/ utils/          Worker 复用的执行模块与工具
drizzle/              SQL 迁移与快照
scripts/              数据库迁移入口
tests/                执行模块回归测试
docs/                 平台教程、运维说明和项目图片
```

## Product Console

The new platform is organized as a SaaS application:

- `app/` contains the Next.js App Router pages and same-origin API routes.
- `components/` contains reusable Tailwind/shadcn-style UI components.
- `lib/` contains the strict Drizzle MySQL schema and database singleton.
- `backend/` contains the FastAPI API, billing services, worker, and tests.
- `scripts/` contains migration and operational helpers.
- `core/` remains the browser automation engine while the new Runner wraps it.

The commercial platform supports user and admin roles, encrypted Douyin
accounts, task scheduling, quota-aware subscriptions, API keys, order audit
logs, and Epay V1/V2-compatible checkout callbacks. See
[`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) for the architecture and
acceptance checklist.

平台是唯一受维护的启动方式。旧单机 CLI、定时 Actions、
独立 Docker 入口和配置生成器已移除；仍被 Worker 引用的执行模块保留。

Do not commit `.env` files, browser cookies, API keys, or generated logs.
Review Douyin's terms and obtain the required authorization before operating
accounts for other people or offering paid automation.

For production, set a unique high-entropy `ENCRYPTION_KEY`; empty values and
the example placeholders are rejected by the API. Configure Epay credentials
and `ADMIN_PASSWORD` through the deployment environment, never in Git.

## License

The project is licensed under the MIT License; see [`LICENSE`](LICENSE).
