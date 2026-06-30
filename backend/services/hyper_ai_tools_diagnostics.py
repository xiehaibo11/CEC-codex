"""Hyper AI diagnostics handlers: AI Trader issue diagnosis."""

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


def execute_diagnose_trader_issues(db: Session, trader_id: int) -> str:
    """Diagnose why an AI Trader is not triggering."""
    from database.models import (
        Account, HyperliquidWallet, BinanceWallet, AccountPromptBinding,
        AccountProgramBinding, AccountStrategyConfig, SignalPool,
        HyperliquidAccountSnapshot, BinanceAccountSnapshot, AIDecisionLog, ProgramExecutionLog
    )

    try:
        # Get account
        account = db.query(Account).filter(Account.id == trader_id, Account.is_deleted != True).first()
        if not account:
            return json.dumps({"error": f"AI Trader with id {trader_id} not found"})

        checks = []
        issues = []

        # Check 1: Trader enabled
        trader_enabled = account.is_active == "true"
        checks.append({"check": "trader_enabled", "passed": trader_enabled})
        if not trader_enabled:
            issues.append("AI Trader is disabled")

        # Check 2: Auto trading enabled
        auto_enabled = account.auto_trading_enabled == "true"
        checks.append({"check": "auto_trading_enabled", "passed": auto_enabled})
        if not auto_enabled:
            issues.append("Auto trading is disabled")

        # Check 3: Strategy bound
        prompt_binding = db.query(AccountPromptBinding).filter(
            AccountPromptBinding.account_id == trader_id,
            AccountPromptBinding.is_deleted != True
        ).first()
        program_binding = db.query(AccountProgramBinding).filter(
            AccountProgramBinding.account_id == trader_id,
            AccountProgramBinding.is_active == True,
            AccountProgramBinding.is_deleted != True
        ).first()

        strategy_bound = prompt_binding is not None or program_binding is not None
        strategy_type = "prompt" if prompt_binding else ("program" if program_binding else None)
        checks.append({"check": "strategy_bound", "passed": strategy_bound, "type": strategy_type})
        if not strategy_bound:
            issues.append("No strategy (prompt or program) bound to this trader")

        # Check 4: Wallet bound and has balance
        strategy_config = db.query(AccountStrategyConfig).filter(
            AccountStrategyConfig.account_id == trader_id
        ).first()

        exchange = strategy_config.exchange if strategy_config else "hyperliquid"
        wallet_bound = False
        wallet_balance = 0
        wallet_env = None

        if exchange == "hyperliquid":
            wallet = db.query(HyperliquidWallet).filter(
                HyperliquidWallet.account_id == trader_id,
                HyperliquidWallet.is_active == "true"
            ).first()
            if wallet:
                wallet_bound = True
                wallet_env = wallet.environment
                snapshot = db.query(HyperliquidAccountSnapshot).filter(
                    HyperliquidAccountSnapshot.account_id == trader_id,
                    HyperliquidAccountSnapshot.environment == wallet.environment
                ).order_by(HyperliquidAccountSnapshot.snapshot_time.desc()).first()
                if snapshot:
                    wallet_balance = float(snapshot.available_balance)
        else:
            wallet = db.query(BinanceWallet).filter(
                BinanceWallet.account_id == trader_id,
                BinanceWallet.is_active == "true"
            ).first()
            if wallet:
                wallet_bound = True
                wallet_env = wallet.environment
                snapshot = db.query(BinanceAccountSnapshot).filter(
                    BinanceAccountSnapshot.account_id == trader_id,
                    BinanceAccountSnapshot.environment == wallet.environment
                ).order_by(BinanceAccountSnapshot.snapshot_time.desc()).first()
                if snapshot:
                    wallet_balance = float(snapshot.available_balance)

        checks.append({
            "check": "wallet_bound",
            "passed": wallet_bound,
            "wallet": f"{exchange}/{wallet_env}" if wallet_bound else None
        })
        if not wallet_bound:
            issues.append(f"No {exchange} wallet bound. Go to Settings → Wallets to configure.")

        checks.append({
            "check": "wallet_balance",
            "passed": wallet_balance > 0,
            "balance": wallet_balance,
            "suggestion": "Deposit funds to wallet" if wallet_balance == 0 else None
        })
        if wallet_balance == 0 and wallet_bound:
            issues.append("Wallet balance is 0. Deposit funds to enable trading.")

        # Check 5: Signal pool or scheduled trigger
        if strategy_config:
            has_signal = bool(strategy_config.signal_pool_ids)
            has_scheduled = strategy_config.scheduled_trigger_enabled
            checks.append({
                "check": "trigger_configured",
                "passed": has_signal or has_scheduled,
                "signal_pools": strategy_config.signal_pool_ids,
                "scheduled_enabled": has_scheduled,
                "interval": strategy_config.trigger_interval
            })
            if not has_signal and not has_scheduled:
                issues.append("No trigger configured (neither signal pool nor scheduled)")

        # Check 6: Recent errors
        recent_errors = []
        ai_errors = db.query(AIDecisionLog).filter(
            AIDecisionLog.account_id == trader_id,
            AIDecisionLog.executed == "false"
        ).order_by(AIDecisionLog.decision_time.desc()).limit(3).all()

        for err in ai_errors:
            recent_errors.append({
                "time": err.decision_time.strftime("%Y-%m-%d %H:%M UTC") if err.decision_time else None,
                "type": "ai_decision",
                "message": err.reason[:100] if err.reason else "Unknown"
            })

        status = "healthy" if not issues else "issues_found"
        summary = issues[0] if issues else "All checks passed. Trader should be operational."

        return json.dumps({
            "trader_id": trader_id,
            "trader_name": account.name,
            "status": status,
            "checks": checks,
            "summary": summary,
            "recent_errors": recent_errors
        }, indent=2)

    except Exception as e:
        logger.error(f"[diagnose_trader_issues] Error: {e}")
        return json.dumps({"error": str(e)})


