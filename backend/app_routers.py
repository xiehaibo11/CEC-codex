"""API router imports and registration extracted from main.py.

``register_routers(app)`` calls ``app.include_router(...)`` in exactly the same
order as the original main.py. Router modules are imported at module load time
(same as before), preserving any import-time side effects.
"""
from api.local_auth_routes import router as local_auth_router
from api.market_data_routes import router as market_data_router
from api.order_routes import router as order_router
from api.account_routes import router as account_router
from api.config_routes import router as config_router
from api.ranking_routes import router as ranking_router
from api.crypto_routes import router as crypto_router
from api.arena_routes import router as arena_router
from api.system_log_routes import router as system_log_router
from api.prompt_routes import router as prompt_router
from api.sampling_routes import router as sampling_router
from api.hyperliquid_action_routes import router as hyperliquid_action_router
from api.hyperliquid_routes import router as hyperliquid_router
from api.user_routes import router as user_router
from api.kline_routes import router as kline_router
from api.kline_analysis_routes import router as kline_analysis_router
from api.market_flow_routes import router as market_flow_router
from api.signal_routes import router as signal_router
from api.market_regime_routes import router as market_regime_router
from api.analytics_routes import router as analytics_router
from api.ai_review_routes import router as ai_review_router
from api.trader_data_routes import router as trader_data_router
from api.prompt_backtest_routes import router as prompt_backtest_router
from api.system_routes import router as system_router
from api.binance_routes import router as binance_router
from api.hibt_routes import router as hibt_router
from api.ai_stream_routes import router as ai_stream_router
from api.hyper_ai_routes import router as hyper_ai_router
from api.bot_routes import router as bot_router
from api.factor_routes import router as factor_router
from api.news_routes import router as news_router
from api.market_intelligence_routes import router as market_intelligence_router
from api.coinglass_routes import router as coinglass_router
from api.event_contract_routes import router as event_contract_router
from routes.program_routes import router as program_router


def register_routers(app):
    """Include all API routers on the FastAPI app, preserving original order."""
    app.include_router(local_auth_router)
    app.include_router(market_data_router)
    app.include_router(order_router)
    app.include_router(account_router)
    app.include_router(config_router)
    app.include_router(ranking_router)
    app.include_router(crypto_router)
    app.include_router(arena_router)
    app.include_router(system_log_router)
    app.include_router(prompt_router)
    app.include_router(sampling_router)
    app.include_router(hyperliquid_action_router)
    app.include_router(hyperliquid_router)
    app.include_router(user_router)
    app.include_router(kline_router)
    app.include_router(kline_analysis_router)
    app.include_router(market_flow_router)
    app.include_router(signal_router)
    app.include_router(market_regime_router)
    app.include_router(analytics_router)
    app.include_router(ai_review_router)
    app.include_router(trader_data_router)
    app.include_router(prompt_backtest_router)
    app.include_router(program_router)
    app.include_router(system_router)
    app.include_router(binance_router)
    app.include_router(hibt_router)
    app.include_router(ai_stream_router)
    app.include_router(hyper_ai_router)
    app.include_router(bot_router)
    app.include_router(factor_router)
    app.include_router(news_router)
    app.include_router(market_intelligence_router)
    app.include_router(coinglass_router)
    app.include_router(event_contract_router)
    # app.include_router(ai_account_router, prefix="/api")  # Removed - merged into account_router
