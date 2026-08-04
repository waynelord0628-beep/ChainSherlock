from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from crypto_investigator.application import (
    ArtifactCandidate,
    ArtifactType,
    CasePackageService,
    CaseReportService,
    CaseResultService,
    Completeness,
    ExecutionArtifact,
    ExecutionStatus,
)
from crypto_investigator.cases import (
    CaseFact,
    CaseInterpretation,
    CaseObservation,
    CaseRepository,
    CaseResult,
    EvidenceIndexEntry,
    RecommendedFollowUp,
    UnresolvedQuestion,
)
from crypto_investigator.cases.deidentification import Deidentifier
from crypto_investigator.cases.importer import (
    CasePackageImporter,
    CasePackageValidationError,
)
from crypto_investigator.cases.results import CandidateType, ReviewStatus
from crypto_investigator.cli import app
from crypto_investigator.services import (
    ArtifactService,
    CaseNarrativeService,
    ExecutionStateService,
)
from crypto_investigator.application.execution_models import CaseExecution


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    return CaseRepository(tmp_path / "cases")


@pytest.fixture
def populated_case(repository: CaseRepository):
    case = repository.create("測試案件", description="Case output fixture")
    workspace = repository.workspace(case.case_id)
    execution = CaseExecution(
        execution_id="execution_" + "a" * 32,
        case_id=case.case_id,
        plan_id="plan_fixture",
        plan_version=1,
        status=ExecutionStatus.COMPLETED,
    )
    state = ExecutionStateService(repository)
    state.create_layout(execution)
    payload = {
        "metadata": {
            "chain": "tron",
            "target_address": "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE",
            "completeness": "complete",
        },
        "summary": {"transaction_count": 12, "assets": ["TRX", "USDT"]},
        "observations": [
            {
                "code": "funding_changed",
                "factual_statement": "主要供款來源發生變化。",
                "metrics": {"count": 2},
                "confidence": "high",
                "evidence_refs": ["ev-1"],
            }
        ],
        "conclusion_fact_items": [
            {
                "fact_code": "funding_source_changed",
                "value": True,
                "confidence": "high",
                "evidence_refs": ["ev-1"],
            }
        ],
        "services": [
            {"address": "TService111111111111111111111111111", "service_type": "exchange"}
        ],
    }
    artifact_path = state.execution_dir(case.case_id, execution.execution_id) / "artifacts" / "investigation.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    artifact = ArtifactService(workspace).register(
        execution_id=execution.execution_id,
        step_id="step_investigation",
        candidate=ArtifactCandidate(
            artifact_type=ArtifactType.INVESTIGATION_RESULT,
            relative_path="artifacts/investigation.json",
            source="mock_investigation",
        ),
    )
    execution = execution.model_copy(update={"artifacts": [artifact]})
    state.save(execution)
    case = repository.load(case.case_id)
    repository.save(
        case.model_copy(
            update={
                "goals": [
                    {
                        "goal_id": "goal-1",
                        "goal_type": "trace_funds",
                        "title": "追蹤資金",
                    }
                ],
                "executions": [
                    {
                        "execution_id": execution.execution_id,
                        "plan_id": execution.plan_id,
                        "status": "completed",
                    }
                ],
                "execution_summary": {"status": "completed", "artifact_count": 1},
                "metadata": {"case_number": "CASE-SECRET-001"},
            }
        )
    )
    return repository.load(case.case_id), artifact


@pytest.mark.parametrize("candidate_type", list(CandidateType))
def test_candidate_types(candidate_type: CandidateType) -> None:
    item = CaseInterpretation(
        interpretation_id="candidate",
        title="Candidate",
        statement="Possible role.",
        candidate_type=candidate_type,
    )
    assert item.candidate_type is candidate_type


@pytest.mark.parametrize("review_status", list(ReviewStatus))
def test_review_statuses(review_status: ReviewStatus) -> None:
    item = CaseInterpretation(
        interpretation_id="candidate",
        title="Candidate",
        statement="Possible role.",
        review_status=review_status,
    )
    assert item.review_status is review_status


@pytest.mark.parametrize(
    "model",
    [
        CaseFact(
            fact_id="fact", category="test", statement="fact", source_type="manual"
        ),
        CaseObservation(
            observation_id="observation",
            category="test",
            factual_statement="observed",
            source_artifact="artifact",
        ),
        CaseInterpretation(
            interpretation_id="candidate", title="Candidate", statement="possible"
        ),
        UnresolvedQuestion(
            question_id="question",
            question="What remains?",
            reason_unresolved="missing",
        ),
        RecommendedFollowUp(
            recommendation_id="followup",
            title="Follow",
            description="Obtain data",
            reason="missing",
            expected_answer="answer",
        ),
        EvidenceIndexEntry(
            evidence_id="evidence",
            evidence_type="source",
            description="evidence",
            relative_path="evidence/a",
            source="case",
        ),
    ],
)
def test_output_models_round_trip(model) -> None:
    assert type(model).model_validate_json(model.model_dump_json()) == model


