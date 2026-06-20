"""单测 — chinese_sentiment fetcher 系列.

策略：
- 真实网络测试（marker=integration）少量覆盖关键路径（茅台/腾讯），保证联调能跑通；
- mock 测试（marker=unit）覆盖：非目标市场返回 None / cache 命中 / 异常 graceful-degrade /
  防 look-ahead 过滤。

可以用 ``pytest tests/test_chinese_sentiment.py -v -m "not integration"`` 跳过网络测试。
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents.dataflows import chinese_sentiment as cs


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def test_to_em_rank_symbol_a_share():
    assert cs._to_em_rank_symbol("600519.SS") == "SH600519"
    assert cs._to_em_rank_symbol("000001.SZ") == "SZ000001"


def test_to_em_rank_symbol_hk():
    assert cs._to_em_rank_symbol("0700.HK") == "00700"
    assert cs._to_em_rank_symbol("7709.HK") == "07709"


# ---------------------------------------------------------------------------
# fetch_cn_comment
# ---------------------------------------------------------------------------
def test_cn_comment_returns_none_for_us():
    """非 A 股市场直接返回 None，不打 akshare。"""
    assert cs.fetch_cn_comment("AAPL") is None
    assert cs.fetch_cn_comment("0700.HK") is None


def test_cn_comment_returns_none_when_akshare_fails():
    """全市场快照取数失败时返回 None，不抛栈。"""
    cs._reset_comment_cache_for_tests()
    with patch.object(cs, "_get_cached_comment_df", return_value=None):
        assert cs.fetch_cn_comment("600519.SS") is None


def test_cn_comment_returns_none_when_ticker_not_in_market():
    """全市场表里没有目标 ticker → None（例如新上市 / 退市标的）。"""
    cs._reset_comment_cache_for_tests()
    fake_df = pd.DataFrame({
        "代码": ["000001", "000002"],
        "名称": ["平安银行", "万科A"],
        "综合得分": [60.0, 55.0],
        "机构参与度": [0.5, 0.4],
        "关注指数": [80.0, 70.0],
        "上升": [1, -1],
        "目前排名": [100, 200],
        "最新价": [10.0, 8.0],
        "涨跌幅": [1.0, -0.5],
        "换手率": [0.3, 0.4],
        "主力成本": [9.5, 7.8],
        "交易日": ["2026-06-18", "2026-06-18"],
    })
    with patch.object(cs, "_get_cached_comment_df", return_value=fake_df):
        assert cs.fetch_cn_comment("600519.SS") is None


def test_cn_comment_formats_real_row():
    cs._reset_comment_cache_for_tests()
    fake_df = pd.DataFrame({
        "代码": ["600519"],
        "名称": ["贵州茅台"],
        "综合得分": [69.13757],
        "机构参与度": [0.534536],
        "关注指数": [93.6],
        "上升": [8],
        "目前排名": [495],
        "最新价": [1215.0],
        "涨跌幅": [-2.02],
        "换手率": [0.46],
        "主力成本": [1230.0],
        "交易日": ["2026-06-18"],
    })
    with patch.object(cs, "_get_cached_comment_df", return_value=fake_df):
        out = cs.fetch_cn_comment("600519.SS", curr_date="2026-06-19")
    assert out is not None
    assert "贵州茅台" in out
    assert "综合得分" in out
    assert "69.13757" in out
    assert "目前排名" in out
    assert "495" in out


def test_cn_comment_look_ahead_filter():
    """交易日 > curr_date 时丢弃 → None（防回测穿越）。"""
    cs._reset_comment_cache_for_tests()
    fake_df = pd.DataFrame({
        "代码": ["600519"], "名称": ["贵州茅台"], "综合得分": [69.0],
        "机构参与度": [0.5], "关注指数": [93.0], "上升": [0], "目前排名": [495],
        "最新价": [1200.0], "涨跌幅": [0.0], "换手率": [0.3], "主力成本": [1200.0],
        "交易日": ["2026-06-18"],
    })
    with patch.object(cs, "_get_cached_comment_df", return_value=fake_df):
        # 当前日期是 6-17，6-18 的数据是"未来"
        assert cs.fetch_cn_comment("600519.SS", curr_date="2026-06-17") is None


# ---------------------------------------------------------------------------
# fetch_cn_hot_trend
# ---------------------------------------------------------------------------
def test_cn_hot_trend_returns_none_for_us_and_hk():
    assert cs.fetch_cn_hot_trend("AAPL") is None
    assert cs.fetch_cn_hot_trend("0700.HK") is None


def test_cn_hot_trend_formats_table():
    """正常路径：返回包含趋势摘要 + markdown 表格的字符串。"""
    fake_df = pd.DataFrame({
        "时间": pd.date_range("2026-05-01", periods=20, freq="D").strftime("%Y-%m-%d"),
        "排名": list(range(100, 80, -1)),     # 排名从 100 提升到 81（热度上升）
        "证券代码": ["SH600519"] * 20,
        "新晋粉丝": [0.4] * 20,
        "铁杆粉丝": [0.6] * 20,
    })
    with patch("akshare.stock_hot_rank_detail_em", return_value=fake_df):
        out = cs.fetch_cn_hot_trend("600519.SS", curr_date="2026-06-19", days=10)
    assert out is not None
    assert "排名走势" in out
    assert "热度上升" in out


def test_cn_hot_trend_look_ahead():
    """所有数据时间 > curr_date 时丢弃 → None。"""
    fake_df = pd.DataFrame({
        "时间": ["2026-06-20", "2026-06-21"],
        "排名": [100, 99],
        "证券代码": ["SH600519"] * 2,
        "新晋粉丝": [0.4, 0.4],
        "铁杆粉丝": [0.6, 0.6],
    })
    with patch("akshare.stock_hot_rank_detail_em", return_value=fake_df):
        assert cs.fetch_cn_hot_trend("600519.SS", curr_date="2026-06-19") is None


# ---------------------------------------------------------------------------
# fetch_cn_hot_keyword
# ---------------------------------------------------------------------------
def test_cn_hot_keyword_returns_none_for_non_a():
    assert cs.fetch_cn_hot_keyword("AAPL") is None
    assert cs.fetch_cn_hot_keyword("0700.HK") is None


def test_cn_hot_keyword_formats():
    fake_df = pd.DataFrame({
        "时间": ["2026-06-19 23:00:00"] * 3,
        "股票代码": ["SH600519"] * 3,
        "概念名称": ["白酒", "电商概念", "茅指数"],
        "概念代码": ["BK0896", "BK0665", "BK0999"],
        "热度": [11862, 436, 115],
    })
    with patch("akshare.stock_hot_keyword_em", return_value=fake_df):
        out = cs.fetch_cn_hot_keyword("600519.SS", curr_date="2026-06-20")
    assert out is not None
    assert "白酒" in out
    assert "11862" in out


# ---------------------------------------------------------------------------
# fetch_hk_hot_trend
# ---------------------------------------------------------------------------
def test_hk_hot_trend_returns_none_for_non_hk():
    assert cs.fetch_hk_hot_trend("AAPL") is None
    assert cs.fetch_hk_hot_trend("600519.SS") is None


def test_hk_hot_trend_formats():
    fake_df = pd.DataFrame({
        "时间": ["2026-06-19 09:00:00", "2026-06-19 14:00:00"],
        "排名": [5, 1],
    })
    with patch("akshare.stock_hk_hot_rank_detail_realtime_em", return_value=fake_df):
        out = cs.fetch_hk_hot_trend("0700.HK", curr_date="2026-06-20")
    assert out is not None
    assert "热度上升" in out
    assert "0700.HK" in out.upper()


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
def test_comment_cache_hit_avoids_second_call():
    """命中 5 分钟内的 cache → 第二次调用不打 akshare。"""
    cs._reset_comment_cache_for_tests()
    fake_df = pd.DataFrame({
        "代码": ["600519"], "名称": ["贵州茅台"], "综合得分": [69.0],
        "机构参与度": [0.5], "关注指数": [93.0], "上升": [0], "目前排名": [495],
        "最新价": [1200.0], "涨跌幅": [0.0], "换手率": [0.3], "主力成本": [1200.0],
        "交易日": ["2026-06-18"],
    })

    call_count = {"n": 0}

    def _fake_call():
        call_count["n"] += 1
        return fake_df

    import akshare as ak
    with patch.object(ak, "stock_comment_em", side_effect=_fake_call):
        df1 = cs._get_cached_comment_df()
        df2 = cs._get_cached_comment_df()
    assert df1 is fake_df
    assert df2 is fake_df
    assert call_count["n"] == 1  # 第二次走 cache


# ---------------------------------------------------------------------------
# Integration（真实网络）
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_real_cn_comment_maotai():
    cs._reset_comment_cache_for_tests()
    out = cs.fetch_cn_comment("600519.SS")
    assert out is not None
    assert "贵州茅台" in out
    assert "综合得分" in out


@pytest.mark.integration
def test_real_hk_hot_trend_tencent():
    out = cs.fetch_hk_hot_trend("0700.HK")
    assert out is not None
    assert "0700.HK" in out.upper()
