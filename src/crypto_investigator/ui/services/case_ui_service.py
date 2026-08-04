from __future__ import annotations

from pathlib import Path

from crypto_investigator.application import (
    CasePackageService,
    CaseReportService,
    CaseResultService,
)
from crypto_investigator.cases import AuditLog, CaseRecord, CaseRepository, EvidenceManager
from crypto_investigator.config import load_config
from crypto_investigator.planner import (
    GoalType,
    InvestigationGoal,
    InvestigationPlan,
    PlanConfirmation,
    PlannerFactory,
    PlanningService,
)


class CaseUIService:
    """UI-safe adapter around public Case and Case Output services."""

    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def list_cases(self, query: str = "", include_archived: bool = False) -> tuple[CaseRecord, ...]:
        normalized = query.casefold().strip()
        records = self.repository.list(include_archived=include_archived)
        if not normalized:
            return records
        return tuple(
            item for item in records
            if normalized in item.title.casefold() or normalized in item.case_id.casefold()
        )

    def create_case(self, title: str, description: str = "") -> CaseRecord:
        title = title.strip()
        if not title:
            raise ValueError("Case title is required")
        return self.repository.create(title, description=description.strip())

    def archive_case(self, case_id: str) -> CaseRecord:
        return self.repository.archive(case_id)

    def delete_case(self, case_id: str) -> Path:
        return self.repository.delete(case_id)

    def import_evidence(self, case_id: str, source: Path, description: str = ""):
        return EvidenceManager(self.repository).import_file(
            case_id, source, description=description or None
        )

    def verify_evidence(self, case_id: str, evidence_id: str) -> bool:
        return EvidenceManager(self.repository).verify(case_id, evidence_id)

    def add_goal(
        self, case_id: str, goal_type: str, title: str, targets: list[str] | None = None
    ) -> InvestigationGoal:
        service = self._planning_service()
        return service.add_goal(
            case_id,
            InvestigationGoal(
                goal_type=GoalType(goal_type),
                title=title.strip() or GoalType(goal_type).value,
                target_entities=list(targets or []),
                confirmed_by_user=True,
            ),
        )

    def create_plan(self, case_id: str) -> InvestigationPlan:
        return self._planning_service().create_plan(case_id)

    def confirm_latest_plan(self, case_id: str) -> InvestigationPlan:
        case = self.repository.load(case_id)
        if not case.plans:
            raise ValueError("No plan is available")
        plan = InvestigationPlan.model_validate(case.plans[-1])
        return self._planning_service().confirm_plan(
            plan, PlanConfirmation(confirmed=True, confirmed_by="local-user")
        )

    def _planning_service(self) -> PlanningService:
        planner = PlannerFactory.create(load_config(), ai_enabled=False)
        return PlanningService(self.repository, planner)

    def result(self, case_id: str):
        return CaseResultService(self.repository).build_case_result(case_id)

    def reports(self, case_id: str) -> tuple[dict, ...]:
        return CaseReportService(self.repository).list_reports(case_id)

    def create_report(
        self,
        case_id: str,
        requested_format: str = "all",
        *,
        ai_enrichment_enabled: bool = False,
    ) -> dict:
        return CaseReportService(self.repository).generate(
            self.result(case_id),
            requested_format,
            ai_enrichment_enabled=ai_enrichment_enabled,
        )

    def export_package(self, case_id: str, destination: Path, mode: str = "full") -> Path:
        return CasePackageService(self.repository).export_case_package(
            case_id, destination, mode
        )

    def audit_entries(self, case_id: str):
        return tuple(AuditLog(self.repository.workspace(case_id)).entries())

    def audit_valid(self, case_id: str) -> bool:
        return AuditLog(self.repository.workspace(case_id)).verify()
