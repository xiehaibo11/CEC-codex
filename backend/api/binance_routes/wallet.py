"""
Binance wallet setup and configuration endpoints.

Covers credential binding (setup), configuration retrieval, wallet disabling,
rebate-eligibility pre-checks, and limited (non-rebate) binding confirmation.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database.connection import get_db
from database.models import BinanceWallet, User
from api.auth_dependencies import get_current_user, get_account_for_current_user
from utils.encryption import encrypt_private_key, decrypt_private_key
from services.binance_trading_client import BinanceTradingClient
from services.hyperliquid_environment import get_global_trading_mode

from ._shared import (
    router,
    logger,
    _get_client,
    _clear_client_cache,
    _is_premium_user,
    _format_credential_error,
)


# Request/Response Models
class BinanceSetupRequest(BaseModel):
    """Request model for Binance wallet setup"""
    environment: str = Field(..., pattern="^(testnet|mainnet)$")
    api_key: str = Field(..., min_length=10, alias="apiKey")
    secret_key: str = Field(..., min_length=10, alias="secretKey")
    max_leverage: int = Field(20, ge=1, le=125, alias="maxLeverage")
    default_leverage: int = Field(1, ge=1, le=125, alias="defaultLeverage")

    class Config:
        populate_by_name = True


@router.post("/accounts/{account_id}/setup")
def setup_wallet(
    account_id: int,
    request: BinanceSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Setup Binance Futures wallet for an account.
    Encrypts and stores API credentials.

    For mainnet, checks rebate eligibility first. If not eligible,
    returns error code 'REBATE_INELIGIBLE' for frontend to show options.
    """
    get_account_for_current_user(account_id, current_user, db)

    # Validate credentials by testing connection
    try:
        test_client = BinanceTradingClient(
            api_key=request.api_key,
            secret_key=request.secret_key,
            environment=request.environment
        )
        balance = test_client.get_balance()
    except Exception as e:
        detail = _format_credential_error(request.environment, e)
        logger.warning("Binance wallet setup credential validation failed: %s", detail)
        raise HTTPException(status_code=400, detail=detail)

    # For mainnet, check rebate eligibility
    rebate_working = None
    if request.environment == "mainnet":
        rebate_info = test_client.check_rebate_eligibility()
        rebate_working = rebate_info.get("rebate_working", False)

        if not rebate_info.get("eligible", False):
            # Check if user is premium - premium users can proceed without rebate
            is_premium = _is_premium_user(db)
            if not is_premium:
                # Return special response for frontend to handle
                return {
                    "success": False,
                    "error_code": "REBATE_INELIGIBLE",
                    "message": "Account not eligible for API rebate",
                    "rebate_info": rebate_info,
                    "environment": request.environment
                }
            # Premium user - proceed with binding, rebate_working=False

    # Encrypt credentials
    api_key_encrypted = encrypt_private_key(request.api_key)
    secret_key_encrypted = encrypt_private_key(request.secret_key)

    # Check if wallet exists for this account+environment
    existing = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == request.environment
    ).first()

    if existing:
        # Update existing wallet
        existing.api_key_encrypted = api_key_encrypted
        existing.secret_key_encrypted = secret_key_encrypted
        existing.max_leverage = request.max_leverage
        existing.default_leverage = request.default_leverage
        existing.is_active = "true"
        if request.environment == "mainnet":
            existing.rebate_working = rebate_working
        _clear_client_cache(account_id, request.environment)
    else:
        # Create new wallet
        wallet = BinanceWallet(
            account_id=account_id,
            environment=request.environment,
            api_key_encrypted=api_key_encrypted,
            secret_key_encrypted=secret_key_encrypted,
            max_leverage=request.max_leverage,
            default_leverage=request.default_leverage,
            is_active="true",
            rebate_working=rebate_working if request.environment == "mainnet" else None
        )
        db.add(wallet)

    db.commit()

    return {
        "success": True,
        "message": f"Binance {request.environment} wallet configured",
        "environment": request.environment,
        "balance": balance
    }


