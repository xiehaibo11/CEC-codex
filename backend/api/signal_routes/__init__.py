"""Signal system API routes.

This package was split from a single ``signal_routes.py`` module. The shared
``APIRouter`` lives in ``._base``; each sibling module attaches its endpoints to
that same router instance. Importing the endpoint modules below registers all
routes on ``router``.

Public contract (must remain importable from ``api.signal_routes``):
- ``router``
- ``create_pool_from_config``
- ``SignalPoolConfigRequest``
"""
from __future__ import annotations

from ._base import router

# Import endpoint modules for their side effect of registering routes on ``router``.
from . import definitions  # noqa: F401,E402
from . import wallet_tracking  # noqa: F401,E402
from . import pools  # noqa: F401,E402
from . import analysis  # noqa: F401,E402
from . import trigger_logs  # noqa: F401,E402
from . import testing  # noqa: F401,E402
from . import ai_chat  # noqa: F401,E402

# Re-export public symbols used by other modules.
from .pool_config import (  # noqa: E402
    SignalPoolConfigRequest,
    create_pool_from_config,
)

__all__ = ["router", "SignalPoolConfigRequest", "create_pool_from_config"]
