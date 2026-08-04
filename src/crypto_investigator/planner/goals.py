from __future__ import annotations

from datetime import date
from enum import IntEnum, StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class GoalType(StrEnum):
    TRACE_FUNDS = "trace_funds"
    IDENTIFY_MAIN_SOURCES = "identify_main_sources"
    IDENTIFY_MAIN_DESTINATIONS = "identify_main_destinations"
    VERIFY_VICTIM_PAYMENT = "verify_victim_payment"
    IDENTIFY_EXCHANGE_EXPOSURE = "identify_exchange_exposure"
    IDENTIFY_SERVICE_CANDIDATES = "identify_service_candidates"
    DETECT_BATCH_DISTRIBUTION = "detect_batch_distribution"
    DETECT_RAPID_PASS_THROUGH = "detect_rapid_pass_through"
    DETECT_FUNDING_TRANSITION = "detect_funding_transition"
    ANALYZE_OPERATION_STAGES = "analyze_operation_stages"
    COMPARE_KNOWN_ADDRESSES = "compare_known_addresses"
    GENERATE_INVESTIGATION_REPORT = "generate_investigation_report"
    CUSTOM = "custom"


class GoalStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GoalPriority(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class DateRange(BaseModel):
    model_config = ConfigDict(extra="allow")
    date_from: date | None = None
    date_to: date | None = None


class InvestigationGoal(BaseModel):
    model_config = ConfigDict(extra="allow")

    goal_id: str = Field(default_factory=lambda: f"goal_{uuid4().hex}")
    goal_type: GoalType
    title: str
    description: str = ""
    priority: GoalPriority = GoalPriority.NORMAL
    target_entities: list[str] = Field(default_factory=list)
    target_assets: list[str] = Field(default_factory=list)
    target_date_range: DateRange | None = None
    completion_criteria: list[str] = Field(default_factory=list)
    status: GoalStatus = GoalStatus.PROPOSED
    created_by: str = "local-user"
    confirmed_by_user: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
