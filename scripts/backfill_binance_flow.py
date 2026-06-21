#!/usr/bin/env python3
"""Backfill Binance taker-flow data from 1m futures klines."""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from database.connection import SessionLocal  # noqa: E402
from services.exchanges.binance_adapter import BinanceAdapter  # noqa: E402
from services.exchanges.data_persistence import ExchangeDataPersistence  # noqa: E402


def parse_time_ms(value: str, *, end: bool = False) -> int:
    if value.lower() == "now":
        return int(time.time() * 1000)

    raw = value.strip()
    if len(raw) == 10:
        dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def backfill(symbol: str, start_ms: int, end_ms: int, delay: float) -> dict:
    adapter = BinanceAdapter()
    db = SessionLocal()
    persistence = ExchangeDataPersistence(db)
    current_ms = start_ms
    pages = 0
    rows = 0

    try:
        while current_ms <= end_ms:
            klines = adapter.fetch_klines(
                symbol,
                "1m",
                limit=1500,
                start_time=current_ms,
                end_time=end_ms,
            )
            if not klines:
                break

            result = persistence.upsert_taker_volumes_from_klines_bulk(klines)
            pages += 1
            rows += result.get("upserted", 0)

            last_open_ms = klines[-1].timestamp * 1000
            print(
                f"{symbol} page={pages} rows={rows} last={iso(last_open_ms)}",
                flush=True,
            )

            next_ms = last_open_ms + 60_000
            if len(klines) < 1500 or next_ms <= current_ms:
                break
            current_ms = next_ms
            if delay > 0:
                time.sleep(delay)

        return {"symbol": symbol, "pages": pages, "rows": rows, "start": iso(start_ms), "end": iso(end_ms)}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--start", default="2025-06-01")
    parser.add_argument("--end", default="now")
    parser.add_argument("--delay", type=float, default=0.12)
    args = parser.parse_args()

    start_ms = parse_time_ms(args.start)
    end_ms = parse_time_ms(args.end, end=True)
    if start_ms >= end_ms:
        raise SystemExit("--start must be earlier than --end")

    result = backfill(args.symbol.upper(), start_ms, end_ms, args.delay)
    print(result)


if __name__ == "__main__":
    main()
