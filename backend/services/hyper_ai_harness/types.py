from dataclasses import dataclass
from typing import Dict


TOOL_STATUS_SUCCESS = "success"
TOOL_STATUS_DOMAIN_ERROR = "domain_error"
TOOL_STATUS_INFRA_ERROR = "infra_error"
TOOL_STATUS_BLOCKED = "blocked"
TOOL_STATUS_WARNING = "warning"

RISK_READONLY = "readonly"
RISK_LOW_WRITE = "low_write"
RISK_HIGH = "high_risk"

CIRCUIT_BREAKER_THRESHOLD = 5
CONTRACT_FAIL_PREFIX = "[CONTRACT_FAIL]"


@dataclass
class ToolExecutionMeta:
    tool_name: str
    status: str = TOOL_STATUS_SUCCESS
    code: str = "ok"
    message: str = ""
    retryable: bool = False


@dataclass
class ToolRiskAssessment:
    tool_name: str
    risk_level: str
    reason: str = ""
    description: str = ""


class ToolFailureTracker:
    """Track consecutive infrastructure failures per tool within one chat task."""

    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD):
        self.threshold = threshold
        self._failures: Dict[str, int] = {}

    def record(self, meta: ToolExecutionMeta) -> None:
        if meta.status == TOOL_STATUS_INFRA_ERROR:
            self._failures[meta.tool_name] = self._failures.get(meta.tool_name, 0) + 1
        else:
            self._failures.pop(meta.tool_name, None)

    def is_tripped(self, tool_name: str) -> bool:
        return self._failures.get(tool_name, 0) >= self.threshold

    def failure_count(self, tool_name: str) -> int:
        return self._failures.get(tool_name, 0)
