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
    Counterparty,
    FlowResult,
    SummaryResult,
    TimelineResult,
)


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
