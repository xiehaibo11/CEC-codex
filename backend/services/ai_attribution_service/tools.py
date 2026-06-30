"""Tool implementations for AI Attribution Analysis.

Each `_tool_*` function queries trading performance data and returns a JSON string.
`_execute_tool` dispatches a tool call by name.
"""

import json
import logging
from typing import Dict, List
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models import Account, AIDecisionLog, SignalPool
from database.snapshot_connection import SnapshotSessionLocal
from database.snapshot_models import HyperliquidTrade

logger = logging.getLogger(__name__)


def _execute_tool(db: Session, tool_name: str, args: Dict) -> str:
    """Execute a tool and return JSON result string"""
    try:
        if tool_name == "list_ai_accounts":
            return _tool_list_ai_accounts(db)
        elif tool_name == "get_attribution_summary":
            return _tool_get_attribution_summary(db, args)
        elif tool_name == "get_account_strategy":
            return _tool_get_account_strategy(db, args)
        elif tool_name == "get_prompt_template":
            return _tool_get_prompt_template(db, args)
        elif tool_name == "get_signal_pool_config":
            return _tool_get_signal_pool_config(db, args)
        elif tool_name == "get_trade_decision_chain":
            return _tool_get_trade_decision_chain(db, args)
        elif tool_name == "suggest_prompt_modification":
            return _tool_suggest_prompt_modification(args)
        elif tool_name == "get_factor_attribution":
            return _tool_get_factor_attribution(db, args)
        elif tool_name == "query_factors":
            from services.hyper_ai_tools import execute_query_factors
            return execute_query_factors(db, args.get("exchange", "hyperliquid"), args.get("symbol"), forward_period=args.get("forward_period", "4h"))
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        logger.error(f"Tool execution error: {tool_name}: {e}")
        return json.dumps({"error": str(e)})


def _get_fees_for_decisions(decisions: List[AIDecisionLog]) -> Dict[int, float]:
    """Batch query HyperliquidTrade to get total fees for each decision."""
    if not decisions:
        return {}

    # Collect all order IDs (main, tp, sl)
    order_ids = set()
    decision_orders: Dict[int, List[str]] = {}

    for d in decisions:
        orders = []
        if d.hyperliquid_order_id:
            order_ids.add(d.hyperliquid_order_id)
            orders.append(d.hyperliquid_order_id)
        if d.tp_order_id:
            order_ids.add(d.tp_order_id)
            orders.append(d.tp_order_id)
        if d.sl_order_id:
            order_ids.add(d.sl_order_id)
            orders.append(d.sl_order_id)
        decision_orders[d.id] = orders

    if not order_ids:
        return {d.id: 0.0 for d in decisions}

    # Batch query fees from HyperliquidTrade
    fee_map: Dict[str, float] = {}
    try:
        snapshot_db = SnapshotSessionLocal()
        trades = snapshot_db.query(HyperliquidTrade).filter(
            HyperliquidTrade.order_id.in_(list(order_ids))
        ).all()
        for t in trades:
            if t.order_id:
                fee_map[str(t.order_id)] = float(t.fee or 0)
        snapshot_db.close()
    except Exception as e:
        logger.warning(f"Failed to fetch fees from HyperliquidTrade: {e}")

    # Calculate total fee for each decision
    result: Dict[int, float] = {}
    for d in decisions:
        total_fee = 0.0
        for oid in decision_orders.get(d.id, []):
            total_fee += fee_map.get(oid, 0.0)
        result[d.id] = total_fee

    return result


