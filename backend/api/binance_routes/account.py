"""
Binance account data endpoints.

Balance, positions, account summary, rate-limit, cross-account wallet listing,
trading statistics, and daily-quota usage for non-rebate mainnet accounts.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import time

from database.connection import get_db
from database.models import Account, BinanceWallet, User, AIDecisionLog, ProgramExecutionLog
from api.auth_dependencies import get_current_user, get_account_for_current_user
from utils.encryption import decrypt_private_key
from services.hyperliquid_environment import get_global_trading_mode
from utils.runtime_diagnostics import get_current_thread_count, log_hot_path_delta

from ._shared import (
    router,
    logger,
    _get_client,
    _is_premium_user,
    DAILY_QUOTA_LIMIT,
)


@router.get("/accounts/{account_id}/balance")
def get_balance(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Binance Futures account balance"""
    start_threads = get_current_thread_count()
    start_time = time.monotonic()
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true"
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} wallet configured")

    try:
        client = _get_client(wallet)
        return client.get_balance()
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        log_hot_path_delta(
            logger,
            "binance:balance",
            "/api/binance/accounts/{account_id}/balance",
            start_threads,
            start_time,
            account_id=account_id,
            environment=environment,
        )


@router.get("/accounts/{account_id}/positions")
def get_positions(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Binance Futures open positions"""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true"
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} wallet configured")

    try:
        client = _get_client(wallet)
        return {"positions": client.get_positions()}
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/summary")
def get_account_summary(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Binance account summary for dashboard display."""
    start_threads = get_current_thread_count()
    start_time = time.monotonic()
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true"
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} wallet configured")

    try:
        client = _get_client(wallet)
        balance = client.get_balance()
        rate_limit = client.get_rate_limit()

        total_equity = balance.get("total_equity", 0.0)
        used_margin = balance.get("used_margin", 0.0)
        margin_usage = (used_margin / total_equity * 100) if total_equity > 0 else 0.0

        return {
            "account_id": account_id,
            "environment": environment,
            "exchange": "binance",
            "equity": total_equity,
            "available_balance": balance.get("available_balance", 0.0),
            "used_margin": used_margin,
            "margin_usage": round(margin_usage, 1),
            "unrealized_pnl": balance.get("unrealized_pnl", 0.0),
            "rate_limit": rate_limit,
            "last_updated": balance.get("timestamp"),
        }
    except Exception as e:
        logger.error(f"Failed to get account summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        log_hot_path_delta(
            logger,
            "binance:summary",
            "/api/binance/accounts/{account_id}/summary",
            start_threads,
            start_time,
            account_id=account_id,
            environment=environment,
        )


