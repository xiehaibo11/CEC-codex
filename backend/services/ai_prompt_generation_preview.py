"""
Preview rendering for AI prompt generation tools.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

from services.ai_decision_service import SafeDict, _build_prompt_context
from services.ai_prompt_generation_variables import (
    ACCOUNT_VARIABLES,
    _extract_variables_from_text,
)
from services.market_data import get_ticker_data

logger = logging.getLogger(__name__)


def _execute_preview_prompt(args: Dict[str, Any], request_id: str) -> str:
    """Execute preview_prompt tool - render prompt with real market data."""
    prompt_text = args.get("prompt_text", "")
    asset = args.get("asset", "BTC").upper()

    # Extract variables from prompt
    variables = _extract_variables_from_text(prompt_text)

    resolved_vars = []
    placeholder_vars = []
    failed_vars = []

    # Build minimal context for preview (no account data)
    context = {}

    # System variables
    context["current_time_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    context["output_format"] = '{"action": "hold|buy|sell|close", "symbol": "BTC", ...}'
    context["selected_symbols_detail"] = f"Primary: {asset}"
    context["news_section"] = "[News preview not available in prompt generation mode]"
    context["market_regime_description"] = "[Market regime definitions - available at runtime]"

    # Account placeholders
    context["total_equity"] = "[PLACEHOLDER: Will show actual equity when bound to AI Trader]"
    context["available_balance"] = "[PLACEHOLDER: Will show actual balance when bound to AI Trader]"
    context["margin_usage_percent"] = "[PLACEHOLDER: Will show actual margin usage when bound to AI Trader]"
    context["maintenance_margin"] = "[PLACEHOLDER: Will show actual maintenance margin when bound to AI Trader]"
    context["positions_detail"] = "[PLACEHOLDER: Will show actual positions when bound to AI Trader]"
    context["recent_trades_summary"] = "[PLACEHOLDER: Will show actual trades when bound to AI Trader]"
    context["open_orders_detail"] = "[PLACEHOLDER: Will show actual orders when bound to AI Trader]"
    context["runtime_minutes"] = "[PLACEHOLDER: Will show actual runtime when AI Trader is running]"
    context["trading_environment"] = "[PLACEHOLDER: testnet or mainnet when bound to AI Trader]"
    context["trigger_context"] = "[PLACEHOLDER: Will show signal/scheduled trigger info at runtime]"
    context["trigger_market_regime"] = "[PLACEHOLDER: Will show regime snapshot at trigger time]"

    # Try to get real market data
    try:
        from services.hyperliquid_symbol_service import get_available_symbol_map
        from services.sampling_pool import sampling_pool

        symbol_map = get_available_symbol_map()
        symbols_to_fetch = [asset]

        # Check if other symbols are referenced
        for var in variables:
            match = re.match(r"^([A-Z]+)_", var)
            if match:
                sym = match.group(1)
                if sym not in symbols_to_fetch and sym in symbol_map:
                    symbols_to_fetch.append(sym)

        realtime_tickers = {}

        # Fetch market data for each symbol
        for sym in symbols_to_fetch[:5]:  # Limit to 5 symbols
            try:
                ticker = get_ticker_data(sym, "CRYPTO", environment="mainnet")
                realtime_tickers[sym] = ticker
                price = float(ticker.get("price", 0) or 0)
                context[f"{sym}_market_data"] = f"Symbol: {sym}, Price: ${price:,.2f}"

                # Get sampling data if available
                sample = sampling_pool.get(sym)
                if sample:
                    context[f"{sym}_market_data"] = (
                        f"Symbol: {sym}\n"
                        f"Price: ${sample.get('price', price):,.2f}\n"
                        f"24h Change: {sample.get('change_24h', 'N/A')}%\n"
                        f"Volume: ${sample.get('volume_24h', 'N/A'):,.0f}"
                        if isinstance(sample.get("volume_24h"), (int, float))
                        else f"Volume: {sample.get('volume_24h', 'N/A')}"
                    )
            except Exception as e:
                logger.warning(f"[Preview {request_id}] Failed to get price for {sym}: {e}")
                context[f"{sym}_market_data"] = f"[Failed to fetch {sym} market data: {e}]"
    except Exception as e:
        logger.warning(f"[Preview {request_id}] Market data fetch error: {e}")

    # Build context with indicators using _build_prompt_context
    try:
        # Create minimal account-like object for context building
        class MinimalAccount:
            id = 0
            name = "Preview"

        minimal_portfolio = {"cash": 0, "positions": {}, "total_assets": 0}
        prices = {
            sym: float(ticker.get("price", 0) or 0)
            for sym, ticker in locals().get("realtime_tickers", {}).items()
            if float(ticker.get("price", 0) or 0) > 0
        }

        full_context = _build_prompt_context(
            MinimalAccount(),
            minimal_portfolio,
            prices,
            context.get("news_section", ""),
            None,
            None,
            None,
            db=None,
            symbol_metadata={asset: {"name": asset}},
            symbol_order=[asset],
            environment="mainnet",
            template_text=prompt_text,
        )
        # Merge indicator data into context
        for key, value in full_context.items():
            if key not in context or context[key].startswith("[PLACEHOLDER"):
                context[key] = value
    except Exception as e:
        logger.warning(f"[Preview {request_id}] Context building error: {e}")

    # Render the prompt
    try:
        rendered = prompt_text.format_map(SafeDict(context))
    except Exception as e:
        rendered = f"[Render error: {e}]"

    # Categorize variables
    for var in variables:
        if var in ACCOUNT_VARIABLES:
            placeholder_vars.append(var)
        elif f"{{{var}}}" in rendered or f"[PLACEHOLDER" in context.get(var, "") or "N/A" in str(context.get(var, "")):
            # Check if variable was not resolved
            if var not in context or context.get(var, "").startswith("["):
                failed_vars.append(var)
            else:
                placeholder_vars.append(var)
        else:
            resolved_vars.append(var)

    # Build result
    result = {
        "success": True,
        "rendered_preview": rendered[:2000] + ("..." if len(rendered) > 2000 else ""),
        "preview_length": len(rendered),
        "variables_status": {
            "total": len(variables),
            "resolved": len(resolved_vars),
            "placeholder": len(placeholder_vars),
            "failed": len(failed_vars),
            "resolved_list": sorted(resolved_vars)[:20],
            "placeholder_list": sorted(placeholder_vars),
            "failed_list": sorted(failed_vars),
        },
        "note": "Account-related variables show placeholders. Apply to AI Trader for full preview with real account data.",
    }

    if failed_vars:
        result["warning"] = f"Found {len(failed_vars)} variable(s) that could not be resolved: {', '.join(failed_vars)}"

    return json.dumps(result, indent=2, ensure_ascii=False)
