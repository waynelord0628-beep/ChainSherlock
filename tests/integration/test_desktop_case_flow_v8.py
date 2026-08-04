from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from crypto_investigator.application import (
    ArtifactCandidate,
    ArtifactType,
    CaseExecutionService,
    ExecutionRegistry,
    ExecutionStepStatus,
    StepExecutionResult,
)
from crypto_investigator.cases import CaseRepository
from crypto_investigator.planner import InvestigationPlan, executable_steps
from crypto_investigator.ui.main_window import MainWindow
from crypto_investigator.ui.services import CaseUIService


class FlowMockHandler:
    resume_supported = True
    retry_supported = True
    expected_artifacts = ("other",)

    def __init__(self, step_type) -> None:
        self.supported_step_type = step_type
        self.expected_artifacts = (
            ("graph_html",)
            if step_type.value == "build_graph"
            else (
                ("investigation_result",)
                if step_type.value == "run_investigation_features"
                else ("other",)
            )
        )

    def validate_input(self, case, step, context) -> None:
        return None

    def execute(self, case, step, context, cancellation_token) -> StepExecutionResult:
        artifact_type = ArtifactType.OTHER
        filename = f"{step.step_id}.json"
        payload = {"step": step.step_type.value, "records": 5}
        if step.step_type.value == "build_graph":
            artifact_type = ArtifactType.GRAPH_HTML
            filename = "flow.html"
            content = "<!doctype html><meta charset='utf-8'><p>Mock graph</p>"
        elif step.step_type.value == "run_investigation_features":
            artifact_type = ArtifactType.INVESTIGATION_RESULT
            filename = "investigation.json"
            payload = {
                "metadata": {
                    "chain": "tron",
                    "target_address": "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE",
                },
                "conclusion_fact_items": [
                    {
                        "fact_code": "mock_flow_completed",
                        "value": True,
                        "confidence": "high",
                        "evidence_refs": [],
                    }
                ],
                "observations": [
                    {
                        "code": "bounded_mock",
                        "factual_statement": "Bounded mock execution completed.",
                        "confidence": "high",
                    }
                ],
            }
            content = json.dumps(payload)
        else:
            content = json.dumps(payload)
        path = context.artifacts_dir / filename
        path.write_text(content, encoding="utf-8")
        return StepExecutionResult(
            status=ExecutionStepStatus.COMPLETED,
            records_processed=5,
            artifacts=[
                ArtifactCandidate(
                    artifact_type=artifact_type,
                    relative_path=f"artifacts/{filename}",
                    source="m5_mock",
                )
            ],
        )

    def cancel(self, context) -> None:
        return None


def test_tron_case_mock_execution_and_case_output(qtbot, tmp_path: Path) -> None:
    repository = CaseRepository(tmp_path / "cases")
    ui_service = CaseUIService(repository)
    case = ui_service.create_case("TRON M5 Acceptance")
    case = repository.save(
        case.model_copy(
            update={
                "metadata": {
                    "chain": "tron",
                    "known_addresses": [
                        "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"
                    ],
                }
            }
        )
    )
    evidence = tmp_path / "bounded.csv"
    evidence.write_text("tx_hash,amount,asset\nmock,1,TRX\n", encoding="utf-8")
    ui_service.import_evidence(case.case_id, evidence)
    for goal in (
        "identify_main_sources",
        "identify_main_destinations",
        "detect_batch_distribution",
        "detect_funding_transition",
        "identify_service_candidates",
        "generate_investigation_report",
    ):
        ui_service.add_goal(
            case.case_id,
            goal,
            goal.replace("_", " ").title(),
            ["TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"],
        )
    plan = ui_service.create_plan(case.case_id)
    confirmed = ui_service.confirm_latest_plan(case.case_id)
    assert confirmed.confirmed_at is not None

    registry = ExecutionRegistry()
    for step in executable_steps(InvestigationPlan.model_validate(confirmed)):
        registry.register(FlowMockHandler(step.step_type))
    execution_service = CaseExecutionService(repository, registry)
    execution = execution_service.create_execution(case.case_id, plan.plan_id)
    events = []
    completed = execution_service.run_execution(
        execution.execution_id, event_callback=events.append
    )
    assert completed.success
    assert events

    result = ui_service.result(case.case_id)
    assert result.confirmed_facts
    assert result.deterministic_observations
    report = ui_service.create_report(case.case_id)
    assert report["report_version"] == 1

    window = MainWindow(
        repository.root,
        tmp_path / "settings.json",
        execution_service=execution_service,
    )
    qtbot.addWidget(window)
    window.open_case(case.case_id)
    assert "mock_flow_completed" in window.tab_views["Investigation"].toPlainText()
    assert "flow.html" in window.tab_views["Graph"].toPlainText()
    assert window.case_service.audit_valid(case.case_id)
