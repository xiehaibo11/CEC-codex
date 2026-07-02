"""State helpers for AI trading strategy scheduling."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


def as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure stored timestamps are timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class StrategyState:
    account_id: int
    price_threshold: float
    trigger_interval: int
    signal_pool_ids: List[int]
    enabled: bool
    scheduled_trigger_enabled: bool
    last_trigger_at: Optional[datetime]
    exchange: str = "hyperliquid"
    running: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def signal_pool_id(self) -> Optional[int]:
        return self.signal_pool_ids[0] if self.signal_pool_ids else None

    def should_trigger_scheduled(self, event_time: datetime) -> bool:
        """Check whether scheduled fallback should trigger."""
        if not self.enabled or not self.scheduled_trigger_enabled or self.running:
            return False

        with self.lock:
            if self.running:
                return False

            now_ts = event_time.timestamp()
            last_ts = self.last_trigger_at.timestamp() if self.last_trigger_at else 0
            time_diff = now_ts - last_ts
            if time_diff < self.trigger_interval:
                return False

            self.last_trigger_at = event_time
            self.running = True
            logger.info(
                "Strategy scheduled trigger for account %s: Time interval (%.1fs / %ss)",
                self.account_id,
                time_diff,
                self.trigger_interval,
            )
            return True

    def mark_triggered_by_signal(self, event_time: datetime) -> bool:
        """Mark strategy as triggered by signal."""
        if not self.enabled:
            return False

        with self.lock:
            if self.running:
                return False
            self.last_trigger_at = event_time
            self.running = True
            return True
