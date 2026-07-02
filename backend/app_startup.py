"""FastAPI startup initialization tasks."""
import os
import threading

from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import DEFAULT_TRADING_CONFIGS
from database.connection import Base, SessionLocal, engine
from database.models import SystemConfig, TradingConfig, User


def run_startup_tasks() -> None:
    """Run synchronous startup tasks that prepare storage and services."""
    Base.metadata.create_all(bind=engine)
    _init_snapshot_database()
    _run_idempotent_migrations()
    _validate_schema()
    _seed_core_database()
    _init_hyper_ai_from_env()
    _ensure_hyperliquid_environment()
    _seed_prompt_templates()
    _setup_system_logger()
    _apply_sampling_pool_config()
    _cleanup_leftover_backfill_tasks()
    _initialize_services()
    threading.Thread(target=_warmup_numba, daemon=True).start()


def _init_snapshot_database() -> None:
    try:
        from database.init_snapshot_db import init_snapshot_database

        init_snapshot_database()
    except Exception as err:
        print(f"[startup] Snapshot DB init error (non-fatal): {err}")


def _run_idempotent_migrations() -> None:
    try:
        from database.migration_manager import run_all_migrations

        run_all_migrations()
    except Exception as err:
        print(f"[startup] Migration error (non-fatal): {err}")


def _validate_schema() -> None:
    try:
        from database.schema_validator import validate_and_sync_schema

        validate_and_sync_schema()
    except Exception as err:
        print(f"[startup] Schema validation error (non-fatal): {err}")


def _seed_core_database() -> None:
    db: Session = SessionLocal()
    try:
        _ensure_ai_decision_log_snapshot_columns(db)
        _ensure_sampling_depth_column(db)
        _ensure_crypto_klines_exchange_column(db)
        _ensure_crypto_klines_environment_column(db)
        _seed_trading_configs(db)
        _ensure_default_user(db)
    finally:
        db.close()


def _table_columns(db: Session, table_name: str) -> set[str]:
    result = db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :table_name
    """), {"table_name": table_name})
    return {row[0] for row in result}


def _ensure_ai_decision_log_snapshot_columns(db: Session) -> None:
    try:
        columns = _table_columns(db, "ai_decision_logs")
        if "prompt_snapshot" not in columns:
            db.execute(text("ALTER TABLE ai_decision_logs ADD COLUMN prompt_snapshot TEXT"))
        if "reasoning_snapshot" not in columns:
            db.execute(text("ALTER TABLE ai_decision_logs ADD COLUMN reasoning_snapshot TEXT"))
        if "decision_snapshot" not in columns:
            db.execute(text("ALTER TABLE ai_decision_logs ADD COLUMN decision_snapshot TEXT"))
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"[startup] Failed to ensure AI decision log snapshot columns: {err}")


def _ensure_sampling_depth_column(db: Session) -> None:
    try:
        columns = _table_columns(db, "global_sampling_configs")
        if "sampling_depth" not in columns:
            db.execute(text("ALTER TABLE global_sampling_configs ADD COLUMN sampling_depth INTEGER NOT NULL DEFAULT 10"))
            print("[startup] Added sampling_depth column to global_sampling_configs")
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"[startup] Failed to ensure global_sampling_configs.sampling_depth: {err}")


def _ensure_crypto_klines_exchange_column(db: Session) -> None:
    try:
        columns = _table_columns(db, "crypto_klines")
        if "exchange" not in columns:
            print("[startup] Adding exchange column to crypto_klines table...")
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD COLUMN exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid'
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_crypto_klines_exchange ON crypto_klines(exchange)"))
            db.execute(text("""
                ALTER TABLE crypto_klines
                DROP CONSTRAINT IF EXISTS crypto_klines_symbol_market_period_timestamp_key
            """))
            print("[startup] Successfully added exchange column to crypto_klines")
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"[startup] Failed to ensure crypto_klines.exchange: {err}")


def _ensure_crypto_klines_environment_column(db: Session) -> None:
    try:
        columns = _table_columns(db, "crypto_klines")
        if "environment" not in columns:
            print("[startup] Adding environment column to crypto_klines table...")
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD COLUMN environment VARCHAR(20) NOT NULL DEFAULT 'mainnet'
            """))
            db.execute(text("UPDATE crypto_klines SET environment = 'mainnet' WHERE environment IS NULL"))
            db.execute(text("""
                ALTER TABLE crypto_klines
                DROP CONSTRAINT IF EXISTS crypto_klines_exchange_symbol_market_period_timestamp_key
            """))
            db.execute(text("ALTER TABLE crypto_klines DROP CONSTRAINT IF EXISTS uq_crypto_klines_unique"))
            db.execute(text("""
                ALTER TABLE crypto_klines
                ADD CONSTRAINT crypto_klines_exchange_symbol_market_period_timestamp_environment_key
                UNIQUE (exchange, symbol, market, period, timestamp, environment)
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_crypto_klines_environment ON crypto_klines(environment)"))
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crypto_klines_symbol_period_env
                ON crypto_klines(symbol, period, environment)
            """))
            print("[startup] Successfully added environment column to crypto_klines")
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"[startup] Failed to ensure crypto_klines.environment: {err}")


