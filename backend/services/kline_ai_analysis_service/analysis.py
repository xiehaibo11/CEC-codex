"""
K-line AI Analysis Service - Chart analysis and history retrieval

Performs AI-powered analysis on K-line chart data (via the AI Trader's
configured model) and reads back persisted analysis history.
"""
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from database.models import Account, KlineAIAnalysisLog
from config.prompt_templates import KLINE_ANALYSIS_PROMPT_TEMPLATE
from services.ai_decision_service import (
    build_chat_completion_endpoints,
    _extract_text_from_message,
    get_max_tokens,
    build_llm_payload,
    build_llm_headers,
    is_reasoning_model,
)

from services.kline_ai_analysis_service.formatting import (
    SafeDict,
    _format_klines_summary,
    _format_positions_summary,
    _format_indicators_summary,
    _format_flow_indicators_summary,
)


logger = logging.getLogger(__name__)


def analyze_kline_chart(
    db: Session,
    account: Account,
    symbol: str,
    period: str,
    klines: List[Dict],
    indicators: Dict[str, Any],
    market_data: Dict[str, Any],
    user_message: Optional[str] = None,
    positions: List[Dict[str, Any]] = None,
    kline_limit: Optional[int] = None,
    user_id: int = 1,
    selected_flow_indicators: List[str] = None,
    exchange: str = "hyperliquid",
) -> Optional[Dict[str, Any]]:
    """
    Perform AI analysis on K-line chart data

    Args:
        db: Database session
        account: AI Trader account with model configuration
        symbol: Trading symbol (e.g., 'BTC')
        period: K-line period (e.g., '1m', '1h', '1d')
        klines: List of K-line data points
        indicators: Dictionary of technical indicators
        market_data: Current market data (price, volume, etc.)
        user_message: Optional custom question from user
        user_id: User ID for logging

    Returns:
        Dictionary with analysis result or None if failed
    """
    analysis_start = time.time()
    logger.info(f"[K-line Analysis] Starting analysis: symbol={symbol}, period={period}, "
               f"account={account.name}, model={account.model}, klines={len(klines)}, "
               f"user_message={'Yes' if user_message else 'No'}")

    if not account.api_key or account.api_key in ["", "default-key-please-update-in-settings", "default"]:
        logger.info(f"[K-line Analysis] Account {account.name} has no valid API key")
        return {"error": "AI Trader has no valid API key configured"}

    try:
        # Build prompt context
        logger.info(f"[K-line Analysis] Building prompt context...")
        now = datetime.utcnow()

        # respect kline_limit if provided
        display_klines = klines[-kline_limit:] if kline_limit else klines

        klines_summary = _format_klines_summary(display_klines)
        indicators_summary = _format_indicators_summary(indicators)
        positions_summary = _format_positions_summary(positions or [])
        flow_indicators_summary = _format_flow_indicators_summary(
            db, symbol, period, selected_flow_indicators or [], exchange=exchange
        )

        context = {
            "symbol": symbol,
            "exchange": exchange,
            "period": period,
            "current_time_utc": now.isoformat() + "Z",
            "current_price": market_data.get("price", "N/A"),
            "change_24h": f"{market_data.get('percentage24h', 0):.2f}",
            "volume_24h": f"{market_data.get('volume24h', 0):,.0f}",
            "open_interest": f"{market_data.get('open_interest', 0):,.0f}",
            "funding_rate": f"{market_data.get('funding_rate', 0) * 100:.4f}",
            "kline_count": len(display_klines),
            "klines_summary": klines_summary,
            "indicators_summary": indicators_summary,
            "flow_indicators_summary": flow_indicators_summary,
            "positions_summary": positions_summary,
            "user_message": user_message if user_message else "No specific question provided. Please provide a general analysis.",
            "additional_instructions": "",
        }

        # Render prompt
        try:
            prompt = KLINE_ANALYSIS_PROMPT_TEMPLATE.format_map(SafeDict(context))
        except Exception as e:
            logger.error(f"Failed to render prompt: {e}")
            prompt = KLINE_ANALYSIS_PROMPT_TEMPLATE

    # Build API request
        # Use unified headers/payload builders (see build_llm_payload in ai_decision_service)
        headers = build_llm_headers("openai", account.api_key)

        payload = build_llm_payload(
            model=account.model,
            messages=[{"role": "user", "content": prompt}],
            api_format="openai",
        )

        # Call AI API
        endpoints = build_chat_completion_endpoints(account.base_url, account.model)
        if not endpoints:
            logger.error(f"No valid API endpoint for account {account.name}")
            return {"error": "Failed to build API endpoint"}

        max_retries = 3
        response = None
        success = False
        request_timeout = 600  # 10 minutes for all models (reasoning models can be very slow)

        logger.info(f"[K-line AI API] Starting AI API call: model={account.model}, timeout={request_timeout}s, "
                   f"endpoints={len(endpoints)}, max_retries={max_retries}")

        for endpoint_idx, endpoint in enumerate(endpoints):
            logger.info(f"[K-line AI API] Trying endpoint {endpoint_idx + 1}/{len(endpoints)}: {endpoint}")

            for attempt in range(max_retries):
                try:
                    api_start = time.time()
                    logger.info(f"[K-line AI API] Sending request (attempt {attempt + 1}/{max_retries})...")

                    response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=request_timeout,
                        verify=False,
                    )

                    api_elapsed = time.time() - api_start
                    logger.info(f"[K-line AI API] Received response in {api_elapsed:.2f}s: status={response.status_code}, "
                               f"content_length={len(response.content) if response.content else 0}")

                    if response.status_code == 200:
                        success = True
                        logger.info(f"[K-line AI API] Success! Total API time: {api_elapsed:.2f}s")
                        break

                    if response.status_code == 429:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        logger.info(f"[K-line AI API] Rate limited (429), waiting {wait_time:.1f}s...")
                        if attempt < max_retries - 1:
                            time.sleep(wait_time)
                            continue

                    logger.info(f"[K-line AI API] API returned error status {response.status_code}: {response.text[:200]}")
                    break

                except requests.Timeout as e:
                    api_elapsed = time.time() - api_start
                    logger.error(f"[K-line AI API] Request timeout after {api_elapsed:.2f}s (configured: {request_timeout}s): {e}")
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        logger.info(f"[K-line AI API] Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    logger.error(f"[K-line AI API] Timeout after {max_retries} attempts")
                    break

                except requests.RequestException as e:
                    api_elapsed = time.time() - api_start
                    logger.error(f"[K-line AI API] Request failed after {api_elapsed:.2f}s: {type(e).__name__}: {e}")
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        logger.info(f"[K-line AI API] Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    logger.error(f"[K-line AI API] Failed after {max_retries} attempts")
                    break

            if success:
                break

        if not success or not response:
            logger.error(f"[K-line AI API] All API endpoints failed for account {account.name}")
            return {"error": "AI API request failed"}

        # Parse response
        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            message = choice.get("message", {})
            raw_content = message.get("content")

            analysis_text = _extract_text_from_message(raw_content)

            if not analysis_text:
                logger.error("Empty content in AI response")
                return {"error": "AI returned empty response"}

            # Save to database
            analysis_log = KlineAIAnalysisLog(
                user_id=user_id,
                account_id=account.id,
                symbol=symbol,
                period=period,
                user_message=user_message,
                model_used=account.model,
                prompt_snapshot=prompt,
                analysis_result=analysis_text,
            )

            db.add(analysis_log)
            db.commit()
            db.refresh(analysis_log)

            total_elapsed = time.time() - analysis_start
            logger.info(f"[K-line Analysis] Analysis completed successfully in {total_elapsed:.2f}s: "
                       f"symbol={symbol}, period={period}, account={account.name}, analysis_id={analysis_log.id}")

            return {
                "success": True,
                "analysis_id": analysis_log.id,
                "symbol": symbol,
                "period": period,
                "model": account.model,
                "trader_name": account.name,
                "analysis": analysis_text,
                "created_at": analysis_log.created_at.isoformat() if analysis_log.created_at else None,
                "prompt": prompt,
            }

        logger.error(f"[K-line Analysis] Unexpected AI response format: {result}")
        return {"error": "Unexpected AI response format"}

    except Exception as e:
        elapsed = time.time() - analysis_start
        logger.error(f"[K-line Analysis] Analysis failed after {elapsed:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return {"error": f"Analysis failed: {str(e)}"}


def get_analysis_history(
    db: Session,
    user_id: int,
    symbol: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get K-line analysis history for a user"""
    query = db.query(KlineAIAnalysisLog).filter(
        KlineAIAnalysisLog.user_id == user_id
    )

    if symbol:
        query = query.filter(KlineAIAnalysisLog.symbol == symbol)

    logs = query.order_by(KlineAIAnalysisLog.created_at.desc()).limit(limit).all()

    return [
        {
            "id": log.id,
            "symbol": log.symbol,
            "period": log.period,
            "model_used": log.model_used,
            "user_message": log.user_message,
            "analysis": log.analysis_result,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
