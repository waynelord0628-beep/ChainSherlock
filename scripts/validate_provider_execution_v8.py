from __future__ import annotations

import argparse
import json
from pathlib import Path

from crypto_investigator.application import (
    CaseExecutionService,
    create_desktop_execution_registry,
)
from crypto_investigator.cases import CaseRepository
from crypto_investigator.config import load_config
from crypto_investigator.ui.services import CaseUIService


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded V8 Provider execution validation")
    parser.add_argument("chain", choices=("ethereum", "tron", "bitcoin"))
    parser.add_argument("address")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    settings = load_config()
    settings = settings.model_copy(
        update={
            "pagination": settings.pagination.model_copy(
                update={"max_pages": 1, "max_records": 20, "page_size": 20}
            ),
            "http": settings.http.model_copy(
                update={
                    "connect_timeout_seconds": 10,
                    "read_timeout_seconds": 30,
                    "total_timeout_seconds": 45,
                    "retries": 0,
                }
            ),
            "cache": settings.cache.model_copy(
                update={
                    "enabled": True,
                    "directory": args.output / "cache",
                    "ttl_seconds": 86400,
                }
            ),
        }
    )
    repository = CaseRepository(args.output / "cases")
    ui = CaseUIService(repository)
    case = ui.create_case(f"M8 {args.chain} validation")
    case = repository.save(
        case.model_copy(
            update={
                "metadata": {
                    "chain": args.chain,
                    "known_addresses": [args.address],
                }
            }
        )
    )
    ui.add_goal(
        case.case_id,
        "identify_main_sources",
        "Identify main sources",
        [args.address],
    )
    plan = ui.create_plan(case.case_id)
    ui.confirm_latest_plan(case.case_id)
    service = CaseExecutionService(
        repository,
        create_desktop_execution_registry(repository, settings=settings),
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    completed = service.run_execution(execution.execution_id)
    provider_artifacts = [
        item
        for item in completed.artifacts
        if item.artifact_type.value
        in {"provider_status", "provider_errors", "rejected_records"}
    ]
    summary = {
        "chain": args.chain,
        "execution_status": completed.execution.status.value,
        "success": completed.success,
        "step_statuses": {
            item.step_type.value: item.status.value
            for item in completed.execution.steps
        },
        "artifact_types": sorted(
            {item.artifact_type.value for item in completed.artifacts}
        ),
        "artifact_count": len(completed.artifacts),
        "provider_artifact_count": len(provider_artifacts),
        "warning_count": len(completed.execution.warnings),
        "failure_count": len(completed.execution.failures),
        "bounded": {
            "max_pages": settings.pagination.max_pages,
            "max_records": settings.pagination.max_records,
            "retries": settings.http.retries,
            "cache": settings.cache.enabled,
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
