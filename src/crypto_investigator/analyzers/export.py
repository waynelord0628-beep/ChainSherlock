import csv
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping

from crypto_investigator.analyzers.models import (
    AnalysisResult,
    AssetStatistics,
    Counterparty,
    FlowEdge,
    FlowNode,
    FlowResult,
    StatisticsResult,
    SummaryResult,
    TimelineBucket,
    TimelineResult,
    TransactionAmountRef,
)
from crypto_investigator.domain.transaction import Direction


class AnalysisExporter:
    """Export analysis data only; no report or visualization generation."""

    def export_all(self, result: AnalysisResult, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "analysis": output_dir / "analysis.json",
            "summary": output_dir / "summary.json",
            "counterparties": output_dir / "counterparties.csv",
            "timeline_json": output_dir / "timeline.json",
            "timeline_csv": output_dir / "timeline.csv",
            "flow": output_dir / "flow.json",
        }
        self.write_json(paths["analysis"], result)
        self.write_summary(paths["summary"], result.summary)
        self.write_counterparties(paths["counterparties"], result.counterparties)
        self.write_timeline_json(paths["timeline_json"], result.timeline)
        self.write_timeline_csv(paths["timeline_csv"], result.timeline)
        self.write_flow(paths["flow"], result.flow)
        return paths

    def write_summary(self, path: Path, summary: SummaryResult) -> None:
        self.write_json(path, summary)

    def write_counterparties(
        self, path: Path, counterparties: tuple[Counterparty, ...]
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = (
            "address",
            "incoming_count",
            "outgoing_count",
            "incoming_amount_by_asset",
            "outgoing_amount_by_asset",
            "first_seen",
            "last_seen",
            "interaction_count",
            "direction",
        )
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for counterparty in counterparties:
                row = self.to_primitive(counterparty)
                row["incoming_amount_by_asset"] = json.dumps(
                    row["incoming_amount_by_asset"], ensure_ascii=False
                )
                row["outgoing_amount_by_asset"] = json.dumps(
                    row["outgoing_amount_by_asset"], ensure_ascii=False
                )
                writer.writerow(row)

    def write_timeline_json(self, path: Path, timeline: TimelineResult) -> None:
        self.write_json(path, timeline)

    def write_timeline_csv(self, path: Path, timeline: TimelineResult) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(
                output,
                fieldnames=(
                    "granularity",
                    "period",
                    "transaction_count",
                    "amounts_by_asset",
                ),
            )
            writer.writeheader()
            for granularity, buckets in (
                ("daily", timeline.daily),
                ("monthly", timeline.monthly),
            ):
                for period, bucket in buckets.items():
                    writer.writerow(
                        {
                            "granularity": granularity,
                            "period": period,
                            "transaction_count": bucket.transaction_count,
                            "amounts_by_asset": json.dumps(
                                self.to_primitive(bucket.amounts_by_asset),
                                ensure_ascii=False,
                            ),
                        }
                    )

    def write_flow(self, path: Path, flow: FlowResult) -> None:
        self.write_json(path, flow)

    def write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_primitive(value), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def read_analysis(self, path: Path) -> AnalysisResult:
        value = json.loads(path.read_text(encoding="utf-8"))
        timestamp = lambda item: datetime.fromisoformat(item) if item else None
        summary = value["summary"]
        statistics = value["statistics"]
        timeline = value["timeline"]
        flow = value["flow"]
        amount_refs = lambda items: {
            asset: TransactionAmountRef(
                tx_hash=item["tx_hash"], amount=Decimal(item["amount"])
            )
            for asset, item in items.items()
        }
        return AnalysisResult(
            summary=SummaryResult(
                **{
                    **summary,
                    "first_seen": timestamp(summary.get("first_seen")),
                    "last_seen": timestamp(summary.get("last_seen")),
                    "assets": tuple(summary.get("assets", [])),
                }
            ),
            statistics=StatisticsResult(
                incoming_amount={
                    key: Decimal(item)
                    for key, item in statistics["incoming_amount"].items()
                },
                outgoing_amount={
                    key: Decimal(item)
                    for key, item in statistics["outgoing_amount"].items()
                },
                asset_breakdown={
                    key: AssetStatistics(
                        **{
                            **item,
                            "total_amount": Decimal(item["total_amount"]),
                            "average_amount": Decimal(item["average_amount"]),
                            "median_amount": Decimal(item["median_amount"]),
                            "max_amount": Decimal(item["max_amount"]),
                            "min_amount": Decimal(item["min_amount"]),
                        }
                    )
                    for key, item in statistics["asset_breakdown"].items()
                },
                top_asset=statistics.get("top_asset"),
                average_amount={
                    key: Decimal(item)
                    for key, item in statistics["average_amount"].items()
                },
                median_amount={
                    key: Decimal(item)
                    for key, item in statistics["median_amount"].items()
                },
                max_transaction=amount_refs(statistics["max_transaction"]),
                min_transaction=amount_refs(statistics["min_transaction"]),
                transaction_frequency=statistics["transaction_frequency"],
            ),
            counterparties=tuple(
                Counterparty(
                    **{
                        **item,
                        "incoming_amount_by_asset": {
                            key: Decimal(amount)
                            for key, amount in item[
                                "incoming_amount_by_asset"
                            ].items()
                        },
                        "outgoing_amount_by_asset": {
                            key: Decimal(amount)
                            for key, amount in item[
                                "outgoing_amount_by_asset"
                            ].items()
                        },
                        "first_seen": timestamp(item.get("first_seen")),
                        "last_seen": timestamp(item.get("last_seen")),
                        "direction": Direction(item["direction"]),
                    }
                )
                for item in value["counterparties"]
            ),
            timeline=TimelineResult(
                daily={
                    key: TimelineBucket(
                        transaction_count=item["transaction_count"],
                        amounts_by_asset={
                            asset: Decimal(amount)
                            for asset, amount in item["amounts_by_asset"].items()
                        },
                    )
                    for key, item in timeline["daily"].items()
                },
                monthly={
                    key: TimelineBucket(
                        transaction_count=item["transaction_count"],
                        amounts_by_asset={
                            asset: Decimal(amount)
                            for asset, amount in item["amounts_by_asset"].items()
                        },
                    )
                    for key, item in timeline["monthly"].items()
                },
                hourly_distribution={
                    int(key): count
                    for key, count in timeline["hourly_distribution"].items()
                },
                weekly_distribution=timeline["weekly_distribution"],
            ),
            flow=FlowResult(
                nodes=tuple(FlowNode(**item) for item in flow["nodes"]),
                edges=tuple(
                    FlowEdge(
                        **{
                            **item,
                            "direction": Direction(item["direction"]),
                            "weight": Decimal(item["weight"]),
                            "timestamp": timestamp(item.get("timestamp")),
                        }
                    )
                    for item in flow["edges"]
                ),
            ),
            metadata=value.get("metadata", {}),
            warnings=tuple(value.get("warnings", [])),
        )

    @classmethod
    def to_primitive(cls, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: cls.to_primitive(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, Mapping):
            return {str(key): cls.to_primitive(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [cls.to_primitive(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return value
