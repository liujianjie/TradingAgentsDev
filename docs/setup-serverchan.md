# Server酱 配置指南

## 目的

Server酱是一个将消息推送到微信的免费服务。TradingAgents 分析完成后，通过 Server酱 把报告发到你的微信，无需安装额外 App。

跳过此步骤：C# 后端无法发送微信推送，阶段一功能无法使用。

## 前置条件

- 微信账号（已实名）
- 能访问 sct.ftqq.com

## 步骤

### 1. 注册账号

前往 [https://sct.ftqq.com](https://sct.ftqq.com)，点击右上角「登录」→ 选择「微信扫码登录」。

用微信扫码后，Server酱 自动绑定你的微信账号。

**成功标志**：登录后看到控制台界面，右上角显示你的微信头像。

### 2. 获取 SendKey

登录后，进入「SendKey」页面（导航栏「消息通道」→「方糖服务号」或「微信测试号」）。

你会看到一串以 `SCT` 开头的字符串，形如 `SCTxxxxxxxxxxxxxxxxxxx`。

这就是你的 **SendKey**，后面会填到配置文件里。

**注意**：SendKey 等同于密码，不要分享给他人，不要提交到 Git。

### 3. 测试推送是否成功

在 Server酱 控制台页面，找到「发送消息」测试框，填入：
- 标题：`测试消息`
- 内容：`Hello from TradingAgents`

点击「发送」，1-10 秒后微信应收到来自「Server酱」公众号的消息。

**成功标志**：微信收到消息，内容正确。

**常见卡点**：
- 没收到消息 → 检查是否已关注「Server酱」公众号（登录后控制台会有二维码）
- SendKey 错误 → 重新从控制台复制，注意不要有多余空格

### 4. 填写到项目配置

将 SendKey 填入 C# 后端的配置文件：

```bash
# 方式一（推荐）：设置环境变量，不写入文件
export SERVERCHAN_SEND_KEY=SCTxxxxxxxxxxxxxxxxxxx

# 方式二：写入 appsettings.local.json（已在 .gitignore 中）
# 文件路径：TradingPlatform/TradingPlatform.Api/appsettings.local.json
```

`appsettings.local.json` 内容格式：
```json
{
  "ServerChan": {
    "SendKey": "SCTxxxxxxxxxxxxxxxxxxx"
  }
}
```

**填写完成后**，回到开发流程继续阶段一的代码实现。

## 免费版限制

| 项目 | 免费版 | 付费版 |
|------|--------|--------|
| 每日推送条数 | 5 条 | 无限制 |
| 消息模板 | 基础 | 自定义 |

若你每天分析 3 只股票（盘前+盘后各 1 次 = 6 条/天），需要购买付费版（约 ¥99/年）。

若只做盘后推送，3 只股票 = 3 条/天，免费版够用。
