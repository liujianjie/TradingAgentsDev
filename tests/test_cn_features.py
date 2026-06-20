"""单测 — akshare_cn_features fetcher（北向资金 / 龙虎榜）+ fundamentals_analyst 集成.

策略：
- mock akshare 返回 fake DataFrame 覆盖 happy / 失败 / 防 look-ahead
- 非 A 股 ticker 返回 n/a 占位串而非抛栈
- fundamentals_analyst tools 列表含新工具
- integration: 真实网络（marker, 跳过时不影响 CI）
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents.dataflows import akshare_cn_features as f
from tradingagents.agents.utils import cn_features_tools as t


# ---------------------------------------------------------------------------
# 非 A 股：返回 n/a 占位串
# ---------------------------------------------------------------------------
def test_north_bound_returns_na_for_hk():
    out = f.get_north_bound_holding("0700.HK")
    assert "n/a" in out
    assert "A 股" in out


def test_north_bound_returns_na_for_us():
    out = f.get_north_bound_holding("AAPL")
    assert "n/a" in out


def test_dragon_tiger_returns_na_for_non_a():
    assert "n/a" in f.get_dragon_tiger_list("AAPL")
    assert "n/a" in f.get_dragon_tiger_list("0700.HK")


# ---------------------------------------------------------------------------
# 北向资金
# ---------------------------------------------------------------------------
def test_north_bound_formats_with_real_data_shape():
    """正常路径：fake DataFrame 对齐 akshare 真实列结构。"""
    fake_df = pd.DataFrame({
        "持股日期": pd.date_range("2026-05-20", periods=20, freq="B").strftime("%Y-%m-%d"),
        "当日收盘价": [1200.0] * 20,
        "当日涨跌幅": [0.5] * 20,
        "持股数量": [80_000_000] * 20,
        "持股市值": [80e9 + i * 1e8 for i in range(20)],
        "持股数量占A股百分比": [6.0 + i * 0.01 for i in range(20)],
        "当日增持股数": [10000] * 20,
        "当日净流入资金": [1e8, -5e7, 2e8] * 6 + [3e8, 4e8],  # 20 个值
        "当日持股市值变化": [1e8] * 20,
    })
    with patch("akshare.stock_hsgt_individual_em", return_value=fake_df):
        out = f.get_north_bound_holding("600519.SS", curr_date="2026-06-19", days=30)
    assert "北向资金" in out
    assert "600519.SS" in out
    assert "持股市值" in out
    assert "区间累计净流入" in out


def test_north_bound_handles_akshare_failure():
    with patch("akshare.stock_hsgt_individual_em",
               side_effect=Exception("connection reset")):
        out = f.get_north_bound_holding("600519.SS")
    assert "暂不可用" in out
    assert "600519.SS" in out


def test_north_bound_look_ahead_filter():
    """所有数据 > curr_date → 输出占位串而非崩。"""
    fake_df = pd.DataFrame({
        "持股日期": ["2026-07-01", "2026-07-02"],
        "持股市值": [1e10, 1.1e10],
        "持股数量占A股百分比": [6.0, 6.1],
        "当日净流入资金": [1e8, 1e8],
    })
    with patch("akshare.stock_hsgt_individual_em", return_value=fake_df):
        out = f.get_north_bound_holding("600519.SS", curr_date="2026-06-19")
    assert "暂无" in out


# ---------------------------------------------------------------------------
# 龙虎榜
# ---------------------------------------------------------------------------
def test_dragon_tiger_formats_when_ticker_on_list():
    fake_df = pd.DataFrame({
        "排名": [1, 2],
        "代码": ["600519", "000001"],
        "名称": ["贵州茅台", "平安银行"],
        "最近上榜日": ["2026-06-15", "2026-06-10"],
        "收盘价": [1200.0, 12.0],
        "涨跌幅": [9.5, 5.0],
        "上榜次数": [3, 1],
        "累计买入额": [5e8, 1e8],
        "累计卖出额": [3e8, 0.5e8],
        "累计成交额": [8e8, 1.5e8],
        "买方机构数": [4, 1],
        "卖方机构数": [2, 0],
        "机构买入净额": [1e8, 5e7],
        "机构买入总额": [3e8, 1e8],
        "近1月涨跌幅": [15.0, 5.0],
        "近3月涨跌幅": [20.0, 10.0],
        "近6月涨跌幅": [25.0, 12.0],
        "近1年涨跌幅": [30.0, 15.0],
    })
    f._reset_lhb_cache_for_tests()
    with patch("akshare.stock_lhb_stock_statistic_em", return_value=fake_df):
        out = f.get_dragon_tiger_list("600519.SS", curr_date="2026-06-19")
    assert "龙虎榜" in out
    assert "上榜次数" in out
    assert "3 次" in out
    assert "贵州茅台" not in out  # 不一定渲染名称，只确保关键统计


def test_dragon_tiger_returns_not_on_list_when_no_match():
    fake_df = pd.DataFrame({
        "代码": ["000001"], "名称": ["平安银行"], "最近上榜日": ["2026-06-15"],
        "上榜次数": [1], "累计买入额": [1e8], "累计卖出额": [5e7],
        "累计成交额": [1.5e8], "买方机构数": [1], "卖方机构数": [0],
        "机构买入净额": [5e7], "近1月涨跌幅": [5.0], "近3月涨跌幅": [10.0], "近6月涨跌幅": [12.0],
    })
    f._reset_lhb_cache_for_tests()
    with patch("akshare.stock_lhb_stock_statistic_em", return_value=fake_df):
        out = f.get_dragon_tiger_list("600519.SS", curr_date="2026-06-19")
    assert "未上龙虎榜" in out
    assert "600519.SS" in out


def test_dragon_tiger_handles_akshare_failure():
    f._reset_lhb_cache_for_tests()
    with patch("akshare.stock_lhb_stock_statistic_em",
               side_effect=Exception("net timeout")):
        out = f.get_dragon_tiger_list("600519.SS")
    assert "暂不可用" in out


def test_dragon_tiger_cache_avoids_second_call():
    f._reset_lhb_cache_for_tests()
    fake_df = pd.DataFrame({
        "代码": ["000001"], "名称": ["平安银行"], "最近上榜日": ["2026-06-15"],
        "上榜次数": [1], "累计买入额": [1e8], "累计卖出额": [5e7],
        "累计成交额": [1.5e8], "买方机构数": [1], "卖方机构数": [0],
        "机构买入净额": [5e7], "近1月涨跌幅": [5.0], "近3月涨跌幅": [10.0], "近6月涨跌幅": [12.0],
    })
    call_count = {"n": 0}

    def _fake(symbol):
        call_count["n"] += 1
        return fake_df

    with patch("akshare.stock_lhb_stock_statistic_em", side_effect=_fake):
        f.get_dragon_tiger_list("600519.SS")
        f.get_dragon_tiger_list("000001.SZ")
    assert call_count["n"] == 1  # 全市场表只取一次


# ---------------------------------------------------------------------------
# fundamentals_analyst 集成
# ---------------------------------------------------------------------------
def test_fundamentals_analyst_tools_include_cn_features():
    """A 股特色 tools 已被注册到 fundamentals_analyst 的 tools 列表。"""
    from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
    from unittest.mock import MagicMock

    captured_tools = []

    class _FakeLLM:
        def bind_tools(self, tools):
            captured_tools.extend(tools)
            return MagicMock(invoke=MagicMock(return_value=MagicMock(tool_calls=[], content="ok")))

    node = create_fundamentals_analyst(_FakeLLM())
    state = {"trade_date": "2026-06-19", "company_of_interest": "600519.SS",
             "messages": [], "instrument_metadata": None}
    try:
        node(state)
    except Exception:
        pass  # 我们只关心 bind_tools 时传的 tools 列表，不关心 invoke 结果

    names = {tool.name for tool in captured_tools}
    assert "get_north_bound_holding" in names
    assert "get_dragon_tiger_list" in names
    assert "get_fundamentals" in names  # 原有 tools 没被删


def test_cn_features_tools_passthrough():
    """LangChain @tool wrapper 用 .func 暴露底层；调用应转发给 dataflows 层。"""
    with patch.object(t, "_get_north_bound_holding", return_value="## stub north"):
        result = t.get_north_bound_holding.func("600519.SS", "2026-06-19")
    assert result == "## stub north"


# ---------------------------------------------------------------------------
# Integration（真实网络）
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_real_north_bound_maotai():
    out = f.get_north_bound_holding("600519.SS")
    assert "北向资金" in out
    # 茅台是沪深港通标的，应有数据
    assert "持股市值" in out or "暂不可用" in out


@pytest.mark.integration
def test_real_lhb_market_snapshot():
    f._reset_lhb_cache_for_tests()
    out = f.get_dragon_tiger_list("600519.SS")
    assert "龙虎榜" in out
