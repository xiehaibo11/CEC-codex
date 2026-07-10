"""Database ORM models package.

This package was split from the original single-file ``database/models.py``.
All model classes, the shared declarative ``Base``, and module-level
constants are re-exported here so that ``from database.models import <Name>``
continues to work identically to before the split.
"""

from ..connection import Base

from .accounts_auth import (
    User,
    Account,
    UserAuthSession,
    UserSubscription,
    UserExchangeConfig,
    CoinGlassUserKey,
)
from .system_config import (
    SystemConfig,
    TradingConfig,
    GlobalSamplingConfig,
    MarketRegimeConfig,
)
from .trading import (
    CRYPTO_MIN_COMMISSION,
    CRYPTO_COMMISSION_RATE,
    CRYPTO_MIN_ORDER_QUANTITY,
    CRYPTO_LOT_SIZE,
    Position,
    Order,
    Trade,
    AIDecisionLog,
    AIReviewRun,
    AIReviewAgentReport,
    AccountAssetSnapshot,
    AccountStrategyConfig,
)
from .market_data import (
    CryptoPrice,
    CryptoKline,
    CryptoPriceTick,
    PerpFunding,
    PriceSample,
    KlineCollectionTask,
    MarketTradesAggregated,
    MarketOrderbookSnapshots,
    MarketAssetMetrics,
    MarketSentimentMetrics,
    NewsArticle,
)
from .prompts import (
    PromptTemplate,
    AccountPromptBinding,
    PromptBacktestTask,
    PromptBacktestItem,
)
from .hyperliquid import (
    HyperliquidWallet,
    HyperliquidAccountSnapshot,
    HyperliquidPosition,
    HyperliquidExchangeAction,
    HyperliquidBackfillTask,
)
from .binance import (
    BinanceWallet,
    BinanceAccountSnapshot,
    BinanceBackfillTask,
)
from .hibt import (
    HibtBackfillTask,
    HibtWallet,
)
from .signals import (
    SignalDefinition,
    SignalPool,
    SignalTriggerLog,
    TraderTriggerConfig,
)
from .ai_conversations import (
    KlineAIAnalysisLog,
    AiPromptConversation,
    AiPromptMessage,
    AiSignalConversation,
    AiSignalMessage,
    AiAttributionConversation,
    AiAttributionMessage,
    AiProgramConversation,
    AiProgramMessage,
)
from .program_backtest import (
    TradingProgram,
    AccountProgramBinding,
    ProgramExecutionLog,
    BacktestResult,
    BacktestTriggerLog,
)
from .event_contract import (
    EventContractBacktestRun,
    EventContractTradeLog,
    EventContractBacktestTask,
    EventContractPaperTrader,
    EventContractPaperBet,
    EventContractValidationLog,
)
from .hyper_ai import (
    HyperAiProfile,
    HyperAiMemory,
    HyperAiConversation,
    HyperAiMessage,
    BotConfig,
    BotChatBinding,
)
from .factors import (
    FactorValue,
    FactorEffectiveness,
    CustomFactor,
)
from .arb import (
    ArbOpportunityLog,
)

__all__ = [
    "Base",
    "User",
    "Account",
    "UserAuthSession",
    "UserSubscription",
    "UserExchangeConfig",
    "CoinGlassUserKey",
    "SystemConfig",
    "TradingConfig",
    "GlobalSamplingConfig",
    "MarketRegimeConfig",
    "CRYPTO_MIN_COMMISSION",
    "CRYPTO_COMMISSION_RATE",
    "CRYPTO_MIN_ORDER_QUANTITY",
    "CRYPTO_LOT_SIZE",
    "Position",
    "Order",
    "Trade",
    "AIDecisionLog",
    "AIReviewRun",
    "AIReviewAgentReport",
    "AccountAssetSnapshot",
    "AccountStrategyConfig",
    "CryptoPrice",
    "CryptoKline",
    "CryptoPriceTick",
    "PerpFunding",
    "PriceSample",
    "KlineCollectionTask",
    "MarketTradesAggregated",
    "MarketOrderbookSnapshots",
    "MarketAssetMetrics",
    "MarketSentimentMetrics",
    "NewsArticle",
    "PromptTemplate",
    "AccountPromptBinding",
    "PromptBacktestTask",
    "PromptBacktestItem",
    "HyperliquidWallet",
    "HyperliquidAccountSnapshot",
    "HyperliquidPosition",
    "HyperliquidExchangeAction",
    "HyperliquidBackfillTask",
    "BinanceWallet",
    "BinanceAccountSnapshot",
    "BinanceBackfillTask",
    "HibtWallet",
    "HibtBackfillTask",
    "SignalDefinition",
    "SignalPool",
    "SignalTriggerLog",
    "TraderTriggerConfig",
    "KlineAIAnalysisLog",
    "AiPromptConversation",
    "AiPromptMessage",
    "AiSignalConversation",
    "AiSignalMessage",
    "AiAttributionConversation",
    "AiAttributionMessage",
    "AiProgramConversation",
    "AiProgramMessage",
    "TradingProgram",
    "AccountProgramBinding",
    "ProgramExecutionLog",
    "BacktestResult",
    "BacktestTriggerLog",
    "EventContractBacktestRun",
    "EventContractTradeLog",
    "EventContractBacktestTask",
    "EventContractPaperTrader",
    "EventContractPaperBet",
    "EventContractValidationLog",
    "HyperAiProfile",
    "HyperAiMemory",
    "HyperAiConversation",
    "HyperAiMessage",
    "BotConfig",
    "BotChatBinding",
    "FactorValue",
    "FactorEffectiveness",
    "CustomFactor",
    "ArbOpportunityLog",
]