@router.get("/accounts/{account_id}/config")
def get_config(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Binance wallet configuration for an account"""
    get_account_for_current_user(account_id, current_user, db)
    wallets = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id
    ).all()

    # Helper to mask API key
    def mask_api_key(wallet: BinanceWallet) -> str:
        try:
            api_key = decrypt_private_key(wallet.api_key_encrypted)
            if len(api_key) > 8:
                return f"{api_key[:4]}****{api_key[-4:]}"
            return "****"
        except:
            return "****"

    # Get wallet info for each environment
    testnet_wallet = next((w for w in wallets if w.environment == "testnet" and w.is_active == "true"), None)
    mainnet_wallet = next((w for w in wallets if w.environment == "mainnet" and w.is_active == "true"), None)

    testnet_info = None
    if testnet_wallet:
        testnet_info = {
            "configured": True,
            "api_key_masked": mask_api_key(testnet_wallet),
            "max_leverage": testnet_wallet.max_leverage,
            "default_leverage": testnet_wallet.default_leverage
        }

    mainnet_info = None
    if mainnet_wallet:
        mainnet_info = {
            "configured": True,
            "api_key_masked": mask_api_key(mainnet_wallet),
            "max_leverage": mainnet_wallet.max_leverage,
            "default_leverage": mainnet_wallet.default_leverage
        }

    global_env = get_global_trading_mode(db)

    return {
        "testnet_configured": testnet_wallet is not None,
        "mainnet_configured": mainnet_wallet is not None,
        "testnet": testnet_info,
        "mainnet": mainnet_info,
        "current_environment": global_env
    }


@router.delete("/accounts/{account_id}/wallet")
def delete_wallet(
    account_id: int,
    environment: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable Binance wallet for an account"""
    get_account_for_current_user(account_id, current_user, db)
    wallet = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == environment
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    wallet.is_active = "false"
    _clear_client_cache(account_id, environment)
    db.commit()

    return {"success": True, "message": f"Binance {environment} wallet disabled"}


@router.post("/check-rebate-eligibility")
def check_rebate_eligibility(
    api_key: str,
    secret_key: str,
    environment: str = "mainnet",
    current_user: User = Depends(get_current_user),
):
    """
    Check if a Binance account is eligible for API broker rebate.

    This endpoint can be called before wallet setup to pre-check eligibility.

    Args:
        api_key: Binance API key
        secret_key: Binance secret key
        environment: 'testnet' or 'mainnet' (default mainnet)

    Returns:
        {
            "eligible": bool,
            "rebate_working": bool,  # No prior referral and VIP < 3
            "is_new_user": bool,     # Registered after broker joined
            "message": str
        }
    """
    try:
        client = BinanceTradingClient(
            api_key=api_key,
            secret_key=secret_key,
            environment=environment
        )

        # Verify credentials first
        try:
            client.get_balance()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=_format_credential_error(environment, e),
            )

        # Check rebate eligibility
        result = client.check_rebate_eligibility()

        return {
            "success": True,
            "eligible": result.get("eligible", False),
            "rebate_working": result.get("rebate_working", False),
            "is_new_user": result.get("is_new_user", False),
            "message": "Eligible for rebate" if result.get("eligible") else "Not eligible for rebate"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check rebate eligibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ConfirmLimitedBindingRequest(BaseModel):
    """Request model for confirming limited binding"""
    environment: str = Field("mainnet", pattern="^mainnet$")
    api_key: str = Field(..., min_length=10, alias="apiKey")
    secret_key: str = Field(..., min_length=10, alias="secretKey")
    max_leverage: int = Field(20, ge=1, le=125, alias="maxLeverage")
    default_leverage: int = Field(1, ge=1, le=125, alias="defaultLeverage")

    class Config:
        populate_by_name = True


@router.post("/accounts/{account_id}/confirm-limited-binding")
def confirm_limited_binding(
    account_id: int,
    request: ConfirmLimitedBindingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm binding for non-rebate mainnet account with daily quota limit.
    Called when user chooses "Continue with limited quota" in RebateIneligibleModal.
    """
    get_account_for_current_user(account_id, current_user, db)

    # Validate credentials
    try:
        test_client = BinanceTradingClient(
            api_key=request.api_key,
            secret_key=request.secret_key,
            environment="mainnet"
        )
        balance = test_client.get_balance()
    except Exception as e:
        detail = _format_credential_error("mainnet", e)
        logger.warning("Binance limited binding credential validation failed: %s", detail)
        raise HTTPException(status_code=400, detail=detail)

    # Encrypt credentials
    api_key_encrypted = encrypt_private_key(request.api_key)
    secret_key_encrypted = encrypt_private_key(request.secret_key)

    # Check if wallet exists
    existing = db.query(BinanceWallet).filter(
        BinanceWallet.account_id == account_id,
        BinanceWallet.environment == "mainnet"
    ).first()

    if existing:
        existing.api_key_encrypted = api_key_encrypted
        existing.secret_key_encrypted = secret_key_encrypted
        existing.max_leverage = request.max_leverage
        existing.default_leverage = request.default_leverage
        existing.is_active = "true"
        existing.rebate_working = False  # Explicitly set to False
        _clear_client_cache(account_id, "mainnet")
    else:
        wallet = BinanceWallet(
            account_id=account_id,
            environment="mainnet",
            api_key_encrypted=api_key_encrypted,
            secret_key_encrypted=secret_key_encrypted,
            max_leverage=request.max_leverage,
            default_leverage=request.default_leverage,
            is_active="true",
            rebate_working=False
        )
        db.add(wallet)

    db.commit()

    return {
        "success": True,
        "message": "Binance mainnet wallet configured with daily quota limit",
        "environment": "mainnet",
        "balance": balance,
        "quota_limited": True
    }
