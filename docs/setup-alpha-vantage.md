# 配置 Alpha Vantage 数据 API

## 目的

TradingAgents 默认用 Yahoo Finance（yfinance）拉取行情数据，但 Yahoo Finance 是无 Key 的爬取接口，高频调用时容易触发 429 限流。Alpha Vantage 是有正式 API Key 的数据服务，稳定性更好。

切换后不影响 LLM 配置，只影响行情/财务/新闻数据的来源。

## 前置条件

- 已完成 Python 环境配置（见 docs/setup-python-env.md）
- 已有 `config/apikeys.local.json`（见 docs/setup-apikeys.md）

## 第一步：注册 Alpha Vantage 账号并获取 API Key

1. 打开 https://www.alphavantage.co/support/#api-key
2. 填写表单：
   - **Organization**：随便填，个人用填自己名字即可
   - **Email**：填你的邮箱（Key 会发到这里）
   - **Intended Use**：选 `Personal/Academic`
3. 点击 **GET FREE API KEY**
4. 页面会立即显示你的 API Key（格式类似 `ABCD1234EFGH5678`），同时发到邮箱
5. 复制这个 Key

**成功标志**：看到一串大写字母+数字组成的 Key，长度约 16 位。

**免费版限制**：
- 每分钟最多 5 次请求
- 每天最多 25 次请求
- 对单只股票跑一次完整分析约消耗 8-12 次请求，免费版够日常测试用

**常见卡点**：
- 表单提交后没反应 → 检查邮箱垃圾箱
- 当天 25 次用完 → 第二天零点（UTC 时间）重置

## 第二步：填入配置文件

打开 `config/apikeys.local.json`，在 `data_apis` 字段填入 Key：

```json
{
  "active_provider": "deepseek",
  "providers": { ... },
  "serverchan": { ... },
  "data_apis": {
    "alpha_vantage": "你的Alpha Vantage Key"
  }
}
```

**为什么填这里**：`config_loader.py` 会在启动 Python API 时读取这个字段，自动设置 `ALPHA_VANTAGE_API_KEY` 环境变量，TradingAgents 的 Alpha Vantage 数据模块从这个环境变量读 Key。

## 第三步：验证配置生效

启动 Python API 后，查看启动日志，应该看到：

```
[apikeys] loaded provider=deepseek ...
[apikeys] alpha_vantage key loaded
```

或在 Python 中快速验证：

```python
from api.config_loader import load_apikeys
load_apikeys()
import os
print(os.environ.get('ALPHA_VANTAGE_API_KEY', 'NOT SET'))
```

## 填回位置汇总

| 获取的内容 | 填入文件 | 字段路径 |
|---|---|---|
| Alpha Vantage API Key | `config/apikeys.local.json` | `data_apis.alpha_vantage` |
