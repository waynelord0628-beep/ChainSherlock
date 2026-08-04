from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.application import (
    ArtifactType,
    CaseExecutionService,
    ExecutionStatus,
    create_desktop_execution_registry,
)
from crypto_investigator.cases import CaseRepository
from crypto_investigator.domain import Chain, Direction, Transaction
from crypto_investigator.ui.services import CaseUIService


TARGET = "0x" + "1" * 40
OTHER = "0x" + "2" * 40
FAKE_SECRET = "sk-proj-" + "x" * 32


class RecordedProviderRunner:
    def __init__(self, completeness: str = "complete") -> None:
        self.completeness = completeness
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(
            {
                key: value
                for key, value in kwargs.items()
                if key not in {"settings", "output_dir"}
            }
        )
        output = kwargs["output_dir"]
        output.mkdir(parents=True, exist_ok=True)
        identifier = kwargs["identifier"]
        chain = kwargs["chain"]
        transactions = (
            Transaction(
                chain=chain,
                tx_hash="0x" + "a" * 64,
                from_address=OTHER,
                to_address=identifier,
                asset_symbol="ETH",
                amount=1,
                direction=Direction.INCOMING,
            ),
            Transaction(
                chain=chain,
                tx_hash="0x" + "b" * 64,
                from_address=identifier,
                to_address=OTHER,
                asset_symbol="ETH",
                amount=1,
                direction=Direction.OUTGOING,
            ),
        )
        analysis = AnalysisEngine().analyze(transactions, identifier)
        analysis = replace(
            analysis,
            metadata={
                **analysis.metadata,
                "chain": chain.value,
                "target_address": identifier,
                "completeness": self.completeness,
            },
        )
        paths = AnalysisExporter().export_all(analysis, output)
        status = [
            {
                "provider": "primary",
                "chain": chain.value,
                "capability": "address_transactions",
                "status": "partial",
                "fallback_attempted": True,
                "fallback_result": self.completeness,
                "final_completeness": self.completeness,
                "fetched_records": 2,
                "truncated": self.completeness == "partial",
            },
            {
                "provider": "fallback",
                "chain": chain.value,
                "capability": "address_transactions",
                "status": self.completeness,
                "fallback_attempted": False,
                "fallback_result": None,
                "final_completeness": self.completeness,
                "fetched_records": 2,
                "truncated": self.completeness == "partial",
            },
        ]
        errors = [
            {
                "error_type": "RecordedProviderError",
                "safe_message": f"temporary failure {FAKE_SECRET}",
                "authorization": "Bearer should-not-persist",
                "resolved_by_fallback": self.completeness == "complete",
            }
        ]
        for name, payload in (
            ("provider_status", status),
            ("provider_errors", errors),
            ("rejected_records", []),
        ):
            path = output / f"{name}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            paths[name] = path
        return paths


def _case(repository: CaseRepository, goal_type: str = "generate_investigation_report"):
    ui = CaseUIService(repository)
    case = ui.create_case("Provider M8")
    case = repository.save(
        case.model_copy(
            update={
                "metadata": {
                    "chain": "ethereum",
                    "known_addresses": [TARGET],
                }
            }
        )
    )
    ui.add_goal(case.case_id, goal_type, goal_type, [TARGET])
    plan = ui.create_plan(case.case_id)
    ui.confirm_latest_plan(case.case_id)
    return case, plan


def test_provider_execution_fallback_reaches_graph_investigation_and_report(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CHAINSHERLOCK_PDF_CJK_FONT", r"C:\Windows\Fonts\kaiu.ttf")
    repository = CaseRepository(tmp_path / "cases")
    case, plan = _case(repository)
    runner = RecordedProviderRunner()
    service = CaseExecutionService(
        repository,
        create_desktop_execution_registry(
            repository, provider_runner=runner
        ),
    )

    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)

    assert completed.success
    assert completed.execution.status is ExecutionStatus.COMPLETED
    assert len(runner.calls) == 1
    assert runner.calls[0]["provider"] is None
    types = {item.artifact_type for item in completed.artifacts}
    assert {
        ArtifactType.ANALYSIS_RESULT,
        ArtifactType.PROVIDER_STATUS,
        ArtifactType.PROVIDER_ERRORS,
        ArtifactType.REJECTED_RECORDS,
        ArtifactType.GRAPH_HTML,
        ArtifactType.INVESTIGATION_RESULT,
        ArtifactType.REPORT_MARKDOWN,
        ArtifactType.REPORT_HTML,
        ArtifactType.REPORT_DOCX,
        ArtifactType.REPORT_PDF,
    }.issubset(types)
    error = next(
        item
        for item in completed.artifacts
        if item.artifact_type is ArtifactType.PROVIDER_ERRORS
    )
    content = repository.workspace(case.case_id).resolve_relative(
        error.relative_path
    ).read_text(encoding="utf-8")
    assert FAKE_SECRET not in content
    assert "Bearer should-not-persist" not in content
    assert str(tmp_path) not in content


def test_provider_partial_is_preserved_without_second_request(
    tmp_path: Path,
) -> None:
    repository = CaseRepository(tmp_path / "cases")
    case, plan = _case(repository, "identify_main_sources")
    runner = RecordedProviderRunner("partial")
    service = CaseExecutionService(
        repository,
        create_desktop_execution_registry(
            repository, provider_runner=runner
        ),
    )

    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)

    assert not completed.success
    assert completed.execution.status is ExecutionStatus.PARTIAL
    assert len(runner.calls) == 1
    status = next(
        item
        for item in completed.artifacts
        if item.artifact_type is ArtifactType.PROVIDER_STATUS
    )
    payload = json.loads(
        repository.workspace(case.case_id)
        .resolve_relative(status.relative_path)
        .read_text(encoding="utf-8")
    )
    assert payload[0]["fallback_attempted"] is True
    assert payload[-1]["final_completeness"] == "partial"
