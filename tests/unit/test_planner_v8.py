from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from crypto_investigator.cases import (
    AuditLog,
    CaseRecord,
    CaseRepository,
    EvidenceManager,
    migrate_case_payload,
    new_case_id,
)
from crypto_investigator.config import Settings, load_config
from crypto_investigator.domain import Chain
from crypto_investigator.planner import (
    DateRange,
    DeterministicPlanner,
    GoalPriority,
    GoalStatus,
    GoalType,
    InvestigationGoal,
    InvestigationPlan,
    PlanConfirmation,
    PlannerFactory,
    PlanningService,
    StepStatus,
    StepType,
    executable_steps,
    plan_validation_issues,
    validate_plan,
)
from crypto_investigator.planner.errors import (
    NoExecutableClueError,
    PlanValidationError,
    UnconfirmedPlanError,
)
from crypto_investigator.providers.models import ProviderCapability, ProviderDescriptor

TRON = "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"
ETHEREUM = "0x" + "a" * 40
ETHEREUM_TX = "0x" + "b" * 64
BITCOIN = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
BITCOIN_TX = "c" * 64


@pytest.fixture
def settings() -> Settings:
    return load_config()


@pytest.fixture
def descriptors() -> tuple[ProviderDescriptor, ...]:
    return (
        ProviderDescriptor(
            "trongrid",
            Chain.TRON,
            (
                ProviderCapability.ADDRESS_TRANSACTIONS,
                ProviderCapability.TOKEN_TRANSFERS,
            ),
            True,
        ),
        ProviderDescriptor(
            "etherscan",
            Chain.ETHEREUM,
            (
                ProviderCapability.ADDRESS_TRANSACTIONS,
                ProviderCapability.TOKEN_TRANSFERS,
            ),
            True,
        ),
        ProviderDescriptor(
            "blockstream",
            Chain.BITCOIN,
            (
                ProviderCapability.ADDRESS_TRANSACTIONS,
                ProviderCapability.UTXO,
            ),
            False,
        ),
    )


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    return CaseRepository(tmp_path / "cases")


def goal(goal_type: GoalType, *targets: str) -> InvestigationGoal:
    return InvestigationGoal(
        goal_id=f"goal_{goal_type.value}",
        goal_type=goal_type,
        title=goal_type.value,
        target_entities=list(targets),
        completion_criteria=["required artifacts exist"],
        confirmed_by_user=True,
    )


