"""验证 serenity prompts 派生自 SKILL.md 的关键约束没丢。"""
from __future__ import annotations

import pytest

from tradingagents.serenity.prompts import build_system_prompt, build_user_message
from tradingagents.serenity.schemas import Market, ResearchMode


_NINE_STEP_KEYWORDS = [
    "Set scope",
    "system change",
    "value chain",
    "scarce layer",
    "company universe",
    "evidence",
    "Rank priorities",
    "what could go wrong",
    "next research move",
]

_FIVE_FIELDS_CN = [
    "卡住的环节",
    "产业链位置",
    "排序原因",
    "证据",
    "主要风险",
]


@pytest.mark.parametrize("mode", list(ResearchMode))
@pytest.mark.parametrize("market", list(Market))
def test_nine_steps_present(mode, market):
    p = build_system_prompt(mode, market)
    for kw in _NINE_STEP_KEYWORDS:
        assert kw in p, f"9 步关键词 {kw!r} 不在 prompt 里（mode={mode}, market={market}）"


@pytest.mark.parametrize("mode", list(ResearchMode))
def test_five_field_contract(mode):
    p = build_system_prompt(mode, Market.a_share)
    for kw in _FIVE_FIELDS_CN:
        assert kw in p, f"五段式字段 {kw!r} 不在 prompt 里"


def test_output_contract_has_json_schema():
    p = build_system_prompt(ResearchMode.theme_scan, Market.a_share)
    for kw in ["top_priorities", "value_chain_layers", "scarce_layers",
               "company_universe", "what_could_go_wrong", "next_research_moves"]:
        assert kw in p


def test_market_hint_differs():
    """每个 market 的专属源在对应 prompt 中存在；交叉互不包含其专属关键词。"""
    a = build_system_prompt(ResearchMode.theme_scan, Market.a_share)
    us = build_system_prompt(ResearchMode.theme_scan, Market.us)
    hk = build_system_prompt(ResearchMode.theme_scan, Market.hk)
    # A 股专属（不应出现在 US/HK 的 market hint 段；hint 段以 _MARKET_HINTS 区分）
    assert "互动易" in a
    assert "互动易" not in us
    assert "互动易" not in hk
    # US 专属 10-K / 10-Q（这些短语只在 _MARKET_HINTS[US] 里）
    assert "10-K" in us
    assert "10-K" not in a
    assert "10-K" not in hk
    # HK 专属 HKEX
    assert "HKEX" in hk
    assert "HKEX" not in us
    assert "HKEX" not in a


def test_mode_block_differs():
    t = build_system_prompt(ResearchMode.theme_scan, Market.us)
    s = build_system_prompt(ResearchMode.single_challenge, Market.us)
    c = build_system_prompt(ResearchMode.candidate_compare, Market.us)
    assert "主题扫描" in t and "至少 20 家" in t
    assert "单公司挑战" in s
    assert "候选比较" in c


def test_risk_boundary_present():
    p = build_system_prompt(ResearchMode.theme_scan, Market.a_share)
    assert "不下买卖" in p
    assert "MNPI" in p


def test_user_message_theme_scan():
    m = build_user_message(
        ResearchMode.theme_scan,
        Market.a_share,
        theme="AI 半导体",
        time_window_months=18,
    )
    assert "A-share" in m
    assert "18" in m
    assert "AI 半导体" in m
    assert "标的" not in m


def test_user_message_single_challenge():
    m = build_user_message(
        ResearchMode.single_challenge,
        Market.us,
        tickers=["NVDA"],
    )
    assert "NVDA" in m
    assert "标的" in m


def test_primary_source_required():
    """evidence 至少 1 条 primary source 的强约束必须在 prompt 里。"""
    p = build_system_prompt(ResearchMode.theme_scan, Market.a_share)
    assert "primary" in p
    assert "至少 1 条" in p or "至少 2 条" in p
