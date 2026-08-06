import csv
import json
from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import (
    AllocationMethod,
    SeedType,
    TraceDirection,
    TraceEdge,
    TraceResult,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.domain.investigation_priority import (
    PrioritySignals,
    score_investigation_priority,
)
from crypto_investigator.domain.trace_evidence_package import (
    TraceAuditRecord,
    write_trace_evidence_package,
)


def _result() -> TraceResult:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return TraceResult(
        run_id="TRACE-1",
        status=TraceRunStatus.COMPLETED,
        seed=TraceSeed(SeedType.ADDRESS, "TARGET", "tron", "USDT", ("EV-1",)),
        scope=TraceScope(
            "full_history",
            3,
            100,
            1000,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.FORWARD,
        ),
        nodes=(),
        edges=(
            TraceEdge(
                "E-1",
                "TARGET",
                "NEXT",
                "TX-1",
                "USDT",
                Decimal("10.25"),
                now,
                AllocationMethod.DIRECT_TRANSACTION,
                Decimal("1"),
                ("EV-1",),
            ),
        ),
    )


def test_package_writes_all_required_files(tmp_path):
    result = _result()
    priority = score_investigation_priority(
        candidate_id="C-1",
        address="NEXT",
        asset="USDT",
        signals=PrioritySignals(exclusive_amount_ratio=Decimal("1")),
    )
    outputs = write_trace_evidence_package(
        tmp_path,
        result=result,
        priorities=(priority,),
        audit_records=(
            TraceAuditRecord("AUD-1", "classification", "C-1", "candidate", "rule"),
        ),
    )
    assert set(outputs) == {
        "all_paths",
        "service_candidates",
        "terminal_candidates",
        "provider_incomplete",
        "allocation_groups",
        "trace_graph",
        "trace_audit",
    }
    assert all(path.exists() for path in outputs.values())


def test_all_paths_preserves_real_tx_hash_and_decimal(tmp_path):
    outputs = write_trace_evidence_package(tmp_path, result=_result())
    with outputs["all_paths"].open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["tx_hash"] == "TX-1"
    assert row["amount"] == "10.25"


def test_json_uses_iso_dates_and_relative_content_only(tmp_path):
    outputs = write_trace_evidence_package(tmp_path, result=_result())
    payload = json.loads(outputs["trace_graph"].read_text(encoding="utf-8"))
    assert payload["edges"][0]["timestamp"].endswith("+00:00")
    assert str(tmp_path) not in outputs["trace_graph"].read_text(encoding="utf-8")


def test_package_never_contains_secret_headers(tmp_path):
    outputs = write_trace_evidence_package(tmp_path, result=_result())
    text = "\n".join(path.read_text(encoding="utf-8-sig") for path in outputs.values())
    assert "Authorization" not in text
    assert "API Key" not in text
