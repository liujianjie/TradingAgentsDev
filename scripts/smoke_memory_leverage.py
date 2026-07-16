"""Manual network smoke test for the memory-leverage data path."""

from __future__ import annotations

import argparse

from tradingagents.quant.memory_leverage import MemoryLeverageService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    report = MemoryLeverageService().get_report(days=args.days)
    print(f"as_of={report['as_of']} generated_at={report['generated_at']}")
    for item in report["series"]:
        latest = item["latest"]
        if latest is None:
            print(f"{item['id']}: unavailable")
            continue
        print(
            f"{item['id']}: ratio={latest['ratio']:.4f} "
            f"underlying_usd={latest['underlying_turnover_usd']:.0f}"
        )
    missing = [row["symbol"] for row in report["coverage"] if row["status"] != "ok"]
    print(f"coverage={len(report['coverage']) - len(missing)}/{len(report['coverage'])}")
    if missing:
        print("missing=" + ",".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
