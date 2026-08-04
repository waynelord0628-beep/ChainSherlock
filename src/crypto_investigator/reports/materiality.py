from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AssetPresentation:
    asset: str
    incoming: Decimal
    outgoing: Decimal
    transaction_count: int
    material: bool
    dust: bool
    spam_candidate: bool
    reason: str


def classify_assets(
    incoming: Mapping[str, object],
    outgoing: Mapping[str, object],
    breakdown: Mapping[str, Mapping[str, object]],
    *,
    materiality_thresholds: Mapping[str, Decimal] | None = None,
    include_assets: frozenset[str] = frozenset(),
    exclude_assets: frozenset[str] = frozenset(),
) -> tuple[AssetPresentation, ...]:
    """Classify display materiality without comparing unlike assets."""
    thresholds = materiality_thresholds or {}
    rows = []
    for asset in sorted(set(incoming) | set(outgoing) | set(breakdown)):
        received = Decimal(str(incoming.get(asset, 0)))
        sent = Decimal(str(outgoing.get(asset, 0)))
        count = int((breakdown.get(asset) or {}).get("transaction_count", 0))
        threshold = Decimal(str(thresholds.get(asset, 0)))
        dust = threshold > 0 and received + sent < threshold
        spam = dust and received > 0 and sent == 0 and count <= 2
        if asset in include_assets:
            material, reason = True, "user_included"
        elif asset in exclude_assets:
            material, reason = False, "user_excluded"
        elif spam:
            material, reason = False, "spam_candidate"
        elif dust:
            material, reason = False, "below_materiality_threshold"
        else:
            material, reason = True, "material"
        rows.append(
            AssetPresentation(
                asset,
                received,
                sent,
                count,
                material,
                dust,
                spam,
                reason,
            )
        )
    return tuple(rows)
