from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from crypto_investigator.investigation.investigation_result import LabelRecord


class AssetInvestigationRole(StrEnum):
    PRINCIPAL_VALUE = "principal_value_asset"
    SECONDARY_VALUE = "secondary_value_asset"
    OPERATIONAL = "operational_asset"
    LOW_MATERIALITY = "spam_or_low_materiality_asset"
    UNKNOWN = "unknown_or_non_value_event"


@dataclass(frozen=True, slots=True)
class FirstHopGoal:
    goal_types: tuple[str, ...] = ("address_profile", "first_hop_fund_flow")
    required_assets: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    scope_type: str = "full_history"
    materiality_thresholds: Mapping[str, Decimal] | None = None
    output_type: str = "first_hop_investigation_report"
    completeness_required: str = "complete"


def _amount(record: Mapping[str, Any]) -> Decimal:
    raw = Decimal(str(record.get("amount_raw", record.get("amount", "0"))))
    decimals = int(record.get("decimals") or 0)
    return raw / (Decimal(10) ** decimals)


def _timestamp(record: Mapping[str, Any]) -> datetime:
    return datetime.fromisoformat(str(record["timestamp"]).replace("Z", "+00:00"))


def _direction(record: Mapping[str, Any], target: str) -> str:
    if str(record.get("to_address", "")) == target:
        return "incoming"
    if str(record.get("from_address", "")) == target:
        return "outgoing"
    return "unclassified"


def _asset_key(record: Mapping[str, Any]) -> tuple[str, str | None]:
    symbol = str(record.get("asset_symbol") or "UNKNOWN").strip() or "UNKNOWN"
    contract = record.get("asset_contract")
    return symbol, str(contract) if contract else None


def _is_native(record: Mapping[str, Any]) -> bool:
    return str(record.get("source_type", "")) != "token_transfer" and str(
        record.get("transaction_type", "")
    ) in {"native_transfer", "transfer"}


def _material_threshold(goal: FirstHopGoal, asset: str) -> Decimal:
    thresholds = goal.materiality_thresholds or {}
    return Decimal(str(thresholds.get(asset, thresholds.get("*", "0"))))


def _label_index(labels: Iterable[LabelRecord]) -> dict[tuple[str, str], LabelRecord]:
    priority = {
        "manual_confirmed": 5,
        "verified": 4,
        "trusted_local": 4,
        "provider_label": 3,
        "provider": 3,
        "unverified_candidate": 2,
        "candidate": 2,
    }
    result: dict[tuple[str, str], LabelRecord] = {}
    for label in labels:
        key = (label.chain.casefold(), label.address)
        current = result.get(key)
        current_status = _label_verification(current) if current else ""
        candidate_status = _label_verification(label)
        current_rank = priority.get(current_status, 0)
        candidate_rank = priority.get(candidate_status, 1)
        if current is None or candidate_rank > current_rank:
            result[key] = label
    return result


def _label_verification(label: LabelRecord) -> str:
    status = getattr(label, "verification_status", "")
    if status == "unverified_candidate" and label.confidence in {
        "verified",
        "trusted_local",
        "manual_confirmed",
        "provider_label",
    }:
        return label.confidence
    return status or label.confidence


