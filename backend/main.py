from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app_runtime import build_frontend, start_frontend_watcher, start_runtime_monitor, stop_runtime_monitor
from app_startup import run_startup_tasks
from database.connection import SessionLocal
from version import __version__

app = FastAPI(
    title="CEC-codex API",
    version=__version__,
    description="Cryptocurrency perpetual contract trading platform with AI-powered decision making"
)

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "Trading API is running",
        "version": __version__
    }


# Manual frontend rebuild endpoint
@app.post("/api/rebuild-frontend")
async def rebuild_frontend():
    """Manually trigger frontend rebuild"""
    try:
        build_frontend()
        return {"status": "success", "message": "Frontend rebuild triggered"}
    except Exception as e:
        return {"status": "error", "message": f"Frontend rebuild failed: {str(e)}"}

# CORS: allow same-origin and user-configured origins
_cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress JSON/JS/CSS responses over the wire (the frontend bundle ships
# uncompressed otherwise; gzip cuts it roughly 3-4x).
app.add_middleware(GZipMiddleware, minimum_size=1000)


class ImmutableStaticFiles(StaticFiles):
    """StaticFiles that marks content-hashed build assets as long-lived/immutable.

    Safe because Vite fingerprints every asset filename with a content hash,
    so a new deploy always produces new filenames instead of overwriting these.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        return response


# Mount static files for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", ImmutableStaticFiles(directory=assets_dir), name="assets")


@app.on_event("startup")
def on_startup():
    start_frontend_watcher()
    start_runtime_monitor()
    run_startup_tasks()


@app.on_event("startup")
async def restore_bot_webhooks():
    """Restore Telegram webhook and register adapter after container restart."""
    try:
        from services.telegram_bot_service import restore_telegram_webhook, get_telegram_adapter
        from services.bot_adapter import register_adapter
        from services.bot_service import get_decrypted_bot_token
        from database.connection import SessionLocal
        from database.models import BotConfig

        await restore_telegram_webhook()

        # Register Telegram adapter if connected
        db = SessionLocal()
        try:
            config = db.query(BotConfig).filter(
                BotConfig.platform == "telegram",
                BotConfig.status == "connected"
            ).first()
            if config:
                token = get_decrypted_bot_token(db, "telegram")
                if token:
                    adapter = get_telegram_adapter()
                    await adapter.start(token)
                    register_adapter(adapter)
                    print(f"[startup] Telegram adapter registered")
        finally:
            db.close()
    except Exception as e:
        print(f"[startup] Telegram webhook restore failed (non-fatal): {e}")


@app.on_event("startup")
async def restore_discord_gateway():
    """Restore Discord Gateway connection and register adapter after container restart."""
    try:
        from database.connection import SessionLocal
        from database.models import BotConfig
        from services.bot_service import get_decrypted_bot_token
        from services.discord_bot_service import start_discord_gateway, get_discord_adapter
        from services.bot_adapter import register_adapter
        from api.bot_routes import _process_discord_message_internal
        import asyncio

        db = SessionLocal()
        try:
            config = db.query(BotConfig).filter(
                BotConfig.platform == "discord",
                BotConfig.status == "connected"
            ).first()

            if not config:
                return

            token = get_decrypted_bot_token(db, "discord")
            if not token:
                return

            # Register Discord adapter
            adapter = get_discord_adapter()
            await adapter.start(token)
            register_adapter(adapter)
            print(f"[startup] Discord adapter registered")

            async def handle_discord_message(user_id: int, username: str, display_name: str, text: str) -> str:
                return await _process_discord_message_internal(user_id, username, display_name, text)

            asyncio.create_task(start_discord_gateway(token, handle_discord_message))
            print(f"[startup] Discord Gateway restore initiated for @{config.bot_username}")
        finally:
            db.close()
    except Exception as e:
        print(f"[startup] Discord Gateway restore failed (non-fatal): {e}")


@app.on_event("shutdown")
def on_shutdown():
    stop_runtime_monitor()

    # Shutdown all services (scheduler, market data tasks, auto trading, etc.)
    from services.startup import shutdown_services
    shutdown_services()


@app.on_event("shutdown")
async def shutdown_discord_gateway():
    """Stop Discord Gateway on shutdown."""
    try:
        from services.discord_bot_service import stop_discord_gateway
        await stop_discord_gateway()
    except Exception as e:
        print(f"[shutdown] Discord Gateway stop failed (non-fatal): {e}")


# API routes
from api.auth_dependencies import get_current_user
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
# Removed: AI account routes merged into account_routes (unified AI trader accounts)

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/accounts/{account_id}/strategy")
async def get_account_strategy_alias(
    account_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias for strategy config endpoint"""
    from api.account_routes import get_account_strategy
    return get_account_strategy(account_id, current_user, db)

@app.put("/api/accounts/{account_id}/strategy")
async def update_account_strategy_alias(
    account_id: int,
    payload: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias for strategy config endpoint"""
    from api.account_routes import update_account_strategy
    from schemas.account import StrategyConfigUpdate
    from pydantic import ValidationError
    try:
        strategy_update = StrategyConfigUpdate(**payload)
        return update_account_strategy(account_id, strategy_update, current_user, db)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/strategy/status")
async def get_strategy_manager_status():
    """Get strategy manager status"""
    from services.trading_strategy import get_strategy_status
    return get_strategy_status()

# WebSocket endpoint
from api.ws import websocket_endpoint

app.websocket("/ws")(websocket_endpoint)

# Serve frontend index.html for root and SPA routes
@app.get("/")
async def serve_root():
    """Serve the frontend index.html for root route"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        return {"message": "Frontend not built yet"}

# Catch-all route for SPA routing (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve existing frontend files first, then index.html for SPA routes."""
    # Skip API and explicitly mounted/config routes
    if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    
    static_dir = Path(os.path.dirname(__file__)) / "static"
    static_root = static_dir.resolve()
    requested_path = (static_dir / full_path).resolve()

    try:
        requested_path.relative_to(static_root)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    if requested_path.is_file():
        return FileResponse(requested_path)

    index_path = static_dir / "index.html"
    
    if index_path.exists():
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        return {"message": "Frontend not built yet"}
