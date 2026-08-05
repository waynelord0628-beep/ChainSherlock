"""Framework-independent domain entities and value objects."""

from crypto_investigator.domain.address import Address
from crypto_investigator.domain.asset import Asset
from crypto_investigator.domain.case import InvestigationCase
from crypto_investigator.domain.counterparty import Counterparty
from crypto_investigator.domain.fund_tracing import (
    AllocationMethod,
    OffRampCandidate,
    SeedType,
    StopCondition,
    StopConditionType,
    TraceEdge,
    TraceNode,
    TraceScope,
    TraceSeed,
)
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
    "AllocationMethod",
    "AnalysisScope",
    "Asset",
    "Chain",
    "CompletenessRequirement",
    "Counterparty",
    "Direction",
    "InvestigationCase",
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
    "TraceNode",
    "TraceScope",
    "TraceSeed",
]
