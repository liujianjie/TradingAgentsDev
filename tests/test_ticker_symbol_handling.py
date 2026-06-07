import unittest

import pytest

from cli.utils import normalize_ticker_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.dataflows.utils import to_yfinance_symbol


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    def test_to_yfinance_symbol_normalizes_hk_leading_zeros(self):
        # 港交所 5 位代码（带前导 0）→ Yahoo 的去前导 0 补足 4 位格式
        self.assertEqual(to_yfinance_symbol("07709.HK"), "7709.HK")
        self.assertEqual(to_yfinance_symbol("00700.HK"), "0700.HK")
        self.assertEqual(to_yfinance_symbol("09988.HK"), "9988.HK")
        # 已是 4 位 / 3 位 → 补足到 4 位
        self.assertEqual(to_yfinance_symbol("0700.HK"), "0700.HK")
        self.assertEqual(to_yfinance_symbol("700.HK"), "0700.HK")
        # strip + 大小写归一
        self.assertEqual(to_yfinance_symbol(" 07709.hk "), "7709.HK")

    def test_to_yfinance_symbol_preserves_non_hk_markets(self):
        # 韩股前导 0 必须保留（000660.KS 是真实代码，动了就 404）
        self.assertEqual(to_yfinance_symbol("000660.KS"), "000660.KS")
        # A股 .SS/.SZ、美股、指数、带横杠代码均原样
        self.assertEqual(to_yfinance_symbol("600519.SS"), "600519.SS")
        self.assertEqual(to_yfinance_symbol("000001.SZ"), "000001.SZ")
        self.assertEqual(to_yfinance_symbol("AAPL"), "AAPL")
        self.assertEqual(to_yfinance_symbol("BRK-B"), "BRK-B")
        self.assertEqual(to_yfinance_symbol("^GSPC"), "^GSPC")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)

    def test_single_get_ticker_no_shadow(self):
        # Regression: cli/main.py had a duplicate get_ticker with an empty
        # questionary prompt (rendered as a bare "?") that shadowed the
        # descriptive one in cli/utils. Keep a single canonical definition.
        import cli.main
        import cli.utils
        self.assertIs(cli.main.get_ticker, cli.utils.get_ticker)


if __name__ == "__main__":
    unittest.main()
