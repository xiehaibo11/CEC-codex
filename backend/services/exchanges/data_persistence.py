"""
Exchange data persistence service.

Handles writing unified exchange data to database tables.
Works with any exchange adapter that produces unified data structures.
"""

import logging
from decimal import Decimal
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.models import (
    MarketTradesAggregated,
    MarketOrderbookSnapshots,
    MarketAssetMetrics,
    MarketSentimentMetrics,
)
from services.exchanges.base_adapter import (
    UnifiedKline,
    UnifiedTrade,
    UnifiedOrderbook,
    UnifiedFunding,
    UnifiedOpenInterest,
    UnifiedSentiment,
)

logger = logging.getLogger(__name__)


class ExchangeDataPersistence:
    """
    Persists unified exchange data to database.

    All data is stored with exchange identifier to support multi-exchange queries.
    """

    def __init__(self, db: Session):
        self.db = db

    def save_klines(
        self,
        klines: List[UnifiedKline],
        environment: str = "mainnet",
    ) -> dict:
        """
        Save K-line data to crypto_klines table.

        Args:
            klines: List of UnifiedKline objects
            environment: "mainnet" or "testnet"

        Returns:
            Dict with inserted and updated counts
        """
        if not klines:
            return {"inserted": 0, "updated": 0, "upserted": 0}

        result = self.upsert_klines_bulk(klines, environment=environment)
        upserted = int(result.get("upserted") or 0)
        logger.info("Saved klines: %s upserted", upserted)
        return {"inserted": 0, "updated": upserted, "upserted": upserted}

    def upsert_klines_bulk(
        self,
        klines: List[UnifiedKline],
        environment: str = "mainnet",
    ) -> dict:
        """Bulk upsert K-line data for large historical backfills."""
        if not klines:
            return {"upserted": 0}

        rows = []
        for kline in klines:
            dt = datetime.fromtimestamp(kline.timestamp, tz=timezone.utc)
            rows.append({
                "exchange": kline.exchange,
                "symbol": kline.symbol,
                "market": "CRYPTO",
                "period": kline.interval,
                "timestamp": kline.timestamp,
                "datetime_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "environment": environment,
                "open_price": kline.open_price,
                "high_price": kline.high_price,
                "low_price": kline.low_price,
                "close_price": kline.close_price,
                "volume": kline.volume,
                "amount": kline.quote_volume,
            })

        self.db.execute(text("""
            INSERT INTO crypto_klines (
                exchange, symbol, market, period, timestamp, datetime_str, environment,
                open_price, high_price, low_price, close_price, volume, amount
            ) VALUES (
                :exchange, :symbol, :market, :period, :timestamp, :datetime_str, :environment,
                :open_price, :high_price, :low_price, :close_price, :volume, :amount
            )
            ON CONFLICT (exchange, symbol, market, period, timestamp, environment)
            DO UPDATE SET
                datetime_str = EXCLUDED.datetime_str,
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount
        """), rows)
        self.db.commit()
        logger.info("Bulk upserted %s klines", len(rows))
        return {"upserted": len(rows)}

    def insert_klines_ignore_conflicts_bulk(
        self,
        klines: List[UnifiedKline],
        environment: str = "mainnet",
    ) -> dict:
        """Bulk insert K-lines without replacing existing exchange-provided rows."""
        if not klines:
            return {"inserted": 0}

        rows = []
        for kline in klines:
            dt = datetime.fromtimestamp(kline.timestamp, tz=timezone.utc)
            rows.append({
                "exchange": kline.exchange,
                "symbol": kline.symbol,
                "market": "CRYPTO",
                "period": kline.interval,
                "timestamp": kline.timestamp,
                "datetime_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "environment": environment,
                "open_price": kline.open_price,
                "high_price": kline.high_price,
                "low_price": kline.low_price,
                "close_price": kline.close_price,
                "volume": kline.volume,
                "amount": kline.quote_volume,
            })

        result = self.db.execute(text("""
            INSERT INTO crypto_klines (
                exchange, symbol, market, period, timestamp, datetime_str, environment,
                open_price, high_price, low_price, close_price, volume, amount
            ) VALUES (
                :exchange, :symbol, :market, :period, :timestamp, :datetime_str, :environment,
                :open_price, :high_price, :low_price, :close_price, :volume, :amount
            )
            ON CONFLICT (exchange, symbol, market, period, timestamp, environment)
            DO NOTHING
        """), rows)
        self.db.commit()
        inserted = int(result.rowcount or 0)
        logger.info("Bulk inserted %s derived klines (ignored %s conflicts)", inserted, len(rows) - inserted)
        return {"inserted": inserted}

    def save_taker_volumes_from_klines(
        self,
        klines: List[UnifiedKline],
    ) -> dict:
        """
        Save taker buy/sell volumes from K-line data to market_trades_aggregated.

        This is used for exchanges like Binance where K-lines include taker volumes,
        eliminating the need for separate trade stream collection.
        """
        inserted = 0
        updated = 0

        for kline in klines:
            if kline.taker_buy_volume is None:
                continue

            # Convert timestamp from seconds to milliseconds
            timestamp_ms = kline.timestamp * 1000

            # Calculate notional if not provided (fallback: volume * close_price)
            taker_buy_notional = kline.taker_buy_notional
            taker_sell_notional = kline.taker_sell_notional
            if taker_buy_notional is None and kline.close_price:
                taker_buy_notional = kline.taker_buy_volume * kline.close_price
            if taker_sell_notional is None and kline.close_price:
                taker_sell_notional = kline.taker_sell_volume * kline.close_price

            existing = self.db.query(MarketTradesAggregated).filter(
                MarketTradesAggregated.exchange == kline.exchange,
                MarketTradesAggregated.symbol == kline.symbol,
                MarketTradesAggregated.timestamp == timestamp_ms,
            ).first()

            if existing:
                existing.taker_buy_volume = kline.taker_buy_volume
                existing.taker_sell_volume = kline.taker_sell_volume
                existing.taker_buy_count = kline.trade_count or 0
                existing.taker_buy_notional = taker_buy_notional or 0
                existing.taker_sell_notional = taker_sell_notional or 0
                existing.high_price = kline.high_price
                existing.low_price = kline.low_price
                updated += 1
            else:
                record = MarketTradesAggregated(
                    exchange=kline.exchange,
                    symbol=kline.symbol,
                    timestamp=timestamp_ms,
                    taker_buy_volume=kline.taker_buy_volume,
                    taker_sell_volume=kline.taker_sell_volume,
                    taker_buy_count=kline.trade_count or 0,
                    taker_sell_count=0,
                    taker_buy_notional=taker_buy_notional or 0,
                    taker_sell_notional=taker_sell_notional or 0,
                    high_price=kline.high_price,
                    low_price=kline.low_price,
                )
                self.db.add(record)
                inserted += 1

        self.db.commit()
        return {"inserted": inserted, "updated": updated}

    def upsert_taker_volumes_from_klines_bulk(
        self,
        klines: List[UnifiedKline],
    ) -> dict:
        """Bulk upsert Binance taker buy/sell volumes into market flow storage."""
        rows = []
        for kline in klines:
            if kline.taker_buy_volume is None:
                continue

            timestamp_ms = kline.timestamp * 1000
            taker_buy_notional = kline.taker_buy_notional
            taker_sell_notional = kline.taker_sell_notional
            if taker_buy_notional is None and kline.close_price:
                taker_buy_notional = kline.taker_buy_volume * kline.close_price
            if taker_sell_notional is None and kline.close_price:
                taker_sell_notional = kline.taker_sell_volume * kline.close_price

            trade_count = kline.trade_count or 0
            total_notional = (taker_buy_notional or Decimal("0")) + (taker_sell_notional or Decimal("0"))
            if trade_count > 0 and total_notional > 0:
                buy_count = int((Decimal(trade_count) * (taker_buy_notional or Decimal("0")) / total_notional).to_integral_value())
                sell_count = max(0, trade_count - buy_count)
            else:
                buy_count = 0
                sell_count = 0

            rows.append({
                "exchange": kline.exchange,
                "symbol": kline.symbol,
                "timestamp": timestamp_ms,
                "taker_buy_volume": kline.taker_buy_volume,
                "taker_sell_volume": kline.taker_sell_volume or Decimal("0"),
                "taker_buy_count": buy_count,
                "taker_sell_count": sell_count,
                "taker_buy_notional": taker_buy_notional or Decimal("0"),
                "taker_sell_notional": taker_sell_notional or Decimal("0"),
                "high_price": kline.high_price,
                "low_price": kline.low_price,
            })

        if not rows:
            return {"upserted": 0}

        self.db.execute(text("""
            INSERT INTO market_trades_aggregated (
                exchange, symbol, timestamp, taker_buy_volume, taker_sell_volume,
                taker_buy_count, taker_sell_count, taker_buy_notional,
                taker_sell_notional, high_price, low_price
            ) VALUES (
                :exchange, :symbol, :timestamp, :taker_buy_volume, :taker_sell_volume,
                :taker_buy_count, :taker_sell_count, :taker_buy_notional,
                :taker_sell_notional, :high_price, :low_price
            )
            ON CONFLICT (exchange, symbol, timestamp)
            DO UPDATE SET
                taker_buy_volume = EXCLUDED.taker_buy_volume,
                taker_sell_volume = EXCLUDED.taker_sell_volume,
                taker_buy_count = EXCLUDED.taker_buy_count,
                taker_sell_count = EXCLUDED.taker_sell_count,
                taker_buy_notional = EXCLUDED.taker_buy_notional,
                taker_sell_notional = EXCLUDED.taker_sell_notional,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price
        """), rows)
        self.db.commit()
        logger.info("Bulk upserted %s taker flow records", len(rows))
        return {"upserted": len(rows)}

    def upsert_taker_trades_bulk(
        self,
        trades: List[UnifiedTrade],
        bucket_seconds: int = 15,
    ) -> dict:
        """Aggregate public trades and upsert taker buy/sell market flow.

        This is used by venues such as HiBT where the public feed exposes recent
        deals instead of Binance-style K-lines with taker split fields.
        """
        if not trades:
            return {"upserted": 0}

        bucket_ms = max(1, int(bucket_seconds)) * 1000
        buckets = {}
        for trade in trades:
            side = str(trade.side or "").lower()
            if side not in {"buy", "sell"}:
                continue
            timestamp_ms = (int(trade.timestamp) // bucket_ms) * bucket_ms
            key = (trade.exchange, trade.symbol, timestamp_ms)
            values = buckets.setdefault(
                key,
                {
                    "exchange": trade.exchange,
                    "symbol": trade.symbol,
                    "timestamp": timestamp_ms,
                    "taker_buy_volume": Decimal("0"),
                    "taker_sell_volume": Decimal("0"),
                    "taker_buy_count": 0,
                    "taker_sell_count": 0,
                    "taker_buy_notional": Decimal("0"),
                    "taker_sell_notional": Decimal("0"),
                    "high_price": trade.price,
                    "low_price": trade.price,
                },
            )

            notional = trade.price * trade.size
            if side == "buy":
                values["taker_buy_volume"] += trade.size
                values["taker_buy_count"] += 1
                values["taker_buy_notional"] += notional
            else:
                values["taker_sell_volume"] += trade.size
                values["taker_sell_count"] += 1
                values["taker_sell_notional"] += notional
            if trade.price > values["high_price"]:
                values["high_price"] = trade.price
            if trade.price < values["low_price"]:
                values["low_price"] = trade.price

        rows = list(buckets.values())
        if not rows:
            return {"upserted": 0}

        self.db.execute(text("""
            INSERT INTO market_trades_aggregated (
                exchange, symbol, timestamp, taker_buy_volume, taker_sell_volume,
                taker_buy_count, taker_sell_count, taker_buy_notional,
                taker_sell_notional, high_price, low_price
            ) VALUES (
                :exchange, :symbol, :timestamp, :taker_buy_volume, :taker_sell_volume,
                :taker_buy_count, :taker_sell_count, :taker_buy_notional,
                :taker_sell_notional, :high_price, :low_price
            )
            ON CONFLICT (exchange, symbol, timestamp)
            DO UPDATE SET
                taker_buy_volume = EXCLUDED.taker_buy_volume,
                taker_sell_volume = EXCLUDED.taker_sell_volume,
                taker_buy_count = EXCLUDED.taker_buy_count,
                taker_sell_count = EXCLUDED.taker_sell_count,
                taker_buy_notional = EXCLUDED.taker_buy_notional,
                taker_sell_notional = EXCLUDED.taker_sell_notional,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price
        """), rows)
        self.db.commit()
        logger.info("Bulk upserted %s taker trade buckets", len(rows))
        return {"upserted": len(rows)}

    def upsert_taker_volume_proxy_from_klines_bulk(
        self,
        klines: List[UnifiedKline],
        bucket_seconds: int = 60,
    ) -> dict:
        """Backfill market-flow coverage from candles when taker split is absent.

        HiBT does not expose historical taker buy/sell volume. This writes a
        neutral 50/50 volume proxy from historical 1m candles so coverage and
        downstream joins have time-aligned rows without inventing a directional
        taker imbalance.
        """
        rows = []
        bucket_ms = max(1, int(bucket_seconds)) * 1000
        for kline in klines:
            timestamp_ms = (int(kline.timestamp) * 1000 // bucket_ms) * bucket_ms
            base_volume = kline.volume or Decimal("0")
            notional = kline.quote_volume or Decimal("0")
            if notional <= 0 and base_volume > 0 and kline.close_price:
                notional = base_volume * kline.close_price
            if base_volume <= 0 and notional <= 0:
                continue

            buy_volume = base_volume / Decimal("2")
            sell_volume = base_volume - buy_volume
            buy_notional = notional / Decimal("2")
            sell_notional = notional - buy_notional
            rows.append({
                "exchange": kline.exchange,
                "symbol": kline.symbol,
                "timestamp": timestamp_ms,
                "taker_buy_volume": buy_volume,
                "taker_sell_volume": sell_volume,
                "taker_buy_count": 1 if buy_notional > 0 else 0,
                "taker_sell_count": 1 if sell_notional > 0 else 0,
                "taker_buy_notional": buy_notional,
                "taker_sell_notional": sell_notional,
                "high_price": kline.high_price,
                "low_price": kline.low_price,
            })

        if not rows:
            return {"upserted": 0}

        self.db.execute(text("""
            INSERT INTO market_trades_aggregated (
                exchange, symbol, timestamp, taker_buy_volume, taker_sell_volume,
                taker_buy_count, taker_sell_count, taker_buy_notional,
                taker_sell_notional, high_price, low_price
            ) VALUES (
                :exchange, :symbol, :timestamp, :taker_buy_volume, :taker_sell_volume,
                :taker_buy_count, :taker_sell_count, :taker_buy_notional,
                :taker_sell_notional, :high_price, :low_price
            )
            ON CONFLICT (exchange, symbol, timestamp)
            DO UPDATE SET
                taker_buy_volume = EXCLUDED.taker_buy_volume,
                taker_sell_volume = EXCLUDED.taker_sell_volume,
                taker_buy_count = EXCLUDED.taker_buy_count,
                taker_sell_count = EXCLUDED.taker_sell_count,
                taker_buy_notional = EXCLUDED.taker_buy_notional,
                taker_sell_notional = EXCLUDED.taker_sell_notional,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price
        """), rows)
        self.db.commit()
        logger.info("Bulk upserted %s taker proxy flow records", len(rows))
        return {"upserted": len(rows)}

    def save_orderbook(self, orderbook: UnifiedOrderbook) -> bool:
        """Save orderbook snapshot to market_orderbook_snapshots table."""
        try:
            existing = self.db.query(MarketOrderbookSnapshots).filter(
                MarketOrderbookSnapshots.exchange == orderbook.exchange,
                MarketOrderbookSnapshots.symbol == orderbook.symbol,
                MarketOrderbookSnapshots.timestamp == orderbook.timestamp,
            ).first()

            if existing:
                existing.best_bid = orderbook.best_bid
                existing.best_ask = orderbook.best_ask
                existing.bid_depth_5 = orderbook.bid_depth_5 or orderbook.bid_depth_sum
                existing.ask_depth_5 = orderbook.ask_depth_5 or orderbook.ask_depth_sum
                existing.bid_depth_10 = orderbook.bid_depth_10 or orderbook.bid_depth_sum
                existing.ask_depth_10 = orderbook.ask_depth_10 or orderbook.ask_depth_sum
                existing.spread = orderbook.spread
                existing.bid_orders_count = orderbook.bid_orders_count or 0
                existing.ask_orders_count = orderbook.ask_orders_count or 0
                existing.raw_levels = orderbook.raw_levels
            else:
                record = MarketOrderbookSnapshots(
                    exchange=orderbook.exchange,
                    symbol=orderbook.symbol,
                    timestamp=orderbook.timestamp,
                    best_bid=orderbook.best_bid,
                    best_ask=orderbook.best_ask,
                    bid_depth_5=orderbook.bid_depth_5 or orderbook.bid_depth_sum,
                    ask_depth_5=orderbook.ask_depth_5 or orderbook.ask_depth_sum,
                    bid_depth_10=orderbook.bid_depth_10 or orderbook.bid_depth_sum,
                    ask_depth_10=orderbook.ask_depth_10 or orderbook.ask_depth_sum,
                    spread=orderbook.spread,
                    bid_orders_count=orderbook.bid_orders_count or 0,
                    ask_orders_count=orderbook.ask_orders_count or 0,
                    raw_levels=orderbook.raw_levels,
                )
                self.db.add(record)

            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save orderbook: {e}")
            self.db.rollback()
            return False

    def save_asset_metrics(
        self,
        symbol: str,
        exchange: str,
        timestamp_ms: int,
        open_interest: Optional[Decimal] = None,
        funding_rate: Optional[Decimal] = None,
        mark_price: Optional[Decimal] = None,
    ) -> bool:
        """Save asset metrics (OI, funding rate) to market_asset_metrics table."""
        try:
            existing = self.db.query(MarketAssetMetrics).filter(
                MarketAssetMetrics.exchange == exchange,
                MarketAssetMetrics.symbol == symbol,
                MarketAssetMetrics.timestamp == timestamp_ms,
            ).first()

            if existing:
                if open_interest is not None:
                    existing.open_interest = open_interest
                if funding_rate is not None:
                    existing.funding_rate = funding_rate
                if mark_price is not None:
                    existing.mark_price = mark_price
            else:
                record = MarketAssetMetrics(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=timestamp_ms,
                    open_interest=open_interest,
                    funding_rate=funding_rate,
                    mark_price=mark_price,
                )
                self.db.add(record)

            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save asset metrics: {e}")
            self.db.rollback()
            return False

    def save_open_interest(self, oi: UnifiedOpenInterest) -> bool:
        """Save open interest data."""
        return self.save_asset_metrics(
            symbol=oi.symbol,
            exchange=oi.exchange,
            timestamp_ms=oi.timestamp,
            open_interest=oi.open_interest,
        )

    def save_funding_rate(self, funding: UnifiedFunding) -> bool:
        """Save funding rate data."""
        return self.save_asset_metrics(
            symbol=funding.symbol,
            exchange=funding.exchange,
            timestamp_ms=funding.timestamp,
            funding_rate=funding.funding_rate,
            mark_price=funding.mark_price,
        )

    def save_open_interest_batch(self, oi_list: List[UnifiedOpenInterest]) -> dict:
        """Save batch of open interest records."""
        inserted = 0
        updated = 0
        for oi in oi_list:
            existing = self.db.query(MarketAssetMetrics).filter(
                MarketAssetMetrics.exchange == oi.exchange,
                MarketAssetMetrics.symbol == oi.symbol,
                MarketAssetMetrics.timestamp == oi.timestamp,
            ).first()

            if existing:
                existing.open_interest = oi.open_interest
                updated += 1
            else:
                record = MarketAssetMetrics(
                    exchange=oi.exchange,
                    symbol=oi.symbol,
                    timestamp=oi.timestamp,
                    open_interest=oi.open_interest,
                )
                self.db.add(record)
                inserted += 1

        self.db.commit()
        return {"inserted": inserted, "updated": updated}

    def save_funding_rate_batch(self, funding_list: List[UnifiedFunding]) -> dict:
        """Save batch of funding rate records."""
        inserted = 0
        updated = 0
        for funding in funding_list:
            existing = self.db.query(MarketAssetMetrics).filter(
                MarketAssetMetrics.exchange == funding.exchange,
                MarketAssetMetrics.symbol == funding.symbol,
                MarketAssetMetrics.timestamp == funding.timestamp,
            ).first()

            if existing:
                existing.funding_rate = funding.funding_rate
                if funding.mark_price:
                    existing.mark_price = funding.mark_price
                updated += 1
            else:
                record = MarketAssetMetrics(
                    exchange=funding.exchange,
                    symbol=funding.symbol,
                    timestamp=funding.timestamp,
                    funding_rate=funding.funding_rate,
                    mark_price=funding.mark_price,
                )
                self.db.add(record)
                inserted += 1

        self.db.commit()
        return {"inserted": inserted, "updated": updated}

    def save_sentiment(
        self,
        sentiment: UnifiedSentiment,
        data_type: str = "top_position",
    ) -> bool:
        """Save sentiment data to market_sentiment_metrics table."""
        try:
            existing = self.db.query(MarketSentimentMetrics).filter(
                MarketSentimentMetrics.exchange == sentiment.exchange,
                MarketSentimentMetrics.symbol == sentiment.symbol,
                MarketSentimentMetrics.timestamp == sentiment.timestamp,
                MarketSentimentMetrics.data_type == data_type,
            ).first()

            if existing:
                existing.long_ratio = sentiment.long_ratio
                existing.short_ratio = sentiment.short_ratio
                existing.long_short_ratio = sentiment.long_short_ratio
            else:
                record = MarketSentimentMetrics(
                    exchange=sentiment.exchange,
                    symbol=sentiment.symbol,
                    timestamp=sentiment.timestamp,
                    long_ratio=sentiment.long_ratio,
                    short_ratio=sentiment.short_ratio,
                    long_short_ratio=sentiment.long_short_ratio,
                    data_type=data_type,
                )
                self.db.add(record)

            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save sentiment: {e}")
            self.db.rollback()
            return False

    def save_sentiment_batch(
        self,
        sentiment_list: List[UnifiedSentiment],
        data_type: str = "top_position",
    ) -> dict:
        """Save batch of sentiment records."""
        inserted = 0
        updated = 0
        for sentiment in sentiment_list:
            existing = self.db.query(MarketSentimentMetrics).filter(
                MarketSentimentMetrics.exchange == sentiment.exchange,
                MarketSentimentMetrics.symbol == sentiment.symbol,
                MarketSentimentMetrics.timestamp == sentiment.timestamp,
                MarketSentimentMetrics.data_type == data_type,
            ).first()

            if existing:
                existing.long_ratio = sentiment.long_ratio
                existing.short_ratio = sentiment.short_ratio
                existing.long_short_ratio = sentiment.long_short_ratio
                updated += 1
            else:
                record = MarketSentimentMetrics(
                    exchange=sentiment.exchange,
                    symbol=sentiment.symbol,
                    timestamp=sentiment.timestamp,
                    long_ratio=sentiment.long_ratio,
                    short_ratio=sentiment.short_ratio,
                    long_short_ratio=sentiment.long_short_ratio,
                    data_type=data_type,
                )
                self.db.add(record)
                inserted += 1

        self.db.commit()
        return {"inserted": inserted, "updated": updated}
