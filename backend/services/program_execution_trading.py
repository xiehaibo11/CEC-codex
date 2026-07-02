"""Trade execution helpers for Program Trader decisions."""
import logging

from database.models import AccountProgramBinding, BinanceWallet
from program_trader.data_provider import DataProvider

logger = logging.getLogger(__name__)


class ProgramExecutionTradingMixin:
    """Execute program decisions through Hyperliquid or Binance clients."""

    def _handle_decision(
        self,
        db,
        binding: AccountProgramBinding,
        decision,
        symbol: str,
        wallet_address: str | None,
        exchange: str = "hyperliquid",
        trading_client=None,
    ):
        """Handle the decision from program execution - execute actual trade."""
        from program_trader.executor import validate_decision
        from services.hyperliquid_environment import get_global_trading_mode

        op = decision.operation.lower() if hasattr(decision, "operation") else decision.action.value
        if op == "hold":
            logger.info(f"[ProgramExecution] Binding {binding.id} decision: HOLD - {decision.reason}")
            return None

        positions_dict = {}
        environment = get_global_trading_mode(db)
        client = trading_client or self._create_trading_client(db, binding.account_id, environment, exchange)
        if not client:
            return False

        if hasattr(decision, "operation"):
            positions_dict = self._load_positions_for_validation(db, binding, client, environment, exchange)
            is_valid, errors = validate_decision(decision, positions_dict)
            if not is_valid:
                logger.error(f"[ProgramExecution] Invalid decision: {errors}")
                return False

        logger.info(
            f"[ProgramExecution] Binding {binding.id} decision: {op} "
            f"{decision.symbol} portion={getattr(decision, 'target_portion_of_balance', 0)} "
            f"leverage={decision.leverage}x exchange={exchange} - {decision.reason}"
        )

        if not wallet_address and exchange != "binance":
            logger.error(f"[ProgramExecution] No wallet address for binding {binding.id}")
            return False
        if not environment:
            logger.error("[ProgramExecution] No trading environment configured")
            return False

        try:
            account_info = client.get_account_state(db)
            available_balance = account_info.get("available_balance", 0)
            market_price = self._get_market_price(client, decision, environment, exchange)
            if not market_price:
                logger.error(f"[ProgramExecution] No price available for {decision.symbol}")
                return False

            if not self._validate_entry_tpsl(op, decision, market_price):
                return False

            order_result = self._execute_decision_order(
                db,
                client,
                decision,
                op,
                available_balance,
                market_price,
                environment,
                positions_dict,
            )
            if order_result and order_result.get("status") in ["filled", "resting"]:
                logger.info(f"[ProgramExecution] Order succeeded on {exchange}: {order_result}")
                return order_result

            error_msg = order_result.get("error", "Unknown error") if order_result else "No result"
            logger.error(f"[ProgramExecution] Order failed on {exchange}: {error_msg}")
            return None
        except Exception as err:
            logger.error(f"[ProgramExecution] Error executing trade on {exchange}: {err}")
            return None

    def _create_trading_client(self, db, account_id: int, environment: str | None, exchange: str):
        if exchange == "binance":
            return self._create_binance_trading_client(db, account_id, environment or "mainnet")

        from services.hyperliquid_environment import get_hyperliquid_client

        return get_hyperliquid_client(db, account_id, override_environment=environment)

    def _create_binance_trading_client(self, db, account_id: int, environment: str):
        try:
            from services.binance_trading_client import BinanceTradingClient
            from utils.encryption import decrypt_private_key

            wallet = db.query(BinanceWallet).filter(
                BinanceWallet.account_id == account_id,
                BinanceWallet.environment == environment,
                BinanceWallet.is_active == "true",
            ).first()
            if not wallet:
                logger.error(f"[ProgramExecution] No active Binance wallet found for account {account_id}")
                return None

            api_key = decrypt_private_key(wallet.api_key_encrypted)
            secret_key = decrypt_private_key(wallet.secret_key_encrypted)
            return BinanceTradingClient(api_key, secret_key, environment)
        except Exception as err:
            logger.error(f"[ProgramExecution] Failed to create Binance client: {err}")
            return None

    def _load_positions_for_validation(self, db, binding, client, environment: str, exchange: str) -> dict:
        positions_dict = {}
        if not environment or not client:
            return positions_dict

        try:
            data_provider = DataProvider(db, binding.account_id, environment, client, exchange=exchange)
            for symbol, position in data_provider.get_positions().items():
                positions_dict[symbol] = {"side": position.side, "size": position.size}
        except Exception as err:
            logger.warning(f"[ProgramExecution] Failed to get positions for validation: {err}")
        return positions_dict

    def _get_market_price(self, client, decision, environment: str, exchange: str):
        if exchange == "binance":
            market_price = client.get_mark_price(decision.symbol)
        else:
            from services.hyperliquid_market_data import get_last_price_from_hyperliquid

            market_price = get_last_price_from_hyperliquid(decision.symbol, environment)

        if not market_price or market_price <= 0:
            market_price = getattr(decision, "max_price", None) or getattr(decision, "min_price", None)
        return market_price

    def _validate_entry_tpsl(self, op: str, decision, market_price: float) -> bool:
        if op not in ("buy", "sell"):
            return True

        from program_trader.executor import validate_tp_sl_prices

        tp_valid, tp_errors = validate_tp_sl_prices(
            operation=op,
            entry_price=market_price,
            take_profit_price=getattr(decision, "take_profit_price", None),
            stop_loss_price=getattr(decision, "stop_loss_price", None),
        )
        if not tp_valid:
            logger.error(f"[ProgramExecution] Invalid TP/SL: {tp_errors}")
            return False
        return True

    def _execute_decision_order(
        self,
        db,
        client,
        decision,
        op: str,
        available_balance: float,
        market_price: float,
        environment: str,
        positions_dict: dict,
    ):
        if op == "buy":
            return self._execute_buy(db, client, decision, available_balance, market_price, environment)
        if op == "sell":
            return self._execute_sell(db, client, decision, available_balance, market_price, environment)
        if op == "close":
            return self._execute_close(db, client, decision, positions_dict, market_price, environment)
        return None

    def _execute_buy(self, db, client, decision, available_balance, market_price, environment):
        """Execute BUY order with price bounds and IOC->GTC retry."""
        symbol = decision.symbol
        leverage = decision.leverage
        quantity = _calculate_order_quantity(available_balance, decision, market_price)
        max_price = getattr(decision, "max_price", None)
        if max_price:
            price_to_use = min(max_price, market_price * 1.01)
            if price_to_use != max_price:
                logger.warning(f"[ProgramExecution] BUY {symbol}: max_price {max_price:.2f} clamped to {price_to_use:.2f}")
        else:
            price_to_use = market_price * 1.005
            logger.warning(f"[ProgramExecution] BUY {symbol}: No max_price, using {price_to_use:.2f}")

        logger.info(f"[ProgramExecution] BUY {symbol}: size={quantity}, price={price_to_use:.2f}, leverage={leverage}x")
        order_result = _place_entry_order(db, client, decision, True, quantity, price_to_use, leverage)
        return _retry_entry_as_gtc(db, client, decision, True, quantity, price_to_use, leverage, order_result)

    def _execute_sell(self, db, client, decision, available_balance, market_price, environment):
        """Execute SELL order with price bounds and IOC->GTC retry."""
        symbol = decision.symbol
        leverage = decision.leverage
        quantity = _calculate_order_quantity(available_balance, decision, market_price)
        min_price = getattr(decision, "min_price", None)
        if min_price:
            price_to_use = max(min_price, market_price * 0.99)
            if price_to_use != min_price:
                logger.warning(f"[ProgramExecution] SELL {symbol}: min_price {min_price:.2f} clamped to {price_to_use:.2f}")
        else:
            price_to_use = market_price * 0.995
            logger.warning(f"[ProgramExecution] SELL {symbol}: No min_price, using {price_to_use:.2f}")

        logger.info(f"[ProgramExecution] SELL {symbol}: size={quantity}, price={price_to_use:.2f}, leverage={leverage}x")
        order_result = _place_entry_order(db, client, decision, False, quantity, price_to_use, leverage)
        return _retry_entry_as_gtc(db, client, decision, False, quantity, price_to_use, leverage, order_result)

    def _execute_close(self, db, client, decision, positions_dict, market_price, environment):
        """Execute CLOSE order with multi-retry and GTC fallback."""
        symbol = decision.symbol
        portion = getattr(decision, "target_portion_of_balance", 1.0)
        pos_info = positions_dict.get(symbol, {})
        is_long = pos_info.get("side") == "long"
        position_size = pos_info.get("size", 0)
        if not position_size or position_size <= 0:
            logger.warning(f"[ProgramExecution] CLOSE {symbol}: No position found")
            return {"status": "error", "error": "No position to close"}

        close_size = position_size * portion
        close_price = _resolve_close_price(decision, is_long, market_price)
        logger.info(
            f"[ProgramExecution] CLOSE {symbol}: size={close_size}, price={close_price:.2f}, "
            f"direction={'long->sell' if is_long else 'short->buy'}"
        )

        order_result = _place_close_with_retries(db, client, decision, is_long, close_size, close_price, market_price)
        if order_result and order_result.get("status") == "filled":
            return order_result

        fallback_price = market_price * (0.99 if is_long else 1.01)
        logger.warning(f"[ProgramExecution] CLOSE {symbol} fallback: GTC at {fallback_price:.2f}")
        return client.place_order_with_tpsl(
            db=db,
            symbol=symbol,
            is_buy=(not is_long),
            size=close_size,
            price=fallback_price,
            leverage=1,
            time_in_force="Gtc",
            reduce_only=True,
            take_profit_price=None,
            stop_loss_price=None,
        )


