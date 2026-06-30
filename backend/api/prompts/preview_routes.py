from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from repositories import prompt_repo

from .dependencies import get_db

router = APIRouter()


@router.post("/preview")
def preview_prompt(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """
    Preview filled prompt for selected accounts and symbols.

    Payload:
    {
        "templateText": "...",  # Optional: Use this template text directly (for preview before save)
        "promptTemplateKey": "pro",  # Optional: Fallback to database template if templateText not provided
        "accountIds": [1, 2],
        "symbols": ["BTC", "ETH"],
        "exchanges": ["hyperliquid", "binance"]  # Optional: Array of exchanges (default: ["hyperliquid"])
    }

    Returns:
    {
        "previews": [
            {
                "accountId": 1,
                "accountName": "Trader-A",
                "exchange": "hyperliquid",
                "filledPrompt": "..."
            },
            ...
        ]
    }
    """
    from services.ai_decision_service import (
        _build_prompt_context,
        _get_portfolio_data,
        SafeDict,
        SUPPORTED_SYMBOLS,
    )
    from services.market_data import get_last_price
    from services.news_feed import fetch_latest_news
    from services.sampling_pool import sampling_pool
    from database.models import Account
    import logging
    from services.hyperliquid_symbol_service import (
        get_available_symbol_map as get_hyperliquid_symbol_map,
        get_selected_symbols as get_hyperliquid_selected_symbols,
    )
    from services.binance_symbol_service import (
        get_selected_symbols as get_binance_selected_symbols,
    )

    logger = logging.getLogger(__name__)

    # Priority: use templateText if provided (for preview before save), otherwise query from database
    template_text = payload.get("templateText")
    prompt_key = payload.get("promptTemplateKey", "default")
    account_ids = payload.get("accountIds", [])
    # Support both old "exchange" (string) and new "exchanges" (array) format
    exchanges = payload.get("exchanges") or [payload.get("exchange", "hyperliquid")]

    raw_symbols = [str(sym).upper() for sym in payload.get("symbols", []) if sym]
    requested_symbols: List[str] = []
    seen_requested = set()
    for symbol in raw_symbols:
        if symbol and symbol not in seen_requested:
            seen_requested.add(symbol)
            requested_symbols.append(symbol)

    base_symbol_order = list(SUPPORTED_SYMBOLS.keys())
    hyper_watchlist = get_hyperliquid_selected_symbols()
    hyper_symbol_map = get_hyperliquid_symbol_map()

    if not account_ids:
        raise HTTPException(status_code=400, detail="At least one account must be selected")

    # Get template text: use provided templateText or query from database
    if not template_text:
        # Fallback: query from database using promptTemplateKey
        template = prompt_repo.get_template_by_key(db, prompt_key)
        if not template:
            raise HTTPException(status_code=404, detail=f"Prompt template '{prompt_key}' not found")
        template_text = template.template_text
        logger.info(f"Preview: Using database template '{prompt_key}'")
    else:
        logger.info(f"Preview: Using provided templateText (length: {len(template_text)})")

    # Get news
    try:
        news_summary = fetch_latest_news()
        news_section = news_summary if news_summary else "No recent CoinJournal news available."
    except Exception as err:
        logger.warning(f"Failed to fetch news: {err}")
        news_section = "No recent CoinJournal news available."

    # Import multi-symbol sampling data builder
    from services.ai_decision_service import _build_multi_symbol_sampling_data

    previews = []

    for account_id in account_ids:
        account = db.get(Account, account_id)
        if not account:
            logger.warning(f"Account {account_id} not found, skipping")
            continue

        # Generate preview for each selected exchange
        for exchange in exchanges:
            try:
                preview_result = _generate_single_preview(
                    db=db,
                    account=account,
                    exchange=exchange,
                    template_text=template_text,
                    news_section=news_section,
                    requested_symbols=requested_symbols,
                    base_symbol_order=base_symbol_order,
                    hyper_watchlist=hyper_watchlist,
                    hyper_symbol_map=hyper_symbol_map,
                    sampling_pool=sampling_pool,
                    logger=logger,
                    SUPPORTED_SYMBOLS=SUPPORTED_SYMBOLS,
                    get_last_price=get_last_price,
                    _get_portfolio_data=_get_portfolio_data,
                    _build_prompt_context=_build_prompt_context,
                    _build_multi_symbol_sampling_data=_build_multi_symbol_sampling_data,
                    SafeDict=SafeDict,
                )
                previews.append(preview_result)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to generate preview for {account.name} ({exchange}): {e}")
                previews.append({
                    "accountId": account.id,
                    "accountName": account.name,
                    "exchange": exchange,
                    "symbols": requested_symbols if requested_symbols else [],
                    "filledPrompt": f"Error generating preview: {str(e)[:200]}",
                })

    return {"previews": previews}


def _generate_single_preview(
    db,
    account,
    exchange: str,
    template_text: str,
    news_section: str,
    requested_symbols,
    base_symbol_order,
    hyper_watchlist,
    hyper_symbol_map,
    sampling_pool,
    logger,
    SUPPORTED_SYMBOLS,
    get_last_price,
    _get_portfolio_data,
    _build_prompt_context,
    _build_multi_symbol_sampling_data,
    SafeDict,
) -> dict:
    """Generate a single preview for one account and one exchange."""
    from typing import Dict

    hyperliquid_state = None
    binance_state = None
    portfolio = None
    environment = "mainnet"

    if exchange == "binance":
        from services.binance_trading_client import BinanceTradingClient
        from database.models import BinanceWallet
        from utils.encryption import decrypt_private_key
        from services.hyperliquid_environment import get_global_trading_mode

        # Get global trading environment (same as Hyperliquid)
        binance_environment = get_global_trading_mode(db)
        environment = binance_environment

        binance_wallet = db.query(BinanceWallet).filter(
            BinanceWallet.account_id == account.id,
            BinanceWallet.environment == binance_environment,
            BinanceWallet.is_active == "true"
        ).first()

        # IMPORTANT: If wallet not configured or API error, use N/A values but continue prompt generation.
        # Any data fetch error should NOT block prompt generation - just show N/A for that section.
        if not binance_wallet or not binance_wallet.api_key_encrypted:
            logger.warning(f"No Binance {binance_environment} wallet for {account.name}, using N/A values")
            portfolio = {
                'cash': 'N/A',
                'frozen_cash': 'N/A',
                'positions': {},
                'total_assets': 'N/A'
            }
            binance_state = None
        else:
            try:
                api_key = decrypt_private_key(binance_wallet.api_key_encrypted)
                secret_key = decrypt_private_key(binance_wallet.secret_key_encrypted)

                client = BinanceTradingClient(
                    api_key=api_key,
                    secret_key=secret_key,
                    environment=binance_environment
                )

                account_state = client.get_account_state(db)
                positions = client.get_positions()

                portfolio = {
                    'cash': account_state['available_balance'],
                    'frozen_cash': account_state.get('used_margin', 0),
                    'positions': {},
                    'total_assets': account_state['total_equity']
                }

                for pos in positions:
                    symbol = pos.get('coin') or pos.get('symbol', '')
                    portfolio['positions'][symbol] = {
                        'quantity': pos.get('szi') or pos.get('size', 0),
                        'avg_cost': pos.get('entry_px') or pos.get('entry_price', 0),
                        'current_value': pos.get('position_value', 0),
                        'unrealized_pnl': pos.get('unrealized_pnl', 0),
                        'leverage': pos.get('leverage', 1)
                    }

                binance_state = {
                    'total_equity': account_state['total_equity'],
                    'available_balance': account_state['available_balance'],
                    'used_margin': account_state.get('used_margin', 0),
                    'margin_usage_percent': account_state.get('margin_usage_percent', 0),
                    'maintenance_margin': account_state.get('maintenance_margin', 0),
                    'positions': positions
                }

                logger.info(f"Preview: Using Binance {environment} data for {account.name}")
            except Exception as bn_err:
                # API error - use N/A values, but continue with prompt generation
                logger.warning(f"Failed to get Binance data for {account.name}: {bn_err}, using N/A values")
                portfolio = {
                    'cash': 'N/A',
                    'frozen_cash': 'N/A',
                    'positions': {},
                    'total_assets': 'N/A'
                }
                binance_state = None

    else:
        # Hyperliquid exchange
        from services.hyperliquid_environment import get_global_trading_mode, get_hyperliquid_client
        from database.models import HyperliquidWallet

        hyperliquid_environment = get_global_trading_mode(db)
        environment = hyperliquid_environment

        if hyperliquid_environment in ["testnet", "mainnet"]:
            # IMPORTANT: Check wallet exists BEFORE calling get_hyperliquid_client()
            # If wallet not configured, use N/A values but still generate the prompt.
            # Any data fetch error should NOT block prompt generation.
            wallet = db.query(HyperliquidWallet).filter(
                HyperliquidWallet.account_id == account.id,
                HyperliquidWallet.environment == hyperliquid_environment,
                HyperliquidWallet.is_active == "true"
            ).first()

            if not wallet or not wallet.private_key_encrypted:
                # No wallet - use N/A values, but continue with prompt generation
                logger.warning(f"No Hyperliquid {hyperliquid_environment} wallet for {account.name}, using N/A values")
                portfolio = {
                    'cash': 'N/A',
                    'frozen_cash': 'N/A',
                    'positions': {},
                    'total_assets': 'N/A'
                }
                hyperliquid_state = None
            else:
                try:
                    client = get_hyperliquid_client(db, account.id, override_environment=hyperliquid_environment)
                    account_state = client.get_account_state(db)
                    positions = client.get_positions(db, include_timing=True)

                    portfolio = {
                        'cash': account_state['available_balance'],
                        'frozen_cash': account_state.get('used_margin', 0),
                        'positions': {},
                        'total_assets': account_state['total_equity']
                    }

                    for pos in positions:
                        symbol = pos['coin']
                        portfolio['positions'][symbol] = {
                            'quantity': pos['szi'],
                            'avg_cost': pos['entry_px'],
                            'current_value': pos['position_value'],
                            'unrealized_pnl': pos['unrealized_pnl'],
                            'leverage': pos['leverage']
                        }

                    hyperliquid_state = {
                        'total_equity': account_state['total_equity'],
                        'available_balance': account_state['available_balance'],
                        'used_margin': account_state.get('used_margin', 0),
                        'margin_usage_percent': account_state['margin_usage_percent'],
                        'maintenance_margin': account_state.get('maintenance_margin', 0),
                        'positions': positions
                    }

                    logger.info(f"Preview: Using Hyperliquid {hyperliquid_environment} data for {account.name}")
                except Exception as hl_err:
                    # API error - use N/A values, but continue with prompt generation
                    logger.warning(f"Failed to get Hyperliquid data for {account.name}: {hl_err}, using N/A values")
                    portfolio = {
                        'cash': 'N/A',
                        'frozen_cash': 'N/A',
                        'positions': {},
                        'total_assets': 'N/A'
                    }
                    hyperliquid_state = None
        else:
            # Environment not recognized - use N/A
            portfolio = {
                'cash': 'N/A',
                'frozen_cash': 'N/A',
                'positions': {},
                'total_assets': 'N/A'
            }
            hyperliquid_state = None

    # Determine active symbols + metadata
    market_param = "binance" if exchange == "binance" else "CRYPTO"

    if exchange == "binance":
        from services.binance_symbol_service import get_selected_symbols as get_binance_selected_symbols
        binance_watchlist = get_binance_selected_symbols()
        active_symbols = requested_symbols or binance_watchlist or base_symbol_order
        symbol_metadata_map = {sym: SUPPORTED_SYMBOLS.get(sym, sym) for sym in active_symbols}
        logger.info(f"[Prompt Preview] Using Binance watchlist: {binance_watchlist}, active: {active_symbols}")
    elif environment in ["testnet", "mainnet"]:
        active_symbols = requested_symbols or hyper_watchlist or base_symbol_order
        symbol_metadata_map = {}
        for sym in active_symbols:
            entry = dict(hyper_symbol_map.get(sym, {}))
            entry.setdefault("name", sym)
            symbol_metadata_map[sym] = entry
    else:
        active_symbols = requested_symbols or base_symbol_order
        symbol_metadata_map = {sym: SUPPORTED_SYMBOLS.get(sym, sym) for sym in active_symbols}

    if not active_symbols:
        active_symbols = base_symbol_order

    prices: Dict[str, float] = {}
    for sym in active_symbols:
        try:
            prices[sym] = get_last_price(sym, market_param, environment=environment or "mainnet")
        except Exception as err:
            logger.warning(f"Failed to get price for {sym}: {err}")
            prices[sym] = 0.0

    # Get sampling interval
    sampling_interval = None
    try:
        from database.models import GlobalSamplingConfig
        config = db.query(GlobalSamplingConfig).first()
        if config:
            sampling_interval = config.sampling_interval
    except Exception:
        pass

    sampling_data = _build_multi_symbol_sampling_data(active_symbols, sampling_pool, sampling_interval)

    sample_trigger_context = {
        "trigger_type": "signal",
        "signal_pool_id": 1,
        "signal_pool_name": "OI Surge Monitor",
        "pool_logic": "OR",
        "triggered_signals": [
            {
                "signal_name": "OI Delta Alert",
                "description": "Open Interest increased significantly",
                "metric": "oi_delta",
                "operator": ">",
                "threshold": 2.0,
                "current_value": 2.5,
                "time_window": "15m",
            }
        ],
        "trigger_symbol": "BTC",
    }

    exchange_state = binance_state if exchange == "binance" else hyperliquid_state

    context = _build_prompt_context(
        account,
        portfolio,
        prices,
        news_section,
        None,
        None,
        exchange_state,
        db=db,
        symbol_metadata=symbol_metadata_map,
        symbol_order=active_symbols,
        sampling_interval=sampling_interval,
        environment=environment or "mainnet",
        template_text=template_text,
        trigger_context=sample_trigger_context,
        exchange=exchange,
    )
    context["sampling_data"] = sampling_data

    try:
        filled_prompt = template_text.format_map(SafeDict(context))
    except Exception as err:
        logger.error(f"Failed to fill prompt for {account.name}: {err}")
        filled_prompt = f"Error filling prompt: {err}"

    return {
        "accountId": account.id,
        "accountName": account.name,
        "exchange": exchange,
        "symbols": requested_symbols if requested_symbols else [],
        "filledPrompt": filled_prompt,
    }