def _counterparties(
    records: Sequence[Mapping[str, Any]],
    target: str,
    direction: str,
    *,
    labels: Mapping[tuple[str, str], LabelRecord],
    chain: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        amount = _amount(record)
        if amount <= 0 or _direction(record, target) != direction:
            continue
        address = str(
            record.get("from_address")
            if direction == "incoming"
            else record.get("to_address")
        )
        item = grouped.setdefault(
            address,
            {
                "address": address,
                "amount": Decimal("0"),
                "returned_amount": Decimal("0"),
                "transaction_count": 0,
                "timestamps": [],
                "evidence_refs": [],
            },
        )
        item["amount"] += amount
        item["transaction_count"] += 1
        item["timestamps"].append(_timestamp(record))
        if record.get("tx_hash"):
            item["evidence_refs"].append(str(record["tx_hash"]))
    total = sum((item["amount"] for item in grouped.values()), Decimal("0"))
    ranked = sorted(
        grouped.values(),
        key=lambda item: (-item["amount"], -item["transaction_count"], item["address"]),
    )
    for rank, item in enumerate(ranked, 1):
        label = labels.get((chain.casefold(), item["address"]))
        item.update(
            rank=rank,
            share=item["amount"] / total if total else Decimal("0"),
            first_seen=min(item["timestamps"]).isoformat(),
            last_seen=max(item.pop("timestamps")).isoformat(),
            label=label.label if label else None,
            label_source=label.source if label else None,
            verification_status=(
                _label_verification(label)
                if label
                else "unverified"
            ),
        )
    return ranked


def _shares(ranked: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {
        f"top_{count}_share": str(
            sum(
                (Decimal(str(item["share"])) for item in ranked[:count]),
                Decimal("0"),
            )
        )
        for count in (1, 3, 5, 10)
    }


def _series(
    records: Sequence[Mapping[str, Any]], target: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    daily: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"incoming": Decimal("0"), "outgoing": Decimal("0")}
    )
    monthly: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"incoming": Decimal("0"), "outgoing": Decimal("0")}
    )
    for record in records:
        direction = _direction(record, target)
        amount = _amount(record)
        if amount <= 0 or direction not in {"incoming", "outgoing"}:
            continue
        stamp = _timestamp(record)
        daily[stamp.strftime("%Y-%m-%d")][direction] += amount
        monthly[stamp.strftime("%Y-%m")][direction] += amount

    def rows(values):
        return [
            {
                "period": period,
                "incoming": str(item["incoming"]),
                "outgoing": str(item["outgoing"]),
                "net": str(item["incoming"] - item["outgoing"]),
            }
            for period, item in sorted(values.items())
        ]

    return rows(daily), rows(monthly)


def _adjacent_timing(
    records: Sequence[Mapping[str, Any]], target: str
) -> dict[str, Any]:
    ordered = sorted(
        (item for item in records if _amount(item) > 0), key=_timestamp
    )
    intervals = []
    for current, following in zip(ordered, ordered[1:]):
        if (
            _direction(current, target) == "incoming"
            and _direction(following, target) == "outgoing"
        ):
            seconds = (_timestamp(following) - _timestamp(current)).total_seconds()
            if seconds >= 0:
                intervals.append(seconds)
    return {
        "adjacent_inflow_outflow_count": len(intervals),
        "within_1_hour_count": sum(value <= 3600 for value in intervals),
        "within_24_hours_count": sum(value <= 86400 for value in intervals),
        "within_1_hour_ratio": (
            str(Decimal(sum(value <= 3600 for value in intervals)) / len(intervals))
            if intervals
            else "0"
        ),
        "within_24_hours_ratio": (
            str(Decimal(sum(value <= 86400 for value in intervals)) / len(intervals))
            if intervals
            else "0"
        ),
        "limitation": (
            "相鄰流入後流出僅表示時間接近，不代表兩筆交易為同一資金。"
        ),
    }


def _stages(asset: Mapping[str, Any]) -> list[dict[str, Any]]:
    monthly = list(asset["monthly"])
    if len(monthly) < 3:
        return []
    volumes = [
        Decimal(item["incoming"]) + Decimal(item["outgoing"]) for item in monthly
    ]
    change_scores = [
        (
            abs(volumes[index] - volumes[index - 1]) / volumes[index - 1],
            index,
        )
        for index in range(1, len(volumes))
        if volumes[index - 1]
        and abs(volumes[index] - volumes[index - 1]) / volumes[index - 1]
        >= Decimal("0.50")
    ]
    changes = sorted(index for _, index in sorted(change_scores, reverse=True)[:3])
    if not changes:
        return []
    boundaries = [0, *changes, len(monthly)]
    result = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), 1):
        rows = monthly[start:end]
        incoming = sum((Decimal(item["incoming"]) for item in rows), Decimal("0"))
        outgoing = sum((Decimal(item["outgoing"]) for item in rows), Decimal("0"))
        result.append(
            {
                "stage": f"時間區段 {index}",
                "period_from": rows[0]["period"],
                "period_to": rows[-1]["period"],
                "incoming": str(incoming),
                "outgoing": str(outgoing),
                "net": str(incoming - outgoing),
                "transaction_count": None,
                "main_source": None,
                "main_destination": None,
                "change_from_previous": (
                    "月度雙向總量相較前期變化達 50% 門檻"
                    if index > 1
                    else "起始區段"
                ),
                "rule_basis": "monthly_bidirectional_volume_change",
                "confidence": "medium",
                "limitation": "月度彙總未提供區段內逐月主要對手方變化。",
                "observation_id": f"OBS-STAGE-{index:03d}",
            }
        )
    return result