@router.get("/accounts/{account_id}/rate-limit")
def get_rate_limit(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Binance API rate limit (weight per minute) for an account."""
    if not environment:
        environment = get_global_trading_mode(db)
    get_account_for_current_user(account_id, current_user, db)

    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true"
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail=f"No {environment} wallet configured")

    try:
        client = _get_client(wallet)
        # Make a lightweight call to get fresh weight from response header
        client.get_balance()
        return {"success": True, "rate_limit": client.get_rate_limit()}
    except Exception as e:
        logger.error(f"Failed to get rate limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallets/all")
def get_all_binance_wallets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all Binance wallets across all accounts for manual trading page.
    Returns wallet info with masked API keys.
    """
    wallets = db.query(BinanceWallet).join(
        Account, BinanceWallet.account_id == Account.id
    ).filter(
        BinanceWallet.is_active == "true",
        Account.user_id == current_user.id,
        Account.is_deleted != True,
    ).all()

    result = []
    for wallet in wallets:
        account = db.query(Account).filter(Account.id == wallet.account_id, Account.is_deleted != True).first()
        if not account:
            continue

        # Mask API key for display
        try:
            api_key = decrypt_private_key(wallet.api_key_encrypted)
            if len(api_key) > 8:
                masked_key = f"{api_key[:4]}****{api_key[-4:]}"
            else:
                masked_key = "****"
        except:
            masked_key = "****"

        result.append({
            "wallet_id": wallet.id,
            "account_id": wallet.account_id,
            "account_name": account.name,
            "model": account.model,
            "api_key_masked": masked_key,
            "environment": wallet.environment,
            "is_active": wallet.is_active == "true",
            "max_leverage": wallet.max_leverage,
            "default_leverage": wallet.default_leverage,
        })

    return result


@router.get("/accounts/{account_id}/trading-stats")
def get_binance_trading_stats(
    account_id: int,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get trading statistics for Binance account.

    Returns win rate, profit factor, and other trading metrics based on
    historical trades.

    Args:
        account_id: Account ID
        environment: Optional environment override ("testnet" or "mainnet")
                    If not specified, uses global trading mode
        db: Database session

    Returns:
        Trading statistics including win rate, total trades, PnL metrics
    """
    try:
        get_account_for_current_user(account_id, current_user, db)

        # Determine environment
        if environment is None:
            environment = get_global_trading_mode(db)

        # Get wallet
        wallet = db.query(BinanceWallet).filter(
            BinanceWallet.account_id == account_id,
            BinanceWallet.environment == environment,
            BinanceWallet.is_active == "true"
        ).first()

        if not wallet:
            raise HTTPException(
                status_code=400,
                detail=f"No active Binance wallet for account {account_id} in {environment}"
            )

        client = _get_client(wallet)
        stats = client.get_trading_stats()

        return {
            "success": True,
            "accountId": account_id,
            "environment": environment,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Binance trading stats for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/daily-quota")
def get_daily_quota(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get daily quota usage for Binance mainnet non-rebate accounts.

    Returns:
        - limited: False if not subject to quota (rebate account, premium, or no mainnet wallet)
        - used: Number of decisions/executions today
        - limit: Maximum allowed per day (20)
        - remaining: Remaining quota
    """
    start_threads = get_current_thread_count()
    start_time = time.monotonic()
    get_account_for_current_user(account_id, current_user, db)

    def _log_request() -> None:
        log_hot_path_delta(
            logger,
            "binance:daily-quota",
            "/api/binance/accounts/{account_id}/daily-quota",
            start_threads,
            start_time,
            account_id=account_id,
        )

    # Check if mainnet wallet exists
    mainnet_wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == "mainnet",
        BinanceWallet.is_active == "true"
    ).first()

    # No mainnet wallet - not limited
    if not mainnet_wallet:
        _log_request()
        return {"limited": False, "used": 0, "limit": DAILY_QUOTA_LIMIT, "remaining": DAILY_QUOTA_LIMIT}

    # Rebate working - not limited
    if mainnet_wallet.rebate_working is True:
        _log_request()
        return {"limited": False, "used": 0, "limit": DAILY_QUOTA_LIMIT, "remaining": DAILY_QUOTA_LIMIT}

    # Check premium status
    if _is_premium_user(db):
        _log_request()
        return {"limited": False, "used": 0, "limit": DAILY_QUOTA_LIMIT, "remaining": DAILY_QUOTA_LIMIT}

    # Use UTC midnight for quota reset
    from sqlalchemy import func

    today_start_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Count AIDecisionLog entries (only actual trades: buy/sell/close)
    ai_count = db.query(func.count(AIDecisionLog.id)).filter(
        AIDecisionLog.account_id == account_id,
        AIDecisionLog.exchange == "binance",
        AIDecisionLog.hyperliquid_environment == "mainnet",
        AIDecisionLog.created_at >= today_start_utc,
        AIDecisionLog.operation.in_(["buy", "sell", "close"]),
    ).scalar() or 0

    # Count ProgramExecutionLog entries (only actual trades: buy/sell/close)
    program_count = db.query(func.count(ProgramExecutionLog.id)).filter(
        ProgramExecutionLog.account_id == account_id,
        ProgramExecutionLog.exchange == "binance",
        ProgramExecutionLog.environment == "mainnet",
        ProgramExecutionLog.created_at >= today_start_utc,
        ProgramExecutionLog.decision_action.in_(["buy", "sell", "close"]),
    ).scalar() or 0

    used = ai_count + program_count
    remaining = max(0, DAILY_QUOTA_LIMIT - used)

    # Calculate next reset time (next UTC midnight)
    from datetime import timedelta
    tomorrow_utc = today_start_utc + timedelta(days=1)
    reset_timestamp = int(tomorrow_utc.timestamp())

    result = {
        "limited": True,
        "used": used,
        "limit": DAILY_QUOTA_LIMIT,
        "remaining": remaining,
        "reset_at": reset_timestamp
    }
    _log_request()
    return result