def _calculate_order_quantity(available_balance: float, decision, market_price: float) -> float:
    portion = getattr(decision, "target_portion_of_balance", 0)
    margin = available_balance * portion
    order_value = margin * decision.leverage
    return round(order_value / market_price, 6)


def _place_entry_order(db, client, decision, is_buy: bool, quantity: float, price: float, leverage: int):
    return client.place_order_with_tpsl(
        db=db,
        symbol=decision.symbol,
        is_buy=is_buy,
        size=quantity,
        price=price,
        leverage=leverage,
        time_in_force=getattr(decision, "time_in_force", "Ioc"),
        reduce_only=False,
        take_profit_price=getattr(decision, "take_profit_price", None),
        stop_loss_price=getattr(decision, "stop_loss_price", None),
        tp_execution=getattr(decision, "tp_execution", "limit"),
        sl_execution=getattr(decision, "sl_execution", "limit"),
    )


def _retry_entry_as_gtc(db, client, decision, is_buy: bool, quantity: float, price: float, leverage: int, order_result):
    if not order_result or order_result.get("status") != "error":
        return order_result

    error_msg = order_result.get("error", "").lower()
    if "could not immediately match" not in error_msg and "no resting orders" not in error_msg:
        return order_result

    side = "BUY" if is_buy else "SELL"
    logger.warning(f"[ProgramExecution] {side} {decision.symbol} IOC failed, retrying with GTC...")
    retry_result = client.place_order_with_tpsl(
        db=db,
        symbol=decision.symbol,
        is_buy=is_buy,
        size=quantity,
        price=price,
        leverage=leverage,
        time_in_force="Gtc",
        reduce_only=False,
        take_profit_price=getattr(decision, "take_profit_price", None),
        stop_loss_price=getattr(decision, "stop_loss_price", None),
        tp_execution=getattr(decision, "tp_execution", "limit"),
        sl_execution=getattr(decision, "sl_execution", "limit"),
    )
    if retry_result and retry_result.get("status") in ["filled", "resting"]:
        logger.info(f"[ProgramExecution] {side} {decision.symbol} GTC fallback succeeded")
    return retry_result


