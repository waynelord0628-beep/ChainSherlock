from collections import Counter
from datetime import UTC
from decimal import Decimal
from zoneinfo import ZoneInfo

from crypto_investigator.investigation.investigation_result import (
    ActivityAnalysis,
    ActivityPeriod,
)
from crypto_investigator.investigation.statistics import median


def analyze_activity(edges, timezone: str) -> ActivityAnalysis:
    zone = ZoneInfo(timezone)
    timestamps = sorted(
        edge.timestamp.astimezone(zone)
        for edge in edges
        if edge.timestamp and edge.timestamp.tzinfo
    )
    excluded = sum(not edge.timestamp or not edge.timestamp.tzinfo for edge in edges)
    daily = Counter(item.strftime("%Y-%m-%d") for item in timestamps)
    weekly = Counter(f"{item.isocalendar().year}-W{item.isocalendar().week:02d}" for item in timestamps)
    monthly = Counter(item.strftime("%Y-%m") for item in timestamps)
    intervals = [
        Decimal(str((current.astimezone(UTC) - previous.astimezone(UTC)).total_seconds()))
        for previous, current in zip(timestamps, timestamps[1:])
    ]
    return ActivityAnalysis(
        tuple(ActivityPeriod(key, daily[key]) for key in sorted(daily)),
        tuple(ActivityPeriod(key, weekly[key]) for key in sorted(weekly)),
        tuple(ActivityPeriod(key, monthly[key]) for key in sorted(monthly)),
        sum(intervals, Decimal("0")) / len(intervals) if intervals else None,
        median(intervals),
        max(intervals) if intervals else None,
        excluded,
        timezone,
    )