def make_plan(
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    *goals: InvestigationGoal,
    ai_enabled: bool = False,
    case: CaseRecord | None = None,
) -> InvestigationPlan:
    planner = DeterministicPlanner(
        settings, provider_descriptors=descriptors, ai_enabled=ai_enabled
    )
    return planner.create_plan(
        case or CaseRecord(case_id=new_case_id(), title="Case"),
        goals,
        generated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize("goal_type", list(GoalType))
def test_all_goal_types_round_trip(goal_type: GoalType) -> None:
    item = goal(goal_type, TRON)
    restored = InvestigationGoal.model_validate_json(item.model_dump_json())
    assert restored.goal_type is goal_type


def test_goal_model_contains_required_fields() -> None:
    item = InvestigationGoal(
        goal_type=GoalType.TRACE_FUNDS,
        title="Trace",
        description="Trace funds",
        priority=GoalPriority.HIGH,
        target_entities=[TRON],
        target_assets=["USDT"],
        target_date_range=DateRange(date_from=date(2026, 1, 1), date_to=date(2026, 2, 1)),
        completion_criteria=["graph"],
        status=GoalStatus.ACTIVE,
        created_by="analyst",
        confirmed_by_user=True,
    )
    assert item.priority == GoalPriority.HIGH
    assert item.target_date_range.date_to == date(2026, 2, 1)


def test_goal_unknown_fields_are_preserved() -> None:
    item = InvestigationGoal.model_validate(
        {
            "goal_type": "custom",
            "title": "Custom",
            "future_option": {"keep": True},
        }
    )
    assert item.model_extra == {"future_option": {"keep": True}}


def test_plan_timestamp_must_be_timezone_aware(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    with pytest.raises(ValidationError, match="timezone-aware"):
        InvestigationPlan.model_validate(
            {**plan.model_dump(mode="json"), "generated_at": "2026-01-01T00:00:00"}
        )


def test_deterministic_plan_output(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    item = goal(GoalType.TRACE_FUNDS, TRON)
    case = CaseRecord(case_id=new_case_id(), title="Case")
    first = make_plan(settings, descriptors, item, case=case)
    second = make_plan(settings, descriptors, item, case=case)
    assert first.plan_id == second.plan_id
    assert [step.model_dump() for step in first.steps] == [
        step.model_dump() for step in second.steps
    ]


@pytest.mark.parametrize(
    ("target", "chain"),
    [(TRON, Chain.TRON), (ETHEREUM, Chain.ETHEREUM), (BITCOIN, Chain.BITCOIN)],
)
def test_address_plan(
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    target: str,
    chain: Chain,
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, target))
    address = next(step for step in plan.steps if step.step_type is StepType.ANALYZE_ADDRESS)
    assert address.chain is chain
    assert address.prerequisites
    assert address.parameters["max_records"] == settings.pagination.max_records


@pytest.mark.parametrize(
    ("target", "chain"),
    [(ETHEREUM_TX, Chain.ETHEREUM), (BITCOIN_TX, Chain.BITCOIN)],
)
def test_transaction_plan(
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    target: str,
    chain: Chain,
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, target))
    step = next(step for step in plan.steps if step.step_type is StepType.ANALYZE_TRANSACTION)
    assert step.chain is chain


@pytest.mark.parametrize("suffix", [".csv", ".xls", ".xlsx", ".json"])
def test_structured_file_plan(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    tmp_path: Path,
    suffix: str,
) -> None:
    case = repository.create("File case")
    source = tmp_path / f"transactions{suffix}"
    source.write_bytes(b"fixture")
    EvidenceManager(repository).import_file(case.case_id, source)
    plan = make_plan(
        settings,
        descriptors,
        goal(GoalType.IDENTIFY_MAIN_SOURCES),
        case=repository.load(case.case_id),
    )
    types = [step.step_type for step in plan.steps]
    assert StepType.PARSE_STRUCTURED_ATTACHMENT in types
    assert StepType.IMPORT_TRANSACTIONS in types


def test_unstructured_file_is_not_executable_clue(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    tmp_path: Path,
) -> None:
    case = repository.create("File case")
    source = tmp_path / "notes.txt"
    source.write_text("notes", encoding="utf-8")
    EvidenceManager(repository).import_file(case.case_id, source)
    with pytest.raises(NoExecutableClueError):
        make_plan(
            settings,
            descriptors,
            goal(GoalType.IDENTIFY_MAIN_SOURCES),
            case=repository.load(case.case_id),
        )


def test_victim_payment_plan(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.VERIFY_VICTIM_PAYMENT, TRON))
    assert any(step.step_type is StepType.MATCH_VICTIM_TRANSACTIONS for step in plan.steps)


