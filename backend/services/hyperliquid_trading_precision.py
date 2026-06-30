"""Hyperliquid trading client - precision discovery and price/size rounding.

Extracted verbatim from ``hyperliquid_trading_client.py`` as a mixin to keep the
main client module focused. Composed into ``HyperliquidTradingClient``; no logic
changes were made to any method body.
"""
import logging
import math
import requests
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING, InvalidOperation
from typing import Any, Dict, List, Optional

from services.exchanges.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


class HyperliquidPrecisionMixin:
    """Asset precision discovery and price/size rounding helpers.

    Relies on host-class attributes (``self.api_url``) and methods
    (``self._get_exchange_symbol``); only valid when mixed into
    ``HyperliquidTradingClient``.
    """

    def _get_asset_precision(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch asset precision requirements from Hyperliquid /info endpoint

        Returns:
            Dict with:
                - price_decimals: Inferred decimal places for price (for logging/fallback)
                - size_decimals: Size decimal places from meta
                - price_tick: Decimal tick size for price alignment
                - size_step: Decimal step for size alignment
        """
        proxies = {'http': None, 'https': None}
        is_hip3 = SymbolMapper.is_hip3_symbol(symbol)
        exchange_symbol = self._get_exchange_symbol(symbol)
        info_url = "https://api.hyperliquid.xyz/info" if is_hip3 else f"{self.api_url}/info"

        try:
            # Default fallbacks
            price_decimals = 1
            price_tick = Decimal('0.1')
            size_decimals = 5
            size_step = Decimal('1').scaleb(-size_decimals)

            # Fetch meta for size precision
            meta_payload = {"type": "meta"}
            if is_hip3:
                meta_payload["dex"] = "xyz"
            response = requests.post(info_url, json=meta_payload, timeout=10, proxies=proxies)
            response.raise_for_status()

            data = response.json()
            universe = data.get('universe', [])

            for asset in universe:
                if asset.get('name') == exchange_symbol:
                    size_decimals = asset.get('szDecimals', 5)
                    break

            size_step = Decimal('1').scaleb(-size_decimals)

            # Fetch order book to infer tick size
            try:
                l2_payload = {"type": "l2Book", "coin": exchange_symbol}
                l2_response = requests.post(info_url, json=l2_payload, timeout=10, proxies=proxies)
                l2_response.raise_for_status()
                l2_data = l2_response.json()

                price_samples: List[Decimal] = []
                levels = l2_data.get('levels', [])
                for side in levels:
                    for level in side[:10]:
                        px = level.get('px')
                        if px is not None:
                            try:
                                price_samples.append(Decimal(str(px)))
                            except (InvalidOperation, ValueError):
                                continue

                if price_samples:
                    inferred_tick = self._infer_price_tick(price_samples)
                    if inferred_tick is not None and inferred_tick > 0:
                        price_tick = inferred_tick
                        price_decimals = max(0, -price_tick.as_tuple().exponent)
                        logger.info(
                            f"[PRECISION] {symbol} inferred tick={price_tick} "
                            f"(price_decimals={price_decimals})"
                        )
                    else:
                        max_decimals = max(0, max(-p.as_tuple().exponent for p in price_samples))
                        price_decimals = max_decimals
                        price_tick = Decimal('1').scaleb(-price_decimals)
                        logger.warning(
                            f"[PRECISION] {symbol} unable to compute tick, "
                            f"using decimals-based fallback price_tick={price_tick}"
                        )
                else:
                    logger.warning(f"[PRECISION] {symbol} no order book data, using default tick={price_tick}")

            except Exception as e:
                logger.warning(f"[PRECISION] Failed to fetch order book for {symbol}: {e}, using defaults")

            logger.info(
                f"[PRECISION] {symbol} final precision: price_tick={price_tick}, size_step={size_step}, "
                f"price_decimals={price_decimals}, size_decimals={size_decimals}"
            )

            return {
                'price_decimals': price_decimals,
                'size_decimals': size_decimals,
                'price_tick': price_tick,
                'size_step': size_step,
            }

        except Exception as e:
            logger.error(f"[PRECISION] Failed to fetch precision for {symbol}: {e}")
            # Fallback to conservative defaults
            return {
                'price_decimals': 1,
                'size_decimals': 5,
                'price_tick': Decimal('0.1'),
                'size_step': Decimal('1e-5'),
            }

    def _round_to_precision(
        self,
        value: float,
        price_decimals: int,
        size_decimals: int,
        is_price: bool = True,
        price_tick: Optional[Decimal] = None,
        size_step: Optional[Decimal] = None,
        is_buy: Optional[bool] = None,
        force_aggressive: bool = False,
    ) -> float:
        """
        Round a price or size to the required precision/tick size.

        Args:
            value: Value to round
            price_decimals: Number of decimal places for prices (fallback)
            size_decimals: Number of decimal places for sizes (fallback)
            is_price: True for prices, False for sizes
            price_tick: Explicit tick size for prices
            size_step: Explicit step for sizes
        """
        if value is None or math.isnan(value) or math.isinf(value):
            return value

        if is_price and force_aggressive and is_buy is not None:
            slippage = Decimal('1.0005') if is_buy else Decimal('0.9995')
            try:
                value = float(Decimal(str(value)) * slippage)
            except (InvalidOperation, TypeError, ValueError):
                value = value * float(slippage)

        if is_price:
            step = price_tick if price_tick is not None else Decimal('1').scaleb(-price_decimals)
            return self._round_to_step(value, step, sigfigs=5, prefer_up=is_buy, force_aggressive=force_aggressive)
        else:
            step = size_step if size_step is not None else Decimal('1').scaleb(-size_decimals)
            return self._round_to_step(value, step)

    def _round_to_step(
        self,
        value: float,
        step: Decimal,
        sigfigs: Optional[int] = None,
        prefer_up: Optional[bool] = None,
        force_aggressive: bool = False,
    ) -> float:
        """
        Snap a numeric value to the nearest multiple of `step`, optionally limiting significant figures.
        """
        try:
            step_dec = step if isinstance(step, Decimal) else Decimal(str(step))
        except (InvalidOperation, TypeError, ValueError):
            step_dec = Decimal('0')

        if step_dec <= 0:
            base_dec = self._limit_sigfigs(value, sigfigs, prefer_up) if sigfigs else Decimal(str(value))
            return float(base_dec)

        try:
            base_dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            base_dec = Decimal(str(float(value)))

        limited_base = self._limit_sigfigs(base_dec, sigfigs, prefer_up) if sigfigs else base_dec

        try:
            steps = (limited_base / step_dec).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            quantized = steps * step_dec
        except InvalidOperation:
            return float(limited_base)

        if prefer_up is True and quantized < limited_base:
            quantized += step_dec
        elif prefer_up is False and quantized > limited_base:
            quantized -= step_dec

        if quantized <= 0:
            quantized = step_dec

        if force_aggressive:
            if prefer_up is True:
                quantized += step_dec
            elif prefer_up is False:
                quantized -= step_dec
                if quantized <= 0:
                    quantized = step_dec

        return float(quantized.normalize())

    def _limit_sigfigs(self, value: Any, sigfigs: Optional[int], prefer_up: Optional[bool] = None) -> Decimal:
        """
        Limit a numeric value to a maximum number of significant figures.
        """
        if not sigfigs or sigfigs <= 0:
            return Decimal(str(value))

        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            dec = Decimal(str(float(value)))

        if dec.is_zero():
            return Decimal('0')

        numeric = float(dec)
        if math.isnan(numeric) or math.isinf(numeric):
            return dec

        exponent = math.floor(math.log10(abs(numeric)))
        quant_exp = exponent - sigfigs + 1
        quant = Decimal('1').scaleb(quant_exp)

        rounding_mode = ROUND_HALF_UP
        if prefer_up is True:
            rounding_mode = ROUND_CEILING if dec >= 0 else ROUND_FLOOR
        elif prefer_up is False:
            rounding_mode = ROUND_FLOOR if dec >= 0 else ROUND_CEILING

        try:
            return dec.quantize(quant, rounding=rounding_mode)
        except InvalidOperation:
            return dec

    def _infer_price_tick(self, prices: List[Decimal]) -> Optional[Decimal]:
        """
        Infer the minimal tick size from a list of Decimal price samples.
        """
        unique_prices = sorted(set([p for p in prices if p is not None]))
        if len(unique_prices) < 2:
            return None

        diffs: List[Decimal] = []
        for first, second in zip(unique_prices, unique_prices[1:]):
            diff = second - first
            if diff > 0:
                diffs.append(diff)

        if not diffs:
            return None

        tick = diffs[0]
        for diff in diffs[1:]:
            tick = self._decimal_gcd(tick, diff)
            if tick == 0:
                tick = diff

        if tick <= 0:
            tick = min(diffs)

        return tick.normalize()

    def _decimal_gcd(self, a: Decimal, b: Decimal) -> Decimal:
        """
        Compute the GCD for two Decimal numbers by scaling to integers.
        """
        from math import gcd

        a = abs(a)
        b = abs(b)

        if a == 0:
            return b
        if b == 0:
            return a

        scale = max(-a.as_tuple().exponent, -b.as_tuple().exponent, 0)
        factor = Decimal(10) ** scale

        try:
            a_int = int((a * factor).to_integral_value(rounding=ROUND_HALF_UP))
            b_int = int((b * factor).to_integral_value(rounding=ROUND_HALF_UP))
        except InvalidOperation:
            return Decimal('0')

        gcd_value = gcd(a_int, b_int)
        if gcd_value == 0:
            return Decimal('0')

        result = Decimal(gcd_value) / factor
        return result.normalize()
