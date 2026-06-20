# Spec: Serenity 产业链卡点研究（独立模块）

> 状态：草案 v1 · 等待 review
> 分支：`feature/serenity-skill`
> 关联 skill：`C:\Users\Administer\.claude\skills\serenity-skill\SKILL.md`（已部署到 Claude Code 全局）
> 关联记忆：[[project_trading_platform]]

---

## 1. 目标

给用户一个**独立入口**做 Serenity 式产业链卡点研究：输入一个主题 + 市场，得到一份「卡点环节排序 + 优先研究公司清单 + 证据 + 反方理由 + 下一步检查项」的结构化报告。

**不替代**现有 TradingAgents 的多代理交易分析。两者并存、互不干扰、独立入口。

## 2. 用户价值

对应 SKILL.md 的核心承诺：

```
market story → system change → required parts → supply-chain layers →
scarce constraints → public companies → evidence → what the market may be missing →
what could prove the idea wrong
```

输入示例：`"A 股 AI 半导体产业链，研究当前最值得关注的方向"`
输出示例：见 `examples/a-share-ai-semiconductor-demo.md`

## 3. 范围

**In scope（v1）**
- 主题扫描（Theme scan）：给主题 + 市场 → 优先研究清单
- 单公司挑战（Single-company challenge）：给 ticker → 证据 + 反方
- 候选比较（Candidate comparison）：给多个 ticker → 排序对比
- 市场覆盖：A 股 / 港股 / 美股（v1 先做 A 股 + 美股，港股 v1.1）

**Out of scope（v1）**
- 研究伙伴对话模式（多轮 chat 形态，v1.1）
- 学习模式（v1.1）
- 自动评分卡导出 PDF（serenity_scorecard.py 仅作为内部工具调用，输出嵌在报告里，不单独导出）
- 任何交易决策、下单建议（SKILL.md 明令禁止）

## 4. 架构

**L1（UI 独立）+ L2（业务逻辑独立）**，同 repo 不新建项目。

```
F:\AIProject\TradingAgents\
├── tradingagents\serenity\                    # 新模块，自成体系，不依赖 LangGraph 工作流
│   ├── __init__.py
│   ├── prompts.py                             # 从 SKILL.md 派生的 system prompt 拼装
│   ├── tools.py                               # LangChain Tool 封装：Web 搜索、filings、scorecard
│   ├── workflow.py                            # 单 agent + 9 步 tool loop 主流程
│   ├── schemas.py                             # 输入/输出 pydantic 契约
│   └── scorecard.py                           # serenity_scorecard.py 的 thin wrapper
├── api\
│   └── serenity.py                            # 独立路由 /api/v1/serenity/*
├── uniapp-frontend\src\
│   └── pages\serenity\                        # 独立页面（独立 Tab）
│       ├── index.vue                          # 提交研究请求
│       └── report.vue                         # 渲染报告
└── docs\
    └── spec-serenity-research.md              # 本文件
```

**复用现有基础设施**：LLM client（DashScope / OpenAI / Grok）、Google News / Tavily 搜索、akshare 数据源、config_loader、CORS、UniApp 路由结构。

**不复用**：LangGraph 多代理图、`tradingagents/agents/` 下的分析师/研究员/经理。Serenity 是单 agent + tool loop，完全独立。

## 5. 后端 API 契约

### 5.1 `POST /api/v1/serenity/scan`

提交主题扫描任务。

**请求体**：
```json
{
  "mode": "theme_scan",                  // theme_scan | single_challenge | candidate_compare
  "market": "A-share",                   // A-share | US | HK
  "theme": "AI 半导体",                  // theme_scan 必填
  "tickers": ["600536.SH"],              // single_challenge / candidate_compare 必填
  "time_window_months": 12,              // 可选，默认 12
  "llm_overrides": {                     // 可选，复用现有 llm_provider/deep_think_llm 协议
    "llm_provider": "dashscope",
    "deep_think_llm": "qwen-plus"
  }
}
```

**响应**：
```json
{ "job_id": "ser-xxx", "status": "queued" }
```

### 5.2 `GET /api/v1/serenity/jobs/{job_id}`

轮询研究进度 / 取结果。**复用现有 analyzer.py 的 in-memory job 队列模型**，避免引入新依赖。

**响应**（结构化报告，对应 SKILL.md 的 9 步输出）：
```json
{
  "job_id": "ser-xxx",
  "status": "running | completed | failed",
  "progress": { "step": 5, "total": 9, "stage": "build_company_universe" },
  "result": {
    "scope": { "market": "...", "theme": "...", "time_window": "..." },
    "system_change": "...",                              // 第 2 步
    "value_chain_layers": [                              // 第 3 步
      { "name": "存储互连", "rank": 1, "reason": "..." },
      ...
    ],
    "scarce_layers": [                                   // 第 4 步：被点名的卡点
      { "layer": "...", "why_scarce": "...", "evidence_strength": "strong|medium|weak" }
    ],
    "company_universe": [...],                           // 第 5 步：至少 20 家候选
    "top_priorities": [                                  // 第 7 步：排序后的优先研究清单
      {
        "ticker": "600536.SH",
        "company": "中国软件",
        "constrains_what": "...",                        // 卡住的环节
        "chain_position": "...",                         // 产业链位置
        "rank_reason": "...",                            // 排序原因
        "evidence": [                                    // 证据
          { "claim": "...", "source": "...", "strength": "primary|media|analysis|social" }
        ],
        "main_risk": "...",                              // 主要风险
        "score": { "final": 78.5, "verdict": "High research priority" }  // 来自 scorecard.py
      }
    ],
    "what_could_go_wrong": ["...", "..."],               // 第 8 步：反方理由
    "next_research_moves": ["...", "..."]                // 第 9 步：下一步检查
  },
  "sources_consulted": 27,                               // SKILL.md 要求 ≥ 25
  "candidates_inspected": 23,                            // SKILL.md 要求 ≥ 20
  "trace_log": ["..."]                                   // 工具调用轨迹，便于审计
}
```

