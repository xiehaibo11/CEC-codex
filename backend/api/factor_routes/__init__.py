"""
Factor System API Routes (package).

Public contract: `router` — registered in main.py as
`from api.factor_routes import router as factor_router`.

GET    /api/factors/library                          → Factor registry
GET    /api/factors/values                           → Latest factor values
GET    /api/factors/effectiveness                    → Effectiveness ranking
GET    /api/factors/effectiveness/{name}/history     → IC trend
GET    /api/factors/effectiveness/{name}/by-window   → IC per forward period
GET    /api/factors/status                           → Engine status
GET    /api/factors/compute/estimate                 → Pre-compute estimation
POST   /api/factors/compute                          → Manual trigger (async)
GET    /api/factors/compute/progress                 → Computation progress
GET    /api/factors/custom                           → List custom factors
POST   /api/factors/custom                           → Create custom factor
DELETE /api/factors/custom/{factor_id}               → Delete custom factor
PUT    /api/factors/custom/{factor_id}               → Edit custom factor
POST   /api/factors/evaluate                         → Evaluate expression
POST   /api/factors/validate-expression              → Validate expression
GET    /api/factors/expression-functions             → Expression functions

The single shared `router` is defined in `.base`; importing the endpoint
modules below registers their routes on it.
"""

from .base import router

# Import endpoint modules for their route-registration side effects.
from . import library  # noqa: E402,F401
from . import effectiveness  # noqa: E402,F401
from . import compute  # noqa: E402,F401
from . import custom  # noqa: E402,F401
from . import expression  # noqa: E402,F401

__all__ = ["router"]