def _tool_get_attribution_summary(db: Session, args: Dict) -> str:
    """Get trading performance summary"""
    account_id = args.get("account_id", 0)
    exchange = args.get("exchange")
    environment = args.get("environment")
    days = args.get("days", 30)

    if not exchange:
        return json.dumps({"error": "exchange is required (hyperliquid or binance)"})

    if not environment:
        return json.dumps({"error": "environment is required (testnet or mainnet)"})

    start_date = datetime.now() - timedelta(days=days)

    # Build query with exchange and environment filter
    # Only include trades with non-zero PnL (exclude opening trades)
    query = db.query(AIDecisionLog).filter(
        AIDecisionLog.operation.in_(["buy", "sell", "close"]),
        AIDecisionLog.executed == "true",
        AIDecisionLog.realized_pnl.isnot(None),
        AIDecisionLog.realized_pnl != 0,  # Exclude opening trades (no settled PnL)
        AIDecisionLog.created_at >= start_date,
        AIDecisionLog.exchange == exchange,
        AIDecisionLog.hyperliquid_environment == environment
    )

    if account_id > 0:
        query = query.filter(AIDecisionLog.account_id == account_id)

    decisions = query.all()

    if not decisions:
        return json.dumps({"message": "No trading data found for the specified period"})

    # Get fees for all decisions
    fee_map = _get_fees_for_decisions(decisions)

    # Calculate metrics
    total_trades = len(decisions)
    wins = sum(1 for d in decisions if d.realized_pnl and float(d.realized_pnl) > 0)
    losses = sum(1 for d in decisions if d.realized_pnl and float(d.realized_pnl) < 0)
    total_pnl = sum(float(d.realized_pnl or 0) for d in decisions)
    total_fees = sum(fee_map.get(d.id, 0.0) for d in decisions)
    net_pnl = total_pnl - total_fees

    # By operation
    by_operation = {}
    for d in decisions:
        op = d.operation
        if op not in by_operation:
            by_operation[op] = {"count": 0, "wins": 0, "pnl": 0, "fees": 0}
        by_operation[op]["count"] += 1
        by_operation[op]["pnl"] += float(d.realized_pnl or 0)
        by_operation[op]["fees"] += fee_map.get(d.id, 0.0)
        if d.realized_pnl and float(d.realized_pnl) > 0:
            by_operation[op]["wins"] += 1

    # By symbol
    by_symbol = {}
    for d in decisions:
        sym = d.symbol or "UNKNOWN"
        if sym not in by_symbol:
            by_symbol[sym] = {"count": 0, "wins": 0, "pnl": 0, "fees": 0}
        by_symbol[sym]["count"] += 1
        by_symbol[sym]["pnl"] += float(d.realized_pnl or 0)
        by_symbol[sym]["fees"] += fee_map.get(d.id, 0.0)
        if d.realized_pnl and float(d.realized_pnl) > 0:
            by_symbol[sym]["wins"] += 1

    return json.dumps({
        "period_days": days,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": f"{(wins/total_trades*100):.1f}%" if total_trades > 0 else "N/A",
        "total_pnl": round(total_pnl, 2),
        "total_fees": round(total_fees, 2),
        "net_pnl": round(net_pnl, 2),
        "by_operation": by_operation,
        "by_symbol": by_symbol
    })


def _tool_get_account_strategy(db: Session, args: Dict) -> str:
    """Get account strategy configuration"""
    from database.models import AccountStrategyConfig
    from repositories.strategy_repo import parse_signal_pool_ids

    account_id = args.get("account_id")
    if not account_id:
        return json.dumps({"error": "account_id is required"})

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return json.dumps({"error": f"Account {account_id} not found"})

    # Get prompt binding for prompt template info
    prompt_binding = getattr(account, 'prompt_binding', None)
    prompt_info = None
    if prompt_binding and prompt_binding.prompt_template:
        prompt_info = {
            "id": prompt_binding.prompt_template.id,
            "name": prompt_binding.prompt_template.name
        }

    # Get signal pool binding from AccountStrategyConfig (correct source)
    strategy = db.query(AccountStrategyConfig).filter(
        AccountStrategyConfig.account_id == account_id
    ).first()

    signal_pool_ids = []
    signal_pool_names = []
    if strategy:
        signal_pool_ids = parse_signal_pool_ids(strategy)
        # Query pool names
        if signal_pool_ids:
            result = db.execute(
                text("SELECT id, pool_name FROM signal_pools WHERE id = ANY(:ids)"),
                {"ids": signal_pool_ids}
            ).fetchall()
            pool_name_map = {row[0]: row[1] for row in result}
            signal_pool_names = [pool_name_map.get(pid) for pid in signal_pool_ids if pool_name_map.get(pid)]

    return json.dumps({
        "account_id": account.id,
        "name": account.name,
        "model": account.model,
        "auto_trading_enabled": account.auto_trading_enabled,
        "hyperliquid_enabled": account.hyperliquid_enabled,
        "hyperliquid_environment": account.hyperliquid_environment,
        "max_leverage": account.max_leverage,
        "default_leverage": account.default_leverage,
        "prompt_template": prompt_info,
        "signal_pool_ids": signal_pool_ids if signal_pool_ids else None,
        "signal_pool_names": signal_pool_names if signal_pool_names else None,
        "note": "Account not bound to any signal pool" if not signal_pool_ids else None
    })


