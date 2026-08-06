"""Deterministic investigation-priority scoring for trace endpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable


class PriorityTier(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


@dataclass(frozen=True, slots=True)
class PrioritySignals:
    exclusive_amount_ratio: Decimal = Decimal("0")
    first_hop_amount_ratio: Decimal = Decimal("0")
    hop_depth: int = 1
    transaction_activity: Decimal = Decimal("0")
    aggregation_ratio: Decimal = Decimal("0")
    fan_out_ratio: Decimal = Decimal("0")
    onward_speed_ratio: Decimal = Decimal("0")
    repeated_amount_ratio: Decimal = Decimal("0")
    branch_presence_ratio: Decimal = Decimal("0")
    label_confidence: Decimal = Decimal("0")
    provider_completeness: Decimal = Decimal("1")
    evidence_quality: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.hop_depth < 1:
            raise ValueError("hop_depth must be positive")
        for name, value in asdict(self).items():
            if name == "hop_depth":
                continue
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class InvestigationPriority:
    candidate_id: str
    address: str
    asset: str
    score: Decimal
    tier: PriorityTier
    priority_reasons: tuple[str, ...]
    required_next_action: str
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = str(self.score)
        payload["tier"] = self.tier.value
        return payload


_WEIGHTS = {
    "exclusive_amount_ratio": Decimal("0.24"),
    "first_hop_amount_ratio": Decimal("0.12"),
    "transaction_activity": Decimal("0.10"),
    "aggregation_ratio": Decimal("0.10"),
    "fan_out_ratio": Decimal("0.08"),
    "onward_speed_ratio": Decimal("0.08"),
    "repeated_amount_ratio": Decimal("0.04"),
    "branch_presence_ratio": Decimal("0.07"),
    "label_confidence": Decimal("0.07"),
    "provider_completeness": Decimal("0.04"),
    "evidence_quality": Decimal("0.06"),
}


def score_investigation_priority(
    *,
    candidate_id: str,
    address: str,
    asset: str,
    signals: PrioritySignals,
) -> InvestigationPriority:
    """Score investigative usefulness, never criminality or risk."""

    raw = sum(
        (
            getattr(signals, name) * weight
            for name, weight in _WEIGHTS.items()
        ),
        Decimal("0"),
    )
    depth_factor = Decimal("1") / Decimal(signals.hop_depth).sqrt()
    score = min(Decimal("100"), (raw * depth_factor * Decimal("100"))).quantize(
        Decimal("0.01")
    )
    if score >= Decimal("70"):
        tier = PriorityTier.P1
        action = "優先核對標籤來源、完整交易證據及下一層資金去向。"
    elif score >= Decimal("45"):
        tier = PriorityTier.P2
        action = "補齊交易對手與標籤證據後，評估是否提升為優先追查。"
    elif score >= Decimal("20"):
        tier = PriorityTier.P3
        action = "保留於候選清單，依案件目標與剩餘資源安排查核。"
    else:
        tier = PriorityTier.P4
        action = "保留於技術附錄；除非出現新證據，暫不優先展開。"

    reasons: list[str] = []
    if signals.exclusive_amount_ratio >= Decimal("0.25"):
        reasons.append("可歸屬金額占比較高")
    if signals.aggregation_ratio >= Decimal("0.60"):
        reasons.append("呈現資金匯集特徵")
    if signals.fan_out_ratio >= Decimal("0.60"):
        reasons.append("呈現高分散轉出特徵")
    if signals.onward_speed_ratio >= Decimal("0.60"):
        reasons.append("後續轉出速度較快")
    if signals.branch_presence_ratio >= Decimal("0.40"):
        reasons.append("出現在多個第一層分支")
    if signals.label_confidence >= Decimal("0.80"):
        reasons.append("具較高可信度標籤")
    if signals.evidence_quality < Decimal("0.50"):
        reasons.append("證據品質仍待補強")
    if not reasons:
        reasons.append("綜合訊號未達高優先門檻")

    limitations = []
    if signals.provider_completeness < Decimal("1"):
        limitations.append("Provider 資料未完整，評分僅反映目前可得資料。")
    if signals.label_confidence == 0:
        limitations.append("尚無可驗證標籤，不代表已確認服務商或下車點。")

    return InvestigationPriority(
        candidate_id=candidate_id,
        address=address,
        asset=asset,
        score=score,
        tier=tier,
        priority_reasons=tuple(reasons),
        required_next_action=action,
        limitations=tuple(limitations),
    )


def rank_investigation_priorities(
    candidates: Iterable[tuple[str, str, str, PrioritySignals]],
) -> tuple[InvestigationPriority, ...]:
    ranked = tuple(
        score_investigation_priority(
            candidate_id=candidate_id,
            address=address,
            asset=asset,
            signals=signals,
        )
        for candidate_id, address, asset, signals in candidates
    )
    return tuple(
        sorted(ranked, key=lambda item: (-item.score, item.asset, item.address))
    )
