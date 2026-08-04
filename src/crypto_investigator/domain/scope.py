from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScopeType(StrEnum):
    FULL_HISTORY = "full_history"
    CUSTOM_DATE_RANGE = "custom_date_range"
    QUICK_PREVIEW = "quick_preview"


class CompletenessRequirement(StrEnum):
    REQUIRED_CAPABILITIES_COMPLETE = "required_capabilities_complete"
    BEST_EFFORT = "best_effort"


class PaginationPolicy(StrEnum):
    TO_PROVIDER_END = "to_provider_end"
    BOUNDED = "bounded"


class AnalysisScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_type: ScopeType = ScopeType.FULL_HISTORY
    date_from: datetime | None = None
    date_to: datetime | None = None
    timezone: str = "UTC"
    inclusive_start: bool = True
    inclusive_end: bool = True
    completeness_requirement: CompletenessRequirement = (
        CompletenessRequirement.REQUIRED_CAPABILITIES_COMPLETE
    )
    pagination_policy: PaginationPolicy = PaginationPolicy.TO_PROVIDER_END
    max_pages: int | None = Field(default=None, ge=1)
    max_records: int | None = Field(default=None, ge=1)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("date_from", "date_to")
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("scope timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def coherent_scope(self):
        if self.scope_type == ScopeType.CUSTOM_DATE_RANGE:
            if self.date_from is None or self.date_to is None:
                raise ValueError("custom_date_range requires date_from and date_to")
            if self.date_from > self.date_to:
                raise ValueError("date_from must not be after date_to")
        elif self.date_from is not None or self.date_to is not None:
            raise ValueError("date bounds are only valid for custom_date_range")
        if (
            self.scope_type == ScopeType.FULL_HISTORY
            and self.pagination_policy != PaginationPolicy.TO_PROVIDER_END
        ):
            raise ValueError("full_history must paginate to provider end")
        if (
            self.scope_type == ScopeType.FULL_HISTORY
            and (self.max_pages is not None or self.max_records is not None)
        ):
            raise ValueError("full_history cannot use bounded test limits")
        return self


class TimeScopeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_type: ScopeType
    requested_date_from: datetime | None = None
    requested_date_to: datetime | None = None
    timezone: str
    overall_first_seen: datetime | None = None
    overall_last_seen: datetime | None = None
    first_seen_by_asset: dict[str, datetime] = Field(default_factory=dict)
    last_seen_by_asset: dict[str, datetime] = Field(default_factory=dict)
    first_seen_by_capability: dict[str, datetime] = Field(default_factory=dict)
    last_seen_by_capability: dict[str, datetime] = Field(default_factory=dict)
    full_history_complete: bool = False
    excluded_by_scope: int = Field(default=0, ge=0)


def in_scope(timestamp: datetime | None, scope: AnalysisScope) -> bool:
    if scope.scope_type != ScopeType.CUSTOM_DATE_RANGE:
        return True
    if timestamp is None:
        return False
    after_start = (
        timestamp >= scope.date_from
        if scope.inclusive_start
        else timestamp > scope.date_from
    )
    before_end = (
        timestamp <= scope.date_to
        if scope.inclusive_end
        else timestamp < scope.date_to
    )
    return after_start and before_end