def _tool_get_prompt_template(db: Session, args: Dict) -> str:
    """Get prompt template content for an account"""
    account_id = args.get("account_id")
    if not account_id:
        return json.dumps({"error": "account_id is required"})

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return json.dumps({"error": f"Account {account_id} not found"})

    if not account.prompt_binding or not account.prompt_binding.prompt_template:
        return json.dumps({"message": "No prompt template bound to this account"})

    template = account.prompt_binding.prompt_template
    return json.dumps({
        "id": template.id,
        "name": template.name,
        "content": template.template_text,  # Return full content without truncation
        "is_system": template.is_system
    })


def _tool_get_signal_pool_config(db: Session, args: Dict) -> str:
    """Get signal pool configuration with detailed signal trigger conditions"""
    pool_id = args.get("pool_id")
    if not pool_id:
        return json.dumps({"error": "pool_id is required"})

    pool = db.query(SignalPool).filter(SignalPool.id == pool_id).first()
    if not pool:
        return json.dumps({"error": f"Signal pool {pool_id} not found"})

    # Parse signal_ids JSON
    signal_ids = []
    if pool.signal_ids:
        try:
            signal_ids = json.loads(pool.signal_ids) if isinstance(pool.signal_ids, str) else pool.signal_ids
        except:
            pass

    # Parse symbols JSON
    symbols = []
    if pool.symbols:
        try:
            symbols = json.loads(pool.symbols) if isinstance(pool.symbols, str) else pool.symbols
        except:
            pass

    # Fetch detailed signal configurations
    signals_detail = []
    if signal_ids:
        result = db.execute(
            text("SELECT id, signal_name, description, trigger_condition FROM signal_definitions WHERE id = ANY(:ids)"),
            {"ids": signal_ids}
        ).fetchall()
        for row in result:
            trigger_condition = row[3]
            if isinstance(trigger_condition, str):
                try:
                    trigger_condition = json.loads(trigger_condition)
                except:
                    pass
            signals_detail.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "trigger_condition": trigger_condition
            })

    return json.dumps({
        "id": pool.id,
        "name": pool.pool_name,
        "symbols": symbols,
        "logic": pool.logic,
        "enabled": pool.enabled,
        "signal_ids": signal_ids,
        "signals": signals_detail
    })


def _tool_get_trade_decision_chain(db: Session, args: Dict) -> str:
    """Get detailed trade decision chain"""
    account_id = args.get("account_id")
    exchange = args.get("exchange")
    environment = args.get("environment")
    limit = args.get("limit", 10)
    filter_type = args.get("filter_type", "all")

    if not account_id:
        return json.dumps({"error": "account_id is required"})

    if not exchange:
        return json.dumps({"error": "exchange is required (hyperliquid or binance)"})

    if not environment:
        return json.dumps({"error": "environment is required (testnet or mainnet)"})

    query = db.query(AIDecisionLog).filter(
        AIDecisionLog.account_id == account_id,
        AIDecisionLog.executed == "true",
        AIDecisionLog.realized_pnl.isnot(None),
        AIDecisionLog.exchange == exchange,
        AIDecisionLog.hyperliquid_environment == environment
    )

    if filter_type == "wins":
        query = query.filter(AIDecisionLog.realized_pnl > 0)
    elif filter_type == "losses":
        query = query.filter(AIDecisionLog.realized_pnl < 0)

    decisions = query.order_by(AIDecisionLog.created_at.desc()).limit(limit).all()

    # Get fees for all decisions
    fee_map = _get_fees_for_decisions(decisions)

    trades = []
    for d in decisions:
        pnl = float(d.realized_pnl) if d.realized_pnl else 0
        fee = fee_map.get(d.id, 0.0)

        # Parse prices from decision_snapshot
        entry_price = None
        tp_price = None
        sl_price = None
        if d.decision_snapshot:
            try:
                snapshot = json.loads(d.decision_snapshot) if isinstance(d.decision_snapshot, str) else d.decision_snapshot
                entry_price = snapshot.get("max_price") or snapshot.get("entry_price")
                tp_price = snapshot.get("take_profit_price") or snapshot.get("tp_price")
                sl_price = snapshot.get("stop_loss_price") or snapshot.get("sl_price")
            except:
                pass

        trades.append({
            "id": d.id,
            "symbol": d.symbol,
            "operation": d.operation,
            "entry_price": entry_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "realized_pnl": pnl,
            "fee": round(fee, 2),
            "net_pnl": round(pnl - fee, 2),
            "reason": (d.reason[:500] if d.reason else None),  # Truncate
            "created_at": d.created_at.isoformat() if d.created_at else None
        })

    return json.dumps({"trades": trades, "count": len(trades)})


