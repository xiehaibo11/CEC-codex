"""Execution-realism constraints for the event-contract backtest loop."""
from __future__ import annotations

from typing import Optional


class TradeConstraintTracker:
    """Tracks open exposure, trade spacing and venue daily-loss caps."""

    def __init__(
        self,
        *,
        non_overlapping: bool,
        min_seconds_between_trades: int,
        daily_loss_cap: Optional[float],
    ) -> None:
        self.non_overlapping = non_overlapping
        self.min_spacing = max(0, int(min_seconds_between_trades))
        self.daily_loss_cap = daily_loss_cap
        self._open_until: Optional[int] = None
        self._last_entry_ts: Optional[int] = None
        self._loss_day: Optional[int] = None
        self._loss_today = 0.0

    def allow(self, decision_ts: int, entry_ts: int) -> Optional[str]:
        if self.non_overlapping and self._open_until is not None and decision_ts < self._open_until:
            return "overlap_skipped_count"
        if (
            self.min_spacing
            and self._last_entry_ts is not None
            and decision_ts - self._last_entry_ts < self.min_spacing
        ):
            return "frequency_skipped_count"
        # Keyed by entry_ts (not decision_ts) to match record()'s day bucket - a
        # trade whose entry resolves into the next UTC day must not dodge an
        # already-breached cap from that entry day just because the decision
        # itself was made shortly before midnight.
        if self.daily_loss_cap is not None and self._loss_day == entry_ts // 86400:
            if self._loss_today >= self.daily_loss_cap:
                return "daily_cap_skipped_count"
        return None

    def record(self, entry_ts: int, settlement_ts: int, pnl: float) -> None:
        self._open_until = settlement_ts
        self._last_entry_ts = entry_ts
        if pnl < 0:
            day = entry_ts // 86400
            if day != self._loss_day:
                self._loss_day = day
                self._loss_today = 0.0
            self._loss_today += -pnl
