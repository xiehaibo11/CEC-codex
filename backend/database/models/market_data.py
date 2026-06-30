from sqlalchemy import (
    Column, Integer, BigInteger, String, DECIMAL, TIMESTAMP, ForeignKey,
    UniqueConstraint, Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import datetime  # noqa: F401  (kept for parity with original models module)

from ..connection import Base



class CryptoPrice(Base):
    __tablename__ = "crypto_prices"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CRYPTO")
    price = Column(DECIMAL(18, 6), nullable=False)
    price_date = Column(Date, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    __table_args__ = (UniqueConstraint('symbol', 'market', 'price_date'),)


class CryptoKline(Base):
    __tablename__ = "crypto_klines"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid", index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CRYPTO")
    period = Column(String(10), nullable=False)  # 1m, 5m, 15m, 30m, 1h, 1d
    timestamp = Column(Integer, nullable=False, index=True)
    datetime_str = Column(String(50), nullable=False)
    environment = Column(String(20), nullable=False, default="mainnet", index=True)  # testnet or mainnet
    open_price = Column(DECIMAL(18, 6), nullable=True)
    high_price = Column(DECIMAL(18, 6), nullable=True)
    low_price = Column(DECIMAL(18, 6), nullable=True)
    close_price = Column(DECIMAL(18, 6), nullable=True)
    volume = Column(DECIMAL(18, 2), nullable=True)
    amount = Column(DECIMAL(18, 2), nullable=True)
    change = Column(DECIMAL(18, 6), nullable=True)
    percent = Column(DECIMAL(10, 4), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (UniqueConstraint('exchange', 'symbol', 'market', 'period', 'timestamp', 'environment'),)


class CryptoPriceTick(Base):
    __tablename__ = "crypto_price_ticks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False, default="CRYPTO")
    price = Column(DECIMAL(18, 8), nullable=False)
    event_time = Column(TIMESTAMP, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class PerpFunding(Base):
    """Store perpetual contract funding rate data from multiple exchanges"""
    __tablename__ = "perp_funding"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(Integer, nullable=False, index=True)
    funding_rate = Column(DECIMAL(18, 8), nullable=False)
    mark_price = Column(DECIMAL(18, 6), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (UniqueConstraint('exchange', 'symbol', 'timestamp'),)


class PriceSample(Base):
    """Store price sampling data for persistent sampling pools"""
    __tablename__ = "price_samples"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    price = Column(DECIMAL(18, 8), nullable=False)
    sample_time = Column(TIMESTAMP, nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    account = relationship("Account")


class KlineCollectionTask(Base):
    """Store K-line data collection task status"""
    __tablename__ = "kline_collection_tasks"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    period = Column(String(10), nullable=False, default="1m")
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)
    total_records = Column(Integer, default=0)
    collected_records = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class MarketTradesAggregated(Base):
    """15-second aggregated trade data for CVD and Taker Volume analysis"""
    __tablename__ = "market_trades_aggregated"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid", index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)  # milliseconds
    taker_buy_volume = Column(DECIMAL(24, 8), nullable=False, default=0)
    taker_sell_volume = Column(DECIMAL(24, 8), nullable=False, default=0)
    taker_buy_count = Column(Integer, nullable=False, default=0)
    taker_sell_count = Column(Integer, nullable=False, default=0)
    taker_buy_notional = Column(DECIMAL(24, 6), nullable=False, default=0)
    taker_sell_notional = Column(DECIMAL(24, 6), nullable=False, default=0)
    vwap = Column(DECIMAL(18, 6), nullable=True)
    high_price = Column(DECIMAL(18, 6), nullable=True)
    low_price = Column(DECIMAL(18, 6), nullable=True)
    # Large order tracking fields
    large_buy_notional = Column(DECIMAL(24, 6), nullable=False, default=0, server_default=text("0"))
    large_sell_notional = Column(DECIMAL(24, 6), nullable=False, default=0, server_default=text("0"))
    large_buy_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    large_sell_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timestamp',
                         name='market_trades_aggregated_exchange_symbol_timestamp_key'),
    )


class MarketOrderbookSnapshots(Base):
    """Order book snapshots for depth ratio and liquidity analysis"""
    __tablename__ = "market_orderbook_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid", index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)  # milliseconds
    best_bid = Column(DECIMAL(18, 6), nullable=True)
    best_ask = Column(DECIMAL(18, 6), nullable=True)
    spread = Column(DECIMAL(18, 6), nullable=True)
    bid_depth_5 = Column(DECIMAL(24, 8), nullable=False, default=0)
    ask_depth_5 = Column(DECIMAL(24, 8), nullable=False, default=0)
    bid_depth_10 = Column(DECIMAL(24, 8), nullable=False, default=0)
    ask_depth_10 = Column(DECIMAL(24, 8), nullable=False, default=0)
    bid_orders_count = Column(Integer, nullable=False, default=0)
    ask_orders_count = Column(Integer, nullable=False, default=0)
    raw_levels = Column(Text, nullable=True)  # JSON string of full orderbook
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timestamp',
                         name='market_orderbook_snapshots_exchange_symbol_timestamp_key'),
    )


class MarketAssetMetrics(Base):
    """Asset metrics snapshots for OI, Funding Rate, and Premium analysis"""
    __tablename__ = "market_asset_metrics"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, default="hyperliquid", index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)  # milliseconds
    open_interest = Column(DECIMAL(24, 8), nullable=True)
    funding_rate = Column(DECIMAL(18, 8), nullable=True)
    mark_price = Column(DECIMAL(18, 6), nullable=True)
    oracle_price = Column(DECIMAL(18, 6), nullable=True)
    mid_price = Column(DECIMAL(18, 6), nullable=True)
    premium = Column(DECIMAL(18, 8), nullable=True)
    day_notional_volume = Column(DECIMAL(24, 6), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timestamp',
                         name='market_asset_metrics_exchange_symbol_timestamp_key'),
    )


class MarketSentimentMetrics(Base):
    """Market sentiment metrics for long/short ratio analysis (Binance-specific data)"""
    __tablename__ = "market_sentiment_metrics"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)  # milliseconds
    long_ratio = Column(DECIMAL(10, 6), nullable=True)  # e.g., 0.65 = 65% long
    short_ratio = Column(DECIMAL(10, 6), nullable=True)  # e.g., 0.35 = 35% short
    long_short_ratio = Column(DECIMAL(10, 6), nullable=True)  # e.g., 1.86 = longs/shorts
    data_type = Column(String(30), nullable=False, default="top_position")  # top_position, top_account, global
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timestamp', 'data_type',
                         name='market_sentiment_metrics_unique_key'),
    )


class NewsArticle(Base):
    """Aggregated news articles from multiple sources for market intelligence"""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    source_domain = Column(String(255), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    published_at = Column(TIMESTAMP, nullable=True, index=True)
    symbols = Column(Text, nullable=True)  # JSON array: ["BTC","ETH"]
    sentiment = Column(String(20), nullable=True)  # bullish/bearish/neutral
    sentiment_source = Column(String(20), nullable=True)  # api/keyword/ai
    relevance_score = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)  # Thumbnail/preview image URL from source
    raw_data = Column(Text, nullable=True)
    classified = Column(Boolean, nullable=False, default=False)
    fetched_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('source_domain', 'source_url',
                         name='news_articles_source_unique'),
    )
