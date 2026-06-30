"""WebSocket API package.

This package preserves the public ``api.ws`` import surface that existed when
``api/ws.py`` was a single module. The implementation is split by concern:

- ``manager``: the ``ConnectionManager`` class and ``manager`` singleton,
  diagnostic constants, and ``get_current_thread_count``.
- ``snapshots``: paper-mode snapshot helpers and ``get_all_asset_curves_data``.
- ``hyperliquid_snapshots``: Hyperliquid snapshot helpers and mode dispatch.
- ``broadcast``: broadcast helpers used by background services.
- ``endpoint``: the ``websocket_endpoint`` request handler.
"""

from .broadcast import (
    broadcast_arena_asset_update,
    broadcast_asset_curve_update,
    broadcast_model_chat_update,
    broadcast_position_update,
    broadcast_trade_update,
)
from .endpoint import websocket_endpoint
from .hyperliquid_snapshots import (
    HYPERLIQUID_SNAPSHOT_CACHE_TTL,
    _send_hyperliquid_snapshot,
    _send_snapshot_by_mode,
)
from .manager import (
    WS_CONNECTION_WARNING_THRESHOLD,
    WS_DIAGNOSTIC_COOLDOWN_SECONDS,
    ConnectionManager,
    get_current_thread_count,
    manager,
)
from .snapshots import (
    _send_snapshot,
    _send_snapshot_optimized,
    get_all_asset_curves_data,
)

__all__ = [
    "ConnectionManager",
    "manager",
    "get_current_thread_count",
    "WS_DIAGNOSTIC_COOLDOWN_SECONDS",
    "WS_CONNECTION_WARNING_THRESHOLD",
    "get_all_asset_curves_data",
    "_send_snapshot",
    "_send_snapshot_optimized",
    "_send_snapshot_by_mode",
    "_send_hyperliquid_snapshot",
    "HYPERLIQUID_SNAPSHOT_CACHE_TTL",
    "broadcast_asset_curve_update",
    "broadcast_arena_asset_update",
    "broadcast_trade_update",
    "broadcast_position_update",
    "broadcast_model_chat_update",
    "websocket_endpoint",
]
