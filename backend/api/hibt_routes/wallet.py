"""HiBT wallet setup and configuration endpoints."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth_dependencies import get_account_for_current_user, get_current_user
from database.connection import get_db
from database.models import Account, HibtWallet, User
from services.hibt_trading_client import HibtTradingClient
from services.hyperliquid_environment import get_global_trading_mode
from utils.encryption import decrypt_private_key, encrypt_private_key

from ._shared import _clear_client_cache, _format_credential_error, router, logger


class HibtSetupRequest(BaseModel):
    """Request model for HiBT wallet setup."""

    environment: str = Field(..., pattern="^(testnet|mainnet)$")
    access_key: str = Field(..., min_length=6, alias="accessKey")
    secret_key: str = Field(..., min_length=6, alias="secretKey")
    max_leverage: int = Field(20, ge=1, le=125, alias="maxLeverage")
    default_leverage: int = Field(1, ge=1, le=125, alias="defaultLeverage")

    class Config:
        populate_by_name = True


def _mask_access_key(wallet: HibtWallet) -> str:
    try:
        access_key = decrypt_private_key(wallet.access_key_encrypted)
        if len(access_key) > 8:
            return f"{access_key[:4]}****{access_key[-4:]}"
    except Exception:
        pass
    return "****"


@router.post("/accounts/{account_id}/setup")
def setup_wallet(
    account_id: int,
    request: HibtSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Setup HiBT perpetual futures wallet for an account."""
    get_account_for_current_user(account_id, current_user, db)

    try:
        test_client = HibtTradingClient(
            access_key=request.access_key,
            secret_key=request.secret_key,
            environment=request.environment,
        )
        balance = test_client.get_account_state()
    except Exception as e:
        detail = _format_credential_error(request.environment, e)
        logger.warning("HiBT wallet setup credential validation failed: %s", detail)
        raise HTTPException(status_code=400, detail=detail)

    access_key_encrypted = encrypt_private_key(request.access_key)
    secret_key_encrypted = encrypt_private_key(request.secret_key)

    existing = db.query(HibtWallet).filter(
        HibtWallet.account_id == account_id,
        HibtWallet.environment == request.environment,
    ).first()

    if existing:
        existing.access_key_encrypted = access_key_encrypted
        existing.secret_key_encrypted = secret_key_encrypted
        existing.max_leverage = request.max_leverage
        existing.default_leverage = request.default_leverage
        existing.is_active = "true"
        _clear_client_cache(account_id, request.environment)
    else:
        db.add(
            HibtWallet(
                account_id=account_id,
                environment=request.environment,
                access_key_encrypted=access_key_encrypted,
                secret_key_encrypted=secret_key_encrypted,
                max_leverage=request.max_leverage,
                default_leverage=request.default_leverage,
                is_active="true",
            )
        )

    db.commit()

    return {
        "success": True,
        "message": f"HiBT {request.environment} wallet configured",
        "environment": request.environment,
        "balance": balance,
    }


@router.get("/accounts/{account_id}/config")
def get_config(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get HiBT wallet configuration for an account."""
    get_account_for_current_user(account_id, current_user, db)
    wallets = db.query(HibtWallet).filter(HibtWallet.account_id == account_id).all()

    testnet_wallet = next((w for w in wallets if w.environment == "testnet" and w.is_active == "true"), None)
    mainnet_wallet = next((w for w in wallets if w.environment == "mainnet" and w.is_active == "true"), None)

    def wallet_info(wallet: HibtWallet | None):
        if not wallet:
            return None
        return {
            "configured": True,
            "api_key_masked": _mask_access_key(wallet),
            "access_key_masked": _mask_access_key(wallet),
            "max_leverage": wallet.max_leverage,
            "default_leverage": wallet.default_leverage,
        }

    return {
        "testnet_configured": testnet_wallet is not None,
        "mainnet_configured": mainnet_wallet is not None,
        "testnet": wallet_info(testnet_wallet),
        "mainnet": wallet_info(mainnet_wallet),
        "current_environment": get_global_trading_mode(db),
    }


@router.delete("/accounts/{account_id}/wallet")
def delete_wallet(
    account_id: int,
    environment: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable HiBT wallet for an account."""
    get_account_for_current_user(account_id, current_user, db)
    wallet = db.query(HibtWallet).filter(
        HibtWallet.account_id == account_id,
        HibtWallet.environment == environment,
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    wallet.is_active = "false"
    _clear_client_cache(account_id, environment)
    db.commit()

    return {"success": True, "message": f"HiBT {environment} wallet disabled"}


@router.get("/wallets/all")
def get_all_hibt_wallets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all HiBT wallets across all accounts for manual trading page."""
    wallets = db.query(HibtWallet).join(
        Account,
        HibtWallet.account_id == Account.id,
    ).filter(
        HibtWallet.is_active == "true",
        Account.user_id == current_user.id,
        Account.is_deleted.is_(False),
    ).all()

    result = []
    for wallet in wallets:
        account = db.query(Account).filter(
            Account.id == wallet.account_id,
            Account.is_deleted.is_(False),
        ).first()
        if not account:
            continue

        result.append(
            {
                "wallet_id": wallet.id,
                "account_id": wallet.account_id,
                "account_name": account.name,
                "model": account.model,
                "api_key_masked": _mask_access_key(wallet),
                "access_key_masked": _mask_access_key(wallet),
                "environment": wallet.environment,
                "is_active": wallet.is_active == "true",
                "max_leverage": wallet.max_leverage,
                "default_leverage": wallet.default_leverage,
            }
        )

    return result
