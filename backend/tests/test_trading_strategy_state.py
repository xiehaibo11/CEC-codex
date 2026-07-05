"""StrategyState trigger cooldown.

Bug fixed here (2026-07-05, account 3 forensics): mark_triggered_by_signal
had no cooldown at all, unlike should_trigger_scheduled. A noisy signal
(DEPTH_RATIO crossing its threshold back and forth) re-fired every 15-30 min
and each re-fire was treated as an independent buy opportunity, pyramiding
into the same position with no awareness of the recent same-signal entry.
trigger_interval must now bound BOTH trigger sources uniformly.
"""
from datetime import datetime, timedelta, timezone

import pytest

from services.trading_strategy_state import StrategyState


def _state(**overrides):
    defaults = dict(
        account_id=3,
        price_threshold=0.0,
        trigger_interval=900,  # 15 minutes, matches account 3's real config
        signal_pool_ids=[1],
        enabled=True,
        scheduled_trigger_enabled=True,
        last_trigger_at=None,
    )
    defaults.update(overrides)
    return StrategyState(**defaults)


def test_signal_trigger_allowed_when_no_prior_trigger():
    state = _state()
    assert state.mark_triggered_by_signal(datetime.now(timezone.utc)) is True


def test_signal_trigger_blocked_within_cooldown():
    """The exact reported bug: two signal re-fires 13 minutes apart with a
    15-minute trigger_interval must not both execute."""
    t0 = datetime.now(timezone.utc)
    state = _state(last_trigger_at=t0, running=False)
    t1 = t0 + timedelta(minutes=13)
    assert state.mark_triggered_by_signal(t1) is False


def test_signal_trigger_allowed_after_cooldown_elapses():
    t0 = datetime.now(timezone.utc)
    state = _state(last_trigger_at=t0, running=False)
    t1 = t0 + timedelta(minutes=16)
    assert state.mark_triggered_by_signal(t1) is True
    assert state.last_trigger_at == t1


def test_signal_trigger_respects_running_guard_even_past_cooldown():
    t0 = datetime.now(timezone.utc)
    state = _state(last_trigger_at=t0, running=True)
    t1 = t0 + timedelta(minutes=30)
    assert state.mark_triggered_by_signal(t1) is False


def test_signal_trigger_blocked_when_disabled():
    state = _state(enabled=False, last_trigger_at=None)
    assert state.mark_triggered_by_signal(datetime.now(timezone.utc)) is False


def test_scheduled_and_signal_paths_share_the_same_cooldown_clock():
    """A signal trigger must count against the next scheduled trigger's
    cooldown and vice versa - they share one account-level pacing budget."""
    t0 = datetime.now(timezone.utc)
    state = _state(last_trigger_at=None)
    assert state.mark_triggered_by_signal(t0) is True
    state.running = False  # simulate _execute_strategy's finally-block reset

    t1 = t0 + timedelta(minutes=5)
    assert state.should_trigger_scheduled(t1) is False  # too soon

    t2 = t0 + timedelta(minutes=16)
    assert state.should_trigger_scheduled(t2) is True
