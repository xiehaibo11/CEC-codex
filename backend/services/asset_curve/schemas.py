"""Shared type aliases for asset curve helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple, TypeAlias

AssetCurvePoint: TypeAlias = Dict[str, Any]
BucketedSnapshotRow: TypeAlias = Tuple[int, float, float, float, datetime]
