"""Execution logging helpers for Program Trader."""
import json
import logging
from typing import Optional

from database.models import AccountProgramBinding, ProgramExecutionLog

logger = logging.getLogger(__name__)


class ProgramExecutionLoggingMixin:
    """Persist execution logs, order IDs, trade records, and notifications."""

    def _log_execution(
        self,
        db,
        binding: AccountProgramBinding,
        symbol: str,
        pool: dict,
        wallet_address: Optional[str],
        result,
        params: dict,
        data_provider,
        market_data,
        environment: str,
        trigger_type: str = "signal",
        exchange: str = "hyperliquid",
    ):
        """Log program execution to database with full context for analysis."""
        try:
            decision = result.decision
            action_value, size_value = _extract_decision_action_size(decision)
            market_context = _build_market_context(
                symbol,
                pool,
                data_provider,
                market_data,
                result,
                environment,
                trigger_type,
            )

            log = ProgramExecutionLog(
                binding_id=binding.id,
                account_id=binding.account_id,
                program_id=binding.program_id,
                program_name=binding.program.name if binding.program else None,
                trigger_type=trigger_type,
                trigger_symbol=symbol,
                signal_pool_id=pool.get("pool_id"),
                wallet_address=wallet_address,
                environment=environment,
                exchange=exchange,
                success=result.success,
                error_message=result.error,
                execution_time_ms=result.execution_time_ms,
                decision_action=action_value,
                decision_symbol=decision.symbol if decision else None,
                decision_size_usd=size_value,
                decision_leverage=decision.leverage if decision else None,
                decision_reason=decision.reason if decision else None,
                decision_json=json.dumps(decision.to_dict()) if decision else None,
                params_snapshot=json.dumps(params) if params else None,
                market_context=json.dumps(market_context),
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            self._send_program_notification(db, binding, result)
            return log.id
        except Exception as err:
            logger.error(f"[ProgramExecution] Failed to log execution: {err}")
            return None

    def _send_program_notification(self, db, binding: AccountProgramBinding, result) -> None:
        decision = result.decision
        if not result.success or not decision or decision.operation.lower() == "hold":
            return

        try:
            import asyncio

            from api.bot_routes import get_notification_config_dict
            from services.bot_event_service import enqueue_system_event, push_event_to_all_channels

            notif_config = get_notification_config_dict(db)
            if not notif_config.get("program_trader", True):
                return

            event_data = {
                "program_name": binding.program.name if binding.program else "Unknown",
                "operation": decision.operation.upper(),
                "symbol": decision.symbol,
                "size_usd": (
                    f"{decision.target_portion_of_balance * 100:.0f}%"
                    if decision.target_portion_of_balance
                    else "N/A"
                ),
                "leverage": f"{decision.leverage}x" if decision.leverage else "N/A",
                "reason": decision.reason[:100] if decision.reason else "",
            }
            results = enqueue_system_event(db, "program_decision", event_data)
            if not results:
                return

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(push_event_to_all_channels(db, results))
            except RuntimeError:
                asyncio.run(push_event_to_all_channels(db, results))
        except Exception as notif_err:
            logger.warning(f"[ProgramExecution] Failed to send bot notification: {notif_err}")

    def _update_log_with_order(
        self,
        db,
        log_id: int,
        order_result: Optional[dict],
        binding: AccountProgramBinding,
        decision,
        wallet_address: str,
        environment: str,
        exchange: str = "hyperliquid",
    ):
        """Update execution log with order IDs and create HyperliquidTrade if filled."""
        try:
            log = db.query(ProgramExecutionLog).filter(ProgramExecutionLog.id == log_id).first()
            if not log:
                return

            if order_result is None:
                log.success = False
                log.error_message = (log.error_message or "") + " [Order execution failed]"
                db.commit()
                logger.info(f"[ProgramExecution] Updated log {log_id} with order failure status")
                return

            if isinstance(order_result, dict) and order_result.get("quota_exceeded"):
                quota_info = order_result.get("quota_info", {})
                log.success = False
                log.error_message = (
                    f"Executed: NO - Daily quota exceeded "
                    f"({quota_info.get('used', 0)}/{quota_info.get('limit', 20)})"
                )
                db.commit()
                logger.info(f"[ProgramExecution] Updated log {log_id} with quota exceeded status")
                return

            _update_log_order_ids(log, order_result)
            db.commit()
            logger.info(f"[ProgramExecution] Updated log {log_id} with order IDs")

            if order_result.get("status") == "filled":
                self._create_hyperliquid_trade(
                    binding,
                    decision,
                    order_result,
                    wallet_address,
                    environment,
                    exchange,
                )
        except Exception as err:
            logger.error(f"[ProgramExecution] Failed to update log with order: {err}")

    def _create_hyperliquid_trade(
        self,
        binding: AccountProgramBinding,
        decision,
        order_result: dict,
        wallet_address: str,
        environment: str,
        exchange: str = "hyperliquid",
    ):
        """Create HyperliquidTrade record for filled orders."""
        try:
            from database.snapshot_connection import SnapshotSessionLocal
            from database.snapshot_models import HyperliquidTrade
            from decimal import Decimal

            op = decision.operation.lower() if hasattr(decision, "operation") else decision.action.value
            trade_qty, trade_price = _extract_trade_qty_price(decision, order_result, exchange)
            snapshot_db = SnapshotSessionLocal()
            try:
                trade_record = HyperliquidTrade(
                    account_id=binding.account_id,
                    environment=environment,
                    wallet_address=wallet_address,
                    symbol=decision.symbol,
                    side=op,
                    quantity=trade_qty,
                    price=trade_price,
                    leverage=decision.leverage if hasattr(decision, "leverage") else 1,
                    order_id=order_result.get("order_id"),
                    order_status=order_result.get("status"),
                    trade_value=trade_qty * trade_price,
                    fee=Decimal(str(order_result.get("fee", 0))),
                )
                snapshot_db.add(trade_record)
                snapshot_db.commit()
                logger.info(f"[ProgramExecution] HyperliquidTrade record saved for binding {binding.id}")
            finally:
                snapshot_db.close()
        except Exception as err:
            logger.warning(f"[ProgramExecution] Failed to save HyperliquidTrade record: {err}")


def _extract_decision_action_size(decision) -> tuple:
    if not decision:
        return None, None
    if hasattr(decision, "operation"):
        return decision.operation, decision.target_portion_of_balance
    if hasattr(decision, "action"):
        action_value = decision.action.value if hasattr(decision.action, "value") else decision.action
        return action_value, getattr(decision, "size_usd", None)
    return None, None


def _build_market_context(
    symbol: str,
    pool: dict,
    data_provider,
    market_data,
    result,
    environment: str,
    trigger_type: str,
) -> dict:
    positions_snapshot = _build_positions_snapshot(market_data)
    return {
        "input_data": {
            "environment": environment,
            "trigger_symbol": symbol,
            "trigger_type": trigger_type,
            "signal_pool_id": pool.get("pool_id"),
            "signal_pool_name": pool.get("pool_name"),
            "pool_logic": market_data.pool_logic if market_data else "OR",
            "triggered_signals": market_data.triggered_signals if market_data else [],
            "signal_source_type": market_data.signal_source_type if market_data else None,
            "wallet_event": market_data.wallet_event if market_data else None,
            "trigger_market_regime": _serialize_regime(market_data),
            "max_leverage": market_data.max_leverage if market_data else 10,
            "default_leverage": market_data.default_leverage if market_data else 3,
            "available_balance": market_data.available_balance if market_data else 0,
            "total_equity": market_data.total_equity if market_data else 0,
            "margin_usage_percent": market_data.margin_usage_percent if market_data else 0,
            "positions": positions_snapshot,
            "positions_count": len(positions_snapshot),
            "open_orders": _serialize_open_orders(market_data),
            "open_orders_count": len(market_data.open_orders) if market_data else 0,
        },
        "data_queries": data_provider.get_query_log() if data_provider else [],
        "execution_logs": getattr(result, "logs", []) or [],
    }


def _build_positions_snapshot(market_data) -> dict:
    positions_snapshot = {}
    if not market_data or not market_data.positions:
        return positions_snapshot

    for symbol, position in market_data.positions.items():
        positions_snapshot[symbol] = {
            "side": position.side,
            "size": position.size,
            "entry_price": position.entry_price,
            "unrealized_pnl": getattr(position, "unrealized_pnl", 0),
            "leverage": getattr(position, "leverage", None),
            "opened_at": getattr(position, "opened_at", None),
            "opened_at_str": getattr(position, "opened_at_str", None),
            "holding_duration_seconds": getattr(position, "holding_duration_seconds", None),
            "holding_duration_str": getattr(position, "holding_duration_str", None),
        }
    return positions_snapshot


def _serialize_regime(market_data):
    if not market_data or not market_data.trigger_market_regime:
        return None
    regime = market_data.trigger_market_regime
    return {
        "regime": regime.regime,
        "conf": regime.conf,
        "direction": regime.direction,
        "indicators": regime.indicators,
    }


def _serialize_open_orders(market_data) -> list:
    if not market_data:
        return []
    return [
        {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "direction": order.direction,
            "order_type": order.order_type,
            "size": order.size,
            "price": order.price,
            "trigger_price": order.trigger_price,
            "reduce_only": order.reduce_only,
            "timestamp": order.timestamp,
        }
        for order in market_data.open_orders
    ]


def _update_log_order_ids(log, order_result: dict) -> None:
    if order_result.get("order_id"):
        log.hyperliquid_order_id = str(order_result.get("order_id"))
    if order_result.get("tp_order_id"):
        log.tp_order_id = str(order_result.get("tp_order_id"))
    if order_result.get("sl_order_id"):
        log.sl_order_id = str(order_result.get("sl_order_id"))


def _extract_trade_qty_price(decision, order_result: dict, exchange: str):
    from decimal import Decimal

    if exchange == "binance":
        filled_qty = float(order_result.get("filled_qty", 0))
        avg_price = float(order_result.get("avg_price", 0))
        decision_qty = float(decision.quantity) if hasattr(decision, "quantity") else 0
        decision_price = float(decision.price) if hasattr(decision, "price") else 0
        trade_qty = Decimal(str(filled_qty)) if filled_qty > 0 else Decimal(str(decision_qty))
        trade_price = Decimal(str(avg_price)) if avg_price > 0 else Decimal(str(decision_price))
        return trade_qty, trade_price

    return (
        Decimal(str(order_result.get("filled_amount", 0))),
        Decimal(str(order_result.get("average_price", 0))),
    )
