"""serenity workflow 单测：mock LLM/agent，验证 parse + 串联。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tradingagents.serenity.schemas import (
    Market,
    ResearchMode,
    ScanRequest,
    SerenityReport,
)
from tradingagents.serenity.workflow import (
    SerenityWorkflowError,
    parse_report,
    run_serenity_workflow,
)


_VALID_REPORT = {
    "scope": {
        "market": "A-share",
        "theme": "AI 半导体",
        "tickers": None,
        "time_window": "12 个月",
    },
    "system_change": "AI 训练需求拉动存储互连和先进封装产能紧张",
    "value_chain_layers": [
        {"name": "存储互连", "rank": 1, "reason": "HBM 扩产慢、客户认证严"},
        {"name": "先进封装", "rank": 2, "reason": "CoWoS 产能受限"},
    ],
    "scarce_layers": [
        {
            "layer": "HBM",
            "why_scarce": "全球只有 3 家产能",
            "evidence_strength": "strong",
        }
    ],
    "company_universe": [
        {
            "ticker": "688981.SS",
            "company": "中芯国际",
            "chain_position": "代工",
            "classification": "supplies_scarce_layer",
        }
    ],
    "top_priorities": [
        {
            "ticker": "688981.SS",
            "company": "中芯国际",
            "constrains_what": "先进制程产能",
            "chain_position": "代工",
            "rank_reason": "国产替代 + 产能紧张",
            "evidence": [
                {
                    "claim": "Q3 资本开支同比 +35%",
                    "source": "公司公告 2025-10",
                    "strength": "primary",
                },
                {
                    "claim": "联手客户认证多家国产存储",
                    "source": "industry analyst report",
                    "strength": "analysis",
                },
            ],
            "main_risk": "良率不及预期",
            "score": {"final": 78.5, "verdict": "High research priority"},
        }
    ],
    "what_could_go_wrong": ["竞争对手扩产快", "需求疲软"],
    "next_research_moves": ["盯下季度产能利用率", "查客户认证清单"],
}


def test_parse_report_pure_json():
    text = json.dumps(_VALID_REPORT, ensure_ascii=False)
    r = parse_report(text)
    assert isinstance(r, SerenityReport)
    assert r.scope.theme == "AI 半导体"
    assert len(r.top_priorities) == 1


def test_parse_report_with_markdown_block():
    text = f"```json\n{json.dumps(_VALID_REPORT, ensure_ascii=False)}\n```"
    r = parse_report(text)
    assert r.scope.theme == "AI 半导体"


def test_parse_report_with_prose_before_after():
    text = (
        "好的，按 9 步走完后我的报告如下：\n\n"
        + json.dumps(_VALID_REPORT, ensure_ascii=False)
        + "\n\n以上仅为研究排序，不作交易建议。"
    )
    r = parse_report(text)
    assert r.top_priorities[0].ticker == "688981.SS"


def test_parse_report_empty_raises():
    with pytest.raises(SerenityWorkflowError):
        parse_report("")


def test_parse_report_invalid_schema_raises():
    bad = {"scope": {"market": "A-share", "time_window": "12 月"}}
    with pytest.raises(SerenityWorkflowError):
        parse_report(json.dumps(bad))


def test_parse_report_invalid_json_raises():
    with pytest.raises(SerenityWorkflowError):
        parse_report("这里完全没有 JSON")


def _fake_agent(message_content):
    """构造一个 langgraph-like agent 返回 final AIMessage(content=...)。"""
    from langchain_core.messages import AIMessage

    agent = MagicMock()
    agent.invoke.return_value = {"messages": [AIMessage(content=message_content)]}
    return agent


def test_workflow_happy_with_injected_llm():
    req = ScanRequest(
        mode=ResearchMode.theme_scan, market=Market.a_share, theme="AI 半导体"
    )
    fake_agent = _fake_agent(json.dumps(_VALID_REPORT, ensure_ascii=False))

    with patch(
        "tradingagents.serenity.workflow._build_agent", return_value=fake_agent
    ):
        progress_calls = []
        trace_lines = []
        report, sources = run_serenity_workflow(
            req,
            llm=MagicMock(),
            tools=[],
            progress_cb=lambda step, stage: progress_calls.append((step, stage)),
            trace_cb=lambda s: trace_lines.append(s),
        )
    assert isinstance(report, SerenityReport)
    assert report.scope.theme == "AI 半导体"
    assert any(p[0] == 1 for p in progress_calls)
    assert any(p[0] == 9 for p in progress_calls)


def test_workflow_propagates_parse_error():
    req = ScanRequest(
        mode=ResearchMode.theme_scan, market=Market.a_share, theme="AI 半导体"
    )
    bad_agent = _fake_agent("随便编一个不是 JSON")
    with patch(
        "tradingagents.serenity.workflow._build_agent", return_value=bad_agent
    ):
        with pytest.raises(SerenityWorkflowError):
            run_serenity_workflow(req, llm=MagicMock(), tools=[])


def test_workflow_wraps_agent_exception():
    req = ScanRequest(
        mode=ResearchMode.single_challenge, market=Market.us, tickers=["NVDA"]
    )
    bomb_agent = MagicMock()
    bomb_agent.invoke.side_effect = RuntimeError("LLM down")
    with patch(
        "tradingagents.serenity.workflow._build_agent", return_value=bomb_agent
    ):
        with pytest.raises(SerenityWorkflowError) as ei:
            run_serenity_workflow(req, llm=MagicMock(), tools=[])
        assert "agent loop 执行失败" in str(ei.value)


def test_workflow_handles_list_output():
    """部分 provider(OpenAI Responses, Gemini 3)返回 content 是 list of blocks。"""
    req = ScanRequest(
        mode=ResearchMode.theme_scan, market=Market.a_share, theme="AI 半导体"
    )
    fake_agent = _fake_agent(
        [
            {"type": "reasoning", "text": "thinking..."},
            {"type": "text", "text": json.dumps(_VALID_REPORT, ensure_ascii=False)},
        ]
    )
    with patch(
        "tradingagents.serenity.workflow._build_agent", return_value=fake_agent
    ):
        report, _ = run_serenity_workflow(req, llm=MagicMock(), tools=[])
    assert report.scope.theme == "AI 半导体"


def test_workflow_empty_messages_raises():
    req = ScanRequest(
        mode=ResearchMode.theme_scan, market=Market.a_share, theme="x"
    )
    empty_agent = MagicMock()
    empty_agent.invoke.return_value = {"messages": []}
    with patch(
        "tradingagents.serenity.workflow._build_agent", return_value=empty_agent
    ):
        with pytest.raises(SerenityWorkflowError) as ei:
            run_serenity_workflow(req, llm=MagicMock(), tools=[])
        assert "空消息列表" in str(ei.value)