def test_multiple_address_plan(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(
        settings,
        descriptors,
        goal(GoalType.COMPARE_KNOWN_ADDRESSES, TRON, ETHEREUM),
    )
    compare = next(
        step for step in plan.steps if step.step_type is StepType.COMPARE_KNOWN_ADDRESSES
    )
    assert compare.target_ids == [ETHEREUM, TRON]


def test_report_has_required_dependencies(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(
        settings,
        descriptors,
        goal(GoalType.GENERATE_INVESTIGATION_REPORT, TRON),
    )
    report = next(step for step in plan.steps if step.step_type is StepType.GENERATE_REPORT)
    dependency_types = {
        next(item for item in plan.steps if item.step_id == dependency).step_type
        for dependency in report.prerequisites
    }
    assert dependency_types == {
        StepType.BUILD_GRAPH,
        StepType.RUN_INVESTIGATION_FEATURES,
        StepType.EXPORT_EVIDENCE_MANIFEST,
    }


def test_exchange_goal_uses_local_labels_and_unsupported_recommendation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(
        settings,
        descriptors,
        goal(GoalType.IDENTIFY_EXCHANGE_EXPOSURE, TRON),
    )
    assert any(step.step_type is StepType.APPLY_LOCAL_LABELS for step in plan.steps)
    unsupported = next(
        step
        for step in plan.steps
        if step.step_type is StepType.UNSUPPORTED_RECOMMENDED_STEP
    )
    assert unsupported.enabled is False
    assert unsupported.status is StepStatus.SKIPPED


def test_no_executable_clue(settings: Settings) -> None:
    with pytest.raises(NoExecutableClueError):
        DeterministicPlanner(settings).create_plan(
            CaseRecord(case_id=new_case_id(), title="Empty"),
            [goal(GoalType.CUSTOM)],
        )


def test_chain_detection_precedes_analysis(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    analysis = next(step for step in plan.steps if step.step_type is StepType.ANALYZE_ADDRESS)
    detected = next(step for step in plan.steps if step.step_id in analysis.prerequisites)
    assert detected.step_type is StepType.DETECT_CHAIN
    assert detected.order < analysis.order


def test_provider_is_selected_from_public_descriptor(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    analysis = next(step for step in plan.steps if step.step_type is StepType.ANALYZE_ADDRESS)
    assert analysis.provider == "trongrid"


def test_missing_provider_capability_creates_warning(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, ETHEREUM))
    assert any(
        warning.code == "provider_capability_unavailable" for warning in plan.warnings
    )
    internal = next(
        item
        for item in plan.provider_requirements
        if item.capability == ProviderCapability.INTERNAL_TRANSACTIONS.value
    )
    assert internal.available is False


def test_cost_unknown_is_null(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    assert plan.possible_costs is None
    assert all(step.estimated_cost is None for step in plan.steps)
    assert any(warning.code == "cost_unknown" for warning in plan.warnings)


def test_provider_credential_warning_uses_metadata_only(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    warning = next(
        item for item in plan.warnings if item.code == "provider_credentials_required"
    )
    assert warning.kind.value == "provider"
    assert "trongrid" in warning.message


def test_goal_assets_and_dates_propagate_to_analysis_step(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    item = goal(GoalType.TRACE_FUNDS, TRON).model_copy(
        update={
            "target_assets": ["USDT", "TRX"],
            "target_date_range": DateRange(
                date_from=date(2026, 1, 1), date_to=date(2026, 2, 1)
            ),
        }
    )
    plan = make_plan(settings, descriptors, item)
    step = next(step for step in plan.steps if step.step_type is StepType.ANALYZE_ADDRESS)
    assert step.assets == ["TRX", "USDT"]
    assert step.date_from == date(2026, 1, 1)
    assert step.date_to == date(2026, 2, 1)


def test_settings_snapshot_contains_safe_provider_names(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    assert plan.settings_snapshot["providers"]["tron"]["primary"] == "trongrid"
    assert "api_key" not in str(plan.settings_snapshot).lower()


def test_ai_is_disabled_by_default(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = PlannerFactory.create(settings, provider_descriptors=descriptors).create_plan(
        CaseRecord(case_id=new_case_id(), title="Case"),
        [goal(GoalType.GENERATE_INVESTIGATION_REPORT, TRON)],
    )
    assert plan.settings_snapshot["ai_enabled"] is False
    assert not any(step.step_type is StepType.GENERATE_NARRATIVE for step in plan.steps)


def test_ai_narrative_step_requires_confirmation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(
        settings,
        descriptors,
        goal(GoalType.GENERATE_INVESTIGATION_REPORT, TRON),
        ai_enabled=True,
    )
    narrative = next(
        step for step in plan.steps if step.step_type is StepType.GENERATE_NARRATIVE
    )
    assert narrative.optional is True
    assert narrative.requires_confirmation is True


def test_duplicate_step_id_validation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    duplicate = plan.model_copy(update={"steps": [*plan.steps, plan.steps[-1]]})
    with pytest.raises(PlanValidationError, match="duplicate step_id"):
        validate_plan(duplicate)


def test_missing_prerequisite_validation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    steps = list(plan.steps)
    steps[-1] = steps[-1].model_copy(update={"prerequisites": ["step_missing"]})
    invalid = plan.model_copy(update={"steps": steps})
    assert any("missing prerequisite" in item for item in plan_validation_issues(invalid))


def test_cyclic_dependency_validation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    steps = list(plan.steps)
    steps[0] = steps[0].model_copy(update={"prerequisites": [steps[-1].step_id]})
    invalid = plan.model_copy(update={"steps": steps})
    assert "cyclic step dependency" in plan_validation_issues(invalid)


def test_disabled_prerequisite_validation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    analysis_index = next(
        index for index, step in enumerate(plan.steps) if step.step_type is StepType.ANALYZE_ADDRESS
    )
    prerequisite_id = plan.steps[analysis_index].prerequisites[0]
    steps = [
        step.model_copy(update={"enabled": False})
        if step.step_id == prerequisite_id
        else step
        for step in plan.steps
    ]
    invalid = plan.model_copy(update={"steps": steps})
    assert any("disabled prerequisite" in item for item in plan_validation_issues(invalid))


def test_invalid_order_validation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    steps = list(plan.steps)
    steps[-1] = steps[-1].model_copy(update={"order": 99})
    assert "step order must be contiguous from 1" in plan_validation_issues(
        plan.model_copy(update={"steps": steps})
    )


@pytest.mark.parametrize(("parameter", "value"), [("max_pages", 0), ("max_records", 0)])
def test_pagination_lower_boundary(
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    parameter: str,
    value: int,
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    steps = [
        step.model_copy(update={"parameters": {**step.parameters, parameter: value}})
        if step.step_type is StepType.ANALYZE_ADDRESS
        else step
        for step in plan.steps
    ]
    assert any(parameter in item for item in plan_validation_issues(plan.model_copy(update={"steps": steps})))


@pytest.mark.parametrize("parameter", ["max_pages", "max_records"])
def test_pagination_upper_boundary(
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
    parameter: str,
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    value = plan.settings_snapshot[parameter] + 1
    steps = [
        step.model_copy(update={"parameters": {**step.parameters, parameter: value}})
        if step.step_type is StepType.ANALYZE_ADDRESS
        else step
        for step in plan.steps
    ]
    assert any("exceeds configured limit" in item for item in plan_validation_issues(plan.model_copy(update={"steps": steps})))


def test_unconfirmed_plan_is_not_executable(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    with pytest.raises(UnconfirmedPlanError):
        executable_steps(plan)


def test_plan_confirmation(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(
        repository, DeterministicPlanner(settings, provider_descriptors=descriptors)
    )
    service.add_goal(case.case_id, goal(GoalType.TRACE_FUNDS, TRON))
    plan = service.create_plan(case.case_id)
    confirmed = service.confirm_plan(
        plan,
        PlanConfirmation(confirmed=True, confirmed_by="analyst"),
    )
    assert confirmed.is_confirmed
    assert executable_steps(confirmed)
    assert all(
        step.status is StepStatus.APPROVED
        for step in confirmed.steps
        if step.enabled
    )


def test_declined_confirmation_does_not_change_plan(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(repository, DeterministicPlanner(settings, provider_descriptors=descriptors))
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON), case=case)
    result = service.confirm_plan(
        plan, PlanConfirmation(confirmed=False, confirmed_by="analyst")
    )
    assert result is plan
    assert not result.is_confirmed


def test_confirmation_cannot_persist_secret_settings(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(repository, DeterministicPlanner(settings, provider_descriptors=descriptors))
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON), case=case)
    confirmed = service.confirm_plan(
        plan,
        PlanConfirmation(
            confirmed=True,
            confirmed_by="analyst",
            settings_snapshot={"api_key": "sk-proj-secret-value"},
        ),
    )
    assert "api_key" not in confirmed.settings_snapshot
    assert "sk-proj-secret-value" not in repository.workspace(case.case_id).case_file.read_text(
        encoding="utf-8"
    )


def test_capability_metadata_changes_plan_fingerprint(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    item = goal(GoalType.TRACE_FUNDS, ETHEREUM)
    case = CaseRecord(case_id=new_case_id(), title="Case")
    missing_internal = make_plan(settings, descriptors, item, case=case)
    complete_descriptors = (
        *descriptors,
        ProviderDescriptor(
            "blockscout",
            Chain.ETHEREUM,
            (ProviderCapability.INTERNAL_TRANSACTIONS,),
            False,
        ),
    )
    complete = make_plan(settings, complete_descriptors, item, case=case)
    assert missing_internal.plan_id != complete.plan_id


def test_plan_modification_increments_version_and_clears_confirmation(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(repository, DeterministicPlanner(settings, provider_descriptors=descriptors))
    plan = make_plan(
        settings,
        descriptors,
        goal(GoalType.GENERATE_INVESTIGATION_REPORT, TRON),
        ai_enabled=True,
        case=case,
    )
    optional = next(step for step in plan.steps if step.step_type is StepType.GENERATE_NARRATIVE)
    modified = service.modify_plan(plan, enabled={optional.step_id: False})
    assert modified.plan_version == 2
    assert next(step for step in modified.steps if step.step_id == optional.step_id).enabled is False
    assert modified.confirmed_at is None


def test_planning_service_persists_goal_and_plan(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(repository, DeterministicPlanner(settings, provider_descriptors=descriptors))
    saved_goal = service.add_goal(case.case_id, goal(GoalType.TRACE_FUNDS, TRON))
    plan = service.create_plan(case.case_id)
    restored = repository.load(case.case_id)
    assert restored.goals[0]["goal_id"] == saved_goal.goal_id
    assert restored.plans[0]["plan_id"] == plan.plan_id


def test_planner_audit_creation_modification_confirmation(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(repository, DeterministicPlanner(settings, provider_descriptors=descriptors))
    service.add_goal(case.case_id, goal(GoalType.GENERATE_INVESTIGATION_REPORT, TRON))
    plan = service.create_plan(case.case_id)
    optional = next(step for step in plan.steps if step.step_type is StepType.UNSUPPORTED_RECOMMENDED_STEP) if any(
        step.step_type is StepType.UNSUPPORTED_RECOMMENDED_STEP for step in plan.steps
    ) else None
    modified = service.modify_plan(plan, enabled={} if optional is None else {optional.step_id: False})
    service.confirm_plan(modified, PlanConfirmation(confirmed=True, confirmed_by="analyst"))
    actions = [entry.action for entry in AuditLog(repository.workspace(case.case_id)).entries()]
    assert "plan_created" in actions
    assert "plan_modified" in actions
    assert "plan_confirmed" in actions


def test_audit_plan_entries_exclude_secret_values(
    repository: CaseRepository,
    settings: Settings,
    descriptors: tuple[ProviderDescriptor, ...],
) -> None:
    case = repository.create("Case")
    service = PlanningService(repository, DeterministicPlanner(settings, provider_descriptors=descriptors))
    service.add_goal(case.case_id, goal(GoalType.TRACE_FUNDS, TRON))
    plan = service.create_plan(case.case_id)
    service.modify_plan(plan, actor="sk-proj-secret-value")
    content = repository.workspace(case.case_id).audit_file.read_text(encoding="utf-8")
    assert "sk-proj-secret-value" not in content


def test_plan_schema_round_trip_and_unknown_field_preservation(
    settings: Settings, descriptors: tuple[ProviderDescriptor, ...]
) -> None:
    plan = make_plan(settings, descriptors, goal(GoalType.TRACE_FUNDS, TRON))
    payload = plan.model_dump(mode="json")
    payload["future_field"] = {"keep": True}
    restored = InvestigationPlan.model_validate(payload)
    round_trip = InvestigationPlan.model_validate_json(restored.model_dump_json())
    assert round_trip.model_extra == {"future_field": {"keep": True}}


def test_case_v1_migration_adds_planner_collections() -> None:
    payload = {
        "schema_version": 1,
        "case_id": new_case_id(),
        "title": "Legacy",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "unknown": "preserved",
    }
    migrated = migrate_case_payload(payload)
    assert migrated["schema_version"] == 3
    assert migrated["goals"] == []
    assert migrated["plans"] == []
    assert migrated["executions"] == []
    assert migrated["unknown"] == "preserved"
