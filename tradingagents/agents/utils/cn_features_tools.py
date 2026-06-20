"""LangChain tool wrappers for A 股特色数据（北向资金 / 龙虎榜）.

仅 A 股有意义；其他市场会返回 ``n/a`` 占位串而不是抛栈，让 LLM 看到时自然跳过该节，
避免 tool 报错打断 graph。供 ``fundamentals_analyst`` 作为附加工具暴露。
"""

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.akshare_cn_features import (
    get_dragon_tiger_list as _get_dragon_tiger_list,
    get_north_bound_holding as _get_north_bound_holding,
)


@tool
def get_north_bound_holding(
    ticker: Annotated[str, "ticker symbol (only A-share '600519.SS' / '000001.SZ' is meaningful)"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """A-share 北向资金（沪深港通陆股通持仓）近期 30 个交易日时序汇总。

    境外机构对该股的持仓变化反映"聪明钱"动向：持仓占比上升 + 区间累计净流入正 = 北向看多；
    反之净流出 = 北向减仓。仅 A 股有数据；港股 / 美股 / 其他市场会返回明确的 n/a 占位串。

    Args:
        ticker: Ticker symbol (only A-share is meaningful, e.g. '600519.SS').
        curr_date: Current date you are trading at, yyyy-mm-dd.
    Returns:
        Markdown formatted block describing recent foreign-investor holding trend.
    """
    return _get_north_bound_holding(ticker, curr_date)


@tool
def get_dragon_tiger_list(
    ticker: Annotated[str, "ticker symbol (only A-share is meaningful)"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """A-share 龙虎榜近一月上榜统计：是否上榜、上榜次数、累计买卖、机构席位、净买额。

    龙虎榜是 A 股交易所披露的"异常交易"席位数据，反映游资 / 机构短线博弈强度。
    上榜次数多 + 机构净买入 = 多头主力布局；游资为主则短线波动加大。未上榜本身也是有效信号
    （短线主力不活跃）。仅 A 股有数据；其他市场返回 n/a 占位串。

    Args:
        ticker: Ticker symbol.
        curr_date: Current date you are trading at, yyyy-mm-dd.
    Returns:
        Markdown formatted block describing dragon-tiger-list activity.
    """
    return _get_dragon_tiger_list(ticker, curr_date)