def _resolve_close_price(decision, is_long: bool, market_price: float) -> float:
    if is_long:
        ai_price = getattr(decision, "min_price", None)
        fallback_mult = 0.995
    else:
        ai_price = getattr(decision, "max_price", None)
        fallback_mult = 1.005

    close_price = ai_price if ai_price else market_price * fallback_mult
    if not ai_price:
        if not is_long and close_price < market_price:
            close_price = market_price * 1.005
        elif is_long and close_price > market_price:
            close_price = market_price * 0.995
    return close_price


def _place_close_with_retries(db, client, decision, is_long: bool, close_size: float, close_price: float, market_price: float):
    max_retries = 4
    price_mults = [0.996, 0.994, 0.992, 0.99] if is_long else [1.004, 1.006, 1.008, 1.01]
    order_result = None

    for retry in range(max_retries):
        attempt_price = close_price if retry == 0 else market_price * price_mults[retry]
        if retry > 0:
            logger.info(f"[ProgramExecution] CLOSE {decision.symbol} retry {retry}: price={attempt_price:.2f}")

        attempt_result = client.place_order_with_tpsl(
            db=db,
            symbol=decision.symbol,
            is_buy=(not is_long),
            size=close_size,
            price=attempt_price,
            leverage=1,
            time_in_force="Ioc",
            reduce_only=True,
            take_profit_price=None,
            stop_loss_price=None,
        )
        if attempt_result and attempt_result.get("status") == "filled":
            if retry > 0:
                logger.info(f"[ProgramExecution] CLOSE {decision.symbol} succeeded on retry {retry}")
            return attempt_result

        error_msg = attempt_result.get("error", "").lower() if attempt_result else ""
        should_retry = "could not immediately match" in error_msg or "no resting orders" in error_msg
        if not should_retry or retry >= max_retries - 1:
            order_result = attempt_result
            break

    return order_result
