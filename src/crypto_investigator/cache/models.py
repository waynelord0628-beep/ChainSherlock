from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheEntry:
    created_at: datetime
    expires_at: datetime
    value: Any
