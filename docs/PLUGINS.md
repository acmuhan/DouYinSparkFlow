# 插件开发

## 受信任注册表

插件位于 `backend/plugins/`，由 `PLUGINS` 显式注册。
目前只内置 `douyin_streak`；不支持上传、下载或执行用户提交的 Python。
插件在 Worker 进程运行，具有该进程权限，并非不可信代码沙箱。
安装新插件需要代码审查、部署代码并重启 API 和 Worker。

每个 `Plugin` 必须声明稳定的 `id`、名称、说明、`execute`、
Pydantic `config_model` 和 `requires_account`。无账号插件设置
`requires_account=False`，不会接收抖音 Cookie；`legacy_fields` 仅用于旧字段兼容。
目前账号资源模型仍为抖音专用，接入其他平台账号需要新增相应资源契约。

## 配置与执行契约

配置模型应使用 `ConfigDict(extra="forbid")` 并声明长度、数量等边界。
API 验证 `plugin_config`，排队时复制到不可变运行快照。
编辑任务不应影响已入队执行。`GET /api/v1/plugins` 返回配置 schema；
非抖音插件当前通过 JSON 编辑器填写配置。

执行函数签名：

```python
def execute(*, cookies, snapshot, checkpoint, on_sent):
    checkpoint()
    # Read validated input from snapshot.plugin_config.
    # Call checkpoint before each external side effect.
    # Report a monotonic completed-item count using on_sent(count).
```

返回对象需提供非负整数 `sent_count` 和 `missing_count`；
当前通用运行器以 `missing_count == 0` 判断成功。
这是兼容现有发送任务的结果契约，尚不是任意插件自定义结果协议。
不要捕获后忽略取消异常，不要把凭据写入日志。
浏览器依赖应延迟到执行函数加载。

## 权限与测试

在套餐编辑器授予插件权限，同时授予需要的手动或定时执行权限。
旧订阅缺少插件权限字段时仅兼容抖音，不隐式允许新插件。
任务入队及运行检查点都校验租户、订阅和执行权限。

参考 `backend/tests/test_plugins.py` 的无账号诊断插件测试：
覆盖非法配置、权限拒绝、队列分发、配置快照和完成状态。
运行 `python -m pytest backend/tests/test_plugins.py -q`；
通过模拟执行不意味着外部服务集成已经验收。
