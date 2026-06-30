"""K-line / factor template variable parsing and context building.

Parses {SYMBOL_klines_*}, factor, flow, and market-data template variables and
builds their populated context values.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.ai_decision_service.indicator_formatting import (
    _format_flow_indicator,
    _format_single_indicator,
)
from services.ai_decision_service.prompt_formatting import _format_market_data_block

logger = logging.getLogger(__name__)


def _parse_kline_indicator_variables(template_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse K-line and indicator variables from prompt template.

    Extracts variables like:
    - {BTC_klines_15m}(200) - K-line data
    - {BTC_RSI14_15m} - Technical indicators
    - {BTC_market_data} - Market ticker data
    - {BTC_CVD_15m} - Market flow indicators (CVD, TAKER, OI, FUNDING, DEPTH)

    Returns grouped by (symbol, period) for optimization:
    {
        ('BTC', '15m'): {
            'klines': {'count': 200},
            'indicators': ['RSI14', 'MACD'],
            'flow_indicators': ['CVD', 'TAKER'],
            'market_data': True
        },
        ('BTC', None): {
            'market_data': True
        }
    }
    """
    # Pattern for K-line variables: {SYMBOL_klines_PERIOD}(COUNT)
    kline_pattern = r'\{([A-Z]+)_klines_(\w+)\}(?:\((\d+)\))?'

    # Pattern for indicator variables: {SYMBOL_INDICATOR_PERIOD}
    # Supports: RSI14, RSI7, MACD, STOCH, MA, EMA, BOLL, ATR14, VWAP, OBV
    indicator_pattern = r'\{([A-Z]+)_(RSI\d+|MACD|STOCH|MA\d*|EMA\d*|BOLL|ATR\d+|VWAP|OBV)_(\w+)\}'

    # Pattern for market flow variables: {SYMBOL_FLOW_PERIOD}
    # Supports: CVD, TAKER, OI, OI_DELTA, FUNDING, DEPTH, IMBALANCE, PRICE_CHANGE, VOLATILITY
    # Note: OI_DELTA must come before OI in the pattern to match correctly
    flow_pattern = r'\{([A-Z]+)_(CVD|TAKER|OI_DELTA|OI|FUNDING|DEPTH|IMBALANCE|PRICE_CHANGE|VOLATILITY)_(\w+)\}'

    # Pattern for market data: {SYMBOL_market_data}
    market_data_pattern = r'\{([A-Z]+)_market_data\}'

    grouped = {}

    def _ensure_key(key):
        if key not in grouped:
            grouped[key] = {
                'klines': None,
                'indicators': [],
                'flow_indicators': [],
                'market_data': False
            }

    # Parse K-line variables
    for match in re.finditer(kline_pattern, template_text):
        symbol = match.group(1)
        if symbol == "SYMBOL":
            continue  # Skip documentation placeholder
        period = match.group(2)
        count = int(match.group(3)) if match.group(3) else 500  # Default 500

        key = (symbol, period)
        _ensure_key(key)
        grouped[key]['klines'] = {'count': count}

        logger.debug(f"Found K-line variable: {symbol}_klines_{period}({count})")

    # Parse indicator variables
    for match in re.finditer(indicator_pattern, template_text):
        symbol = match.group(1)
        if symbol == "SYMBOL":
            continue  # Skip documentation placeholder
        indicator = match.group(2)
        period = match.group(3)

        key = (symbol, period)
        _ensure_key(key)

        # Handle compound indicators (MA, EMA expand to multiple)
        if indicator == 'MA':
            grouped[key]['indicators'].extend(['MA5', 'MA10', 'MA20'])
        elif indicator == 'EMA':
            grouped[key]['indicators'].extend(['EMA20', 'EMA50', 'EMA100'])
        else:
            grouped[key]['indicators'].append(indicator)

        logger.debug(f"Found indicator variable: {symbol}_{indicator}_{period}")

    # Parse market flow variables
    for match in re.finditer(flow_pattern, template_text):
        symbol = match.group(1)
        if symbol == "SYMBOL":
            continue  # Skip documentation placeholder
        flow_indicator = match.group(2)
        period = match.group(3)

        key = (symbol, period)
        _ensure_key(key)
        grouped[key]['flow_indicators'].append(flow_indicator)

        logger.debug(f"Found flow indicator variable: {symbol}_{flow_indicator}_{period}")
    
    # Parse market data variables
    for match in re.finditer(market_data_pattern, template_text):
        symbol = match.group(1)
        if symbol == "SYMBOL":
            continue  # Skip documentation placeholder

        key = (symbol, None)
        _ensure_key(key)
        grouped[key]['market_data'] = True

        logger.debug(f"Found market data variable: {symbol}_market_data")

    # Remove duplicates from indicators and flow_indicators lists
    for key in grouped:
        grouped[key]['indicators'] = list(set(grouped[key]['indicators']))
        grouped[key]['flow_indicators'] = list(set(grouped[key]['flow_indicators']))

    logger.info(f"Parsed {len(grouped)} groups of K-line/indicator/flow/market-data variables")
    return grouped


