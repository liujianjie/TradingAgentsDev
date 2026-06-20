"""serenity tools 单测：mock 外部网络/akshare/scorecard。"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from tradingagents.serenity.tools import (
    SERENITY_TOOLS,
    compute_bottleneck_score,
    get_filings_cn,
    get_filings_us,
    web_search,
)


def test_tools_registered():
    names = {t.name for t in SERENITY_TOOLS}
    assert names == {
        "web_search",
        "get_filings_cn",
        "get_filings_us",
        "get_dragon_tiger_list",
        "get_north_bound_holding",
        "compute_bottleneck_score",
    }


# ---- web_search ---------------------------------------------------------

_FAKE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>NVIDIA Q3 earnings beat</title>
      <link>https://example.com/a</link>
      <pubDate>Mon, 20 Jun 2026 12:00:00 GMT</pubDate>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>Another headline</title>
      <link>https://example.com/b</link>
      <pubDate>Sun, 19 Jun 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _fake_resp(text="", status=200, json_data=None):
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.json = lambda: (json_data or {})
    return m


def test_web_search_happy():
    with patch("tradingagents.serenity.tools.requests.get", return_value=_fake_resp(_FAKE_RSS)):
        out = web_search.invoke({"query": "AI 半导体", "lang": "zh", "max_items": 5})
    assert "NVIDIA Q3 earnings beat" in out
    assert "Reuters" in out
    assert "https://example.com/a" in out
    assert "AI 半导体" in out


def test_web_search_http_fail():
    with patch("tradingagents.serenity.tools.requests.get", return_value=_fake_resp(status=503)):
        out = web_search.invoke({"query": "x"})
    assert "[web_search 失败]" in out
    assert "503" in out


def test_web_search_empty_items():
    empty_rss = "<rss><channel></channel></rss>"
    with patch("tradingagents.serenity.tools.requests.get", return_value=_fake_resp(empty_rss)):
        out = web_search.invoke({"query": "x"})
    assert "无结果" in out


def test_web_search_network_exception():
    import requests

    with patch(
        "tradingagents.serenity.tools.requests.get",
        side_effect=requests.ConnectionError("dns fail"),
    ):
        out = web_search.invoke({"query": "x"})
    assert "[web_search 失败]" in out
    assert "ConnectionError" in out


def test_web_search_clamps_max_items():
    """max_items > 20 应被 clamp 到 20，避免误传 1000 烧资源。"""
    with patch("tradingagents.serenity.tools.requests.get", return_value=_fake_resp(_FAKE_RSS)) as m:
        web_search.invoke({"query": "x", "max_items": 9999})
    assert m.called


# ---- get_filings_cn ------------------------------------------------------

def test_get_filings_cn_non_a_share_returns_na():
    out = get_filings_cn.invoke({"ticker": "NVDA"})
    assert "n/a" in out
    assert "非 A 股" in out


def test_get_filings_cn_akshare_failure_does_not_raise():
    with patch("tradingagents.dataflows.akshare_utils.market_of", return_value="cn_a"):
        # akshare 包导入失败模拟（实际是模拟 stock_notice_report 抛栈）
        import sys
        fake_ak = MagicMock()
        fake_ak.stock_notice_report.side_effect = RuntimeError("akshare down")
        with patch.dict(sys.modules, {"akshare": fake_ak}):
            out = get_filings_cn.invoke({"ticker": "600519.SS"})
    assert "[get_filings_cn 失败]" in out
    assert "RuntimeError" in out


def test_get_filings_cn_empty_df():
    import pandas as pd
    with patch("tradingagents.dataflows.akshare_utils.market_of", return_value="cn_a"):
        import sys
        fake_ak = MagicMock()
        fake_ak.stock_notice_report.return_value = pd.DataFrame()
        with patch.dict(sys.modules, {"akshare": fake_ak}):
            out = get_filings_cn.invoke({"ticker": "600519.SS"})
    assert "[get_filings_cn 无数据]" in out


def test_get_filings_cn_filters_by_ticker():
    import pandas as pd
    df = pd.DataFrame({
        "代码": ["600519", "000001", "600519"],
        "标题": ["茅台公告A", "招行公告", "茅台扩产"],
    })
    with patch("tradingagents.dataflows.akshare_utils.market_of", return_value="cn_a"):
        import sys
        fake_ak = MagicMock()
        fake_ak.stock_notice_report.return_value = df
        with patch.dict(sys.modules, {"akshare": fake_ak}):
            out = get_filings_cn.invoke({"ticker": "600519.SS"})
    assert "茅台公告A" in out
    assert "茅台扩产" in out
    assert "招行公告" not in out


# ---- get_filings_us ------------------------------------------------------

_FAKE_EDGAR = {
    "hits": {
        "hits": [
            {
                "_id": "0001045810-25-000067:abc",
                "_source": {
                    "form": "10-K",
                    "display_names": ["NVIDIA CORP (NVDA)"],
                    "file_date": "2025-02-21",
                    "ciks": ["0001045810"],
                },
            },
            {
                "_id": "0001045810-25-000099:xyz",
                "_source": {
                    "form": "10-Q",
                    "display_names": ["NVIDIA CORP (NVDA)"],
                    "file_date": "2025-05-15",
                    "ciks": ["0001045810"],
                },
            },
        ]
    }
}


def test_get_filings_us_happy():
    with patch(
        "tradingagents.serenity.tools.requests.get",
        return_value=_fake_resp(json_data=_FAKE_EDGAR),
    ):
        out = get_filings_us.invoke({"ticker_or_query": "NVDA", "forms": "10-K,10-Q"})
    assert "NVIDIA CORP" in out
    assert "10-K" in out
    assert "10-Q" in out
    assert "2025-02-21" in out
    assert "sec.gov" in out


def test_get_filings_us_empty():
    with patch(
        "tradingagents.serenity.tools.requests.get",
        return_value=_fake_resp(json_data={"hits": {"hits": []}}),
    ):
        out = get_filings_us.invoke({"ticker_or_query": "NONESTOCK"})
    assert "无结果" in out


def test_get_filings_us_http_fail():
    with patch("tradingagents.serenity.tools.requests.get", return_value=_fake_resp(status=429)):
        out = get_filings_us.invoke({"ticker_or_query": "NVDA"})
    assert "[get_filings_us 失败]" in out
    assert "429" in out


# ---- compute_bottleneck_score -------------------------------------------

def test_scorecard_happy():
    payload = json.dumps({
        "ticker": "NVDA",
        "company": "NVIDIA",
        "market": "US",
        "factors": {
            "demand_inflection": 5,
            "architecture_coupling": 4,
            "chokepoint_severity": 5,
            "supplier_concentration": 4,
            "expansion_difficulty": 5,
            "evidence_quality": 5,
            "valuation_disconnect": 2,
            "catalyst_timing": 4,
        },
        "penalties": {
            "dilution_financing": 0,
            "governance": 1,
            "geopolitics": 3,
            "liquidity": 0,
            "hype_risk": 2,
            "accounting_quality": 0,
            "cyclicality": 1,
            "alternative_design_risk": 1,
        },
    })
    out = compute_bottleneck_score.invoke({"payload_json": payload})
    data = json.loads(out)
    assert data["ticker"] == "NVDA"
    assert 0 <= data["final_score"] <= 100
    assert data["verdict"] in {
        "Top research priority",
        "High research priority",
        "Worth tracking",
        "Early lead or low priority",
    }


def test_scorecard_invalid_json():
    out = compute_bottleneck_score.invoke({"payload_json": "not json {"})
    assert "失败" in out


def test_scorecard_out_of_range():
    payload = json.dumps({
        "ticker": "X",
        "factors": {"demand_inflection": 99},
        "penalties": {},
    })
    out = compute_bottleneck_score.invoke({"payload_json": payload})
    assert "校验失败" in out or "失败" in out
