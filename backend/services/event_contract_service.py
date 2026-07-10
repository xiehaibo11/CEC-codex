"""Public facade for the 5-minute event-contract engine.

The implementation is split under ``services.event_contract`` so the backtest
loop, data access, snapshot analysis, and LLM consensus can be maintained
independently while keeping the original import path stable.
"""

from __future__ import annotations

from services.event_contract.analysis import EventContractAnalysisMixin
from services.event_contract.backtest import EventContractBacktestMixin
from services.event_contract.coinglass_features import EventContractCoinGlassMixin
from services.event_contract.config import EventContractConfigMixin
from services.event_contract.data import EventContractDataMixin
from services.event_contract.flow_features import EventContractFlowMixin
from services.event_contract.l2_features import EventContractL2Mixin
from services.event_contract.llm import EventContractLlmMixin
from services.event_contract.quality import EventContractQualityMixin
from services.event_contract.professional_ai import EventContractProfessionalAiMixin
from services.event_contract.rules import EventContractRuleMixin
from services.event_contract.signal import EventContractSignalMixin


class EventContractService(
    EventContractBacktestMixin,
    EventContractCoinGlassMixin,
    EventContractFlowMixin,
    EventContractL2Mixin,
    EventContractConfigMixin,
    EventContractDataMixin,
    EventContractQualityMixin,
    EventContractAnalysisMixin,
    EventContractProfessionalAiMixin,
    EventContractSignalMixin,
    EventContractRuleMixin,
    EventContractLlmMixin,
):
    """Compute event-contract predictions and historical settlement backtests."""


event_contract_service = EventContractService()
