from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AIUsage:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    cache_hit: bool = False
    elapsed_seconds: float = 0
    estimated_cost: float | None = None


@dataclass(frozen=True, slots=True)
class AIResponse:
    content: str
    usage: AIUsage
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIStatus:
    enabled: bool
    requested: bool
    provider: str
    model: str
    status: str
    cache_hit: bool
    validation_passed: bool
    fallback_used: bool
    generated_at: datetime
    warnings: tuple[str, ...] = ()
