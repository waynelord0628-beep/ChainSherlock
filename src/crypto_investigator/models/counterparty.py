from datetime import datetime

from pydantic import BaseModel, Field

from crypto_investigator.models.transaction import Chain


class CounterpartySummary(BaseModel):
    address: str
    chain: Chain
    incoming_count: int = 0
    outgoing_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    relationship_score: float = 0.0

