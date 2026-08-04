from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.models import TimelineBucket, TimelineResult


@dataclass(slots=True)
class _Bucket:
    count: int = 0
    amounts: dict[str, Decimal] = field(
        default_factory=lambda: defaultdict(lambda: Decimal("0"))
    )


class TimelineAnalyzer:
    name = "timeline"

    def analyze(self, context: AnalysisContext) -> TimelineResult:
        daily: dict[str, _Bucket] = {}
        monthly: dict[str, _Bucket] = {}
        hourly: Counter[int] = Counter()
        weekly: Counter[str] = Counter()

        for transaction in context.transactions:
            timestamp = transaction.timestamp
            if timestamp is None:
                continue
            self._add(daily.setdefault(timestamp.date().isoformat(), _Bucket()), transaction)
            self._add(monthly.setdefault(timestamp.strftime("%Y-%m"), _Bucket()), transaction)
            hourly[timestamp.hour] += 1
            weekly[timestamp.strftime("%A")] += 1

        return TimelineResult(
            daily=self._freeze_buckets(daily),
            monthly=self._freeze_buckets(monthly),
            hourly_distribution=dict(sorted(hourly.items())),
            weekly_distribution={
                day: weekly[day]
                for day in (
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                )
                if weekly[day]
            },
        )

    @staticmethod
    def _add(bucket: _Bucket, transaction) -> None:
        bucket.count += 1
        if transaction.asset_symbol is not None and transaction.amount is not None:
            bucket.amounts[transaction.asset_symbol] += transaction.amount

    @staticmethod
    def _freeze_buckets(values: dict[str, _Bucket]) -> dict[str, TimelineBucket]:
        return {
            key: TimelineBucket(
                transaction_count=value.count,
                amounts_by_asset=dict(sorted(value.amounts.items())),
            )
            for key, value in sorted(values.items())
        }
