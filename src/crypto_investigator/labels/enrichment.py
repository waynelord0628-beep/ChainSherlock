"""Budget and cache policy for optional commercial label enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class LabelCacheEntry:
    chain: str
    address: str
    provider: str
    labels: tuple[str, ...]
    category: str | None
    fetched_at: datetime
    expires_at: datetime

    def valid_at(self, moment: datetime | None = None) -> bool:
        return (moment or datetime.now(UTC)) < self.expires_at


@dataclass(slots=True)
class EnrichmentBudget:
    maximum_calls: int = 3
    used_calls: int = 0

    @property
    def remaining_calls(self) -> int:
        return max(0, self.maximum_calls - self.used_calls)

    def consume(self) -> bool:
        if self.remaining_calls <= 0:
            return False
        self.used_calls += 1
        return True


class CommercialLabelPolicy:
    """Query only material, unresolved endpoints after local resolution."""

    def __init__(self, *, ttl_days: int = 30):
        self.ttl = timedelta(days=ttl_days)

    def should_query(
        self,
        *,
        has_local_match: bool,
        is_material_endpoint: bool,
        budget: EnrichmentBudget,
        cached: LabelCacheEntry | None = None,
    ) -> bool:
        if cached and cached.valid_at():
            return False
        return (
            not has_local_match
            and is_material_endpoint
            and budget.remaining_calls > 0
        )

