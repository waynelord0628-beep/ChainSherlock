from __future__ import annotations

import hashlib

from crypto_investigator.planner.models import PlanStep, StepType


def stable_step_id(step_type: StepType, target_ids: list[str], occurrence: int = 0) -> str:
    material = f"{step_type.value}|{'|'.join(sorted(target_ids))}|{occurrence}"
    suffix = hashlib.sha256(material.encode()).hexdigest()[:12]
    return f"step_{step_type.value}_{suffix}"


def make_step(
    step_type: StepType,
    *,
    order: int,
    title: str,
    reason: str,
    target_ids: list[str] | None = None,
    occurrence: int = 0,
    **kwargs,
) -> PlanStep:
    targets = list(target_ids or [])
    return PlanStep(
        step_id=stable_step_id(step_type, targets, occurrence),
        order=order,
        title=title,
        reason=reason,
        step_type=step_type,
        target_ids=targets,
        **kwargs,
    )
