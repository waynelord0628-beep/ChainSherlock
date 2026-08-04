from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crypto_investigator.cases.storage import atomic_write_json


class UISettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    theme: str = "light"
    language: str = "zh-TW"
    timezone: str = "Asia/Taipei"
    case_root: str = "cases"
    last_page: str = "Home"
    last_case_id: str | None = None
    window_width: int = 1280
    window_height: int = 820
    ai_enabled: bool = False
    prompt_mode: str = "compact"
    privacy_mode: str = "standard"
    max_pages: int = 1
    max_records: int = 50


class UISettingsService:
    FORBIDDEN = {"api_key", "authorization", "password", "prompt", "secret", "token"}

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> UISettings:
        if not self.path.is_file():
            return UISettings()
        try:
            return UISettings.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return UISettings()

    def save(self, settings: UISettings | dict) -> UISettings:
        raw = (
            settings.model_dump(mode="json")
            if isinstance(settings, UISettings)
            else dict(settings)
        )
        allowed = set(UISettings.model_fields)
        for key in raw:
            if key not in allowed:
                raise ValueError(f"setting is not persistable: {key}")
        safe = UISettings.model_validate(raw)
        atomic_write_json(self.path, safe.model_dump(mode="json"))
        return safe

    def contains_sensitive_data(self) -> bool:
        if not self.path.exists():
            return False
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return any(str(key) not in UISettings.model_fields for key in data)
