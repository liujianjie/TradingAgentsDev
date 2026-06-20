"""新闻面端到端业务级回归——模拟真实 API 路径跑 ``route_to_vendor('get_news', ...)``.

校验三件事：
  1. **正常路径**：A 股 / 港股 / 美股 ticker 都能拿到真新闻；命中预期的主源（akshare/yfinance）。
  2. **兜底路径**：强制 akshare 失败时，A 股 / 港股是否被 google_news 救场，最坏落到 yfinance。
  3. **极端路径**：主链全部失败时，溯源是否正确显示"无数据 + 降级链"（不静默吞错）。

不需要 LLM、不需要任何 API key（akshare/yfinance/google news 全免费）。建议每次升级
akshare / 改动 ``VENDOR_METHODS["get_news"]`` 后跑一遍，作为"新闻面没坏"的最小回归。

用法：
    python scripts/verify_news_e2e.py

输出：表格 + 退出码 0=全通过 / 1=有 ticker 未拿到数据。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

# 让脚本能直接 `python scripts/verify_news_e2e.py` 跑
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# 真实业务路径设置（参考 api/analyzer.py:105）
def _setup_business_path() -> None:
    """模拟生产 API 入口对 config 的覆盖：data_vendors 全 auto → route 按 ticker 市场选。"""
    from tradingagents.dataflows.config import set_config
    set_config({
        "data_vendors": {
            "core_stock_apis": "auto",
            "technical_indicators": "auto",
            "fundamental_data": "auto",
            "news_data": "auto",
        }
    })


_TICKERS = [
    ("A股 茅台",       "600519.SS", "akshare"),
    ("A股 平安银行",   "000001.SZ", "akshare"),
    ("A股 比亚迪",     "002594.SZ", "akshare"),
    ("A股 寒武纪",     "688256.SS", "akshare"),
    ("港股 腾讯",      "0700.HK",   "akshare"),
    ("港股 阿里港股",  "09988.HK",  "akshare"),
    ("港股 美团",      "03690.HK",  "akshare"),
    ("港股 海力士ETP", "07709.HK",  "akshare"),
    ("美股 AAPL",      "AAPL",      "yfinance"),
    ("美股 GOOGL",     "GOOGL",     "yfinance"),
    ("美股 NVDA",      "NVDA",      "yfinance"),
]


def _run_main_path() -> int:
    """正常路径：用真实业务配置跑每个 ticker。返回未达预期的数量。"""
    from tradingagents.dataflows.interface import (
        route_to_vendor, reset_provenance, get_provenance,
    )

    print()
    print("=" * 110)
    print("【1/3】正常路径 — vendor=auto，所有源真实可用")
    print("=" * 110)
    print(f"{'标的':<25} {'耗时':>7}  {'实际命中':<14} {'预期':<10}  {'长度':>6}  {'判定':<6}")
    print("-" * 110)

    failures = 0
    for label, ticker, expected in _TICKERS:
        reset_provenance()
        t0 = time.time()
        try:
            out = route_to_vendor("get_news", ticker, "2026-06-12", "2026-06-19")
            elapsed = time.time() - t0
            recs = [r for r in get_provenance() if r["category"] == "个股新闻"]
            served = recs[-1]["served_by"] if recs else "—"
            data_len = len(out) if isinstance(out, str) else 0
            ok = served == expected and data_len >= 500
            mark = "[OK]  " if ok else "[FAIL]"
            if not ok:
                failures += 1
            print(f"{label + ' ' + ticker:<25} {elapsed:>6.1f}s  {served or '无':<14} "
                  f"{expected:<10}  {data_len:>6}  {mark}")
        except Exception as e:
            failures += 1
            print(f"{label + ' ' + ticker:<25} ERROR: {type(e).__name__}: {str(e)[:80]}")
    return failures


def _run_fallback_path() -> int:
    """兜底路径：强制 akshare 失败，验证 A 股 / 港股能否被 google_news 救场。"""
    from tradingagents.dataflows import interface as iface

    print()
    print("=" * 110)
    print("【2/3】兜底路径 — akshare 强制失败，验证 google_news 救场（A股 / 港股）")
    print("=" * 110)
    print(f"{'标的':<20} {'耗时':>7}  {'命中':<14} {'降级':<24}  {'长度':>6}  {'判定':<6}")
    print("-" * 110)

    def _boom(*_a, **_kw):
        raise Exception("forced akshare failure")

    failures = 0
    cases = [
        ("A股 茅台",    "600519.SS"),
        ("A股 比亚迪",  "002594.SZ"),
        ("港股 腾讯",   "0700.HK"),
        ("港股 海力士", "07709.HK"),
    ]
    for label, ticker in cases:
        iface.reset_provenance()
        t0 = time.time()
        try:
            with patch.dict(iface.VENDOR_METHODS["get_news"], {"akshare": _boom}):
                out = iface.route_to_vendor("get_news", ticker, "2026-06-12", "2026-06-19")
            elapsed = time.time() - t0
            recs = [r for r in iface.get_provenance() if r["category"] == "个股新闻"]
            served = recs[-1]["served_by"] if recs else "—"
            deg = ",".join(recs[-1]["degraded"]) if recs else "—"
            data_len = len(out) if isinstance(out, str) else 0
            # 兜底成功 = google_news 命中 + 有内容；落到 yfinance 也算通过但是次优
            ok = data_len >= 500 and served in ("google_news", "yfinance")
            mark = "[OK]  " if ok else "[FAIL]"
            if not ok:
                failures += 1
            print(f"{label + ' ' + ticker:<20} {elapsed:>6.1f}s  {served:<14} {deg:<24}  "
                  f"{data_len:>6}  {mark}")
        except Exception as e:
            failures += 1
            print(f"{label + ' ' + ticker:<20} ERROR: {type(e).__name__}: {str(e)[:80]}")
    return failures


def _run_extreme_path() -> int:
    """极端路径：所有源失败，验证溯源正确记"无数据 + 全降级"，且不静默吞错。"""
    from tradingagents.dataflows import interface as iface

    print()
    print("=" * 110)
    print("【3/3】极端路径 — 所有源失败，验证溯源正确记降级、不静默吞错")
    print("=" * 110)

    def _boom(*_a, **_kw):
        raise Exception("forced failure")

    failures = 0
    iface.reset_provenance()
    with patch.dict(
        iface.VENDOR_METHODS["get_news"],
        {"akshare": _boom, "google_news": _boom, "yfinance": _boom, "alpha_vantage": _boom},
    ):
        try:
            iface.route_to_vendor("get_news", "600519.SS", "2026-06-12", "2026-06-19")
            print("[FAIL] 全部源失败时本该抛 RuntimeError，结果返回了值（静默吞错风险）")
            failures += 1
        except RuntimeError as e:
            recs = [r for r in iface.get_provenance() if r["category"] == "个股新闻"]
            served = recs[-1]["served_by"] if recs else None
            deg = sorted(recs[-1]["degraded"]) if recs else []
            print(f"  raise RuntimeError: {str(e)[:80]}...")
            print(f"  溯源 served_by={served} (期望 None)")
            print(f"  溯源 degraded={deg} (期望含 akshare / google_news / yfinance / alpha_vantage)")
            ok = (
                served is None
                and {"akshare", "google_news", "yfinance"}.issubset(set(deg))
            )
            print(f"  -> {'[OK] (异常正确抛出 + 溯源完整)' if ok else '[FAIL]'}")
            if not ok:
                failures += 1
        except Exception as e:
            failures += 1
            print(f"[FAIL] 期望 RuntimeError，实际 {type(e).__name__}: {e}")
    return failures


def main() -> int:
    _setup_business_path()
    f1 = _run_main_path()
    f2 = _run_fallback_path()
    f3 = _run_extreme_path()
    total = f1 + f2 + f3

    print()
    print("=" * 110)
    print(f"汇总：正常路径失败 {f1} / 兜底路径失败 {f2} / 极端路径失败 {f3}  → 总失败 {total}")
    print("=" * 110)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
