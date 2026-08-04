import csv
from pathlib import Path

from crypto_investigator.investigation.investigation_result import (
    LabelRecord,
    ServiceDetection,
)


def load_labels(path: Path) -> tuple[LabelRecord, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return tuple(
            LabelRecord(
                address=str(row["address"]).strip(),
                label=str(row.get("label", "")).strip(),
                category=str(row.get("category", "unknown")).strip().casefold(),
                source="csv",
            )
            for row in csv.DictReader(stream)
            if row.get("address")
        )


def detect_services(counterparties, labels=()) -> tuple[ServiceDetection, ...]:
    label_map = {item.address.casefold(): item for item in labels}
    results = []
    for item in counterparties:
        label = label_map.get(item.address.casefold())
        matched = []
        service_type = "unknown"
        if label and label.category in {"exchange", "otc", "payment", "service"}:
            service_type = label.category
            matched.append("local_label")
        elif item.interaction_count >= 20 and item.incoming_count and item.outgoing_count:
            service_type = "possible_service"
            matched.append("high_frequency_bidirectional")
        elif item.interaction_count >= 10 and item.outgoing_count >= item.incoming_count * 3:
            service_type = "possible_payment"
            matched.append("high_outgoing_frequency")
        if matched:
            results.append(
                ServiceDetection(
                    item.address,
                    service_type,
                    tuple(matched),
                    label.label if label else None,
                    label.category if label else None,
                )
            )
    return tuple(results)
