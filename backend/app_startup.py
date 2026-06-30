"""Application startup/shutdown event handlers extracted from main.py.

``register_startup_events(app)`` wires these onto the FastAPI ``app`` in exactly
the same order they were registered via ``@app.on_event`` decorators in main.py.
"""
import os
import threading

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import engine, Base, SessionLocal
from database.models import TradingConfig, User, SystemConfig
from config.settings import DEFAULT_TRADING_CONFIGS
import app_runtime


def on_startup():
    # Start frontend file watcher in background thread
    app_runtime.start_frontend_watcher()
    print("Frontend file watcher started")

    app_runtime._start_runtime_monitor()
    print("Runtime monitor started")

    # Create main database tables
    Base.metadata.create_all(bind=engine)

    # Create snapshot database tables (hyperliquid_trades, hyperliquid_account_snapshots)
    try:
        from database.init_snapshot_db import init_snapshot_database
        init_snapshot_database()
    except Exception as e:
        print(f"[startup] Snapshot DB init error (non-fatal): {e}")

    # Run all migrations (idempotent - safe to run every startup)
    try:
        from database.migration_manager import run_all_migrations
        run_all_migrations()
    except Exception as e:
        print(f"[startup] Migration error (non-fatal): {e}")

    # Run schema validator to auto-fix missing columns
    try:
        from database.schema_validator import validate_and_sync_schema
        validate_and_sync_schema()
    except Exception as e:
        print(f"[startup] Schema validation error (non-fatal): {e}")

    # Seed trading configs if empty
    db: Session = SessionLocal()
    try:
        # Ensure AI decision log table has snapshot columns (backfill on existing installs)
        try:
            # PostgreSQL-compatible column check
            result = db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'ai_decision_logs'
            """))
            columns = {row[0] for row in result}

            if "prompt_snapshot" not in columns:
                db.execute(text("ALTER TABLE ai_decision_logs ADD COLUMN prompt_snapshot TEXT"))
            if "reasoning_snapshot" not in columns:
                db.execute(text("ALTER TABLE ai_decision_logs ADD COLUMN reasoning_snapshot TEXT"))
            if "decision_snapshot" not in columns:
                db.execute(text("ALTER TABLE ai_decision_logs ADD COLUMN decision_snapshot TEXT"))
            db.commit()
        except Exception as migration_err:
            db.rollback()
            print(f"[startup] Failed to ensure AI decision log snapshot columns: {migration_err}")

        # Ensure global_sampling_configs has sampling_depth column (for existing installs)
        try:
            result = db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'global_sampling_configs'
            """))
            columns = {row[0] for row in result}

            if "sampling_depth" not in columns:
                db.execute(text("ALTER TABLE global_sampling_configs ADD COLUMN sampling_depth INTEGER NOT NULL DEFAULT 10"))
                print("[startup] Added sampling_depth column to global_sampling_configs")
            db.commit()
        except Exception as migration_err:
            db.rollback()
            print(f"[startup] Failed to ensure global_sampling_configs.sampling_depth: {migration_err}")

        # Ensure crypto_klines has exchange column (for multi-exchange support)
        try:
            result = db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'crypto_klines'
            """))
            columns = {row[0] for row in result}

            if "exchange" not in columns:
                print("[startup] Adding exchange column to crypto_klines table...")
                # Add exchange column with default value
                db.execute(text("""
                    ALTER TABLE crypto_klines
                    ADD COLUMN exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid'
                """))
                # Create index on exchange field
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_crypto_klines_exchange ON crypto_klines(exchange)
                """))
                # Drop old unique constraint (without exchange)
                db.execute(text("""
                    ALTER TABLE crypto_klines
                    DROP CONSTRAINT IF EXISTS crypto_klines_symbol_market_period_timestamp_key
                """))
                print("[startup] Successfully added exchange column to crypto_klines")
            db.commit()
        except Exception as migration_err:
            db.rollback()
            print(f"[startup] Failed to ensure crypto_klines.exchange: {migration_err}")

        # Ensure crypto_klines has environment column (for testnet/mainnet isolation)
        try:
            result = db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'crypto_klines'
            """))
            columns = {row[0] for row in result}

            if "environment" not in columns:
                print("[startup] Adding environment column to crypto_klines table...")
                # Add environment column with default value
                db.execute(text("""
                    ALTER TABLE crypto_klines
                    ADD COLUMN environment VARCHAR(20) NOT NULL DEFAULT 'mainnet'
                """))

                # Update all existing records to 'mainnet' (they were from mainnet API)
                db.execute(text("""
                    UPDATE crypto_klines SET environment = 'mainnet' WHERE environment IS NULL
                """))

                # Drop old unique constraints if exist
                db.execute(text("""
                    ALTER TABLE crypto_klines
                    DROP CONSTRAINT IF EXISTS crypto_klines_exchange_symbol_market_period_timestamp_key
                """))
                db.execute(text("""
                    ALTER TABLE crypto_klines
                    DROP CONSTRAINT IF EXISTS uq_crypto_klines_unique
                """))

                # Create new unique constraint including environment
                db.execute(text("""
                    ALTER TABLE crypto_klines
                    ADD CONSTRAINT crypto_klines_exchange_symbol_market_period_timestamp_environment_key
                    UNIQUE (exchange, symbol, market, period, timestamp, environment)
                """))

                # Create performance indexes
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_crypto_klines_environment ON crypto_klines(environment)
                """))
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_crypto_klines_symbol_period_env ON crypto_klines(symbol, period, environment)
                """))

                print("[startup] Successfully added environment column to crypto_klines")
            db.commit()
        except Exception as migration_err:
            db.rollback()
            print(f"[startup] Failed to ensure crypto_klines.environment: {migration_err}")

        if db.query(TradingConfig).count() == 0:
            for cfg in DEFAULT_TRADING_CONFIGS.values():
                db.add(
                    TradingConfig(
                        version="v1",
                        market=cfg.market,
                        min_commission=cfg.min_commission,
                        commission_rate=cfg.commission_rate,
                        exchange_rate=cfg.exchange_rate,
                        min_order_quantity=cfg.min_order_quantity,
                        lot_size=cfg.lot_size,
                    )
                )
            db.commit()

        # Ensure default user exists
        default_user = db.query(User).filter(User.username == "default").first()
        if not default_user:
            default_user = User(
                username="default",
                email=None,
                password_hash=None,
                is_active="true"
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
        
        # No default account creation - users must create their own accounts

    finally:
        db.close()

    # Initialize Hyper AI LLM config from env vars (only if not yet configured)
    hyper_ai_provider = os.getenv("HYPER_AI_LLM_PROVIDER", "").strip()
    hyper_ai_api_key = os.getenv("HYPER_AI_LLM_API_KEY", "").strip()
    hyper_ai_model = os.getenv("HYPER_AI_LLM_MODEL", "").strip()
    if hyper_ai_provider and hyper_ai_api_key:
        try:
            from services.hyper_ai_service import save_llm_config, get_or_create_profile
            _hai_db = SessionLocal()
            try:
                profile = get_or_create_profile(_hai_db)
                if not profile.llm_provider:
                    save_llm_config(
                        _hai_db,
                        provider=hyper_ai_provider,
                        api_key=hyper_ai_api_key,
                        model=hyper_ai_model or None,
                    )
                    print(f"[startup] Hyper AI LLM configured: {hyper_ai_provider} / {hyper_ai_model}")
                else:
                    print(f"[startup] Hyper AI LLM already configured: {profile.llm_provider}, skipping env init")
            finally:
                _hai_db.close()
        except Exception as e:
            print(f"[startup] Hyper AI LLM init error (non-fatal): {e}")

    # ============================================================
    # Upgrade: Initialize Hyperliquid trading mode config & fix NULL environment data
    # ============================================================
    # This ensures:
    # 1. New installations have hyperliquid_trading_mode config initialized
    # 2. Existing installations with NULL ai_decision_logs.hyperliquid_environment get fixed
    # 3. Fixes ModelChat empty data issue for GitHub users
    # ============================================================
    db = SessionLocal()
    try:
        # Step 1: Initialize hyperliquid_trading_mode config if missing
        config = db.query(SystemConfig).filter(
            SystemConfig.key == "hyperliquid_trading_mode"
        ).first()

        if not config:
            config = SystemConfig(
                key="hyperliquid_trading_mode",
                value="testnet",
                description="Global Hyperliquid trading environment: 'testnet' or 'mainnet'. Controls which network all AI Traders connect to."
            )
            db.add(config)
            db.commit()
            print("✓ [Upgrade] Initialized global hyperliquid_trading_mode to 'testnet'")
        else:
            print(f"✓ [Upgrade] Global hyperliquid_trading_mode already configured: {config.value}")

        # Step 2: One-time migration - fix NULL hyperliquid_environment in ai_decision_logs
        # Check if there are any NULL records
        null_count = db.execute(text("""
            SELECT COUNT(*) FROM ai_decision_logs WHERE hyperliquid_environment IS NULL
        """)).scalar()

        if null_count > 0:
            print(f"⚠ [Upgrade] Found {null_count} ai_decision_logs with NULL hyperliquid_environment, fixing...")

            # Update all NULL records to 'testnet' (safe default)
            updated = db.execute(text("""
                UPDATE ai_decision_logs
                SET hyperliquid_environment = 'testnet'
                WHERE hyperliquid_environment IS NULL
            """))
            db.commit()

            print(f"✓ [Upgrade] Updated {null_count} records from NULL to 'testnet' (ModelChat fix)")
        else:
            print("✓ [Upgrade] No NULL hyperliquid_environment records found, data is clean")

    except Exception as e:
        db.rollback()
        print(f"✗ [Upgrade] Hyperliquid environment upgrade failed: {e}")
        # Non-fatal - continue startup
    finally:
        db.close()

    # Ensure prompt templates exist
    db = SessionLocal()
    try:
        from services.prompt_initializer import seed_prompt_templates
        seed_prompt_templates(db)
    finally:
        db.close()
    
    # Initialize system log collector
    from services.system_logger import setup_system_logger
    setup_system_logger()

    # Load and apply global sampling configuration (use watchlist if available)
    try:
        from database.models import GlobalSamplingConfig
        from services.sampling_pool import sampling_pool
        from services.trading_commands import AI_TRADING_SYMBOLS
        from services.hyperliquid_symbol_service import get_selected_symbols as get_hyperliquid_selected_symbols

        db = SessionLocal()
        try:
            symbols = get_hyperliquid_selected_symbols() or AI_TRADING_SYMBOLS
            global_config = db.query(GlobalSamplingConfig).first()
            if global_config and global_config.sampling_depth:
                for symbol in symbols:
                    sampling_pool.set_max_samples(symbol, global_config.sampling_depth)
                print(f"✓ Sampling pool configured: depth={global_config.sampling_depth} for {len(symbols)} symbols")
            else:
                print(f"⚠ No global sampling config found, using default depth={sampling_pool.default_max_samples} for {len(symbols)} symbols")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Failed to load global sampling config: {e}")

    # Clean up any leftover backfill tasks from previous runs
    try:
        from database.models import KlineCollectionTask
        db = SessionLocal()
        try:
            # Delete all running and pending backfill tasks
            deleted_count = db.query(KlineCollectionTask).filter(
                KlineCollectionTask.status.in_(['running', 'pending'])
            ).delete(synchronize_session=False)
            db.commit()
            if deleted_count > 0:
                print(f"✓ Cleaned up {deleted_count} leftover backfill tasks")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠ Failed to clean up backfill tasks: {e}")

    # Initialize all services (scheduler, market data tasks, auto trading, etc.)
    print("About to initialize services...")
    from services.startup import initialize_services
    initialize_services()
    print("Services initialization completed")

    # Warmup numba JIT compilation for pandas_ta indicators
    # This prevents timeout on first indicator calculation
    def warmup_numba():
        try:
            from services.technical_indicators import calculate_indicator
            from database.connection import SessionLocal
            db = SessionLocal()
            try:
                print("[startup] Warming up numba JIT compilation...")
                calculate_indicator(db, "BTC", "BOLL", "1h")
                print("[startup] Numba warmup completed")
            finally:
                db.close()
        except Exception as e:
            print(f"[startup] Numba warmup failed (non-fatal): {e}")

    # Run warmup in background thread to not block startup
    threading.Thread(target=warmup_numba, daemon=True).start()


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


def on_shutdown():
    app_runtime.stop_runtime_monitor()

    # Shutdown all services (scheduler, market data tasks, auto trading, etc.)
    from services.startup import shutdown_services
    shutdown_services()


async def shutdown_discord_gateway():
    """Stop Discord Gateway on shutdown."""
    try:
        from services.discord_bot_service import stop_discord_gateway
        await stop_discord_gateway()
    except Exception as e:
        print(f"[shutdown] Discord Gateway stop failed (non-fatal): {e}")


def register_startup_events(app):
    """Register all startup/shutdown handlers on the FastAPI app (order-preserving)."""
    app.on_event("startup")(on_startup)
    app.on_event("startup")(restore_bot_webhooks)
    app.on_event("startup")(restore_discord_gateway)
    app.on_event("shutdown")(on_shutdown)
    app.on_event("shutdown")(shutdown_discord_gateway)
