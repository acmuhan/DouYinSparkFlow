# DouYin Spark Flow / SparkFlow

![项目封面](docs/images/cover.png)

![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6)
![Python](https://img.shields.io/badge/Python-FastAPI-009688)
![Next.js](https://img.shields.io/badge/Next.js-App_Router-black)
![MySQL](https://img.shields.io/badge/MySQL-8%2B-4479A1)
![License](https://img.shields.io/badge/License-MIT-green)

SparkFlow 是插件化任务执行与订阅管理平台，抖音续火花是首个内置插件：
Next.js App Router + TypeScript + Tailwind/shadcn 风格组件，Python FastAPI
负责认证、任务与计费，MySQL 8+ 通过 Drizzle Migration 管理结构。

> 当前是开发中的产品实现，不是已通过生产验收的发行版。真实 MySQL 并发、
> Docker 运行、易支付交易与授权抖音账号执行仍需集成验收。

## 文档导航

- [文档索引](docs/README.md)：平台教程与运维说明
- [本地开发](docs/DEVELOPMENT.md)：环境、迁移、启动、检查
- [部署与运维](docs/DEPLOYMENT.md)：生产配置、代理、备份、排错
- [支付与业务边界](docs/BILLING.md)：订单、回调、退款与验收
- [平台操作](docs/PLATFORM.md)：系统设置、套餐权限、用户、资源与通知
- [插件开发](docs/PLUGINS.md)：配置契约、执行入口与授权
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
管理员账号密码，并将 `AUTO_CREATE_TABLES=false`。然后一键启动：

```powershell
npm run dev:stack
```

生产构建后使用 `npm run start:stack`。所有进程从 `.env.local`
读取 `DATABASE_URL`、`BACKEND_URL` 和加密密钥。访问 `http://localhost:3000`。
API 启动时会初始化套餐，并在配置的管理员邮箱尚不存在时创建管理员；
修改环境变量不会重置已有管理员密码或提升已有账号角色。

## 验证

```powershell
npm run typecheck
npm run lint
npm run build
npm run db:check
python -m pytest backend/tests tests -q
python scripts/smoke_platform.py
```

生产构建与独立类型检查应顺序运行，避免同时读写 `.next` 生成类型。
本地冒烟脚本启动隔离 SQLite API 与 Next.js，使用 Chromium 验证管理流程，
结果保存在 `.runtime/smoke-*/`，结束后关闭临时服务。它不会启动 Worker，
也不等同于真实支付、抖音执行或 MySQL 并发测试。

## 功能范围

用户侧包含订阅配额、加密账号资源、异步 Cookie 检查、会话好友选择、
插件任务、运行事件日志、API 密钥和公告通知。好友结果仅覆盖已加载会话，
不保证是完整好友通讯录。

管理员可创建、编辑和删除套餐，配置插件与操作权限，管理用户与邮箱绑定，
设置注册、Worker、SMTP 和支付，以及发布公告。运行设置加密存储在数据库；
数据库连接和主加密密钥等启动配置仍由部署环境提供。
退款登记不会向支付平台自动发起退款。

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
backend/plugins/      受信任插件注册表、配置与执行入口
core/ utils/          Worker 复用的执行模块与工具
drizzle/              SQL 迁移与快照
scripts/              数据库迁移与本地集成验收
tests/                执行模块回归测试
docs/                 平台教程、运维说明和项目图片
```

## 安全与维护

平台是唯一受维护的启动方式。旧单机 CLI、定时 Actions、
独立 Docker 入口和配置生成器已移除；仍被 Worker 引用的执行模块保留。

不要提交 `.env`、浏览器 Cookie、API 密钥或运行日志。
操作他人账号前取得明确授权，并遵守目标平台规则。
生产使用独立高熵 `ENCRYPTION_KEY`，妥善备份且不要直接替换；
账号 Cookie、SMTP 密码和支付凭据依赖该密钥解密。

## License

The project is licensed under the MIT License; see [`LICENSE`](LICENSE).
