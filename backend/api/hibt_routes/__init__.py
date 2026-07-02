"""HiBT perpetual futures management API routes."""
from ._shared import router, logger, _client_cache, _get_client, _clear_client_cache, _format_credential_error

# Import endpoint modules for their side effect of registering routes.
from . import wallet  # noqa: E402,F401
from . import trading  # noqa: E402,F401
from . import account  # noqa: E402,F401
from . import market  # noqa: E402,F401

from .wallet import HibtSetupRequest  # noqa: E402,F401
from .trading import ManualOrderRequest  # noqa: E402,F401
from .market import HibtSymbolSelectionRequest  # noqa: E402,F401

__all__ = [
    "router",
    "logger",
    "_client_cache",
    "_get_client",
    "_clear_client_cache",
    "_format_credential_error",
    "HibtSetupRequest",
    "ManualOrderRequest",
    "HibtSymbolSelectionRequest",
]
