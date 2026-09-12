# 文档索引

## SparkFlow 多租户平台

建议按以下顺序阅读：

1. [本地开发](DEVELOPMENT.md)：安装、数据库初始化、启动与测试。
2. [部署与运维](DEPLOYMENT.md)：生产配置、安全、代理和排错。
3. [支付与业务边界](BILLING.md)：回调协议、人工补单和退款。
4. [实现状态](IMPLEMENTATION.md)：代码级能力与外部验收缺口。

仓库根目录的 [AGENTS.md](../AGENTS.md) 是贡献规范；
API 请求字段以 `backend/schemas.py` 和启动后的 `/docs` 为准。

## 维护范围

仅维护多租户平台教程。旧单机 CLI、定时 Actions、配置生成器及对应教程
已移除，历史版本可从 Git 查阅。新平台统一使用
`.env.platform.example` 与 `backend/requirements.txt`。
