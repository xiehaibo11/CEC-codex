import asyncio
import json
import logging
import threading
import time
from typing import Dict, Optional, Set

from fastapi import WebSocket

from services.scheduler import add_account_snapshot_job, remove_account_snapshot_job

logger = logging.getLogger(__name__)

WS_DIAGNOSTIC_COOLDOWN_SECONDS = 300
WS_CONNECTION_WARNING_THRESHOLD = 3

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._diagnostic_lock = threading.Lock()
        self._last_warning_at: Dict[str, float] = {}

    async def connect(self, websocket: WebSocket):
        pass  # WebSocket is already accepted in the endpoint

    def register(self, account_id: Optional[int], websocket: WebSocket):
        if account_id is not None:
            self.active_connections.setdefault(account_id, set()).add(websocket)
            # Add scheduled snapshot task for new account
            add_account_snapshot_job(account_id, interval_seconds=10)
            account_connection_count = len(self.active_connections.get(account_id, ()))
            if account_connection_count > WS_CONNECTION_WARNING_THRESHOLD:
                self._emit_warning_once(
                    f"account-connections:{account_id}",
                    (
                        "[WS Diagnostic] account connection count high: "
                        "account_id=%s account_connections=%s total_connections=%s active_accounts=%s"
                    ),
                    account_id,
                    account_connection_count,
                    self.get_total_connection_count(),
                    len(self.active_connections),
                )

    def unregister(self, account_id: Optional[int], websocket: WebSocket):
        if account_id is not None and account_id in self.active_connections:
            self.active_connections[account_id].discard(websocket)
            if not self.active_connections[account_id]:
                del self.active_connections[account_id]
                # Remove the scheduled task for this account
                remove_account_snapshot_job(account_id)

    async def send_to_account(self, account_id: int, message: dict):
        if account_id not in self.active_connections:
            return
        payload = json.dumps(message, ensure_ascii=False)
        for ws in list(self.active_connections[account_id]):
            try:
                # Check if WebSocket is still open before sending
                if ws.client_state.name != "CONNECTED":
                    self.active_connections[account_id].discard(ws)
                    continue
                await ws.send_text(payload)
            except Exception as e:
                # Log the error and remove broken connection
                logging.warning(f"Failed to send message to WebSocket: {e}")
                self.active_connections[account_id].discard(ws)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients"""
        payload = json.dumps(message, ensure_ascii=False)
        for account_id, websockets in list(self.active_connections.items()):
            for ws in list(websockets):
                try:
                    # Check if WebSocket is still open before sending
                    if ws.client_state.name != "CONNECTED":
                        websockets.discard(ws)
                        continue
                    await ws.send_text(payload)
                except Exception as e:
                    # Log the error and remove broken connection
                    logging.warning(f"Failed to broadcast message to WebSocket: {e}")
                    websockets.discard(ws)

    def has_connections(self) -> bool:
        return any(self.active_connections.values())

    def get_total_connection_count(self) -> int:
        return sum(len(websockets) for websockets in self.active_connections.values())

    def get_connection_stats(self) -> dict:
        account_counts = {
            str(account_id): len(websockets)
            for account_id, websockets in self.active_connections.items()
            if websockets
        }
        return {
            "active_accounts": len(account_counts),
            "total_connections": sum(account_counts.values()),
            "account_counts": account_counts,
        }

    def _emit_warning_once(self, key: str, message: str, *args) -> None:
        now = time.time()
        with self._diagnostic_lock:
            last_warning_at = self._last_warning_at.get(key, 0.0)
            if now - last_warning_at < WS_DIAGNOSTIC_COOLDOWN_SECONDS:
                return
            self._last_warning_at[key] = now
        logger.warning(message, *args)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        if loop and loop.is_running():
            self._loop = loop

    def schedule_task(self, coro, source: str = "unknown"):
        loop = None
        if self._loop and self._loop.is_running():
            loop = self._loop
        else:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    self._loop = loop
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
            return

        thread_count = get_current_thread_count()
        connection_stats = self.get_connection_stats()
        self._emit_warning_once(
            f"schedule-fallback:{source}",
            (
                "[WS Diagnostic] schedule_task fallback thread started: "
                "source=%s coro=%s threads=%s total_connections=%s active_accounts=%s account_counts=%s"
            ),
            source,
            getattr(coro, "__qualname__", getattr(coro, "__name__", type(coro).__name__)),
            thread_count,
            connection_stats["total_connections"],
            connection_stats["active_accounts"],
            connection_stats["account_counts"],
        )

        # Fallback: run in a dedicated daemon thread to avoid blocking the caller
        def _run():
            asyncio.run(coro)

        threading.Thread(
            target=_run,
            daemon=True,
            name=f"ws-fallback-{source[:24]}",
        ).start()


manager = ConnectionManager()


def get_current_thread_count() -> int:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as status_file:
            for line in status_file:
                if line.startswith("Threads:"):
                    return int(line.split()[1])
    except OSError:
        return -1
    return -1