def test_case_result_round_trip_decimal_datetime() -> None:
    result = CaseResult(
        case_id="case_" + "a" * 32,
        title="Case",
        case_status="open",
        recommended_follow_ups=[
            RecommendedFollowUp(
                recommendation_id="r",
                title="R",
                description="D",
                reason="reason",
                expected_answer="answer",
                possible_cost="1.2300",
            )
        ],
    )
    restored = CaseResult.model_validate_json(result.model_dump_json())
    assert str(restored.recommended_follow_ups[0].possible_cost) == "1.2300"
    assert restored.generated_at.tzinfo is not None


@pytest.mark.parametrize("integrity_status", ["verified", "hash_mismatch", "unknown"])
def test_evidence_integrity_status_round_trip(integrity_status: str) -> None:
    item = EvidenceIndexEntry(
        evidence_id="evidence",
        evidence_type="artifact",
        description="Evidence",
        relative_path="artifacts/item.json",
        source="case",
        integrity_status=integrity_status,
    )
    assert EvidenceIndexEntry.model_validate_json(
        item.model_dump_json()
    ).integrity_status == integrity_status


@pytest.mark.parametrize(
    "evidence_type",
    [
        "source_evidence",
        "analysis_result",
        "graph_json",
        "investigation_result",
        "narrative_result",
        "report_markdown",
        "report_html",
        "report_docx",
        "report_pdf",
        "audit_log",
    ],
)
def test_evidence_index_types(evidence_type: str) -> None:
    item = EvidenceIndexEntry(
        evidence_id="evidence",
        evidence_type=evidence_type,
        description="Evidence",
        relative_path="evidence/item",
        source="case",
    )
    assert item.evidence_type == evidence_type


@pytest.mark.parametrize("completeness", ["complete", "partial", "unavailable"])
def test_case_result_completeness_round_trip(completeness: str) -> None:
    result = CaseResult(
        case_id="case_" + "a" * 32,
        title="Case",
        case_status="open",
        completeness=completeness,
    )
    assert CaseResult.model_validate_json(result.model_dump_json()).completeness == completeness


def test_artifact_aggregation(populated_case, repository: CaseRepository) -> None:
    case, artifact = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    assert result.execution_ids == ["execution_" + "a" * 32]
    assert result.confirmed_facts[0].source_type == "deterministic_investigation"
    assert result.deterministic_observations[0].source_artifact == artifact.artifact_id
    assert result.candidate_interpretations[0].review_status is ReviewStatus.NOT_REVIEWED
    assert result.assets == ["TRX", "USDT"]


