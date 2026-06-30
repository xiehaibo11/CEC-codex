"""Hyper AI resource listing and event-contract analysis handlers."""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database.models import SystemConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Query Tools: list resources
# =============================================================================

def execute_list_traders(db: Session, trader_id: int = None) -> str:
    """List all AI Traders with bindings, wallet status, and trading status.
    Pass trader_id to get a single trader's detail."""
    from database.models import (
        Account, HyperliquidWallet, BinanceWallet,
        AccountProgramBinding, AccountPromptBinding,
        TradingProgram, PromptTemplate
    )

    try:
        query = db.query(Account).filter(
            Account.is_active == "true",
            Account.account_type == "AI",
            Account.is_deleted != True
        )
        if trader_id:
            query = query.filter(Account.id == trader_id)
        accounts = query.all()
        if trader_id and not accounts:
            return json.dumps({"error": f"AI Trader {trader_id} not found"})

        traders = []
        for acc in accounts:
            # Wallet info
            hl_wallets = db.query(HyperliquidWallet).filter(
                HyperliquidWallet.account_id == acc.id
            ).all()
            bn_wallets = db.query(BinanceWallet).filter(
                BinanceWallet.account_id == acc.id
            ).all()

            wallet_info = []
            for w in hl_wallets:
                wallet_info.append({
                    "exchange": "hyperliquid",
                    "environment": w.environment
                })
            for w in bn_wallets:
                wallet_info.append({
                    "exchange": "binance",
                    "environment": w.environment
                })

            # Prompt binding
            prompt_binding = None
            pb = db.query(AccountPromptBinding).filter(
                AccountPromptBinding.account_id == acc.id,
                AccountPromptBinding.is_deleted != True
            ).first()
            if pb:
                tpl = db.get(PromptTemplate, pb.prompt_template_id)
                prompt_binding = {
                    "prompt_id": pb.prompt_template_id,
                    "prompt_name": tpl.name if tpl else "Unknown"
                }

            # Program bindings
            prog_bindings = db.query(AccountProgramBinding).filter(
                AccountProgramBinding.account_id == acc.id,
                AccountProgramBinding.is_deleted != True
            ).all()
            program_bindings = []
            for pgb in prog_bindings:
                prog = db.get(TradingProgram, pgb.program_id)
                pool_ids = json.loads(pgb.signal_pool_ids) if pgb.signal_pool_ids else []
                program_bindings.append({
                    "binding_id": pgb.id,
                    "program_id": pgb.program_id,
                    "program_name": prog.name if prog else "Unknown",
                    "exchange": pgb.exchange or "hyperliquid",
                    "signal_pool_ids": pool_ids,
                    "trigger_interval": pgb.trigger_interval,
                    "is_active": pgb.is_active
                })

            traders.append({
                "trader_id": acc.id,
                "name": acc.name,
                "model": acc.model,
                "auto_trading_enabled": acc.auto_trading_enabled == "true",
                "wallets": wallet_info,
                "prompt_binding": prompt_binding,
                "program_bindings": program_bindings
            })

        return json.dumps({"traders": traders, "count": len(traders)}, indent=2)

    except Exception as e:
        logger.error(f"[list_traders] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_prompt_backtests(db: Session, trader_id: int = None, task_id: int = None, limit: int = 10) -> str:
    """List Prompt Backtest tasks or inspect a single task's results."""
    from database.models import Account, PromptBacktestItem, PromptBacktestTask

    def _iso(ts):
        return ts.isoformat() if ts else None

    def _float(value):
        return float(value) if value is not None else None

    def _task_dict(task: PromptBacktestTask, account: Account = None) -> dict:
        return {
            "task_id": task.id,
            "trader_id": task.account_id,
            "trader_name": account.name if account else None,
            "name": task.name,
            "status": task.status,
            "total_count": task.total_count,
            "completed_count": task.completed_count,
            "failed_count": task.failed_count,
            "created_at": _iso(task.created_at),
            "started_at": _iso(task.started_at),
            "finished_at": _iso(task.finished_at),
            "error_message": task.error_message,
        }

    try:
        if task_id:
            task = db.query(PromptBacktestTask).filter(PromptBacktestTask.id == task_id).first()
            if not task:
                return json.dumps({"error": f"Prompt Backtest task {task_id} not found"})

            account = db.get(Account, task.account_id)
            items = db.query(PromptBacktestItem).filter(
                PromptBacktestItem.task_id == task.id
            ).order_by(PromptBacktestItem.original_decision_time.desc()).limit(100).all()

            completed = [item for item in items if item.status == "completed"]
            failed = [item for item in items if item.status == "failed"]
            changed = [item for item in completed if item.decision_changed]
            unchanged = [item for item in completed if not item.decision_changed]

            avoided_loss_count = 0
            avoided_loss_amount = 0.0
            missed_profit_count = 0
            missed_profit_amount = 0.0
            for item in changed:
                pnl = _float(item.original_realized_pnl) or 0.0
                original_op = (item.original_operation or "").lower()
                new_op = (item.new_operation or "").lower()
                if original_op in ("buy", "sell") and new_op == "hold" and pnl < 0:
                    avoided_loss_count += 1
                    avoided_loss_amount += pnl
                if original_op in ("buy", "sell") and new_op == "hold" and pnl > 0:
                    missed_profit_count += 1
                    missed_profit_amount += pnl

            return json.dumps({
                "status": "ok",
                "task": _task_dict(task, account),
                "summary": {
                    "returned_items": len(items),
                    "completed": len(completed),
                    "failed": len(failed),
                    "changed": len(changed),
                    "unchanged": len(unchanged),
                    "avoided_loss_count": avoided_loss_count,
                    "avoided_loss_amount": avoided_loss_amount,
                    "missed_profit_count": missed_profit_count,
                    "missed_profit_amount": missed_profit_amount,
                },
                "items": [
                    {
                        "item_id": item.id,
                        "original_decision_log_id": item.original_decision_log_id,
                        "decision_time": _iso(item.original_decision_time),
                        "status": item.status,
                        "original_operation": item.original_operation,
                        "new_operation": item.new_operation,
                        "symbol": item.original_symbol or item.new_symbol,
                        "original_target_portion": _float(item.original_target_portion),
                        "new_target_portion": _float(item.new_target_portion),
                        "original_realized_pnl": _float(item.original_realized_pnl),
                        "decision_changed": item.decision_changed,
                        "change_type": item.change_type,
                        "error_message": item.error_message,
                    }
                    for item in items
                ],
                "note": "Prompt Backtest replays historical AI Trader prompts with modified prompt text. It compares decisions; it does not simulate full market execution or guarantee future PnL.",
            }, indent=2)

        try:
            limit = int(limit or 10)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 20))

        query = db.query(PromptBacktestTask).order_by(PromptBacktestTask.created_at.desc())
        if trader_id:
            query = query.filter(PromptBacktestTask.account_id == trader_id)

        tasks = query.limit(limit).all()
        accounts = {
            account.id: account
            for account in db.query(Account).filter(Account.id.in_([task.account_id for task in tasks])).all()
        } if tasks else {}

        return json.dumps({
            "status": "ok",
            "count": len(tasks),
            "tasks": [_task_dict(task, accounts.get(task.account_id)) for task in tasks],
            "note": "Pass task_id to inspect item-level Prompt Backtest results.",
        }, indent=2)

    except Exception as e:
        logger.error(f"[get_prompt_backtests] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_predict_event_contract_5m(
    db: Session,
    symbol: str,
    exchange: str = "binance",
    period: str = "1m",
    consensus_threshold: int = 30,
    consensus_mode: str = "ai_confirmed",
    ai_trader_id: int = None,
    enable_l2_features: bool = True,
    min_l2_coverage_pct: float = 96,
    strict_l2_quality: bool = True,
    enable_coinglass_features: bool = False,
    min_coinglass_coverage_pct: float = 96,
    strict_coinglass_quality: bool = True,
) -> str:
    """Run current 5-minute event contract prediction."""
    try:
        from services.event_contract_service import event_contract_service

        result = event_contract_service.predict(db, {
            "symbol": symbol,
            "exchange": exchange or "binance",
            "period": period or "1m",
            "consensus_threshold": consensus_threshold or 30,
            "consensus_mode": consensus_mode or "ai_confirmed",
            "ai_trader_id": ai_trader_id,
            "enable_l2_features": bool(enable_l2_features),
            "min_l2_coverage_pct": min_l2_coverage_pct or 96,
            "strict_l2_quality": bool(strict_l2_quality),
            "enable_coinglass_features": bool(enable_coinglass_features),
            "min_coinglass_coverage_pct": min_coinglass_coverage_pct or 96,
            "strict_coinglass_quality": bool(strict_coinglass_quality),
        })
        return json.dumps({
            "status": "ok",
            "prediction": {
                "symbol": result["symbol"],
                "exchange": result["exchange"],
                "current_time": result["current_time"],
                "current_price": result["current_price"],
                "expiry_time": result["expiry_time"],
                "best_action": result["best_action"],
                "allow_trade": result["allow_trade"],
                "long_5m_probability": result["long_5m_probability"],
                "short_5m_probability": result["short_5m_probability"],
                "hold_probability": result["hold_probability"],
                "market_state": result["market_state"],
                "signal_strength": result["signal_strength"],
                "trap_risk": result["trap_risk"],
                "fake_breakout_risk": result["fake_breakout_risk"],
                "entry_warning": result["entry_warning"],
                "reason": result["reason"],
                "consensus_mode": result.get("consensus_mode"),
                "ai_participated": result.get("ai_participated"),
                "ai_model": result.get("ai_model"),
                "ai_account_name": result.get("ai_account_name"),
            },
            "ai_consensus": result["ai_consensus"],
            "top_ai_decisions": result["ai_decisions"][:10],
            "note": "This predicts only whether the expiry price 5 minutes later is more likely above or below current price. It does not place trades.",
        }, indent=2)
    except Exception as e:
        logger.error(f"[predict_event_contract_5m] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_run_event_contract_backtest(
    db: Session,
    symbol: str,
    start_time: str,
    end_time: str,
    exchange: str = "binance",
    period: str = "1m",
    consensus_threshold: int = 30,
    initial_balance: float = 10000,
    stake_amount: float = 100,
    consensus_mode: str = "ai_confirmed",
    ai_trader_id: int = None,
    max_ai_evaluations: int = 20,
    enable_l2_features: bool = True,
    min_l2_coverage_pct: float = 96,
    strict_l2_quality: bool = True,
    enable_coinglass_features: bool = False,
    min_coinglass_coverage_pct: float = 96,
    strict_coinglass_quality: bool = True,
) -> str:
    """Run and save an event contract backtest."""
    try:
        from services.event_contract_service import event_contract_service

        result = event_contract_service.run_backtest(db, {
            "symbol": symbol,
            "exchange": exchange or "binance",
            "period": period or "1m",
            "start_time": start_time,
            "end_time": end_time,
            "consensus_threshold": consensus_threshold or 30,
            "consensus_mode": consensus_mode or "ai_confirmed",
            "ai_trader_id": ai_trader_id,
            "max_ai_evaluations": max_ai_evaluations or 20,
            "initial_balance": initial_balance or 10000,
            "stake_amount": stake_amount or 100,
            "win_payout_ratio": 0.8,
            "enable_l2_features": bool(enable_l2_features),
            "min_l2_coverage_pct": min_l2_coverage_pct or 96,
            "strict_l2_quality": bool(strict_l2_quality),
            "enable_coinglass_features": bool(enable_coinglass_features),
            "min_coinglass_coverage_pct": min_coinglass_coverage_pct or 96,
            "strict_coinglass_quality": bool(strict_coinglass_quality),
            "return_trade_limit": 20,
        })
        return json.dumps({
            "status": "ok",
            "run_id": result["run_id"],
            "summary": result["summary"],
            "sample_trades": result["trades"][:10],
            "total_trade_logs": result["total_trade_logs"],
            "note": "Backtest uses only K-lines available at each entry timestamp for signal generation, then settles against the configured expiry price. It is an event-contract simulation, not normal futures TP/SL backtesting.",
        }, indent=2)
    except Exception as e:
        db.rollback()
        logger.error(f"[run_event_contract_backtest] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_list_signal_pools(db: Session, pool_id: int = None) -> str:
    """List all signal pools. Pass pool_id for single pool detail."""
    from database.models import SignalPool, SignalDefinition

    try:
        query = db.query(SignalPool).filter(SignalPool.is_deleted != True)
        if pool_id:
            query = query.filter(SignalPool.id == pool_id)
        pools = query.all()
        if pool_id and not pools:
            return json.dumps({"error": f"Signal pool {pool_id} not found"})

        result = []
        for pool in pools:
            # Parse signal_ids
            signal_ids = []
            if pool.signal_ids:
                try:
                    raw = pool.signal_ids
                    signal_ids = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    signal_ids = []

            # Parse symbols
            symbols = []
            if pool.symbols:
                try:
                    raw = pool.symbols
                    symbols = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    symbols = []

            source_type = pool.source_type or "market_signals"
            source_config = {}
            if getattr(pool, "source_config", None):
                try:
                    raw = pool.source_config
                    source_config = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    source_config = {}

            # Get signal details from trigger_condition
            signals = []
            for sid in signal_ids:
                sig = db.query(SignalDefinition).filter(
                    SignalDefinition.id == sid,
                    SignalDefinition.is_deleted != True
                ).first()
                if sig:
                    cond = {}
                    if sig.trigger_condition:
                        try:
                            raw = sig.trigger_condition
                            cond = json.loads(raw) if isinstance(raw, str) else raw
                        except Exception:
                            cond = {"raw": sig.trigger_condition}
                    signals.append({
                        "signal_id": sig.id,
                        "signal_name": sig.signal_name,
                        "trigger_condition": cond,
                        "enabled": sig.enabled
                    })

            result.append({
                "pool_id": pool.id,
                "name": pool.pool_name,
                "symbols": symbols,
                "exchange": pool.exchange or "hyperliquid",
                "source_type": source_type,
                "logic": pool.logic or "OR",
                "enabled": pool.enabled,
                "signals": signals,
                "source_config": source_config if source_type == "wallet_tracking" else {},
            })

        return json.dumps({"signal_pools": result, "count": len(result)}, indent=2)

    except Exception as e:
        logger.error(f"[list_signal_pools] Error: {e}")
        return json.dumps({"error": str(e)})


