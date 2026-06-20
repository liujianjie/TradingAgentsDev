"""情感面候选数据源连通性 probe。

在本机（含 TUN 全局代理）环境下，对 A 股 / 港股情感面 7 个候选源各跑一次真实请求，
输出每源的可用性 / 耗时 / 数据量 / 失败原因，作为 sentiment_analyst 多源聚合接入前
的"先看哪个能用"依据。**只读、不修改任何项目状态**，可重复跑。

候选源（与上游讨论已收敛到 3-5 主流，这里含已接入的复用项一并探活）：
  A 股
    1. 东财个股新闻        akshare stock_news_em（已接入，复用打分）
    2. 东财千股千评        akshare stock_comment_em（量化情绪 + 主力参与度）
    3. 东财热度排名        akshare stock_hot_rank_detail_em（个股热度时序）
    4. 雪球热门帖          akshare stock_hot_tweet_xq（akshare 已封装绕反爬）
    5. Google News 中文    news.google.com/rss/search
  港股
    6. akshare 港股新闻    akshare stock_news_em（已接入，复用打分）
    7. 港股实时热度        akshare stock_hk_hot_rank_detail_realtime_em
    8. Google News 中英搜  news.google.com/rss/search

注：首版 probe 测的 stock_guba_em / 直连雪球均失败（接口不存在 / 反爬命中），改用
akshare 的等价封装（stock_comment_em + stock_hot_tweet_xq）— 这是 probe 的价值所在。

用法：
  python scripts/probe_sentiment_sources.py
  python scripts/probe_sentiment_sources.py --cn 600519.SS --hk 0700.HK --timeout 8

输出：
  reports/sentiment_probe/<YYYYMMDD_HHMMSS>/
    report.md          # Markdown 总览表
    <source>.sample.txt  # 每源前若干条原始返回（人工核验数据形状）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# 让脚本能直接 `python scripts/probe_xxx.py` 跑（不强制 pip install -e .）
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class ProbeResult:
    name: str
    market: str               # "A" / "HK" / "共用"
    ok: bool = False
    elapsed_s: float = 0.0
    count: int = 0
    sample: str = ""           # 前几条文本，写入单独文件
    error: str = ""            # 失败原因（前 200 字）
    note: str = ""             # 额外备注（反爬命中 / 需 cookie / 走代理 等）


def _timed(fn: Callable[[], Any]) -> tuple[Any, float, Exception | None]:
    t0 = time.time()
    try:
        return fn(), time.time() - t0, None
    except Exception as e:  # noqa: BLE001 — probe 要把所有异常抓回去汇总
        return None, time.time() - t0, e


# ---------------------------------------------------------------------------
# probe akshare 系（个股新闻 / 千股千评 / 热度 / 雪球封装）
# ---------------------------------------------------------------------------
def _probe_akshare_call(
    name: str, market_label: str, symbol: str, fn_label: str,
    fn: Callable[[Any], Any], note: str = "",
) -> ProbeResult:
    """通用 akshare 接口 probe：调用 + 抓异常 + 截首 5 行样本。"""
    res = ProbeResult(name=f"{name} ({symbol})", market=market_label, note=note)
    try:
        from tradingagents.dataflows.akshare_utils import _akshare_retry
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    df, elapsed, err = _timed(lambda: _akshare_retry(lambda: fn(symbol)))
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if df is None or len(df) == 0:
        res.error = "返回空 DataFrame"
        return res

    res.ok = True
    res.count = len(df)
    head = df.head(5).to_string(max_cols=10, max_colwidth=80)
    res.sample = f"接口: {fn_label}\n列: {list(df.columns)}\n\n{head}"
    return res


def probe_akshare_news(symbol: str, market_label: str, timeout: int) -> ProbeResult:
    """东财个股新闻（akshare stock_news_em）。已在主链路使用，这里复测确认在 probe 环境下也通。"""
    res = ProbeResult(name=f"东财个股新闻 stock_news_em ({symbol})", market=market_label)
    try:
        from tradingagents.dataflows.akshare_utils import to_akshare_symbol, _akshare_retry
        import akshare as ak
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    ak_sym = to_akshare_symbol(symbol)
    df, elapsed, err = _timed(lambda: _akshare_retry(lambda: ak.stock_news_em(symbol=ak_sym)))
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if df is None or len(df) == 0:
        res.error = "返回空 DataFrame"
        return res

    res.ok = True
    res.count = len(df)
    head = df.head(5).to_string(max_cols=8, max_colwidth=80)
    res.sample = f"列: {list(df.columns)}\n\n{head}"
    res.note = "主链路已使用；此处用于对比股吧 / 雪球的连通性基线"
    return res


# ---------------------------------------------------------------------------
# ticker → 东财股票排名接口的 symbol 格式（SH600519 / SZ000001 / 00700）
# ---------------------------------------------------------------------------
def _to_em_rank_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.endswith(".SS"):
        return "SH" + t[:-3]
    if t.endswith(".SZ"):
        return "SZ" + t[:-3]
    if t.endswith(".HK"):
        return t[:-3].zfill(5)
    return t


def probe_em_comment(symbol: str, market_label: str, timeout: int) -> ProbeResult:
    """东财千股千评（akshare stock_comment_em，全市场快照，按 ticker 过滤）。

    返回字段含「市场参与意愿 / 综合得分 / 上升 / 关注指数 / 主力成本」等量化指标，
    是 A 股最直接的「情感+主力情绪」结构化源。无参，返回 5000+ 行需自行过滤。"""
    res = ProbeResult(name=f"东财千股千评 stock_comment_em ({symbol})", market=market_label)
    if market_label != "A":
        res.error = "仅 A 股覆盖（接口为 A 股市场快照）"
        return res
    try:
        import akshare as ak
        from tradingagents.dataflows.akshare_utils import _akshare_retry, to_akshare_symbol
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    df, elapsed, err = _timed(lambda: _akshare_retry(lambda: ak.stock_comment_em()))
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if df is None or len(df) == 0:
        res.error = "返回空 DataFrame"
        return res

    # 按代码列过滤
    code = to_akshare_symbol(symbol)
    code_col = next((c for c in df.columns if "代码" in str(c)), None)
    if not code_col:
        res.error = f"找不到代码列（列: {list(df.columns)[:10]}）"
        return res
    row = df[df[code_col].astype(str).str.zfill(6) == code]
    if row.empty:
        res.error = f"全市场 {len(df)} 行中无 {code}"
        res.note = f"代码列: {code_col}；首 5 个代码示例: {df[code_col].astype(str).head(5).tolist()}"
        return res

    res.ok = True
    res.count = 1
    res.sample = (
        f"全市场行数: {len(df)} / 列: {list(df.columns)}\n\n"
        + row.to_string(max_cols=12, max_colwidth=60)
    )
    res.note = "全市场快照，运行期需 cache 整张表，按 ticker 抽行"
    return res


def probe_em_hot_rank_detail(symbol: str, market_label: str, timeout: int) -> ProbeResult:
    """东财个股热度时序（akshare stock_hot_rank_detail_em，A 股；港股用专用接口）。"""
    is_hk = market_label == "HK"
    name_label = "港股热度时序 stock_hk_hot_rank_detail_realtime_em" if is_hk else "东财热度时序 stock_hot_rank_detail_em"
    res = ProbeResult(name=f"{name_label} ({symbol})", market=market_label)
    try:
        import akshare as ak
        from tradingagents.dataflows.akshare_utils import _akshare_retry
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    em_sym = _to_em_rank_symbol(symbol)
    fn = ak.stock_hk_hot_rank_detail_realtime_em if is_hk else ak.stock_hot_rank_detail_em
    df, elapsed, err = _timed(lambda: _akshare_retry(lambda: fn(symbol=em_sym)))
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if df is None or len(df) == 0:
        res.error = "返回空 DataFrame"
        return res

    res.ok = True
    res.count = len(df)
    res.sample = f"列: {list(df.columns)}\n\n{df.head(5).to_string(max_cols=10, max_colwidth=80)}"
    return res


def probe_em_hot_keyword(symbol: str, market_label: str, timeout: int) -> ProbeResult:
    """东财个股热门关键词（akshare stock_hot_keyword_em，A 股）。"""
    res = ProbeResult(name=f"东财热门关键词 stock_hot_keyword_em ({symbol})", market=market_label)
    if market_label != "A":
        res.error = "仅 A 股覆盖"
        return res
    try:
        import akshare as ak
        from tradingagents.dataflows.akshare_utils import _akshare_retry
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    em_sym = _to_em_rank_symbol(symbol)
    df, elapsed, err = _timed(lambda: _akshare_retry(lambda: ak.stock_hot_keyword_em(symbol=em_sym)))
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if df is None or len(df) == 0:
        res.error = "返回空 DataFrame"
        return res

    res.ok = True
    res.count = len(df)
    res.sample = f"列: {list(df.columns)}\n\n{df.head(5).to_string(max_cols=10, max_colwidth=80)}"
    return res


def probe_xq_hot_tweet(_ignored: str, market_label: str, timeout: int) -> ProbeResult:
    """雪球热门帖排行榜（akshare stock_hot_tweet_xq，全市场，非个股）。

    返回当周/本周新增的雪球热门股，作为「市场关注度」信号——本标的是否在榜上即一项情绪特征。
    symbol 取值: '本周新增' / '最热门'。"""
    res = ProbeResult(name="雪球热门股排行 stock_hot_tweet_xq (全市场)", market=market_label)
    try:
        import akshare as ak
        from tradingagents.dataflows.akshare_utils import _akshare_retry
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    df, elapsed, err = _timed(
        lambda: _akshare_retry(lambda: ak.stock_hot_tweet_xq(symbol="最热门"))
    )
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if df is None or len(df) == 0:
        res.error = "返回空 DataFrame"
        return res

    res.ok = True
    res.count = len(df)
    res.sample = f"列: {list(df.columns)}\n\n{df.head(10).to_string(max_cols=10, max_colwidth=80)}"
    res.note = "全市场排行榜（非个股）；运行期用于判断本标的是否上榜作为热度信号"
    return res


# ---------------------------------------------------------------------------
# probe 4 + 7：Google News（中文 / 中英双搜）
# ---------------------------------------------------------------------------
def probe_google_news(query: str, hl: str, market_label: str, timeout: int) -> ProbeResult:
    """Google News RSS 搜索。

    端点：https://news.google.com/rss/search?q=<query>&hl=<hl>&gl=<country>
    走 RSS 不用 API key、不走 JS；TUN 全局代理下应可通。"""
    res = ProbeResult(name=f"Google News RSS (q={query!r}, hl={hl})", market=market_label)
    try:
        import requests
        from xml.etree import ElementTree as ET
    except ImportError as e:
        res.error = f"import 失败: {e}"
        return res

    gl = "CN" if hl.startswith("zh") else "US"
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"}

    def _call():
        return requests.get(
            url,
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
        )

    r, elapsed, err = _timed(_call)
    res.elapsed_s = elapsed
    if err is not None:
        res.error = f"{type(err).__name__}: {str(err)[:200]}"
        return res
    if r.status_code != 200:
        res.error = f"HTTP {r.status_code}"
        return res

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        res.error = f"XML 解析失败: {e}"
        return res

    items = root.findall(".//item")
    if not items:
        res.error = "RSS 无 item"
        return res

    res.ok = True
    res.count = len(items)
    lines = []
    for it in items[:5]:
        title = (it.findtext("title") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        src = (src_el.text or "").strip() if src_el is not None else ""
        lines.append(f"[{pub}] ({src}) {title}")
    res.sample = "\n".join(lines)
    return res


# ---------------------------------------------------------------------------
# 汇总输出
# ---------------------------------------------------------------------------
def render_report(results: list[ProbeResult], cn: str, hk: str) -> str:
    """生成 Markdown 总览表。"""
    lines = [
        "# 情感面候选源 probe 报告",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 测试 ticker: A股 `{cn}` / 港股 `{hk}`",
        "- 环境: 本机 (TUN 全局代理已开启)",
        "",
        "## 总览",
        "",
        "| # | 源 | 市场 | 状态 | 耗时 | 数据量 | 失败/备注 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        status = "✅ 可用" if r.ok else "❌ 不可用"
        note = r.error if not r.ok else (r.note or "—")
        # 表格转义
        note = note.replace("|", "\\|").replace("\n", " ")[:150]
        lines.append(
            f"| {i} | {r.name} | {r.market} | {status} | {r.elapsed_s:.2f}s | {r.count} | {note} |"
        )
    lines += [
        "",
        "## 接入建议",
        "",
        "- ✅ 标记为可用的源进入正式接入清单。",
        "- ❌ 反爬命中 / 需 cookie 维护的源标注在最终 sentiment_aggregator 的 fallback note 里，",
        "  让运行期溯源表 (`record_provenance`) 显示\"环境不支持\"，不强行硬接。",
        "",
        "## 每源原始样本",
        "",
        "（详见同目录 `<source>.sample.txt`）",
    ]
    return "\n".join(lines)


def _slug(name: str) -> str:
    """文件名安全化。"""
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    return "".join(c if c in keep else "_" for c in name).strip("_")[:80]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cn", default="600519.SS", help="A 股测试 ticker (默认 600519.SS 贵州茅台)")
    ap.add_argument("--hk", default="0700.HK", help="港股测试 ticker (默认 0700.HK 腾讯)")
    ap.add_argument("--timeout", type=int, default=8, help="单次请求超时秒 (默认 8)")
    args = ap.parse_args()

    print(f"[probe] CN={args.cn}  HK={args.hk}  timeout={args.timeout}s")
    print()

    results: list[ProbeResult] = []

    # A 股个股级源
    a_probes = [
        (probe_akshare_news, "东财个股新闻"),
        (probe_em_comment, "东财千股千评"),
        (probe_em_hot_rank_detail, "东财热度时序"),
        (probe_em_hot_keyword, "东财热门关键词"),
    ]
    for fn, label in a_probes:
        print(f"  → {label} (A) ...", end=" ", flush=True)
        r = fn(args.cn, "A", args.timeout)
        results.append(r)
        print("OK" if r.ok else f"FAIL ({r.error[:60]})")

    print(f"  → Google News 中文 (A) ...", end=" ", flush=True)
    r = probe_google_news(f"{args.cn} 股票", "zh-CN", "A", args.timeout)
    results.append(r)
    print("OK" if r.ok else f"FAIL ({r.error[:60]})")

    # 港股
    hk_probes = [
        (probe_akshare_news, "东财港股新闻"),
        (probe_em_hot_rank_detail, "港股热度时序"),
    ]
    for fn, label in hk_probes:
        print(f"  → {label} (HK) ...", end=" ", flush=True)
        r = fn(args.hk, "HK", args.timeout)
        results.append(r)
        print("OK" if r.ok else f"FAIL ({r.error[:60]})")

    print(f"  → Google News 中英 (HK) ...", end=" ", flush=True)
    r = probe_google_news(f"{args.hk} stock", "zh-CN", "HK", args.timeout)
    results.append(r)
    print("OK" if r.ok else f"FAIL ({r.error[:60]})")

    # 全市场情绪信号
    print(f"  → 雪球热门股排行 (全市场) ...", end=" ", flush=True)
    r = probe_xq_hot_tweet("", "共用", args.timeout)
    results.append(r)
    print("OK" if r.ok else f"FAIL ({r.error[:60]})")

    # 落盘
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _REPO_ROOT / "reports" / "sentiment_probe" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "report.md").write_text(render_report(results, args.cn, args.hk), encoding="utf-8")
    for r in results:
        fname = _slug(r.name) + ".sample.txt"
        content = f"# {r.name}\n# market={r.market} ok={r.ok} elapsed={r.elapsed_s:.2f}s count={r.count}\n"
        content += f"# error={r.error}\n# note={r.note}\n\n{r.sample}\n"
        (out_dir / fname).write_text(content, encoding="utf-8")

    print()
    print(f"[probe] 报告: {out_dir / 'report.md'}")
    ok_count = sum(1 for r in results if r.ok)
    print(f"[probe] 可用 {ok_count}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
