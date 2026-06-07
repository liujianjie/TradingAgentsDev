# Clash 开 TUN 时让 akshare（国内数据源）正常工作

## 目的

你用 Clash Verge + TUN 模式是为了访问 grok（境外 api.x.ai）。但 **TUN 是网卡层的全局透明代理**，它会把访问**东财**（akshare 的 A股/港股数据源）的国内流量也绕到境外节点。东财对境外 IP 反爬，直接掐断连接（`RemoteDisconnected`），于是 akshare 取不到 A股/港股数据。

本文让你把 Clash 配成「**国内直连、境外走代理**」——grok 照常用代理，akshare 走直连，两不耽误。

> 注意：就算不改，系统也能用——akshare 取不到时会自动 fallback 到 yfinance（境外源，反而走代理更通）。改这个是为了让 A股/港股用上 akshare 的**全量中文数据**（行情/财报/东财新闻）。

## 前置

- Clash Verge 已开 TUN 模式（你现在的状态）
- 已导入机场订阅配置

## 怎么确认就是这个问题

在项目里跑（`!` 开头可直接在本会话执行）：

```powershell
python -c "import requests; j=requests.get('http://ip-api.com/json/?lang=zh-CN',timeout=12).json(); print(j.get('country'), j.get('regionName'), j.get('query'))"
```

- 显示 **台湾 / 香港 / 美国** 等境外地区 → 确认 TUN 把国内流量也代理了（就是本问题）
- 显示**中国大陆**的省份 → 不是这个问题

## 解决步骤

### 1. 把代理模式从「全局」切到「规则」（最关键）

Clash Verge 主界面 → 顶部「代理模式」→ 选 **规则（Rule）**，**不要**用 **全局（Global）**。

- *为什么*：全局模式下**所有**流量无脑走代理（包括东财）；规则模式按订阅里的分流规则走，国内域名通常被规则指向 `DIRECT`（直连）。大多数机场订阅默认带 `GEOIP,CN,DIRECT` / `GEOSITE,CN,DIRECT`，切到规则模式后东财一般就自动直连了。

### 2. 验证是否已直连

切完再跑一次第「怎么确认」里的命令：
- 出口地区变成**中国大陆** → 成功，进第 4 步实测
- 仍是境外 → 你的订阅规则没覆盖国内分流，做第 3 步

### 3.（仅当第 2 步仍不通）手动加国内财经域名直连规则

Clash Verge →「配置」→ 给当前订阅加一个 **Merge（合并）扩展配置**（不要直接改订阅文件，否则更新订阅会被覆盖），在 `rules` **最前面**加：

```yaml
rules:
  - DOMAIN-SUFFIX,sina.com.cn,DIRECT     # akshare 行情主力源（finance.sina.com.cn / stock.finance.sina.com.cn）——最关键
  - DOMAIN-SUFFIX,sinajs.cn,DIRECT
  - DOMAIN-SUFFIX,eastmoney.com,DIRECT    # 备用（注：东财 push2 API 反爬，本项目已改用新浪源，留着不碍事）
  - DOMAIN-SUFFIX,gtimg.cn,DIRECT
```

> 本项目 akshare 行情走的是**新浪源**（`finance.sina.com.cn`），所以 `sina.com.cn` 那条最关键，必须命中直连。

- *为什么放最前*：规则从上往下匹配，放前面确保这几个域名优先命中直连，不被后面的"全部走代理"兜底规则截走。
- *为什么用 Merge*：直接改订阅文件，下次更新订阅就没了；Merge 扩展配置是独立的，更新订阅也保留。

### 4. 实测 akshare 恢复

让我（或你自己）跑：

```powershell
python -c "import sys; sys.path.insert(0,r'F:\AIProject\TradingAgents'); from tradingagents.dataflows.akshare_utils import get_akshare_stock_data; print(get_akshare_stock_data('600519.SS','2026-05-25','2026-06-06')[:200])"
```

打印出茅台行情 CSV = akshare 通了。

## 成功标志

- 出口 IP 检测显示**中国大陆**
- 上面的 akshare 命令打印出 A股行情数据，不再 `RemoteDisconnected`

## 常见卡点

| 现象 | 原因 / 排查 |
|------|------|
| 切规则模式后 grok 连不上了 | 极少数订阅把 api.x.ai 也归到了 DIRECT。确认 `api.x.ai` 走代理节点（必要时加 `DOMAIN-SUFFIX,x.ai,<你的代理策略组>`）|
| 改了规则不生效 | Clash Verge 改配置后需「重新加载配置」或重启内核；TUN 开关也切一下 |
| 出口 IP 仍境外 | 订阅无国内分流规则集，必须走第 3 步手动加，或换带 `GEOIP,CN,DIRECT` 的订阅 |
| 改订阅文件后更新没了 | 没用 Merge 扩展配置，直接改了订阅正文——改用 Merge |