### 5.3 `GET /api/v1/serenity/jobs`

列出当前用户的研究历史（v1 暂用 in-memory，重启清空；持久化挪到后续 task）。

## 6. 前端页面契约

**两个页面**，挂在 `pages.json` 的独立 Tab "产业链研究"下：

### 6.1 `pages/serenity/index.vue`（提交页）
- 顶部三个 mode 切换（主题扫描 / 公司挑战 / 候选对比）
- 表单字段动态切换（theme_scan 显示主题输入，其它显示 ticker 输入）
- 提交后跳转到 `report.vue?jobId=xxx`

### 6.2 `pages/serenity/report.vue`（报告页）
- 顶部进度条（9 步可视化）
- 报告区分块渲染（按 SKILL.md 的"卡住的环节 / 产业链位置 / 排序原因 / 证据 / 主要风险"字段）
- 每条证据可点开看原文链接
- 底部"下一步检查清单"加 checkbox（v1 不持久化勾选状态）

UI 风格沿用现有 UniApp 设计 token，不引入新组件库。

## 7. 工作流实现（关键）

**严格按 SKILL.md 第 52-105 行的 9 步执行**：

| 步 | 名称 | 实现方式 |
|---|---|---|
| 1 | Set scope | 直接读请求参数 |
| 2 | Translate story → system change | LLM 单次推理 |
| 3 | Map value chain | LLM 推理 + 可选搜索 |
| 4 | Find scarce layer | LLM 推理 |
| 5 | Build company universe | LLM + Web 搜索 + akshare/SEC tools |
| 6 | Gather and grade evidence | LLM + Web 搜索 + filings tools（≥25 sources）|
| 7 | Rank priorities | LLM + 调 `scorecard.py` 评分 |
| 8 | Explain what could go wrong | LLM 推理 |
| 9 | Give the next research move | LLM 推理 |

**实现形态**：LangChain `create_tool_calling_agent` + tool loop（**不是** LangGraph 多代理图）。System prompt 直接读 SKILL.md 内容拼装。

**Tools 清单（v1）**：
1. `web_search`（复用现有 Google News / Tavily）
2. `get_filings_cn`（akshare 公告/财报，A 股）
3. `get_filings_us`（SEC EDGAR，需要新增；v1 用 sec-edgar-api 库）
4. `get_dragon_tiger_list` / `get_north_bound_holding`（复用刚 commit 的 cn_features_tools）
5. `compute_bottleneck_score`（包 serenity_scorecard.py）

## 8. API / 依赖

| 类别 | 是否新增 | 备注 |
|---|---|---|
| LLM | ❌ 复用 | DashScope / OpenAI / Grok |
| Web 搜索 | ❌ 复用 | Google News + 现有搜索基建 |
| akshare | ❌ 复用 | 已有 |
| SEC EDGAR | ✅ 新增 | 免费、无 key、`sec-edgar-api` PyPI 包 |
| serenity-skill 仓库脚本 | ✅ 引用 | 直接 import 部署到 `~/.claude/skills/serenity-skill/scripts/` 的脚本，或拷贝一份到 `tradingagents/serenity/` 内联 |

**关于 scorecard.py 的引用方式**（决策点）：内联拷贝一份到 `tradingagents/serenity/scorecard.py` 更稳，避免依赖外部 skill 目录的安装位置。

## 9. 验收标准

**v1 完成定义**：
1. 后端 `POST /api/v1/serenity/scan` 接收主题扫描请求，30-120 秒内返回完整报告
2. 报告含 §5.2 全部字段，`top_priorities` ≥ 3 家公司
3. 每个 top priority 含至少 2 条证据 + 至少 1 条 primary source（公告/财报/SEC filing）
4. 前端"产业链研究"Tab 可访问，报告页能渲染上述字段
5. 跑通三个市场各一个真实主题（A 股 AI 半导体 / 美股 AI 算力 / 港股机器人）
6. 不影响现有 TradingAgents 多代理分析的任何接口

**测试覆盖**：
- 单测：`tests/test_serenity_workflow.py`（mock LLM + tools，验证 9 步串联）
- 集成：`scripts/probe_serenity_e2e.py`（真实 LLM + 搜索，跑一次主题扫描）

## 10. 明确不做的事

- 不接入 LangGraph 多代理图
- 不修改 `tradingagents/agents/` 下任何文件
- 不修改现有 `/api/v1/analyze` 接口
- 不导出 PDF / 不做账户操作 / 不持久化研究历史（v1）
- 不做研究伙伴多轮对话（v1）
- 不擅自加 SKILL.md 之外的工作流步骤

## 11. 风险与回滚

- **LLM 调 25+ 源 + 9 步推理** → 单次研究成本高（预估 50-200 K tokens），需要给前端"预估成本"提示
- **回滚策略**：分支隔离，未 merge 前不影响 main；如废弃，删 `tradingagents/serenity/` + `api/serenity.py` + `pages/serenity/` 三处即可

## 12. 下一步

本 spec 通过 review 后，按 `planning-and-task-breakdown` 拆 task，预估 8-12 个原子 task，逐 slice 实现。
