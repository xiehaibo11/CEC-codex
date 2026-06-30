"""Small shared HTTP rate limiter for exchange and market-data APIs."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Callable, Mapping


@dataclass
class RateLimitBudget:
    capacity: float
    refill_per_second: float

    @classmethod
    def from_env(cls, prefix: str, *, default_capacity: float, default_refill_per_second: float) -> "RateLimitBudget":
        capacity = float(os.getenv(f"{prefix}_RATE_LIMIT_CAPACITY", str(default_capacity)))
        refill = float(os.getenv(f"{prefix}_RATE_LIMIT_REFILL_PER_SECOND", str(default_refill_per_second)))
        return cls(capacity=max(capacity, 1.0), refill_per_second=max(refill, 0.001))


class ApiRateLimiter:
    """Provider keyed token bucket with response-header backoff support.

    The budgets are runtime configuration, not exchange constants. Binance and
    CoinGlass can change limits by plan or endpoint, so callers feed response
    headers back into the limiter after each request.
    """

    def __init__(
        self,
        budgets: Mapping[str, RateLimitBudget],
        *,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._budgets = {key: value for key, value in budgets.items()}
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._state = {
            key: {"tokens": budget.capacity, "updated_at": clock(), "blocked_until": 0.0}
            for key, budget in self._budgets.items()
        }

    def acquire(self, provider: str, *, cost: float = 1.0) -> None:
        budget = self._budgets.get(provider)
        if budget is None:
            return
        cost = max(float(cost or 1), 0.001)

        while True:
            sleep_for = 0.0
            with self._lock:
                state = self._state.setdefault(
                    provider,
                    {"tokens": budget.capacity, "updated_at": self._clock(), "blocked_until": 0.0},
                )
                now = self._clock()
                elapsed = max(0.0, now - float(state["updated_at"]))
                state["tokens"] = min(budget.capacity, float(state["tokens"]) + elapsed * budget.refill_per_second)
                state["updated_at"] = now

                if now < float(state["blocked_until"]):
                    sleep_for = float(state["blocked_until"]) - now
                elif state["tokens"] >= cost:
                    state["tokens"] = float(state["tokens"]) - cost
                    return
                else:
                    sleep_for = (cost - float(state["tokens"])) / budget.refill_per_second

            self._sleeper(max(sleep_for, 0.001))

    def record_response(self, provider: str, headers: Mapping[str, str] | None) -> None:
        if provider not in self._budgets or not headers:
            return
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        retry_after = normalized.get("retry-after")
        if retry_after:
            delay = self._parse_retry_after(retry_after)
            if delay > 0:
                with self._lock:
                    state = self._state.setdefault(
                        provider,
                        {
                            "tokens": self._budgets[provider].capacity,
                            "updated_at": self._clock(),
                            "blocked_until": 0.0,
                        },
                    )
                    state["blocked_until"] = max(float(state["blocked_until"]), self._clock() + delay)

        used_weight = normalized.get("x-mbx-used-weight-1m") or normalized.get("x-mbx-used-weight")
        if used_weight is not None:
            self._apply_used_weight(provider, used_weight)

        remaining = normalized.get("x-ratelimit-remaining") or normalized.get("x-rate-limit-remaining")
        if remaining is not None:
            self._apply_remaining(provider, remaining)

    def _apply_used_weight(self, provider: str, value: str) -> None:
        budget = self._budgets[provider]
        try:
            used = max(float(value), 0.0)
        except (TypeError, ValueError):
            return
        with self._lock:
            state = self._state.setdefault(
                provider,
                {"tokens": budget.capacity, "updated_at": self._clock(), "blocked_until": 0.0},
            )
            state["tokens"] = max(0.0, budget.capacity - used)
            state["updated_at"] = self._clock()

    def _apply_remaining(self, provider: str, value: str) -> None:
        budget = self._budgets[provider]
        try:
            remaining = max(float(value), 0.0)
        except (TypeError, ValueError):
            return
        with self._lock:
            state = self._state.setdefault(
                provider,
                {"tokens": budget.capacity, "updated_at": self._clock(), "blocked_until": 0.0},
            )
            state["tokens"] = min(budget.capacity, remaining)
            state["updated_at"] = self._clock()

    def _parse_retry_after(self, value: str) -> float:
        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            pass
        try:
            parsed = parsedate_to_datetime(value)
            return max(parsed.timestamp() - self._clock(), 0.0)
        except (TypeError, ValueError, OSError):
            return 0.0


def _default_limiter() -> ApiRateLimiter:
    return ApiRateLimiter(
        {
            "binance": RateLimitBudget.from_env(
                "BINANCE",
                default_capacity=float(os.getenv("BINANCE_RATE_LIMIT_WEIGHT_PER_MINUTE", "1100")),
                default_refill_per_second=float(os.getenv("BINANCE_RATE_LIMIT_WEIGHT_REFILL_PER_SECOND", "18")),
            ),
            "coinglass": RateLimitBudget.from_env(
                "COINGLASS",
                default_capacity=float(os.getenv("COINGLASS_RATE_LIMIT_CAPACITY", "30")),
                default_refill_per_second=float(os.getenv("COINGLASS_RATE_LIMIT_REFILL_PER_SECOND", "1")),
            ),
        }
    )


GLOBAL_API_RATE_LIMITER = _default_limiter()


def acquire_api_slot(provider: str, *, cost: float = 1.0) -> None:
    GLOBAL_API_RATE_LIMITER.acquire(provider, cost=cost)


def record_api_response(provider: str, headers: Mapping[str, str] | None) -> None:
    GLOBAL_API_RATE_LIMITER.record_response(provider, headers)
