from typing import Any

from pydantic import BaseModel, Field


class Observation(BaseModel):
    code: str
    title: str
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    limitations: list[str] = Field(default_factory=list)

