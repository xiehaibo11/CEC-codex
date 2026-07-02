"""Database access and persistence for event-contract backtests."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.event_contract.constants import PERIOD_SECONDS

logger = logging.getLogger(__name__)


class EventContractDataMixin:
    def normalize_symbol(self, symbol: str) -> str:
        value = (symbol or "BTC").upper().strip().replace("/", "")
        for suffix in ("USDT", "USD", "PERP"):
            if value.endswith(suffix) and len(value) > len(suffix):
                value = value[: -len(suffix)]
                break
        return value or "BTC"

    def get_available_symbols(
        self, db: Session, exchange: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        where = ""
        if exchange and exchange != "all":
            where = "WHERE exchange = :exchange"
            params["exchange"] = exchange

        rows = (
            db.execute(
                text(
                    f"""
                SELECT exchange, symbol, period, environment, COUNT(*) AS records,
                       MIN(timestamp) AS earliest_ts, MAX(timestamp) AS latest_ts
                FROM crypto_klines
                {where}
                GROUP BY exchange, symbol, period, environment
                ORDER BY exchange, symbol, period
                """
                ),
                params,
            )
            .mappings()
            .all()
        )

        by_symbol: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for row in rows:
            key = (row["exchange"], row["symbol"], row["environment"])
            entry = by_symbol.setdefault(
                key,
                {
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "environment": row["environment"],
                    "periods": [],
                    "records": 0,
                    "earliest_ts": None,
                    "latest_ts": None,
                },
            )
            entry["periods"].append(row["period"])
            entry["records"] += int(row["records"] or 0)
            if (
                entry["earliest_ts"] is None
                or row["earliest_ts"] < entry["earliest_ts"]
            ):
                entry["earliest_ts"] = row["earliest_ts"]
            if entry["latest_ts"] is None or row["latest_ts"] > entry["latest_ts"]:
                entry["latest_ts"] = row["latest_ts"]

        return list(by_symbol.values())

    def _load_klines(
        self,
        db: Session,
        exchange: str,
        symbol: str,
        period: str,
        start_ts: int,
        end_ts: int,
        environment: str = "mainnet",
        min_bars: int = 0,
    ) -> List[Dict[str, Any]]:
        klines = self._query_klines(
            db, exchange, symbol, period, start_ts, end_ts, environment
        )

        # On-demand backfill: if the local DB has fewer bars than the caller needs
        # (e.g. a fresh DB right after startup), pull the recent window from Binance
        # and re-read. Default min_bars=0 preserves existing callers untouched.
        latest_ts = max((item["timestamp"] for item in klines), default=0)
        interval = PERIOD_SECONDS.get(period, 60)
        requested_bars = max(min_bars, int((end_ts - start_ts) // interval) + 1)
        backfill_limit = min(max(requested_bars + 10, 200), 1500)
        recent_window = (
            end_ts >= int(datetime.now(timezone.utc).timestamp()) - interval * 3
        )
        stale_recent_window = recent_window and latest_ts < end_ts - interval * 2
        recent_gap = recent_window and self._has_kline_gap(
            [
                item
                for item in klines
                if int(item["timestamp"]) >= end_ts - (backfill_limit - 1) * interval
            ],
            interval,
        )
        if (
            (
                min_bars > 0
                and len(klines) < min_bars
                or stale_recent_window
                or recent_gap
            )
            and str(exchange or "").lower() == "binance"
            and environment == "mainnet"
        ):
            self._backfill_recent_binance_klines(
                db, symbol, period, requested_bars, environment
            )
            klines = self._query_klines(
                db, exchange, symbol, period, start_ts, end_ts, environment
            )

        return klines

    def _has_kline_gap(self, klines: List[Dict[str, Any]], interval: int) -> bool:
        timestamps = sorted({int(item["timestamp"]) for item in klines})
        return any(
            cur - prev > interval for prev, cur in zip(timestamps, timestamps[1:])
        )

    def _query_klines(
        self,
        db: Session,
        exchange: str,
        symbol: str,
        period: str,
        start_ts: int,
        end_ts: int,
        environment: str,
    ) -> List[Dict[str, Any]]:
        rows = (
            db.execute(
                text(
                    """
                SELECT timestamp, datetime_str, open_price, high_price, low_price,
                       close_price, volume
                FROM crypto_klines
                WHERE exchange = :exchange
                  AND symbol = :symbol
                  AND period = :period
                  AND environment = :environment
                  AND timestamp BETWEEN :start_ts AND :end_ts
                ORDER BY timestamp
                """
                ),
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "period": period,
                    "environment": environment,
                    "start_ts": int(start_ts),
                    "end_ts": int(end_ts),
                },
            )
            .mappings()
            .all()
        )

        klines = []
        for row in rows:
            try:
                klines.append(
                    {
                        "timestamp": int(row["timestamp"]),
                        "datetime": row["datetime_str"],
                        "open": float(row["open_price"]),
                        "high": float(row["high_price"]),
                        "low": float(row["low_price"]),
                        "close": float(row["close_price"]),
                        "volume": float(row["volume"] or 0),
                    }
                )
            except (TypeError, ValueError):
                continue
        return klines

    def _backfill_recent_binance_klines(
        self,
        db: Session,
        symbol: str,
        period: str,
        min_bars: int,
        environment: str,
    ) -> None:
        """Fetch the most recent ``min_bars`` (+buffer) bars from Binance in a single
        REST request and persist them. Kept intentionally fast for the synchronous
        predict path: one request, no pagination, no long history loop. Failures are
        non-fatal so a backfill error never turns into a 500 -- the caller's existing
        warmup validation still surfaces if data is truly insufficient.
        """
        try:
            from services.exchanges.binance_adapter import BinanceAdapter
            from services.exchanges.data_persistence import ExchangeDataPersistence

            limit = min(max(int(min_bars) + 10, 200), 1500)
            fetched = BinanceAdapter(environment=environment).fetch_klines(
                symbol, period, limit=limit
            )
            if fetched:
                # save_klines() commits internally.
                ExchangeDataPersistence(db).save_klines(
                    fetched, environment=environment
                )
            logger.info(
                "[EventContract] Binance kline backfill %s/%s: fetched %s bars (needed %s)",
                symbol,
                period,
                len(fetched),
                min_bars,
            )
        except Exception as exc:  # noqa: BLE001 - backfill must never be fatal
            logger.warning(
                "[EventContract] Binance kline backfill failed for %s/%s: %s",
                symbol,
                period,
                exc,
            )

    def get_backtest_result(self, db: Session, run_id: int) -> Dict[str, Any]:
        row = (
            db.execute(
                text(
                    """
                SELECT id, symbol, exchange, period, start_time, end_time, config,
                       summary, equity_curve, status, total_trades, win_rate,
                       final_equity, created_at
                FROM event_contract_backtest_runs
                WHERE id = :run_id
                """
                ),
                {"run_id": run_id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ValueError(f"Backtest run {run_id} not found")
        return {
            "run_id": row["id"],
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "period": row["period"],
            "start_time": self._dt_to_iso(row["start_time"]),
            "end_time": self._dt_to_iso(row["end_time"]),
            "config": json.loads(row["config"] or "{}"),
            "summary": json.loads(row["summary"] or "{}"),
            "equity_curve": json.loads(row["equity_curve"] or "[]"),
            "status": row["status"],
            "created_at": self._dt_to_iso(row["created_at"]),
        }

    def get_backtest_response(
        self, db: Session, run_id: int, trade_limit: int = 300
    ) -> Dict[str, Any]:
        result = self.get_backtest_result(db, run_id)
        summary = result.get("summary") or {}
        trades_payload = self.get_trade_logs(db, run_id, limit=trade_limit, offset=0)
        trades = trades_payload.get("trades") or []
        return {
            "run_id": result["run_id"],
            "config": result.get("config") or {},
            "summary": summary,
            "data_quality": summary.get("data_quality"),
            "equity_curve": result.get("equity_curve") or [],
            "trades": trades,
            "trades_returned": len(trades),
            "total_trade_logs": trades_payload.get("total") or len(trades),
            "status": result.get("status"),
        }

    def get_trade_logs(
        self, db: Session, run_id: int, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        limit = min(max(int(limit or 100), 1), 500)
        offset = max(int(offset or 0), 0)
        total = (
            db.execute(
                text(
                    "SELECT COUNT(*) FROM event_contract_trade_logs WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).scalar()
            or 0
        )
        rows = (
            db.execute(
                text(
                    """
                SELECT *
                FROM event_contract_trade_logs
                WHERE run_id = :run_id
                ORDER BY trade_index
                LIMIT :limit OFFSET :offset
                """
                ),
                {"run_id": run_id, "limit": limit, "offset": offset},
            )
            .mappings()
            .all()
        )
        trades = []
        for row in rows:
            trades.append(
                {
                    "id": row["id"],
                    "trade_index": row["trade_index"],
                    "symbol": row["symbol"],
                    "direction": row["direction"],
                    "signal_time": self._dt_to_iso(row.get("signal_time")),
                    "entry_time": self._dt_to_iso(row["entry_time"]),
                    "entry_price": row["entry_price"],
                    "expiry_time": self._dt_to_iso(row["expiry_time"]),
                    "expiry_price": row["expiry_price"],
                    "entry_delay_lag_seconds": row.get("entry_delay_lag_seconds") or 0,
                    "expiry_lag_seconds": row.get("expiry_lag_seconds") or 0,
                    "result": row["result"],
                    "profit_loss": row["profit_loss"],
                    "signal_strength": row["signal_strength"],
                    "ai_consensus_rate": row["ai_consensus_rate"],
                    "consensus_source": row.get("consensus_source"),
                    "ai_participated": row.get("ai_participated") or False,
                    "ai_model": row.get("ai_model"),
                    "ai_account_name": row.get("ai_account_name"),
                    "signal_type": row.get("signal_type"),
                    "event_signal": json.loads(row.get("event_signal") or "{}"),
                    "long_votes": row["long_votes"],
                    "short_votes": row["short_votes"],
                    "hold_votes": row["hold_votes"],
                    "market_state": row["market_state"],
                    "trap_risk": row["trap_risk"],
                    "fake_breakout_risk": row["fake_breakout_risk"],
                    "reason": row["reason"],
                    "factor_snapshot": json.loads(row["factor_snapshot"] or "[]"),
                    "ai_decision_snapshot": json.loads(
                        row["ai_decision_snapshot"] or "[]"
                    ),
                }
            )
        return {
            "run_id": run_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "trades": trades,
        }

    def _persist_backtest(
        self,
        db: Session,
        cfg: Dict[str, Any],
        summary: Dict[str, Any],
        trades: List[Dict[str, Any]],
        equity_curve: List[Dict[str, Any]],
    ) -> int:
        run_status = "partial" if summary.get("partial") else "completed"
        result = db.execute(
            text(
                """
                INSERT INTO event_contract_backtest_runs (
                    symbol, exchange, environment, period, start_time, end_time,
                    config, summary, equity_curve, status, total_trades, win_rate,
                    final_equity, created_at
                ) VALUES (
                    :symbol, :exchange, :environment, :period, :start_time, :end_time,
                    :config, :summary, :equity_curve, :status, :total_trades,
                    :win_rate, :final_equity, CURRENT_TIMESTAMP
                )
                RETURNING id
                """
            ),
            {
                "symbol": cfg["symbol"],
                "exchange": cfg["exchange"],
                "environment": cfg["environment"],
                "period": cfg["period"],
                "start_time": cfg["start_time"].replace(tzinfo=None),
                "end_time": cfg["end_time"].replace(tzinfo=None),
                "config": json.dumps(self._public_config(cfg)),
                "summary": json.dumps(summary),
                "equity_curve": json.dumps(equity_curve),
                "status": run_status,
                "total_trades": summary["total_trades"],
                "win_rate": summary["win_rate"],
                "final_equity": summary["final_equity"],
            },
        )
        run_id = int(result.scalar_one())

        for trade in trades:
            db.execute(
                text(
                    """
                    INSERT INTO event_contract_trade_logs (
                        run_id, trade_index, symbol, direction, entry_time, entry_price,
                        expiry_time, expiry_price, result, profit_loss, signal_strength,
                        ai_consensus_rate, consensus_source, ai_participated,
                        ai_model, ai_account_name, signal_time, signal_type, event_signal,
                        entry_delay_lag_seconds, expiry_lag_seconds, long_votes, short_votes, hold_votes,
                        market_state, trap_risk, fake_breakout_risk, reason,
                        factor_snapshot, ai_decision_snapshot, created_at
                    ) VALUES (
                        :run_id, :trade_index, :symbol, :direction, :entry_time, :entry_price,
                        :expiry_time, :expiry_price, :result, :profit_loss, :signal_strength,
                        :ai_consensus_rate, :consensus_source, :ai_participated,
                        :ai_model, :ai_account_name, :signal_time, :signal_type, :event_signal,
                        :entry_delay_lag_seconds, :expiry_lag_seconds, :long_votes, :short_votes, :hold_votes,
                        :market_state, :trap_risk, :fake_breakout_risk, :reason,
                        :factor_snapshot, :ai_decision_snapshot, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "run_id": run_id,
                    "trade_index": trade["trade_index"],
                    "symbol": trade["symbol"],
                    "direction": trade["direction"],
                    "entry_time": self._parse_datetime(trade["entry_time"]).replace(
                        tzinfo=None
                    ),
                    "entry_price": trade["entry_price"],
                    "expiry_time": self._parse_datetime(trade["expiry_time"]).replace(
                        tzinfo=None
                    ),
                    "expiry_price": trade["expiry_price"],
                    "signal_time": self._parse_datetime(
                        trade.get("signal_time") or trade["entry_time"]
                    ).replace(tzinfo=None),
                    "entry_delay_lag_seconds": trade.get("entry_delay_lag_seconds", 0),
                    "expiry_lag_seconds": trade.get("expiry_lag_seconds", 0),
                    "result": trade["result"],
                    "profit_loss": trade["profit_loss"],
                    "signal_strength": trade["signal_strength"],
                    "ai_consensus_rate": trade["ai_consensus_rate"],
                    "consensus_source": trade.get("consensus_source"),
                    "ai_participated": trade.get("ai_participated", False),
                    "ai_model": trade.get("ai_model"),
                    "ai_account_name": trade.get("ai_account_name"),
                    "signal_type": trade.get("signal_type"),
                    "event_signal": json.dumps(trade.get("event_signal") or {}),
                    "long_votes": trade["long_votes"],
                    "short_votes": trade["short_votes"],
                    "hold_votes": trade["hold_votes"],
                    "market_state": trade["market_state"],
                    "trap_risk": trade["trap_risk"],
                    "fake_breakout_risk": trade["fake_breakout_risk"],
                    "reason": trade["reason"],
                    "factor_snapshot": json.dumps(trade["factor_snapshot"]),
                    "ai_decision_snapshot": json.dumps(trade["ai_decision_snapshot"]),
                },
            )
        db.commit()
        return run_id

    def _public_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in cfg.items():
            if key.startswith("_"):
                continue
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    def _decision_timestamp(self, candle: Dict[str, Any], cfg: Dict[str, Any]) -> int:
        return int(candle["timestamp"]) + PERIOD_SECONDS[cfg["period"]]

    def _expiry_timestamp(
        self, entry_candle: Dict[str, Any], cfg: Dict[str, Any]
    ) -> int:
        return self._decision_timestamp(entry_candle, cfg) + cfg["expiry_minutes"] * 60

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            dt = value
        else:
            text_value = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text_value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _to_iso(self, timestamp_s: int) -> str:
        return (
            datetime.fromtimestamp(int(timestamp_s), tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _dt_to_iso(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return str(value)
