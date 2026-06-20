"""Serenity e2e probe: 真实 LLM + 真实 tools 跑一次，验证 spec §9 验收。

# 使用方法

前置：
1. Python FastAPI 已不必启动（probe 直接 import workflow，不走 HTTP）。
2. config/apikeys.local.json 已配 active_provider 与 deep_think_model。
3. 网络：Google News + SEC EDGAR + akshare 三类源能通（TUN 全局代理可达）。

跑全部场景：

    python scripts/probe_serenity_e2e.py

只跑某一个：

    python scripts/probe_serenity_e2e.py --label A-share_theme_AI半导体

# 输出

    reports/serenity_probe/<YYYYMMDD_HHMMSS>/
        <label>.json     # SerenityReport 原始 JSON
        <label>.md       # 人读摘要
        summary.json     # 多场景汇总

# 验收（spec §9）

- top_priorities ≥ 3 家
- 每家 evidence ≥ 2 条且 ≥ 1 条 primary source
- company_universe ≥ 20 家（主题扫描）
- 全 case 跑通则 stage C 验收过

# 成本提示

单次约 30-120 秒、50-200K LLM tokens。两场景预算约 4-10 分钟、200-500K tokens。
grok 主力国内延迟较高（见 memory），若 timeout 切到 qwen-plus 重试。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config_loader import load_apikeys  # noqa: E402

load_apikeys()

from tradingagents.serenity.schemas import (  # noqa: E402
    Market,
    ResearchMode,
    ScanRequest,
    SerenityReport,
)
from tradingagents.serenity.workflow import (  # noqa: E402
    SerenityWorkflowError,
    run_serenity_workflow,
)


SCENARIOS: list[tuple[str, ScanRequest]] = [
    (
        "A-share_theme_AI半导体",
        ScanRequest(
            mode=ResearchMode.theme_scan,
            market=Market.a_share,
            theme="A 股 AI 半导体产业链：当前最值得优先研究的方向",
        ),
    ),
    (
        "US_theme_AI算力",
        ScanRequest(
            mode=ResearchMode.theme_scan,
            market=Market.us,
            theme="US AI compute infrastructure: which chokepoints matter most now",
        ),
    ),
]


def acceptance_check(report: SerenityReport) -> List[str]:
    """spec §9 验收。返回未过项；空 = 全过。"""
    failed: list[str] = []
    if len(report.top_priorities) < 3:
        failed.append(f"top_priorities {len(report.top_priorities)} 家，要求 ≥ 3")
    for p in report.top_priorities:
        if len(p.evidence) < 2:
            failed.append(f"{p.ticker} evidence {len(p.evidence)} 条，要求 ≥ 2")
        if not any(e.strength == "primary" for e in p.evidence):
            failed.append(f"{p.ticker} 缺 primary source")
    if len(report.company_universe) < 20:
        failed.append(
            f"company_universe {len(report.company_universe)} 家，要求 ≥ 20"
        )
    return failed


def render_markdown(label: str, report: SerenityReport, sources: int) -> str:
    lines = [
        f"# Serenity Probe: {label}",
        "",
        f"- 已查源: {sources} 条",
        f"- 候选公司: {len(report.company_universe)} 家",
        f"- 优先研究: {len(report.top_priorities)} 家",
        "",
        "## 研究范围",
        f"- 市场: {report.scope.market}",
        f"- 主题: {report.scope.theme or 'n/a'}",
        f"- 时间窗: {report.scope.time_window}",
        "",
        "## 驱动逻辑（系统变化）",
        report.system_change,
        "",
        "## 产业链层级排序",
    ]
    for layer in report.value_chain_layers:
        lines.append(f"{layer.rank}. **{layer.name}** — {layer.reason}")
    lines.append("\n## 卡住的环节")
    for s in report.scarce_layers:
        lines.append(f"- **{s.layer}** [{s.evidence_strength}] — {s.why_scarce}")
    lines.append("\n## 优先研究清单")
    for p in report.top_priorities:
        lines.append(f"### {p.ticker} · {p.company}")
        if p.score:
            lines.append(f"- 评分: **{p.score.final:.1f}** ({p.score.verdict})")
        lines.append(f"- 卡住的环节: {p.constrains_what}")
        lines.append(f"- 产业链位置: {p.chain_position}")
        lines.append(f"- 排序原因: {p.rank_reason}")
        lines.append(f"- 主要风险: {p.main_risk}")
        lines.append("- 证据:")
        for e in p.evidence:
            lines.append(f"  - [{e.strength}] {e.claim} — {e.source}")
        lines.append("")
    lines.append("## 反方理由 / 最大风险")
    for r in report.what_could_go_wrong:
        lines.append(f"- {r}")
    lines.append("\n## 下一步检查清单")
    for m in report.next_research_moves:
        lines.append(f"- [ ] {m}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--label", help="只跑某个 scenario（默认跑全部）", default=None
    )
    args = parser.parse_args()

    out_dir = ROOT / "reports" / "serenity_probe" / datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: list[dict] = []
    for label, req in SCENARIOS:
        if args.label and args.label != label:
            continue
        print(f"\n==== {label} ====")
        # 每场景独立 trace 列表（不在循环外预声明，避免跨场景串扰）
        case_traces: list[str] = []

        def progress_cb(step: int, stage: str) -> None:
            print(f"  step={step}/9 stage={stage}")

        def trace_cb(line: str, _store=case_traces) -> None:
            _store.append(line)
            print(f"  trace: {line}")

        try:
            report, sources = run_serenity_workflow(
                req, progress_cb=progress_cb, trace_cb=trace_cb
            )
        except SerenityWorkflowError as e:
            print(f"❌ {label} 失败（workflow）: {e}")
            summary.append({"label": label, "status": "failed", "error": str(e)})
            continue
        except Exception as e:
            print(f"❌ {label} 意外: {type(e).__name__}: {e}")
            summary.append(
                {
                    "label": label,
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            continue

        (out_dir / f"{label}.json").write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / f"{label}.md").write_text(
            render_markdown(label, report, sources), encoding="utf-8"
        )

        failed = acceptance_check(report)
        case_summary = {
            "label": label,
            "sources_consulted": sources,
            "candidates_inspected": len(report.company_universe),
            "top_priorities": len(report.top_priorities),
        }
        if failed:
            print(f"⚠ {label} 验收未过:")
            for f in failed:
                print(f"  - {f}")
            case_summary["status"] = "acceptance_failed"
            case_summary["issues"] = failed
        else:
            print(f"✓ {label} 验收通过")
            case_summary["status"] = "passed"
        summary.append(case_summary)

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n输出目录: {out_dir}")
    print(f"汇总: {json.dumps(summary, ensure_ascii=False, indent=2)}")
    return 0 if all(s.get("status") == "passed" for s in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