def _tool_suggest_prompt_modification(args: Dict) -> str:
    """Generate structured prompt modification suggestion"""
    return json.dumps({
        "_type": "prompt_suggestion",
        "title": args.get("title", "Untitled Suggestion"),
        "current_behavior": args.get("current_behavior", ""),
        "suggested_change": args.get("suggested_change", ""),
        "reason": args.get("reason", "")
    })


def _tool_list_ai_accounts(db: Session) -> str:
    """List all AI trading accounts with their IDs, names, and models"""
    accounts = db.query(Account).filter(Account.account_type == "AI").all()

    if not accounts:
        return json.dumps({"message": "No AI accounts found", "accounts": []})

    account_list = []
    for acc in accounts:
        account_list.append({
            "id": acc.id,
            "name": acc.name,
            "model": acc.model,
            "environment": acc.hyperliquid_environment,
            "auto_trading_enabled": acc.auto_trading_enabled
        })

    return json.dumps({"accounts": account_list, "count": len(account_list)})


def _tool_get_factor_attribution(db: Session, args: Dict) -> str:
    """Analyze trading performance grouped by factor signal triggers."""
    from database.models import SignalTriggerLog

    account_id = args.get("account_id", 0)
    exchange = args.get("exchange")
    environment = args.get("environment")
    days = args.get("days", 30)

    if not exchange:
        return json.dumps({"error": "exchange is required"})
    if not environment:
        return json.dumps({"error": "environment is required"})

    start_date = datetime.now() - timedelta(days=days)

    query = db.query(AIDecisionLog).filter(
        AIDecisionLog.operation.in_(["buy", "sell", "close"]),
        AIDecisionLog.executed == "true",
        AIDecisionLog.realized_pnl.isnot(None),
        AIDecisionLog.realized_pnl != 0,
        AIDecisionLog.created_at >= start_date,
        AIDecisionLog.exchange == exchange,
        AIDecisionLog.hyperliquid_environment == environment,
        AIDecisionLog.signal_trigger_id.isnot(None)
    )
    if account_id > 0:
        query = query.filter(AIDecisionLog.account_id == account_id)

    decisions = query.all()
    if not decisions:
        return json.dumps({"message": "No factor-triggered trades found"})

    fee_map = _get_fees_for_decisions(decisions)

    trigger_ids = set(d.signal_trigger_id for d in decisions)
    triggers = db.query(SignalTriggerLog).filter(
        SignalTriggerLog.id.in_(list(trigger_ids)),
        SignalTriggerLog.trigger_type.like("factor:%")
    ).all()
    trigger_map = {t.id: t for t in triggers}

    by_factor: Dict[str, Dict] = {}
    for d in decisions:
        trig = trigger_map.get(d.signal_trigger_id)
        if not trig:
            continue
        fname = trig.trigger_type.split(":", 1)[1] if ":" in trig.trigger_type else trig.trigger_type
        if fname not in by_factor:
            by_factor[fname] = {"count": 0, "wins": 0, "pnl": 0, "fees": 0}
        by_factor[fname]["count"] += 1
        pnl = float(d.realized_pnl or 0)
        by_factor[fname]["pnl"] += pnl
        by_factor[fname]["fees"] += fee_map.get(d.id, 0.0)
        if pnl > 0:
            by_factor[fname]["wins"] += 1

    items = []
    for fname, stats in by_factor.items():
        items.append({
            "factor_name": fname,
            "trade_count": stats["count"],
            "wins": stats["wins"],
            "win_rate": f"{stats['wins']/stats['count']*100:.1f}%" if stats["count"] > 0 else "N/A",
            "total_pnl": round(stats["pnl"], 2),
            "total_fees": round(stats["fees"], 2),
            "net_pnl": round(stats["pnl"] - stats["fees"], 2),
        })

    items.sort(key=lambda x: x["trade_count"], reverse=True)
    return json.dumps({"period_days": days, "factors": items})