def _seed_trading_configs(db: Session) -> None:
    if db.query(TradingConfig).count() != 0:
        return

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


def _ensure_default_user(db: Session) -> None:
    default_user = db.query(User).filter(User.username == "default").first()
    if default_user:
        return

    default_user = User(
        username="default",
        email=None,
        password_hash=None,
        is_active="true",
    )
    db.add(default_user)
    db.commit()
    db.refresh(default_user)


def _init_hyper_ai_from_env() -> None:
    provider = os.getenv("HYPER_AI_LLM_PROVIDER", "").strip()
    api_key = os.getenv("HYPER_AI_LLM_API_KEY", "").strip()
    model = os.getenv("HYPER_AI_LLM_MODEL", "").strip()
    if not provider or not api_key:
        return

    try:
        from services.hyper_ai_service import get_or_create_profile, save_llm_config

        db = SessionLocal()
        try:
            profile = get_or_create_profile(db)
            if not profile.llm_provider:
                save_llm_config(db, provider=provider, api_key=api_key, model=model or None)
                print(f"[startup] Hyper AI LLM configured: {provider} / {model}")
            else:
                print(f"[startup] Hyper AI LLM already configured: {profile.llm_provider}, skipping env init")
        finally:
            db.close()
    except Exception as err:
        print(f"[startup] Hyper AI LLM init error (non-fatal): {err}")


def _ensure_hyperliquid_environment() -> None:
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == "hyperliquid_trading_mode").first()
        if not config:
            config = SystemConfig(
                key="hyperliquid_trading_mode",
                value="testnet",
                description="Global Hyperliquid trading environment: 'testnet' or 'mainnet'. Controls which network all AI Traders connect to.",
            )
            db.add(config)
            db.commit()
            print("[Upgrade] Initialized global hyperliquid_trading_mode to 'testnet'")
        else:
            print(f"[Upgrade] Global hyperliquid_trading_mode already configured: {config.value}")

        null_count = db.execute(text("""
            SELECT COUNT(*) FROM ai_decision_logs WHERE hyperliquid_environment IS NULL
        """)).scalar()
        if null_count > 0:
            print(f"[Upgrade] Found {null_count} ai_decision_logs with NULL hyperliquid_environment, fixing...")
            db.execute(text("""
                UPDATE ai_decision_logs
                SET hyperliquid_environment = 'testnet'
                WHERE hyperliquid_environment IS NULL
            """))
            db.commit()
            print(f"[Upgrade] Updated {null_count} records from NULL to 'testnet' (ModelChat fix)")
        else:
            print("[Upgrade] No NULL hyperliquid_environment records found, data is clean")
    except Exception as err:
        db.rollback()
        print(f"[Upgrade] Hyperliquid environment upgrade failed: {err}")
    finally:
        db.close()


def _seed_prompt_templates() -> None:
    db = SessionLocal()
    try:
        from services.prompt_initializer import seed_prompt_templates

        seed_prompt_templates(db)
    finally:
        db.close()


def _setup_system_logger() -> None:
    from services.system_logger import setup_system_logger

    setup_system_logger()


def _apply_sampling_pool_config() -> None:
    try:
        from database.models import GlobalSamplingConfig
        from services.hyperliquid_symbol_service import get_selected_symbols as get_hyperliquid_selected_symbols
        from services.sampling_pool import sampling_pool
        from services.trading_commands import AI_TRADING_SYMBOLS

        db = SessionLocal()
        try:
            symbols = get_hyperliquid_selected_symbols() or AI_TRADING_SYMBOLS
            global_config = db.query(GlobalSamplingConfig).first()
            if global_config and global_config.sampling_depth:
                for symbol in symbols:
                    sampling_pool.set_max_samples(symbol, global_config.sampling_depth)
                print(f"Sampling pool configured: depth={global_config.sampling_depth} for {len(symbols)} symbols")
            else:
                print(f"No global sampling config found, using default depth={sampling_pool.default_max_samples} for {len(symbols)} symbols")
        finally:
            db.close()
    except Exception as err:
        print(f"Failed to load global sampling config: {err}")


def _cleanup_leftover_backfill_tasks() -> None:
    try:
        from database.models import KlineCollectionTask

        db = SessionLocal()
        try:
            deleted_count = db.query(KlineCollectionTask).filter(
                KlineCollectionTask.status.in_(["running", "pending"])
            ).delete(synchronize_session=False)
            db.commit()
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} leftover backfill tasks")
        finally:
            db.close()
    except Exception as err:
        print(f"Failed to clean up backfill tasks: {err}")


def _initialize_services() -> None:
    print("About to initialize services...")
    from services.startup import initialize_services

    initialize_services()
    print("Services initialization completed")


def _warmup_numba() -> None:
    try:
        from database.connection import SessionLocal
        from services.technical_indicators import calculate_indicator

        db = SessionLocal()
        try:
            print("[startup] Warming up numba JIT compilation...")
            calculate_indicator(db, "BTC", "BOLL", "1h")
            print("[startup] Numba warmup completed")
        finally:
            db.close()
    except Exception as err:
        print(f"[startup] Numba warmup failed (non-fatal): {err}")
