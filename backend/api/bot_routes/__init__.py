"""Bot Integration API Routes - Manage Telegram/Discord bot configurations.

This package was split from a single ``bot_routes.py`` module by concern:
- ``_router``       : shared ``APIRouter`` instance
- ``config``        : generic bot configuration CRUD endpoints
- ``notifications`` : push notification config endpoints + helper
- ``tool_labels``   : tool-name/language helpers shared by processors
- ``telegram``      : Telegram endpoints + message processing
- ``discord``       : Discord endpoints + message processing

The public contract is preserved: ``router``, ``_process_discord_message_internal``
and ``get_notification_config_dict`` remain importable from ``api.bot_routes``.
"""
from ._router import router

# Import endpoint modules for their side effect: registering routes on ``router``.
# Order matches the original single-module definition order.
from . import config  # noqa: F401
from . import notifications  # noqa: F401
from . import telegram  # noqa: F401
from . import discord  # noqa: F401

from .notifications import get_notification_config_dict
from .discord import _process_discord_message_internal

__all__ = [
    "router",
    "get_notification_config_dict",
    "_process_discord_message_internal",
]
