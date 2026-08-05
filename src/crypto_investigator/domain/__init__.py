"""Framework-independent domain entities and value objects."""

from crypto_investigator.domain.address import Address
from crypto_investigator.domain.asset import Asset
from crypto_investigator.domain.case import InvestigationCase
from crypto_investigator.domain.counterparty import Counterparty
from crypto_investigator.domain.fund_tracing import (
    AllocationSlice,
    AllocationMethod,
    FlowPatternFinding,
    FlowPatternType,
    FundLot,
    OffRampCandidate,
    SeedType,
    StopCondition,
    StopConditionType,
    TraceCheckpoint,
    TraceDirection,
    TraceEdge,
    TraceFrontierItem,
    TraceNode,
    TraceResult,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.domain.fifo_tracing import allocate_fifo
from crypto_investigator.domain.flow_patterns import (
    FlowPatternSettings,
    detect_flow_patterns,
)
from crypto_investigator.domain.multihop_tracing import trace_multihop
from crypto_investigator.domain.off_ramp import detect_off_ramps
from crypto_investigator.domain.fund_trace_engine import investigate_fund_trace
from crypto_investigator.domain.metadata import Metadata
from crypto_investigator.domain.scope import (
    AnalysisScope,
    CompletenessRequirement,
    PaginationPolicy,
    ScopeType,
    TimeScopeResult,
)
from crypto_investigator.domain.transaction import (
    Chain,
    Direction,
    Transaction,
    TransactionType,
)

__all__ = [
    "Address",
    "allocate_fifo",
    "AllocationSlice",
    "AllocationMethod",
    "AnalysisScope",
    "Asset",
    "Chain",
    "CompletenessRequirement",
    "Counterparty",
    "Direction",
    "FlowPatternFinding",
    "FlowPatternSettings",
    "FlowPatternType",
    "FundLot",
    "detect_flow_patterns",
    "detect_off_ramps",
    "InvestigationCase",
    "investigate_fund_trace",
    "Metadata",
    "OffRampCandidate",
    "PaginationPolicy",
    "ScopeType",
    "SeedType",
    "StopCondition",
    "StopConditionType",
    "TimeScopeResult",
    "Transaction",
    "TransactionType",
    "TraceEdge",
    "TraceCheckpoint",
    "TraceDirection",
    "TraceFrontierItem",
    "TraceNode",
    "TraceResult",
    "TraceRunStatus",
    "TraceScope",
    "TraceSeed",
    "trace_multihop",
]
