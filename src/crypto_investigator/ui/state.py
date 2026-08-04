from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class UIState:
    case_root: Path
    current_case_id: str | None = None
    current_page: str = "Home"
    running_execution_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def select_case(self, case_id: str | None) -> None:
        self.current_case_id = case_id

    @property
    def has_case(self) -> bool:
        return self.current_case_id is not None
