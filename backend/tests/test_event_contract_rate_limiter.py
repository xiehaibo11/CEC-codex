def test_rate_limiter_uses_runtime_budget_and_retry_after_header():
    from services.api_rate_limiter import ApiRateLimiter, RateLimitBudget

    now = {"value": 1000.0}
    sleeps: list[float] = []

    def clock() -> float:
        return now["value"]

    def sleeper(seconds: float) -> None:
        sleeps.append(round(seconds, 3))
        now["value"] += seconds

    limiter = ApiRateLimiter(
        {
            "binance": RateLimitBudget(capacity=2, refill_per_second=1),
        },
        clock=clock,
        sleeper=sleeper,
    )

    limiter.acquire("binance", cost=2)
    limiter.acquire("binance", cost=1)
    limiter.record_response("binance", {"Retry-After": "3"})
    limiter.acquire("binance", cost=1)

    assert sleeps == [1.0, 3.0]


def test_rate_limiter_uses_binance_weight_header_to_delay_before_limit():
    from services.api_rate_limiter import ApiRateLimiter, RateLimitBudget

    now = {"value": 2000.0}
    sleeps: list[float] = []

    def clock() -> float:
        return now["value"]

    def sleeper(seconds: float) -> None:
        sleeps.append(round(seconds, 3))
        now["value"] += seconds

    limiter = ApiRateLimiter(
        {
            "binance": RateLimitBudget(capacity=10, refill_per_second=1),
        },
        clock=clock,
        sleeper=sleeper,
    )

    limiter.record_response("binance", {"X-MBX-USED-WEIGHT-1M": "9"})
    limiter.acquire("binance", cost=2)

    assert sleeps == [1.0]
