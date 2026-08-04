from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from crypto_investigator.application import (
    ArtifactType,
    CaseExecutionService,
    ExecutionStatus,
    create_offline_execution_registry,
)
from crypto_investigator.cases import CaseRepository
from crypto_investigator.ui.services import CaseUIService


TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def _csv(path: Path) -> Path:
    path.write_text(
        "from,to,amount,asset,timestamp,hash\n"
        f"{OTHER},{TARGET},10,ETH,2026-01-01T00:00:00Z,"
        "0x0000000000000000000000000000000000000000000000000000000000000001\n"
        f"{TARGET},{OTHER},4,ETH,2026-01-02T00:00:00Z,"
        "0x0000000000000000000000000000000000000000000000000000000000000002\n"
        f"{OTHER},{TARGET},6,ETH,2026-01-03T00:00:00Z,"
        "0x0000000000000000000000000000000000000000000000000000000000000003\n",
        encoding="utf-8",
    )
    return path


def _confirmed_offline_case(repository: CaseRepository, source: Path):
    ui = CaseUIService(repository)
    case = ui.create_case("Offline V8 M7")
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
    ui.import_evidence(case.case_id, source)
    ui.add_goal(
        case.case_id,
        "generate_investigation_report",
        "Generate investigation report",
        [TARGET],
    )
    plan = ui.create_plan(case.case_id)
    ui.confirm_latest_plan(case.case_id)
    return case, plan


def _xlsx(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("from", "to", "amount", "asset", "timestamp", "hash"))
    sheet.append(
        (
            OTHER,
            TARGET,
            "3",
            "ETH",
            "2026-01-01T00:00:00Z",
            "0x" + "1" * 64,
        )
    )
    workbook.save(path)
    workbook.close()
    return path


def test_offline_csv_case_runs_pipeline_to_four_reports(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CHAINSHERLOCK_PDF_CJK_FONT", r"C:\Windows\Fonts\kaiu.ttf")
    repository = CaseRepository(tmp_path / "cases")
    case, plan = _confirmed_offline_case(repository, _csv(tmp_path / "evidence.csv"))
    service = CaseExecutionService(
        repository, create_offline_execution_registry(repository)
    )

    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)

    assert completed.success
    assert completed.execution.status is ExecutionStatus.COMPLETED
    types = {item.artifact_type for item in completed.artifacts}
    assert {
        ArtifactType.NORMALIZED_TRANSACTIONS,
        ArtifactType.ANALYSIS_RESULT,
        ArtifactType.GRAPH_JSON,
        ArtifactType.GRAPHML,
        ArtifactType.GRAPH_HTML,
        ArtifactType.INVESTIGATION_RESULT,
        ArtifactType.OBSERVATIONS,
        ArtifactType.CONCLUSION_FACTS,
        ArtifactType.EVIDENCE_MANIFEST,
        ArtifactType.REPORT_MARKDOWN,
        ArtifactType.REPORT_HTML,
        ArtifactType.REPORT_DOCX,
        ArtifactType.REPORT_PDF,
    }.issubset(types)
    workspace = repository.workspace(case.case_id)
    for artifact in completed.artifacts:
        assert not Path(artifact.relative_path).is_absolute()
        assert workspace.resolve_relative(artifact.relative_path).is_file()
    assert all(
        "provider" not in item.source.casefold() for item in completed.artifacts
    )

    reports = CaseUIService(repository).reports(case.case_id)
    assert reports[-1]["status"] == "complete"
    assert {
        "case_report.md",
        "case_report.html",
        "case_report.docx",
        "case_report.pdf",
    }.issubset(reports[-1]["files"])


def test_offline_manifest_contains_only_relative_evidence_paths(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CHAINSHERLOCK_PDF_CJK_FONT", raising=False)
    monkeypatch.delenv("WINDIR", raising=False)
    repository = CaseRepository(tmp_path / "cases")
    case, plan = _confirmed_offline_case(repository, _csv(tmp_path / "source.csv"))
    service = CaseExecutionService(
        repository, create_offline_execution_registry(repository)
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)

    manifest = next(
        item
        for item in completed.artifacts
        if item.artifact_type is ArtifactType.EVIDENCE_MANIFEST
        and item.source == "case_evidence_manifest"
    )
    payload = json.loads(
        repository.workspace(case.case_id)
        .resolve_relative(manifest.relative_path)
        .read_text(encoding="utf-8")
    )
    assert payload
    assert all(item["relative_path"].startswith("evidence/") for item in payload)
    assert str(tmp_path) not in json.dumps(payload)
    assert completed.execution.status is ExecutionStatus.PARTIAL


def test_offline_execution_refuses_tampered_evidence(tmp_path: Path) -> None:
    repository = CaseRepository(tmp_path / "cases")
    case, plan = _confirmed_offline_case(repository, _csv(tmp_path / "source.csv"))
    stored = repository.workspace(case.case_id).resolve_relative(
        repository.load(case.case_id).evidence[0].relative_path
    )
    stored.chmod(0o600)
    stored.write_text("tampered", encoding="utf-8")
    service = CaseExecutionService(
        repository, create_offline_execution_registry(repository)
    )

    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)

    assert not completed.success
    assert completed.execution.status is ExecutionStatus.FAILED


def test_offline_excel_evidence_reaches_analysis(tmp_path: Path) -> None:
    repository = CaseRepository(tmp_path / "cases")
    ui = CaseUIService(repository)
    case = ui.create_case("Offline Excel")
    case = repository.save(
        case.model_copy(update={"metadata": {"known_addresses": [TARGET]}})
    )
    ui.import_evidence(case.case_id, _xlsx(tmp_path / "evidence.xlsx"))
    ui.add_goal(
        case.case_id,
        "identify_main_sources",
        "Identify main sources",
        [TARGET],
    )
    plan = ui.create_plan(case.case_id)
    ui.confirm_latest_plan(case.case_id)
    service = CaseExecutionService(
        repository, create_offline_execution_registry(repository)
    )

    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)

    assert completed.success
    assert any(
        item.artifact_type is ArtifactType.ANALYSIS_RESULT
        for item in completed.artifacts
    )