def _parse_factor_variables(template_text: str) -> List[tuple]:
    """
    Parse factor variables from prompt template.
    Preferred format: {SYMBOL_factor_PERIOD_NAME}
    Legacy format: {SYMBOL_factor_NAME} -> defaults to 5m

    Returns list of (symbol, period, factor_name, var_name) tuples.
    """
    results = []
    seen = set()

    preferred_pattern = r'\{([A-Z][A-Z0-9]*)_factor_(1m|5m|15m|1h|4h|1d)_([A-Za-z][A-Za-z0-9_]*)\}'
    for match in re.finditer(preferred_pattern, template_text):
        symbol = match.group(1)
        period = match.group(2)
        factor_name = match.group(3)
        if symbol == "SYMBOL":
            continue
        key = (symbol, period, factor_name)
        if key not in seen:
            seen.add(key)
            var_name = f"{symbol}_factor_{period}_{factor_name}"
            results.append((symbol, period, factor_name, var_name))

    legacy_pattern = r'\{([A-Z][A-Z0-9]*)_factor_([A-Za-z][A-Za-z0-9_]*)\}'
    for match in re.finditer(legacy_pattern, template_text):
        symbol = match.group(1)
        factor_name = match.group(2)
        if symbol == "SYMBOL":
            continue
        key = (symbol, "5m", factor_name)
        if key not in seen:
            seen.add(key)
            var_name = f"{symbol}_factor_{factor_name}"
            results.append((symbol, "5m", factor_name, var_name))

    return results


def _build_factor_context(
    factor_vars: List[tuple], environment: str, exchange: str
) -> Dict[str, str]:
    """
    Build factor context dict for prompt template variables.
    Each variable resolves to a text block with value + effectiveness.
    """
    from database.connection import SessionLocal
    from program_trader.data_provider import compute_factor_snapshot
    from services.market_data import get_kline_data

    context = {}
    db = SessionLocal()
    try:
        # Sync rule: Prompt factor variables must stay aligned with Program
        # live get_factor() and Program backtest get_factor().
        for symbol, period, factor_name, var_name in factor_vars:
            try:
                market = "binance" if exchange == "binance" else "CRYPTO"
                snapshot = compute_factor_snapshot(
                    db=db,
                    symbol=symbol,
                    factor_name=factor_name,
                    period=period,
                    exchange=exchange,
                    klines_loader=lambda requested_period, count: get_kline_data(
                        symbol,
                        market=market,
                        period=requested_period,
                        count=count,
                        environment=environment,
                        persist=False,
                    ) or [],
                    include_effectiveness=True,
                )

                if snapshot.get("error"):
                    context[var_name] = snapshot["error"]
                    continue

                desc = snapshot.get("description") or ""
                parts = [
                    f"name={factor_name}(id={snapshot.get('id')})",
                    f"period={period}",
                    f"expr={snapshot.get('expression')}",
                ]
                if desc:
                    parts.append(f"desc={desc}")
                value = snapshot.get("value")
                parts.append(f"value={value:.4f}" if value is not None else "value=N/A")
                if snapshot.get("ic") is not None:
                    parts.append(f"IC={float(snapshot['ic']):.4f}")
                if snapshot.get("icir") is not None:
                    parts.append(f"ICIR={float(snapshot['icir']):.2f}")
                if snapshot.get("win_rate") is not None:
                    parts.append(f"WinRate={float(snapshot['win_rate']):.1f}%")
                if snapshot.get("decay_half_life_hours") is not None:
                    dh = int(snapshot["decay_half_life_hours"])
                    parts.append("Persistent" if dh == -1 else f"Decay={dh}h")

                context[var_name] = " | ".join(parts)
            except Exception as e:
                logger.warning(f"Failed to compute factor {factor_name} for {symbol}/{period}: {e}")
                context[var_name] = f"Error computing factor"

    finally:
        db.close()

    return context
