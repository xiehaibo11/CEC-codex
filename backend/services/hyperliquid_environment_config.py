"""Read-only Hyperliquid environment and leverage configuration helpers."""

import logging
from typing import Dict

from sqlalchemy.orm import Session

from database.models import Account, HyperliquidWallet, SystemConfig

logger = logging.getLogger(__name__)


def get_global_trading_mode(db: Session) -> str:
    """
    Get global Hyperliquid trading mode from system config.

    Returns "testnet" or "mainnet", defaults to "testnet" if not configured.
    """
    config = db.query(SystemConfig).filter(
        SystemConfig.key == "hyperliquid_trading_mode"
    ).first()

    if config and config.value in ["testnet", "mainnet"]:
        return config.value

    return "testnet"


def get_leverage_settings(db: Session, account_id: int, environment: str) -> Dict[str, int]:
    """
    Get leverage settings for an account in a specific environment.

    HyperliquidWallet values are preferred. Account-level values are kept as a
    backward-compatible fallback.
    """
    if environment not in ["testnet", "mainnet"]:
        raise ValueError(f"Invalid environment: {environment}. Must be 'testnet' or 'mainnet'")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account {account_id} not found")

    wallet = db.query(HyperliquidWallet).filter(
        HyperliquidWallet.account_id == account_id,
        HyperliquidWallet.environment == environment,
        HyperliquidWallet.is_active == "true",
    ).first()

    if wallet:
        logger.info(
            "Using leverage from %s wallet for account %s (ID: %s): max=%sx, default=%sx",
            environment,
            account.name,
            account_id,
            wallet.max_leverage,
            wallet.default_leverage,
        )
        return {
            "max_leverage": wallet.max_leverage,
            "default_leverage": wallet.default_leverage,
        }

    max_leverage = account.max_leverage if account.max_leverage is not None else 3
    default_leverage = account.default_leverage if account.default_leverage is not None else 1
    logger.info(
        "No %s wallet found for account %s (ID: %s), using Account table fallback: max=%sx, default=%sx",
        environment,
        account.name,
        account_id,
        max_leverage,
        default_leverage,
    )
    return {
        "max_leverage": max_leverage,
        "default_leverage": default_leverage,
    }
