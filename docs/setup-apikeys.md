# API Keys 配置指南

## 目的

把所有密钥（LLM API Key、Server酱 SendKey）集中放在 **一个 JSON 文件** 里。Python 和 C# 都从它读，不用配环境变量。

文件位置：`F:/AIProject/TradingAgents/config/apikeys.local.json`

**重要**：`apikeys.local.json` 已加入 `.gitignore`，不会被提交。

## 步骤

### 1. 文件已存在，直接编辑

打开 `F:/AIProject/TradingAgents/config/apikeys.local.json`，看到的结构如下（所有 key 都是空的）：

```json
{
  "active_provider": "deepseek",
  "providers": {
    "deepseek": {
      "api_key": "",
      "deep_think_model": "deepseek-chat",
      "quick_think_model": "deepseek-chat"
    },
    "openai": { ... },
    "google": { ... },
    "anthropic": { ... },
    "qwen-cn": { ... }
  },
  "serverchan": {
    "send_key": "SCT..."
  }
}
```

### 2. 填入你的密钥

#### a. 选一个 LLM 提供商（推荐 DeepSeek）

到 [https://platform.deepseek.com](https://platform.deepseek.com) → 注册 → 充值 ¥10 → 创建 API Key → 复制。

把 key 填到 `providers.deepseek.api_key`：

```json
"deepseek": {
  "api_key": "sk-1234567890abcdef",  ← 你复制的
  "deep_think_model": "deepseek-chat",
  "quick_think_model": "deepseek-chat"
}
```

#### b. 切换默认提供商（如果不用 deepseek）

修改 `active_provider` 字段：

```json
"active_provider": "openai"   ← 改成你想用的
```

支持的值：`openai` / `deepseek` / `google` / `anthropic` / `qwen-cn` / `xai`

#### c. Server酱 SendKey

`serverchan.send_key` 已经填好了（你之前给的）。如果重置了，把新值填进去。

### 3. 重启服务让配置生效

杀掉之前的 Python 和 C# 进程，重启：

```powershell
# 终端 1
cd F:\AIProject\TradingAgents
uvicorn api.main:app --port 8000

# 终端 2
cd F:\AIProject\TradingAgents\TradingPlatform\TradingPlatform.Api
dotnet run
```

## 验证

启动后 Python 会打印：

```
[apikeys] loaded provider=deepseek deep=deepseek-chat
```

看到上面这句说明已加载成功。如果看到 `provider 'deepseek' has empty api_key`，说明你忘填了。

C# 启动会打印：

```
apikeys 配置文件路径: F:\AIProject\TradingAgents\config\apikeys.local.json (存在=True)
```

## 文件结构说明

```json
{
  "active_provider": "deepseek",      ← 当前使用哪家
  "providers": {                       ← 各家配置（可同时填多家，随时切换）
    "<provider_name>": {
      "api_key": "...",                ← 必填
      "deep_think_model": "...",       ← 重型模型（投资分析）
      "quick_think_model": "...",      ← 轻型模型（快速判断）
      "base_url": null                 ← 自定义 endpoint，null 用官方
    }
  },
  "serverchan": {
    "send_key": "SCT..."               ← Server酱推送密钥
  }
}
```

## 多 LLM 同时配置

可以同时填多家 key，需要时切换 `active_provider` 即可，无需重新输入：

```json
{
  "active_provider": "openai",         ← 现在用 OpenAI
  "providers": {
    "openai": { "api_key": "sk-aaa..." },
    "deepseek": { "api_key": "sk-bbb..." },   ← 留着备用
    "google": { "api_key": "xxx..." }
  }
}
```

下次想换：直接改 `active_provider` 为 `"deepseek"` → 重启服务 → 生效。

## 切换到 Google Gemini（实测本机可直连，无需代理）

> 适用：DeepSeek/OpenAI key 失效，改用 Gemini。**纯配置，不用改任何代码。**

### 1. 拿 Gemini key

到 **[https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)**（Google AI Studio）→ 用 Google 账号登录 → 「Create API key」→ 点那一行的「Copy」复制。
- *为什么是这个网站*：Gemini 的 API key 在 AI Studio 申请，不是 Google Cloud 控制台。免费层有每日额度，个人用足够起步。
- **⚠️ 认准 key 格式**：正确的是 **`AIza` 开头、共 39 位、只含字母数字 `_-`**。
  如果你复制到的是 `AQ.A...` 开头或几十位带 `.` 的长串，那是 OAuth/临时凭据**不是 API key**，会报 `401 Expected OAuth 2 access token`。复制错行了，回页面找 `AIza` 那一行。

### 2. 改 `config/apikeys.local.json` 三处

```jsonc
"active_provider": "google",              // ← 从 deepseek 改成 google
"providers": {
  "google": {
    "api_key": "<粘贴你的 Gemini key>",    // ← 填上
    "deep_think_model": "gemini-2.5-pro",  // ← 深度推理/多空辩论用 pro
    "quick_think_model": "gemini-2.5-flash", // ← 快思考用 flash，省钱
    "base_url": null
  }
}
```
- *为什么改模型名*：原来填的 `gemini-2.0-flash` 已不在代码推荐列表，建议用当前稳定的 `gemini-2.5-*`。想最省钱：deep/quick 都填 `gemini-2.5-flash`。
- *base_url 保持 null*：代码会自动用 Google 官方端点。本机已实测可直连（HTTP 403=连通，仅因没带 key），**不用挂代理**。

### 3. 让新 key 生效（关键）

Python 服务**只在启动时读一次** key 文件，改完必须让它重新加载。两种方式：
- **若用 `--reload` 启动**：热重载只盯 `.py`，改 `.json` 不触发 → 随便存一下任意 `.py`（如 `api/main.py`）即可触发重载。
- **否则**：关掉 uvicorn 窗口重启（见上文「步骤 3」）。

### 4. 验证（强烈建议，省得白跑一次完整分析）

启动日志应出现：`[apikeys] loaded provider=google deep=gemini-2.5-pro`。
想更稳，跑一个零成本鉴权探测（不消耗 token）：
```powershell
python -c "import json,urllib.request as u; k=json.load(open('config/apikeys.local.json',encoding='utf-8'))['providers']['google']['api_key']; print(u.urlopen(f'https://generativelanguage.googleapis.com/v1beta/models?key={k}',timeout=15).status)"
```
打印 `200` = key 有效，可以放心分析。`403/400` = key 不对，回到第 1 步。

### 常见卡点（Gemini）

| 现象 | 原因 / 排查 |
|------|------|
| 日志仍是 `provider=deepseek` | `active_provider` 没改成 `google`，或没重载 |
| 探测返回 400/403 | key 复制错/有空格，或 AI Studio 里这把 key 被删了 |
| 分析超时但不是 401 | 极少数网络波动；本机实测可直连，重试即可 |

---

## 切换到 xAI Grok

> 适用：已有 xAI API Key，想用 Grok 系列模型。**纯配置，不用改任何代码。**

### 1. 拿 xAI API Key

到 **[https://console.x.ai](https://console.x.ai)** → 用 X 账号登录 → 「API Keys」→「Create API Key」→ 复制。
- *为什么*：xAI 的 key 只在这里申请，没有其他入口。
- key 格式：`xai-` 开头的字符串。
- 注意：key 只在创建时显示一次，必须立刻复制保存。

### 2. 改 `config/apikeys.local.json` 两处

```jsonc
"active_provider": "xai",                        // ← 改成 xai
"providers": {
  "xai": {
    "api_key": "<粘贴你的 xAI key>",              // ← 填上，替换尖括号
    "deep_think_model": "grok-4.3",               // 深度推理 / 多空辩论
    "quick_think_model": "grok-4-fast-non-reasoning", // 快速判断，省钱
    "base_url": null                              // null 用官方端点
  }
}
```

**可选模型**：

| 场景 | 推荐型号 |
|------|---------|
| 深度分析（deep_think） | `grok-4.3`（旗舰，1M ctx，内建推理）|
| 快速判断（quick_think） | `grok-4-fast-non-reasoning`（速度最快）|
| 代码任务 | `grok-build-0.1`（256K ctx，代码专项）|
| 推理（省 quota） | `grok-4-fast-reasoning` |

### 3. 重启服务让配置生效

同上文「步骤 3」。

### 4. 验证

启动日志应出现：
```
[apikeys] loaded provider=xai deep=grok-4.3
```

### 常见卡点（xAI Grok）

| 现象 | 原因 / 排查 |
|------|------|
| 日志仍是 `provider=deepseek` | `active_provider` 没改，或 JSON 格式有误（多/少逗号） |
| `AuthenticationError` | key 填错，或 key 创建时没复制完整（`xai-` 开头） |
| `model not found` | 模型名拼写错误，改回 `grok-4.3` |
| 分析超时 | xAI API 暂时波动，稍后重试 |

---

## 安全注意

- ✅ 文件**只在你电脑上**，已加入 `.gitignore`
- ✅ 别把它发到群里、issue、聊天
- ✅ 怀疑泄漏：去对应平台控制台 revoke 重发
- ❌ 别复制粘贴到 ChatGPT / Claude 等 AI 帮你"修一下"，可能被记录

## 常见卡点

| 现象 | 原因 |
|------|------|
| Python 仍报 Missing credentials | 你改了文件但没重启 Python |
| 切换 provider 不生效 | `active_provider` 字段拼写错误（注意是 `qwen-cn` 不是 `qwen_cn`） |
| Server酱 SendKey 未配置 | C# 没读到，检查 `config/apikeys.local.json` 路径是否正确 |
| 推送失败 401 | SendKey 在 Server酱平台已被 revoke，去重新生成 |
