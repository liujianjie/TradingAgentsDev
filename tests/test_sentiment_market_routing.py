"""单测 — sentiment_analyst 按市场分流 + 各市场 prompt 装配。

不测整条 langgraph 节点（需要 mock LLM + state），只测每市场 ``_build_*_system_message``
函数的核心契约：
- 调用了哪些 fetcher
- system_message 是否包含市场专属的关键段（千股千评 / 港股热度 / Reddit 等）
- 任一 fetcher 失败时是否注入 ``<unavailable>`` 占位串 + 写溯源
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tradingagents.agents.analysts import sentiment_analyst as sa
from tradingagents.dataflows import interface as iface


@pytest.fixture(autouse=True)
def _reset_provenance():
    """每个测试前清空溯源记录，测试后清掉避免污染。"""
    iface.reset_provenance()
    yield
    iface.reset_provenance()


# ---------------------------------------------------------------------------
# US path — keep behaviour
# ---------------------------------------------------------------------------
def test_us_path_calls_stocktwits_and_reddit():
    """US ticker 走原 3 路：news + StockTwits + Reddit。"""
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_stocktwits_messages") as m_st, \
         patch.object(sa, "fetch_reddit_posts") as m_rd:
        m_news.func = lambda t, s, e: "## US news block"
        m_st.return_value = "## StockTwits messages (bullish 30, bearish 5)"
        m_rd.return_value = "## Reddit posts"

        msg = sa._build_us_system_message("AAPL", "2026-06-12", "2026-06-19")

    assert "StockTwits" in msg
    assert "Reddit" in msg
    assert "<start_of_stocktwits>" in msg
    assert "<start_of_reddit>" in msg
    # US 模板不应混入 CN/HK 的专属段
    assert "千股千评" not in msg
    assert "港股实时热度" not in msg
    m_st.assert_called_once()
    m_rd.assert_called_once()


def test_us_path_records_provenance_when_both_social_ok():
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_stocktwits_messages") as m_st, \
         patch.object(sa, "fetch_reddit_posts") as m_rd:
        m_news.func = lambda t, s, e: "news"
        m_st.return_value = "real stocktwits messages here"
        m_rd.return_value = "real reddit posts here"
        sa._build_us_system_message("AAPL", "2026-06-12", "2026-06-19")

    recs = [r for r in iface.get_provenance() if r["category"] == "社交情感"]
    assert len(recs) == 1
    assert recs[0]["served_by"] is not None
    assert "StockTwits" in recs[0]["served_by"]
    assert "Reddit" in recs[0]["served_by"]


def test_us_path_records_degraded_when_social_unavailable():
    """StockTwits/Reddit 返回 <...> 占位串 → 走降级分支，溯源 note 说明非美股社区。"""
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_stocktwits_messages") as m_st, \
         patch.object(sa, "fetch_reddit_posts") as m_rd:
        m_news.func = lambda t, s, e: "news"
        m_st.return_value = "<no messages found>"
        m_rd.return_value = "<no posts found>"
        sa._build_us_system_message("AAPL", "2026-06-12", "2026-06-19")

    recs = [r for r in iface.get_provenance() if r["category"] == "社交情感"]
    assert recs[0]["served_by"] is None
    assert "StockTwits" in recs[0]["degraded"]
    assert "Reddit" in recs[0]["degraded"]


# ---------------------------------------------------------------------------
# A 股 path — News + 千股千评 + 热度时序 + 所属概念热度
# ---------------------------------------------------------------------------
def test_cn_path_calls_chinese_fetchers():
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_cn_comment") as m_c, \
         patch.object(sa, "fetch_cn_hot_trend") as m_t, \
         patch.object(sa, "fetch_cn_hot_keyword") as m_k:
        m_news.func = lambda t, s, e: "## A股 news block"
        m_c.return_value = "## 千股千评 — 贵州茅台\n- 综合得分: 69"
        m_t.return_value = "## 热度时序\n- 排名走势: 100 → 80"
        m_k.return_value = "## 概念热度\n白酒 11862"
        msg = sa._build_cn_system_message("600519.SS", "2026-06-12", "2026-06-19")

    m_c.assert_called_once_with("600519.SS", "2026-06-19")
    m_t.assert_called_once_with("600519.SS", "2026-06-19")
    m_k.assert_called_once_with("600519.SS", "2026-06-19")
    assert "千股千评" in msg
    assert "<start_of_em_comment>" in msg
    assert "<start_of_hot_trend>" in msg
    assert "<start_of_concept_heat>" in msg
    # CN 模板不应混入 StockTwits / Reddit
    assert "StockTwits" not in msg
    assert "Reddit" not in msg


def test_cn_path_injects_unavailable_when_fetcher_returns_none():
    """任一 fetcher 返回 None → 注入 <unavailable: 千股千评> 等占位串 + 走降级溯源。"""
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_cn_comment", return_value=None), \
         patch.object(sa, "fetch_cn_hot_trend", return_value="trend ok"), \
         patch.object(sa, "fetch_cn_hot_keyword", return_value=None):
        m_news.func = lambda t, s, e: "news"
        msg = sa._build_cn_system_message("600519.SS", "2026-06-12", "2026-06-19")

    assert "<unavailable: 千股千评>" in msg
    assert "<unavailable: 所属概念热度>" in msg
    assert "trend ok" in msg
    recs = [r for r in iface.get_provenance() if r["category"] == "中文情感"]
    assert recs[0]["served_by"] == "热度时序"
    assert "千股千评" in recs[0]["degraded"]
    assert "所属概念热度" in recs[0]["degraded"]


def test_cn_path_all_fetchers_fail_logs_all_degraded():
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_cn_comment", return_value=None), \
         patch.object(sa, "fetch_cn_hot_trend", return_value=None), \
         patch.object(sa, "fetch_cn_hot_keyword", return_value=None):
        m_news.func = lambda t, s, e: "news"
        sa._build_cn_system_message("600519.SS", "2026-06-12", "2026-06-19")
    recs = [r for r in iface.get_provenance() if r["category"] == "中文情感"]
    assert recs[0]["served_by"] is None
    assert set(recs[0]["degraded"]) == {"千股千评", "热度时序", "所属概念热度"}
    assert "全部不可用" in recs[0]["note"]


# ---------------------------------------------------------------------------
# 港股 path — News + 港股热度时序
# ---------------------------------------------------------------------------
def test_hk_path_calls_hk_fetchers():
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_hk_hot_trend") as m_t:
        m_news.func = lambda t, s, e: "## HK news block"
        m_t.return_value = "## 港股热度时序\n- 排名走势: 5 → 1"
        msg = sa._build_hk_system_message("0700.HK", "2026-06-12", "2026-06-19")

    m_t.assert_called_once_with("0700.HK", "2026-06-19")
    assert "港股实时热度" in msg
    assert "<start_of_hk_hot_trend>" in msg
    # HK 模板不应混入 A 股 / 美股专属**数据块**（可以教育性提及术语，但不应有数据块标签）。
    assert "<start_of_em_comment>" not in msg
    assert "<start_of_stocktwits>" not in msg
    assert "<start_of_reddit>" not in msg


def test_hk_path_injects_unavailable_when_trend_fails():
    with patch.object(sa, "get_news") as m_news, \
         patch.object(sa, "fetch_hk_hot_trend", return_value=None):
        m_news.func = lambda t, s, e: "news"
        msg = sa._build_hk_system_message("0700.HK", "2026-06-12", "2026-06-19")
    assert "<unavailable: 港股热度时序>" in msg
    recs = [r for r in iface.get_provenance() if r["category"] == "中文情感"]
    assert recs[0]["served_by"] is None
    assert "港股热度时序" in recs[0]["degraded"]