def _summary(
    target: str,
    chain: str,
    principal: Mapping[str, Any] | None,
    candidates: Sequence[Mapping[str, Any]],
    complete: bool,
) -> list[str]:
    if principal is None:
        return [
            f"調查標的為 {chain} 鏈地址 {target}；目前資料不足以識別主要價值資產。"
        ]
    sources = principal["source_concentration"]
    destinations = principal["destination_concentration"]
    sentences = [
        (
            f"本案主要價值資產為 {principal['asset']}；分析範圍內流入"
            f" {principal['incoming_total']}、流出 {principal['outgoing_total']}，"
            f"雙向總量 {principal['bidirectional_volume']}，淨流量"
            f" {principal['net_flow']}。"
        ),
        (
            f"第一大來源占流入 {Decimal(sources['top_1_share']):.2%}，"
            f"前五大來源占 {Decimal(sources['top_5_share']):.2%}；"
            f"第一大去向占流出 {Decimal(destinations['top_1_share']):.2%}，"
            f"前五大去向占 {Decimal(destinations['top_5_share']):.2%}。"
        ),
    ]
    if candidates:
        first = candidates[0]
        sentences.append(
            f"第一層優先追查地址為 {first['address']}，於目前資料中接收"
            f" {first['received_amount']} {first['asset']}；其優先級僅代表"
            "後續查詢順序，不代表身分、風險或下車點已確認。"
        )
    if not complete:
        sentences.append("Provider 資料尚未完整取得，所有排行與期間結論均屬部分範圍。")
    sentences.append(
        "本報告尚未執行第二層追蹤，不能據此確認最終受益人或最終下車點。"
    )
    return sentences


def _follow_up_tasks(
    candidates: Sequence[Mapping[str, Any]], complete: bool
) -> list[dict[str, Any]]:
    tasks = []
    for candidate in candidates[:5]:
        tasks.append(
            {
                "task_type": "first_hop_onward_collection",
                "address": candidate["address"],
                "asset": candidate["asset"],
                "received_amount": candidate["received_amount"],
                "share": candidate["share_of_target_outflow"],
                "transaction_count": candidate["transaction_count"],
                "period": {
                    "from": candidate["first_receipt"],
                    "to": candidate["last_receipt"],
                },
                "current_label": candidate["label"],
                "label_verification_status": candidate["verification_status"],
                "evidence_refs": candidate["evidence_refs"],
                "next_data_required": (
                    "該地址同資產後續交易、完整分頁 metadata 與可信 Local Label"
                ),
                "expected_question_answered": "該第一層去向後續流向何處",
                "stop_condition": (
                    "Provider incomplete、低於重要性門檻、無後續活動或達人工設定深度"
                ),
            }
        )
    if not complete:
        tasks.insert(
            0,
            {
                "task_type": "evidence_completion",
                "next_data_required": "完成 required capabilities 分頁並驗證 artifact SHA-256",
                "expected_question_answered": "目前排行是否涵蓋指定分析範圍",
                "stop_condition": "retrieval completeness = complete",
            },
        )
    return tasks


def _role_order(role: AssetInvestigationRole) -> int:
    return {
        AssetInvestigationRole.PRINCIPAL_VALUE: 0,
        AssetInvestigationRole.SECONDARY_VALUE: 1,
        AssetInvestigationRole.OPERATIONAL: 2,
        AssetInvestigationRole.LOW_MATERIALITY: 3,
        AssetInvestigationRole.UNKNOWN: 4,
    }[role]


