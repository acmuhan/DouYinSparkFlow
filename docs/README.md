# 文档索引

## SparkFlow 多租户平台

建议按以下顺序阅读：

1. [本地开发](DEVELOPMENT.md)：安装、数据库初始化、启动与测试。
2. [部署与运维](DEPLOYMENT.md)：生产配置、安全、代理和排错。
3. [支付与业务边界](BILLING.md)：回调协议、人工补单和退款。
4. [实现状态](IMPLEMENTATION.md)：代码级能力与外部验收缺口。

仓库根目录的 [AGENTS.md](../AGENTS.md) 是贡献规范；
API 请求字段以 `backend/schemas.py` 和启动后的 `/docs` 为准。

## 历史单机脚本

下面的文档服务于 `main.py` 工作流，不是新平台的部署手册：

- [源代码部署说明](源代码部署说明.md)
- [Action 部署说明](Action部署说明.md)
- [Docker 部署说明](Docker部署说明.md)
- [配置生成器使用](配置生成器使用.md)

`index.html`、`static/`、`images/` 保留历史文档及配置页面资源。
新平台使用 `.env.platform.example`，不要把旧脚本的配置直接当成平台配置。
