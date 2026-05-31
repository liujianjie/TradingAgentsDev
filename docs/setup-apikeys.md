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

支持的值：`openai` / `deepseek` / `google` / `anthropic` / `qwen-cn`

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
