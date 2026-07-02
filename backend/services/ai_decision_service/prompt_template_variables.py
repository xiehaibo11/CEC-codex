"""Dynamic template-variable contexts for AI decision prompts."""
import logging
from typing import Any, Dict, Optional, Tuple

from services.ai_decision_service.kline_context import (
    _build_factor_context,
    _build_klines_and_indicators_context,
    _parse_factor_variables,
    _parse_kline_indicator_variables,
)
from services.ai_decision_service.prompt_formatting import _format_market_data_block

logger = logging.getLogger(__name__)


def build_template_variable_contexts(
    template_text: Optional[str],
    realtime_tickers: Dict[str, Dict[str, Any]],
    environment: str,
    exchange: str,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """Build K-line, factor, and news variables requested by a prompt template."""
    if not template_text:
        return {}, {}, {}

    return (
        build_kline_context(template_text, realtime_tickers, environment, exchange),
        build_factor_variable_context(template_text, environment, exchange),
        build_news_variable_context(template_text),
    )


def build_kline_context(
    template_text: str,
    realtime_tickers: Dict[str, Dict[str, Any]],
    environment: str,
    exchange: str,
) -> Dict[str, str]:
    kline_context = {}
    try:
        from database.connection import SessionLocal

        variable_groups = _parse_kline_indicator_variables(template_text)
        if not variable_groups:
            return kline_context

        market_data_groups = {}
        non_market_groups = {}
        for key, requirements in variable_groups.items():
            _symbol, period = key
            if period is None and requirements.get("market_data"):
                market_data_groups[key] = requirements
            else:
                non_market_groups[key] = requirements

        for (symbol, _period), _requirements in market_data_groups.items():
            ticker = realtime_tickers.get(symbol)
            if ticker:
                kline_context[f"{symbol}_market_data"] = _format_market_data_block(symbol, ticker)

        if non_market_groups:
            with SessionLocal() as db:
                kline_context.update(
                    _build_klines_and_indicators_context(
                        non_market_groups,
                        db,
                        environment,
                        exchange,
                    )
                )
        logger.debug("Built K-line context with %s variables", len(kline_context))
    except Exception as err:
        logger.warning("Failed to build K-line context: %s", err, exc_info=True)

    return kline_context


def build_factor_variable_context(
    template_text: str,
    environment: str,
    exchange: str,
) -> Dict[str, str]:
    try:
        factor_vars = _parse_factor_variables(template_text)
        if not factor_vars:
            return {}

        factor_context = _build_factor_context(factor_vars, environment, exchange)
        logger.debug("Built factor context with %s variables", len(factor_context))
        return factor_context
    except Exception as err:
        logger.warning("Failed to build factor context: %s", err, exc_info=True)
        return {}


def build_news_variable_context(template_text: str) -> Dict[str, str]:
    try:
        from database.connection import SessionLocal
        from services.news_prompt_variables import build_news_context

        with SessionLocal() as news_db:
            news_context = build_news_context(template_text, news_db)
        if news_context:
            logger.debug("Built news context with %s variables", len(news_context))
        return news_context
    except Exception as err:
        logger.warning("Failed to build news context: %s", err, exc_info=True)
        return {}