def _build_klines_and_indicators_context(
    variable_groups: Dict[str, Dict[str, Any]],
    db: Session,
    environment: str = "mainnet",
    exchange: str = "hyperliquid",
) -> Dict[str, str]:
    """
    Build K-line and indicator context for prompt filling.

    Uses parallel fetching for improved performance when multiple symbols/periods
    are requested. Each (symbol, period) combination is processed concurrently.

    Args:
        variable_groups: Parsed variable groups from _parse_kline_indicator_variables
        db: Database session
        environment: Trading environment (mainnet/testnet)
        exchange: Exchange to use for market data ("hyperliquid" or "binance")

    Returns:
        Dict mapping variable names to formatted strings
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    context = {}

    # If only one group, process directly without threading overhead
    if len(variable_groups) <= 1:
        for (symbol, period), requirements in variable_groups.items():
            result = _process_single_symbol_period(
                symbol,
                period,
                requirements,
                environment,
                exchange,
            )
            context.update(result)
        logger.info(f"Built context with {len(context)} variables for environment: {environment}")
        return context

    # Use thread pool for parallel fetching
    # Limit workers to avoid overwhelming the API
    max_workers = min(len(variable_groups), 4)

    start_time = time.time()
    logger.info(f"[PARALLEL] Starting parallel fetch for {len(variable_groups)} symbol/period groups with {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_key = {}
        for (symbol, period), requirements in variable_groups.items():
            future = executor.submit(
                _process_single_symbol_period,
                symbol, period, requirements, environment, exchange
            )
            future_to_key[future] = (symbol, period)

        # Collect results as they complete
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
                context.update(result)
                logger.debug(f"[PARALLEL] Completed {key[0]} {key[1]}: {len(result)} variables")
            except Exception as e:
                logger.error(f"[PARALLEL] Error processing {key[0]} {key[1]}: {e}", exc_info=True)

    elapsed = time.time() - start_time
    logger.info(f"[PARALLEL] Built context with {len(context)} variables in {elapsed:.2f}s for environment: {environment}")
    return context


def _process_single_symbol_period(
    symbol: str,
    period: Optional[str],
    requirements: Dict[str, Any],
    environment: str,
    exchange: str = "hyperliquid",
) -> Dict[str, str]:
    """
    Process a single (symbol, period) combination and return context variables.

    This function is designed to be called in parallel for different symbol/period
    combinations. It handles K-line fetching, indicator calculation, and formatting.

    Args:
        symbol: Trading symbol (e.g., "BTC")
        period: Time period (e.g., "5m", "1h") or None for market data
        requirements: Dict with 'klines', 'indicators', 'flow_indicators', 'market_data' keys
        environment: Trading environment (mainnet/testnet)
        exchange: Exchange to use for market data ("hyperliquid" or "binance")

    Returns:
        Dict mapping variable names to formatted strings
    """
    from services.market_data import get_kline_data, get_ticker_data

    context = {}
    # Determine market parameter based on exchange
    market_param = "binance" if exchange == "binance" else "CRYPTO"

    try:
        # Handle market data (no period)
        if period is None and requirements.get('market_data'):
            logger.info(f"Processing market data for {symbol} in {environment} (exchange: {exchange})")
            try:
                ticker = get_ticker_data(symbol, market_param, environment)
                if ticker:
                    var_name = f"{symbol}_market_data"
                    context[var_name] = _format_market_data_block(symbol, ticker)
                    logger.debug(f"Added market data variable: {var_name}")
            except Exception as ticker_err:
                logger.warning(f"Failed to get ticker data for {symbol}: {ticker_err}")
            return context

        # Process K-lines and indicators (has period)
        logger.info(f"Processing {symbol} {period} for environment: {environment} (exchange: {exchange})")
        from services.technical_indicators import calculate_indicators
        from services.kline_ai_analysis_service import _format_klines_summary

        # Always fetch 500 candles for accurate indicator calculation
        # Skip persistence for prompt generation (real-time data only, no DB write overhead)
        kline_data = get_kline_data(
            symbol=symbol,
            market=market_param,
            period=period,
            count=500,
            environment=environment,
            persist=False
        )

        if not kline_data:
            logger.warning(f"No K-line data for {symbol} {period} in {environment}")
            return context

        # Process K-line variables
        if requirements.get('klines'):
            count = requirements['klines']['count']
            # Take last N candles for display
            display_klines = kline_data[-count:] if len(kline_data) >= count else kline_data
            formatted_klines = _format_klines_summary(display_klines)

            # Variable name: {BTC_klines_15m}
            var_name = f"{symbol}_klines_{period}"
            context[var_name] = formatted_klines
            logger.debug(f"Added K-line variable: {var_name} ({len(display_klines)} candles)")

        # Calculate and process indicators
        if requirements.get('indicators'):
            indicators_to_calc = requirements['indicators']
            calculated = calculate_indicators(kline_data, indicators_to_calc)

            # Track compound indicators (MA, EMA) for merged output
            ma_indicators = []
            ema_indicators = []

            for indicator_name in indicators_to_calc:
                indicator_data = calculated.get(indicator_name)
                formatted = _format_single_indicator(indicator_name, indicator_data)

                # Variable name: {BTC_RSI14_15m}
                var_name = f"{symbol}_{indicator_name}_{period}"
                context[var_name] = formatted
                logger.debug(f"Added indicator variable: {var_name}")

                # Track for compound output
                if indicator_name.startswith('MA') and indicator_name[2:].isdigit():
                    ma_indicators.append((indicator_name, formatted))
                elif indicator_name.startswith('EMA') and indicator_name[3:].isdigit():
                    ema_indicators.append((indicator_name, formatted))

            # Generate compound MA variable: {BTC_MA_15m}
            if ma_indicators:
                ma_lines = []
                for ind_name, ind_formatted in sorted(ma_indicators):
                    ma_lines.append(f"**{ind_name}**")
                    ma_lines.append(ind_formatted)
                    ma_lines.append("")
                compound_var = f"{symbol}_MA_{period}"
                context[compound_var] = "\n".join(ma_lines).strip()
                logger.debug(f"Added compound MA variable: {compound_var}")

            # Generate compound EMA variable: {BTC_EMA_15m}
            if ema_indicators:
                ema_lines = []
                for ind_name, ind_formatted in sorted(ema_indicators):
                    ema_lines.append(f"**{ind_name}**")
                    ema_lines.append(ind_formatted)
                    ema_lines.append("")
                compound_var = f"{symbol}_EMA_{period}"
                context[compound_var] = "\n".join(ema_lines).strip()
                logger.debug(f"Added compound EMA variable: {compound_var}")

        # Process market flow indicators
        # Note: flow indicators need db session, create a new one for thread safety
        if requirements.get('flow_indicators'):
            from services.market_flow_indicators import get_flow_indicators_for_prompt
            from database.connection import SessionLocal

            flow_indicators_to_calc = requirements['flow_indicators']
            with SessionLocal() as thread_db:
                flow_data = get_flow_indicators_for_prompt(
                    db=thread_db,
                    symbol=symbol,
                    period=period,
                    indicators=flow_indicators_to_calc,
                    exchange=exchange
                )

            for flow_name in flow_indicators_to_calc:
                flow_indicator_data = flow_data.get(flow_name)
                formatted = _format_flow_indicator(flow_name, flow_indicator_data, symbol=symbol, period=period, exchange=exchange)

                # Variable name: {BTC_CVD_15m}
                var_name = f"{symbol}_{flow_name}_{period}"
                context[var_name] = formatted
                logger.debug(f"Added flow indicator variable: {var_name}")

    except Exception as e:
        logger.error(f"Error processing {symbol} {period}: {e}", exc_info=True)

    return context