def build_first_hop_product(
    records: Sequence[Mapping[str, Any]],
    provider_status: Sequence[Mapping[str, Any]],
    *,
    target_address: str,
    chain: str,
    goal: FirstHopGoal | None = None,
    labels: Iterable[LabelRecord] = (),
) -> dict[str, Any]:
    goal = goal or FirstHopGoal()
    labels = tuple(labels)
    label_map = _label_index(labels)
    grouped: dict[tuple[str, str | None], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[_asset_key(record)].append(record)

    analyses: list[dict[str, Any]] = []
    for (asset, contract), asset_records in grouped.items():
        threshold = _material_threshold(goal, asset)
        material = [
            item
            for item in asset_records
            if _amount(item) > threshold or _amount(item) == 0
        ]
        nonzero = [item for item in material if _amount(item) > 0]
        incoming = [
            item for item in nonzero if _direction(item, target_address) == "incoming"
        ]
        outgoing = [
            item for item in nonzero if _direction(item, target_address) == "outgoing"
        ]
        incoming_total = sum((_amount(item) for item in incoming), Decimal("0"))
        outgoing_total = sum((_amount(item) for item in outgoing), Decimal("0"))
        sources = _counterparties(
            material, target_address, "incoming", labels=label_map, chain=chain
        )
        destinations = _counterparties(
            material, target_address, "outgoing", labels=label_map, chain=chain
        )
        outgoing_by_address = {
            item["address"]: item["amount"] for item in destinations
        }
        incoming_by_address = {item["address"]: item["amount"] for item in sources}
        for item in sources:
            item["returned_amount"] = outgoing_by_address.get(
                item["address"], Decimal("0")
            )
        for item in destinations:
            item["returned_amount"] = incoming_by_address.get(
                item["address"], Decimal("0")
            )
        incoming_set = {item["address"] for item in sources}
        outgoing_set = {item["address"] for item in destinations}
        daily, monthly = _series(material, target_address)
        analyses.append(
            {
                "asset": asset,
                "contract": contract,
                "native": any(_is_native(item) for item in asset_records),
                "records": asset_records,
                "material_records": material,
                "transaction_count": len(asset_records),
                "material_transaction_count": len(nonzero),
                "zero_value_count": sum(_amount(item) == 0 for item in asset_records),
                "excluded_count": len(asset_records) - len(material),
                "incoming_count": len(incoming),
                "outgoing_count": len(outgoing),
                "incoming_total": incoming_total,
                "outgoing_total": outgoing_total,
                "bidirectional_volume": incoming_total + outgoing_total,
                "net_flow": incoming_total - outgoing_total,
                "retained_ratio": (
                    (incoming_total - outgoing_total) / incoming_total
                    if incoming_total
                    else Decimal("0")
                ),
                "unique_incoming_counterparties": len(incoming_set),
                "unique_outgoing_counterparties": len(outgoing_set),
                "bidirectional_counterparties": len(incoming_set & outgoing_set),
                "total_nonzero_counterparties": len(incoming_set | outgoing_set),
                "sources": sources,
                "destinations": destinations,
                "source_concentration": _shares(sources),
                "destination_concentration": _shares(destinations),
                "daily": daily,
                "monthly": monthly,
                "timing": _adjacent_timing(material, target_address),
                "first_seen": (
                    min(map(_timestamp, asset_records)).isoformat()
                    if asset_records
                    else None
                ),
                "last_seen": (
                    max(map(_timestamp, asset_records)).isoformat()
                    if asset_records
                    else None
                ),
            }
        )

    requested = set(goal.required_assets)
    valuable = [
        item
        for item in analyses
        if item["bidirectional_volume"] > 0 and not item["asset"].startswith("UNKNOWN")
    ]
    token_value = [item for item in valuable if not item["native"]]
    principal_pool = (
        [item for item in valuable if item["asset"] in requested]
        or token_value
        or valuable
    )
    principal = max(
        principal_pool,
        key=lambda item: (
            item["bidirectional_volume"],
            item["material_transaction_count"],
            item["asset"],
        ),
        default=None,
    )
    for item in analyses:
        if item is principal:
            role = AssetInvestigationRole.PRINCIPAL_VALUE
        elif item["bidirectional_volume"] <= _material_threshold(goal, item["asset"]):
            role = AssetInvestigationRole.LOW_MATERIALITY
        elif item["native"] and principal is not None and not principal["native"]:
            role = AssetInvestigationRole.OPERATIONAL
        elif item["asset"].startswith("UNKNOWN"):
            role = AssetInvestigationRole.UNKNOWN
        else:
            role = AssetInvestigationRole.SECONDARY_VALUE
        item["role"] = role.value
        item.pop("records")
        item.pop("material_records")

    analyses.sort(
        key=lambda item: (
            _role_order(AssetInvestigationRole(item["role"])),
            -item["bidirectional_volume"],
            item["asset"],
        )
    )
    principal = next(
        (item for item in analyses if item["role"] == "principal_value_asset"), None
    )
    candidates = []
    if principal:
        for index, item in enumerate(principal["destinations"][:10], 1):
            candidates.append(
                {
                    "candidate_id": f"FH-{index:03d}",
                    "address": item["address"],
                    "asset": principal["asset"],
                    "received_amount": str(item["amount"]),
                    "transaction_count": item["transaction_count"],
                    "share_of_target_outflow": str(item["share"]),
                    "first_receipt": item["first_seen"],
                    "last_receipt": item["last_seen"],
                    "return_flow": str(item["returned_amount"]),
                    "onward_data_status": "not_collected",
                    "rapid_onward_transfer": None,
                    "aggregation_indicator": None,
                    "fan_out_indicator": None,
                    "label": item["label"],
                    "label_source": item["label_source"],
                    "verification_status": item["verification_status"],
                    "priority": "high" if index <= 5 else "medium",
                    "priority_reasons": (
                        "principal_value_asset",
                        "received_amount_descending",
                        "share_of_total_outflow",
                    ),
                    "evidence_refs": tuple(item["evidence_refs"]),
                    "recommended_next_action": (
                        "取得該地址後續交易與可信標籤資料；若資料不完整或低於"
                        "重要性門檻則停止。"
                    ),
                }
            )

    statuses = {
        str(item.get("capability")): item
        for item in provider_status
        if item.get("capability")
    }
    required = goal.required_capabilities or tuple(statuses)
    completeness = all(
        statuses.get(item, {}).get("final_completeness") == "complete"
        and not statuses.get(item, {}).get("truncated")
        for item in required
    )
    stages = _stages(principal) if principal else []
    return {
        "product_version": "1",
        "target_address": target_address,
        "chain": chain,
        "goal": {
            "goal_types": goal.goal_types,
            "required_assets": goal.required_assets,
            "required_capabilities": required,
            "scope_type": goal.scope_type,
            "output_type": goal.output_type,
            "completeness_required": goal.completeness_required,
        },
        "retrieval_complete": completeness,
        "assets": analyses,
        "asset_roles": [
            {
                "asset": item["asset"],
                "contract": item["contract"],
                "role": item["role"],
            }
            for item in analyses
        ],
        "principal_asset": principal,
        "first_hop_candidates": candidates,
        "executive_summary": _summary(
            target_address, chain, principal, candidates, completeness
        ),
        "stages": stages,
        "follow_up_tasks": _follow_up_tasks(candidates, completeness),
        "labels": {
            "supplied_count": len(labels),
            "applied_count": sum(
                1
                for item in analyses
                for side in ("sources", "destinations")
                for counterparty in item[side]
                if counterparty["label"]
            ),
        },
        "limitations": (
            "第一層來源與去向並列不代表同一筆資金流向。",
            "尚未取得候選地址後續層級資料，不能確認下車點或最終受益人。",
        ),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _svg_bars(title: str, rows: Sequence[tuple[str, Decimal]]) -> str:
    width, height = 900, max(240, 90 + len(rows) * 38)
    maximum = max((value for _, value in rows), default=Decimal("1")) or Decimal("1")
    bars = []
    for index, (label, value) in enumerate(rows):
        y = 70 + index * 38
        bar_width = int(560 * value / maximum)
        safe_label = (
            label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        bars.append(
            f'<text x="15" y="{y + 17}" font-size="14">{safe_label}</text>'
            f'<rect x="260" y="{y}" width="{bar_width}" height="22" fill="#147d78"/>'
            f'<text x="{270 + bar_width}" y="{y + 17}" font-size="13">{value}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/>'
        f'<text x="15" y="32" font-size="22" font-weight="bold">{title}</text>'
        + "".join(bars)
        + "</svg>"
    )


def write_first_hop_product(
    result: Mapping[str, Any], output_directory: Path
) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    payload = _jsonable(result)
    result_path = output_directory / "first_hop_product.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    artifacts: dict[str, dict[str, str]] = {}
    principal = result.get("principal_asset")
    if principal:
        charts = {
            "top_sources": (
                f"{principal['asset']} 前十大來源",
                [
                    (item["address"], Decimal(str(item["amount"])))
                    for item in principal["sources"][:10]
                ],
            ),
            "top_destinations": (
                f"{principal['asset']} 前十大去向",
                [
                    (item["address"], Decimal(str(item["amount"])))
                    for item in principal["destinations"][:10]
                ],
            ),
            "monthly_flow": (
                f"{principal['asset']} 月度雙向總量",
                [
                    (
                        item["period"],
                        Decimal(str(item["incoming"]))
                        + Decimal(str(item["outgoing"])),
                    )
                    for item in principal["monthly"]
                ],
            ),
            "first_hop_priority": (
                "第一層候選優先級",
                [
                    (
                        item["candidate_id"],
                        Decimal(str(item["received_amount"])),
                    )
                    for item in result.get("first_hop_candidates", ())
                ],
            ),
        }
        for name, (title, rows) in charts.items():
            if not rows:
                continue
            path = output_directory / f"{name}.svg"
            path.write_text(_svg_bars(title, rows), encoding="utf-8")
            artifacts[name] = {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    manifest = output_directory / "first_hop_chart_manifest.json"
    manifest.write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "product": result_path,
        "chart_manifest": manifest,
        "charts": artifacts,
    }