def test_candidate_is_not_confirmed_fact(populated_case, repository: CaseRepository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    assert all("candidate" not in fact.fact_id for fact in result.confirmed_facts)
    assert "possible" in result.candidate_interpretations[0].statement.lower()


def test_questions_and_recommendations_not_auto_executed(populated_case, repository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    assert result.unresolved_questions[0].status == "open"
    assert result.recommended_follow_ups[0].possible_cost is None
    assert result.recommended_follow_ups[0].external_permission_required
    assert not result.recommended_follow_ups[0].supported_by_current_system


def test_hash_mismatch_excluded_and_partial(populated_case, repository) -> None:
    case, artifact = populated_case
    path = repository.workspace(case.case_id).resolve_relative(artifact.relative_path)
    path.chmod(stat.S_IWRITE)
    path.write_text("tampered", encoding="utf-8")
    result = CaseResultService(repository).build_case_result(case.case_id)
    assert result.completeness == "partial"
    assert not result.confirmed_facts
    assert any("integrity failed" in item for item in result.warnings)


def test_missing_execution_warning(populated_case, repository) -> None:
    case, _ = populated_case
    updated = repository.load(case.case_id)
    repository.save(
        updated.model_copy(
            update={"executions": [{"execution_id": "execution_" + "f" * 32}]}
        )
    )
    result = CaseResultService(repository).build_case_result(case.case_id)
    assert result.completeness == "partial"
    assert result.unresolved_questions


def test_evidence_and_audit_index(populated_case, repository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    assert result.evidence_index[0].integrity_status == "verified"
    assert result.audit_summary.chain_integrity
    assert result.audit_summary.entry_count > 0


@pytest.mark.parametrize(
    "section_id",
    [
        "case_brief",
        "goals",
        "confirmed_facts",
        "observations",
        "candidate_interpretations",
        "unresolved_questions",
        "recommended_follow_ups",
        "limitations",
    ],
)
def test_fallback_required_sections(populated_case, repository, section_id: str) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    narrative = CaseNarrativeService().compose(result)
    assert section_id in {item.section_id for item in narrative.sections}
    assert narrative.deterministic


def test_fallback_no_criminal_wording(populated_case, repository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    text = CaseNarrativeService().compose(result).model_dump_json()
    assert "確定犯罪" not in text
    assert "確定洗錢" not in text


@pytest.mark.parametrize(
    "section_id",
    [
        "case_brief",
        "goals",
        "confirmed_facts",
        "observations",
        "candidate_interpretations",
        "unresolved_questions",
        "recommended_follow_ups",
        "limitations",
        "evidence_index",
        "audit_summary",
        "review_status",
    ],
)
def test_case_report_required_sections(populated_case, repository, section_id: str) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    document = CaseReportService(repository).compose_document(result)
    assert section_id in {item.section_id for item in document.sections}


def test_case_report_separates_candidate_and_facts(populated_case, repository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    document = CaseReportService(repository).compose_document(result)
    fact = next(item for item in document.sections if item.section_id == "confirmed_facts")
    candidate = next(item for item in document.sections if item.section_id == "candidate_interpretations")
    assert "possible" not in " ".join(fact.content_blocks).lower()
    assert "candidate" in " ".join(candidate.content_blocks).lower()
    assert "不構成" in document.conclusion.text


@pytest.mark.parametrize("requested_format", ["markdown", "html", "docx"])
def test_case_report_export_formats(populated_case, repository, requested_format: str) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    summary = CaseReportService(repository).generate(result, requested_format)
    expected = {
        "markdown": "case_report.md",
        "html": "case_report.html",
        "docx": "case_report.docx",
    }[requested_format]
    path = repository.workspace(case.case_id).resolve_relative(summary["files"][expected])
    assert path.stat().st_size > 0
    if requested_format == "html":
        assert "http://cdn" not in path.read_text(encoding="utf-8").lower()
    if requested_format == "docx":
        assert zipfile.is_zipfile(path)


def test_case_pdf_and_partial_policy(populated_case, repository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    summary = CaseReportService(repository).generate(result, "pdf")
    assert summary["status"] in {"complete", "partial", "failed"}
    assert "case_export_status.json" in summary["files"]
    assert "case_export_errors.json" in summary["files"]


def test_report_versioning_retains_old(populated_case, repository) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    service = CaseReportService(repository)
    first = service.generate(result, "markdown")
    second = service.generate(result, "markdown")
    assert first["report_version"] == 1
    assert second["report_version"] == 2
    assert len(service.list_reports(case.case_id)) == 2
    assert service.latest_report(case.case_id)["report_version"] == 2


@pytest.mark.parametrize("mode", ["full", "report_only", "deidentified"])
def test_package_modes(populated_case, repository, tmp_path: Path, mode: str) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    CaseReportService(repository).generate(result, "markdown")
    service = CasePackageService(repository)
    path = service.export_case_package(case.case_id, tmp_path / mode, mode)
    manifest = service.validate_case_package(path)
    assert manifest.export_mode == mode
    assert manifest.deidentified is (mode == "deidentified")
    assert zipfile.is_zipfile(path)


def test_full_package_import_new_id_and_provenance(populated_case, repository, tmp_path) -> None:
    case, _ = populated_case
    service = CasePackageService(repository)
    path = service.export_case_package(case.case_id, tmp_path / "full", "full")
    imported = service.import_case_package(path)
    assert imported.case_id != case.case_id
    assert imported.metadata["original_case_id"] == case.case_id
    assert repository.workspace(imported.case_id).path.exists()


def test_report_only_contains_no_raw_evidence(populated_case, repository, tmp_path) -> None:
    case, _ = populated_case
    result = CaseResultService(repository).build_case_result(case.case_id)
    CaseReportService(repository).generate(result, "markdown")
    path = CasePackageService(repository).export_case_package(
        case.case_id, tmp_path / "report", "report_only"
    )
    with zipfile.ZipFile(path) as archive:
        assert all(not name.startswith("evidence/") for name in archive.namelist())
        assert all("/artifacts/" not in name for name in archive.namelist())


def test_deidentification_consistency_and_no_mapping() -> None:
    address = "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"
    tx_hash = "a" * 64
    deidentifier = Deidentifier()
    transformed = deidentifier.transform(
        {"a": address, "b": address, "tx": tx_hash, "title": "Person Name"}
    )
    assert transformed["a"] == transformed["b"]
    assert address not in json.dumps(transformed)
    assert tx_hash not in json.dumps(transformed)
    assert "title" not in transformed
    assert deidentifier.manifest()["mapping_included"] is False
    assert "salt" not in deidentifier.manifest()


def test_no_secrets_or_absolute_paths_in_package(populated_case, repository, tmp_path) -> None:
    case, _ = populated_case
    current = repository.load(case.case_id)
    repository.save(
        current.model_copy(
            update={"metadata": {"api_key": "sk-proj-super-secret-value", "path": r"C:\private\file"}}
        )
    )
    path = CasePackageService(repository).export_case_package(
        case.case_id, tmp_path / "safe", "full"
    )
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        content = b"\n".join(archive.read(name) for name in names).lower()
    assert b"sk-proj-super-secret-value" not in content
    assert b"c:\\private" not in content
    assert all(".env" not in name.lower() for name in names)


def make_zip(path: Path, entries: dict[str, bytes], *, symlink: str | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            if symlink == name:
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, data)
            else:
                archive.writestr(name, data)
    return path


@pytest.mark.parametrize("unsafe", ["../escape", "/absolute", r"C:\absolute"])
def test_zip_unsafe_paths_blocked(repository, tmp_path, unsafe: str) -> None:
    path = make_zip(tmp_path / "unsafe.zip", {unsafe: b"x"})
    with pytest.raises(CasePackageValidationError, match="Unsafe"):
        CasePackageImporter(repository).validate(path)


def test_zip_symlink_blocked(repository, tmp_path) -> None:
    path = make_zip(tmp_path / "symlink.zip", {"link": b"target"}, symlink="link")
    with pytest.raises(CasePackageValidationError, match="Symlink"):
        CasePackageImporter(repository).validate(path)


@pytest.mark.parametrize("content", [b"", b"not a zip"])
def test_corrupt_zip_blocked(repository, tmp_path, content: bytes) -> None:
    path = tmp_path / "corrupt.zip"
    path.write_bytes(content)
    with pytest.raises(CasePackageValidationError, match="Invalid"):
        CasePackageImporter(repository).validate(path)


def test_missing_manifest_blocked(repository, tmp_path) -> None:
    path = make_zip(tmp_path / "missing.zip", {"case.json": b"{}"})
    with pytest.raises(CasePackageValidationError, match="manifest"):
        CasePackageImporter(repository).validate(path)


def test_hash_mismatch_blocked(populated_case, repository, tmp_path) -> None:
    case, _ = populated_case
    service = CasePackageService(repository)
    original = service.export_case_package(case.case_id, tmp_path / "full", "full")
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            target.writestr(name, b"tampered" if name == "case.json" else data)
    with pytest.raises(CasePackageValidationError, match="hash mismatch"):
        service.validate_case_package(tampered)


def test_file_count_and_size_limits(repository, tmp_path, monkeypatch) -> None:
    importer = CasePackageImporter(repository)
    monkeypatch.setattr(importer, "MAX_FILES", 1)
    path = make_zip(tmp_path / "many.zip", {"a": b"a", "b": b"b"})
    with pytest.raises(CasePackageValidationError, match="too many"):
        importer.validate(path)
    monkeypatch.setattr(importer, "MAX_FILES", 100)
    monkeypatch.setattr(importer, "MAX_FILE_SIZE", 1)
    path = make_zip(tmp_path / "large.zip", {"a": b"large"})
    with pytest.raises(CasePackageValidationError, match="size limit"):
        importer.validate(path)


def test_atomic_import_failure_leaves_no_case(repository, tmp_path) -> None:
    before = set(repository.root.iterdir())
    path = make_zip(tmp_path / "bad.zip", {"case.json": b"{}"})
    with pytest.raises(CasePackageValidationError):
        CasePackageImporter(repository).import_package(path)
    assert set(repository.root.iterdir()) == before


@pytest.mark.parametrize(
    "command",
    ["case-result", "case-report", "case-export", "case-import", "case-package-validate"],
)
def test_case_cli_help(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0


def test_existing_cli_compatibility() -> None:
    result = CliRunner().invoke(app, ["detect", "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"])
    assert result.exit_code == 0
