"""单测 — google_news fetcher + route_to_vendor 链上 fallback.

策略：
- mock requests 覆盖 happy path / 404 / 网络错 / RSS 解析失败 / 全部超时 end_date
- integration: 真实跑一次（标 marker，方便 CI 跳过）
- route_to_vendor 集成：A 股链 mock akshare 失败 → 应命中 google_news
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pytest

from tradingagents.dataflows import google_news as gn
from tradingagents.dataflows import interface as iface


def _fake_rss_response(items: list[dict]) -> MagicMock:
    """构造一个 RSS XML 响应（带 item 列表的 mock requests.Response）。"""
    root = ET.Element("rss")
    channel = ET.SubElement(root, "channel")
    for it in items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = it.get("title", "")
        ET.SubElement(item, "link").text = it.get("link", "")
        ET.SubElement(item, "pubDate").text = it.get("pubDate", "")
        ET.SubElement(item, "description").text = it.get("description", "")
        if "source" in it:
            ET.SubElement(item, "source").text = it["source"]
    xml = ET.tostring(root, encoding="unicode")
    resp = MagicMock()
    resp.status_code = 200
    resp.text = xml
    return resp


# ---------------------------------------------------------------------------
# query 参数
# ---------------------------------------------------------------------------
def test_query_params_a_share():
    q, hl, gl = gn._ticker_query_params("600519.SS")
    assert "600519" in q
    assert "股票" in q
    assert hl == "zh-CN"
    assert gl == "CN"


def test_query_params_hk():
    q, hl, gl = gn._ticker_query_params("0700.HK")
    assert "700" in q
    assert "港股" in q
    assert hl == "zh-CN"
    assert gl == "HK"


def test_query_params_us():
    q, hl, gl = gn._ticker_query_params("AAPL")
    assert "AAPL" in q
    assert hl == "en"
    assert gl == "US"


# ---------------------------------------------------------------------------
# 主路径
# ---------------------------------------------------------------------------
def test_happy_path_returns_formatted_block():
    resp = _fake_rss_response([
        {
            "title": "茅台一季报营收增 15%",
            "link": "http://example.com/news1",
            "pubDate": "Mon, 15 Jun 2026 12:00:00 GMT",
            "description": "<a href=\"x\">茅台一季报营收增 15%</a> 详细内容...",
            "source": "财联社",
        },
        {
            "title": "白酒板块全线走高",
            "link": "http://example.com/news2",
            "pubDate": "Sun, 14 Jun 2026 06:00:00 GMT",
            "description": "今日白酒板块普涨...",
            "source": "新浪财经",
        },
    ])
    with patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        out = gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")
    assert "茅台一季报营收增 15%" in out
    assert "财联社" in out
    assert "白酒板块全线走高" in out


def test_raises_on_http_error():
    resp = MagicMock()
    resp.status_code = 503
    resp.text = ""
    with patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        with pytest.raises(gn.GoogleNewsUnavailableError):
            gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")


def test_raises_on_network_error():
    import requests as _r
    with patch("tradingagents.dataflows.google_news.requests.get", side_effect=_r.ConnectTimeout("conn timeout")):
        with pytest.raises(gn.GoogleNewsUnavailableError) as exc:
            gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")
        assert "ConnectTimeout" in str(exc.value) or "网络异常" in str(exc.value)


def test_raises_on_empty_rss():
    resp = _fake_rss_response([])
    with patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        with pytest.raises(gn.GoogleNewsUnavailableError):
            gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")


# ---------------------------------------------------------------------------
# 防 look-ahead
# ---------------------------------------------------------------------------
def test_look_ahead_filter_drops_future_items():
    resp = _fake_rss_response([
        {"title": "未来新闻", "pubDate": "Mon, 25 Jun 2026 12:00:00 GMT", "link": "http://x/1"},
        {"title": "过去新闻", "pubDate": "Mon, 15 Jun 2026 12:00:00 GMT", "link": "http://x/2"},
    ])
    with patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        out = gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")
    assert "过去新闻" in out
    assert "未来新闻" not in out


def test_look_ahead_filter_keeps_items_without_pubdate():
    """无 pubDate 的 item 不丢，留给下游 LLM 自行判断（避免静默丢失全部）。"""
    resp = _fake_rss_response([
        {"title": "无日期新闻", "pubDate": "", "link": "http://x/1"},
    ])
    with patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        out = gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")
    assert "无日期新闻" in out


def test_look_ahead_filter_all_future_raises():
    resp = _fake_rss_response([
        {"title": "未来 A", "pubDate": "Mon, 25 Jun 2026 12:00:00 GMT", "link": "http://x/1"},
        {"title": "未来 B", "pubDate": "Tue, 26 Jun 2026 12:00:00 GMT", "link": "http://x/2"},
    ])
    with patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        with pytest.raises(gn.GoogleNewsUnavailableError) as exc:
            gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")
        assert "晚于" in str(exc.value)


# ---------------------------------------------------------------------------
# route_to_vendor 集成
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_provenance():
    iface.reset_provenance()
    yield
    iface.reset_provenance()


@pytest.fixture
def _auto_news_vendor():
    """强制 ``get_news`` 走自动市场链——隔离前序测试污染 config 的副作用。

    项目 conftest 不保证 ``data_vendors`` / ``tool_vendors`` 在每个测试之间复位；
    上游 ``test_dataflows_config`` 等会改 ``tool_vendors.get_news``，留下脏值；
    本 fixture 显式把它复位到 "auto" 让 route_to_vendor 走 ``_auto_vendor_chain``。
    """
    from tradingagents.dataflows.config import get_config
    cfg = get_config()
    saved_tool = cfg.get("tool_vendors", {}).copy()
    saved_cat = cfg.get("data_vendors", {}).copy()
    cfg.setdefault("tool_vendors", {})["get_news"] = "auto"
    cfg.setdefault("data_vendors", {})["news_data"] = "auto"
    yield
    cfg["tool_vendors"] = saved_tool
    cfg["data_vendors"] = saved_cat


def _boom(*_a, **_kw):
    raise Exception("forced failure")


def _stub_news(text: str):
    def _fn(*_a, **_kw):
        return text
    return _fn


def _stub_assert_not_called(*_a, **_kw):
    raise AssertionError("此 vendor 不该被调用")


def test_route_a_share_fallback_to_google_when_akshare_fails(_auto_news_vendor):
    """A 股链：akshare 抛异常 → 应命中 google_news 而不是直接落 yfinance.

    VENDOR_METHODS 字典在 import 时已拷贝函数引用，因此用 ``patch.dict`` 替换字典里
    那一个 entry，而不是 patch interface 模块下的同名属性。``alpha_vantage`` 也要 stub
    掉：conftest 给所有测试设了 ``ALPHA_VANTAGE_API_KEY=placeholder``，没 stub 它会
    真发请求拿到错误响应，被路由当成"非空"误命中。
    """
    resp = _fake_rss_response([
        {"title": "A 股新闻 X", "pubDate": "Mon, 15 Jun 2026 12:00:00 GMT", "link": "http://x"},
    ])
    with patch.dict(
        iface.VENDOR_METHODS["get_news"],
        {"akshare": _boom, "alpha_vantage": _boom, "yfinance": _stub_assert_not_called},
    ), patch("tradingagents.dataflows.google_news.requests.get", return_value=resp):
        out = iface.route_to_vendor("get_news", "600519.SS", "2026-06-12", "2026-06-19")
    assert "A 股新闻 X" in out
    recs = [r for r in iface.get_provenance() if r["category"] == "个股新闻"]
    assert recs[-1]["served_by"] == "google_news"
    assert "akshare" in recs[-1]["degraded"]


def test_route_a_share_falls_through_to_yfinance_when_both_fail(_auto_news_vendor):
    """akshare + google_news 都失败 → 落 yfinance；溯源记两个降级。"""
    with patch.dict(
        iface.VENDOR_METHODS["get_news"],
        {"akshare": _boom, "alpha_vantage": _boom,
         "yfinance": _stub_news("## yfinance for 600519.SS\nrescued")},
    ), patch("tradingagents.dataflows.google_news.requests.get",
             side_effect=Exception("network down")):
        out = iface.route_to_vendor("get_news", "600519.SS", "2026-06-12", "2026-06-19")
    assert "rescued" in out
    recs = [r for r in iface.get_provenance() if r["category"] == "个股新闻"]
    assert recs[-1]["served_by"] == "yfinance"
    assert "akshare" in recs[-1]["degraded"]
    assert "google_news" in recs[-1]["degraded"]


def test_route_us_path_unchanged_no_google_news_call(_auto_news_vendor):
    """美股链路不变：yfinance 命中即返回，google_news 不被调用。"""
    with patch.dict(
        iface.VENDOR_METHODS["get_news"],
        {"yfinance": _stub_news("## yfinance AAPL news\nactive"), "alpha_vantage": _boom},
    ), patch("tradingagents.dataflows.google_news.requests.get",
             side_effect=AssertionError("google_news 不该被调用，美股链应直接命中 yfinance")):
        out = iface.route_to_vendor("get_news", "AAPL", "2026-06-12", "2026-06-19")
    assert "AAPL news" in out
    recs = [r for r in iface.get_provenance() if r["category"] == "个股新闻"]
    assert recs[-1]["served_by"] == "yfinance"


# ---------------------------------------------------------------------------
# Integration（真实网络）
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_real_google_news_a_share():
    out = gn.get_google_news("600519.SS", "2026-06-12", "2026-06-19")
    assert "600519" in out
    assert "###" in out  # 至少有一条新闻
