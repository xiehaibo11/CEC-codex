"""Retention configuration and scheduled cleanup of old market flow data."""

import logging

logger = logging.getLogger(__name__)


# Data retention settings
DATA_RETENTION_DAYS = 365


def get_retention_days(exchange: str = "hyperliquid") -> int:
    """Get retention days from SystemConfig for specific exchange, fallback to default"""
    try:
        from database.connection import SessionLocal
        from database.models import SystemConfig

        key = f"{exchange}_retention_days"
        db = SessionLocal()
        try:
            config = db.query(SystemConfig).filter(
                SystemConfig.key == key
            ).first()
            if config and config.value:
                return int(config.value)
        finally:
            db.close()
    except Exception:
        pass
    return DATA_RETENTION_DAYS


def cleanup_old_market_flow_data():
    """
    Delete market flow data older than configured retention days.
    Cleans up data for each exchange based on their individual retention settings.
    This function is designed to be called by a scheduled task.
    """
    import time
    from database.connection import SessionLocal
    from database.models import (
        MarketTradesAggregated,
        MarketOrderbookSnapshots,
        MarketAssetMetrics,
        MarketSentimentMetrics,
    )

    db = SessionLocal()
    try:
        total_deleted = 0

        # Clean up Hyperliquid data
        hl_retention = get_retention_days("hyperliquid")
        hl_cutoff_ms = int((time.time() - hl_retention * 86400) * 1000)

        hl_trades = (
            db.query(MarketTradesAggregated)
            .filter(
                MarketTradesAggregated.exchange == "hyperliquid",
                MarketTradesAggregated.timestamp < hl_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        hl_orderbook = (
            db.query(MarketOrderbookSnapshots)
            .filter(
                MarketOrderbookSnapshots.exchange == "hyperliquid",
                MarketOrderbookSnapshots.timestamp < hl_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        hl_metrics = (
            db.query(MarketAssetMetrics)
            .filter(
                MarketAssetMetrics.exchange == "hyperliquid",
                MarketAssetMetrics.timestamp < hl_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        hl_total = hl_trades + hl_orderbook + hl_metrics
        if hl_total > 0:
            logger.info(
                f"Hyperliquid cleanup: {hl_trades} trades, {hl_orderbook} orderbook, "
                f"{hl_metrics} metrics (older than {hl_retention} days)"
            )
        total_deleted += hl_total

        # Clean up Binance data
        bn_retention = get_retention_days("binance")
        bn_cutoff_ms = int((time.time() - bn_retention * 86400) * 1000)

        bn_trades = (
            db.query(MarketTradesAggregated)
            .filter(
                MarketTradesAggregated.exchange == "binance",
                MarketTradesAggregated.timestamp < bn_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        bn_orderbook = (
            db.query(MarketOrderbookSnapshots)
            .filter(
                MarketOrderbookSnapshots.exchange == "binance",
                MarketOrderbookSnapshots.timestamp < bn_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        bn_metrics = (
            db.query(MarketAssetMetrics)
            .filter(
                MarketAssetMetrics.exchange == "binance",
                MarketAssetMetrics.timestamp < bn_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        bn_sentiment = (
            db.query(MarketSentimentMetrics)
            .filter(
                MarketSentimentMetrics.exchange == "binance",
                MarketSentimentMetrics.timestamp < bn_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        bn_total = bn_trades + bn_orderbook + bn_metrics + bn_sentiment
        if bn_total > 0:
            logger.info(
                f"Binance cleanup: {bn_trades} trades, {bn_orderbook} orderbook, "
                f"{bn_metrics} metrics, {bn_sentiment} sentiment (older than {bn_retention} days)"
            )
        total_deleted += bn_total

        # Clean up HiBT data
        hibt_retention = get_retention_days("hibt")
        hibt_cutoff_ms = int((time.time() - hibt_retention * 86400) * 1000)

        hibt_trades = (
            db.query(MarketTradesAggregated)
            .filter(
                MarketTradesAggregated.exchange == "hibt",
                MarketTradesAggregated.timestamp < hibt_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        hibt_orderbook = (
            db.query(MarketOrderbookSnapshots)
            .filter(
                MarketOrderbookSnapshots.exchange == "hibt",
                MarketOrderbookSnapshots.timestamp < hibt_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        hibt_metrics = (
            db.query(MarketAssetMetrics)
            .filter(
                MarketAssetMetrics.exchange == "hibt",
                MarketAssetMetrics.timestamp < hibt_cutoff_ms
            )
            .delete(synchronize_session=False)
        )
        hibt_total = hibt_trades + hibt_orderbook + hibt_metrics
        if hibt_total > 0:
            logger.info(
                f"HiBT cleanup: {hibt_trades} trades, {hibt_orderbook} orderbook, "
                f"{hibt_metrics} metrics (older than {hibt_retention} days)"
            )
        total_deleted += hibt_total

        db.commit()

        if total_deleted == 0:
            logger.debug("Market flow data cleanup: no old records to delete")

    except Exception as e:
        db.rollback()
        logger.error(f"Market flow data cleanup failed: {e}")
    finally:
        db.close()
