# 推送渠道调研 · TradingAgents 投研助手

> 2026-06-24 · 上下文：当前 Server酱免费 5 条/天，盘前盘后 + 自选股估算 30-60 条/天，必须换。设备主要是 iPhone（兼顾 Android），用户在中国大陆，部署将上服务器。

## 维度对比表

| 渠道 | 免费配额 | iOS 推送质量 | 接入难度 | 隐私 | 国内可达 | Markdown | 长期可靠性 |
|---|---|---|---|---|---|---|---|
| **Bark（官方服务器）** | 不限量、不限频（仅作者道德约束） | 走 APNs，锁屏弹、声音、分组、URL 跳转、加密推送 | 极低：装 App 拿 key，HTTP GET/POST | 默认明文，**支持端到端 AES 加密**（key 仅在手机） | 优 | 标题+body 文本；不渲染 md | 中：依赖作者个人服务器，可自建兜底 |
| **Bark（自建）** | 自建无限 | 同上 | 中：VPS + docker + APNs 走作者证书（不需自己签） | 私有服务器，仅你能看到 | 看 VPS 位置 | 同上 | 高：开源 + APNs 走作者证书风险点是证书续期 |
| **PushPlus** | 免费 200 条/天，超 400 封 2 天；付费可扩 | 经微信公众号转发，需手动点开公众号才看到，**非系统弹窗** | 极低：扫码绑微信 | 内容明文经平台 + 腾讯服务器 | 优 | 支持 markdown 渲染 | 中：商业产品，可能涨价 |
| **企业微信群机器人** | 不限总量，**20 条/分钟**上限 | iOS 企微 App 弹通知（非系统级精致），需装企微 | 中：注册企业（个人可注册一人企业）+ 群 + webhook | 内容经腾讯企业微信服务器 | 优 | 原生 markdown | 高：腾讯官方、稳 |
| **飞书自定义机器人** | 不限量，频率有软限 | 飞书 App 推送，需装飞书 | 中：注册飞书 + 群 + webhook | 内容经字节飞书服务器 | 优 | 原生 markdown | 高 |
| **Telegram Bot** | 30 msg/秒，无日限 | 系统级、锁屏弹、声音、分组 | 低：@BotFather 拿 token | 经 Telegram 服务器（境外），有 MTProto 加密 | **差**：需稳定梯子，服务器侧调用需出境 | 完整 md | 高，但**中国大陆合规风险** |
| **ntfy.sh（官方）** | 250 条/天 | iOS 走 APNs，锁屏弹、声音、分组、Action | 极低：选 topic 即用 | topic 公开可订阅，**任何人猜到 topic 名都能看**，需自加复杂 topic 或自建 | 良（CDN 全球） | 标题+body 文本 | 中-高：开源 + 商业并行 |
| **ntfy（自建）** | 无限 | 同上 | 中：VPS + docker；iOS 客户端要在 App 里配 upstream 到 ntfy.sh 才能用 APNs | 完全私有 | 看 VPS | 同上 | 高 |
| **邮件 SMTP** | 看邮箱服务商（Gmail 500/天、QQ 邮箱较松） | iOS Mail App 收到，**不是即时弹窗**（看推送设置） | 极低 | 经邮箱服务商，未加密 | Gmail 需梯子；QQ/163 优 | 全 HTML | 极高 |
| **微信公众号模板消息** | 模板已停用，**改 OA/订阅通知**且**仅限服务号 + 已关注用户** | 微信内通知 | **极高**：要个人/企业主体注册 + 服务号认证（300 元/年）+ 模板审核 | 经腾讯 | 优 | 受模板字段限制 | 中：政策易变 |
| **Pushover**（补充） | 一次性 $5 买断、10000 msg/月 | 系统级 APNs、锁屏、自定义声音、Emergency 重复响 | 低：买 App + 拿 key | 经境外服务器 | 良-中（服务器在境外） | 标题+body+URL | 极高，运营 10+ 年稳定 |

## 推荐方案

### 个人 + iPhone 主推：**Bark**（先官方，后自建）

- 系统级 APNs，锁屏弹、声音、分组都齐，体验和 iMessage 一档
- 接入 5 分钟：装 App，复制 `https://api.day.app/<key>/<title>/<body>`，HTTP GET 即推
- 国内直连官方服务器无障碍；后续上服务器再迁自建
- 不限量，不会被配额掐死
- 投资内容敏感 → 开启 **Bark 的加密推送**（AES，key 留在手机），即使经过公共服务器，作者也看不到明文

### 完全自建/隐私第一：**Bark 自建服务器 + 加密推送**

- 比 ntfy 自建省心：Bark 自建只需 VPS 跑 docker，APNs 证书作者已开源签好用直接复用（不用自己申请 Apple Developer）
- 内容全程不出你的服务器，配合 AES 加密即使有人截包也读不出
- 备选 ntfy 自建：客户端体验略弱于 Bark（分组/声音定制少），但生态更国际化

### 主备双通道：**建议做，轻量做**

- **主**：Bark（投研报告、自选股、盘前盘后）
- **备**：邮件 SMTP（QQ 邮箱，全部报告归档 + Bark 挂掉时兜底）
- 理由：Bark 服务器偶尔抖动（作者个人维护），但邮件几乎不可能同时挂；邮件本身就有归档价值（你 1 个月后想翻历史报告，Bark 不存）
- **不推荐**主备都用第三方推送（PushPlus + 企微）：两者隐私相同、都会经腾讯服务器，没分散风险
- 实现成本：抽象一个 `INotifier` 接口（当前 `IPushService` 即是），加 `EmailNotifier` 作 fallback，主通道连续失败 N 次自动转备，< 100 行代码

## 避坑提示

- **Telegram**：iOS 体验最好但服务器调用要出境，本地跑 OK，上境内云直接 GG，不推荐做主通道
- **PushPlus**：免费 200 条够用但**走微信公众号转发**，没有系统弹窗，看消息得点公众号，不是"推送"是"通知中心"，体验差一档
- **微信公众号模板消息**：服务号 300/年 + 审核，个人玩家性价比低，pass
- **ntfy.sh 官方**：topic 名是唯一凭证，**别用 `trading-report` 这种猜得到的名字**，要 `tr-x7k9m2pq...` 这种高熵串
- **企微/飞书机器人**：适合"团队推送"，单人用要装个企微/飞书 App 才能收，多 1 个 App 不优雅

## 落地建议

1. **短期**（本仓库下一步）：新增 `BarkPushService : IPushService`，与现有 `ServerChanPushService` 并列；apikeys 加 `bark.device_key` 字段；设置页加 provider 切换（Server酱 / Bark）
2. **中期**（上服务器后）：自建 Bark 服务器 + AES 加密推送；apikeys 加 `bark.endpoint` 字段
3. **长期**（可选）：邮件作备用通道，主通道连续 3 次失败自动转邮件

## Sources

- [PushPlus 限制文档](https://www.pushplus.plus/doc/help/limit.html) — 免费 200 条/天，超 400 封停 2 天
- [Bark GitHub](https://github.com/Finb/Bark) — 开源 + 自建说明 + AES 加密推送
- [Bark 官方文档](https://bark.day.app/) — APNs 推送机制
- [企业微信群机器人文档](https://developer.work.weixin.qq.com/document/path/91770) — 20 条/分钟限流
- [ntfy FAQ](https://docs.ntfy.sh/faq/) — 官方 250 条/天，自建无限
