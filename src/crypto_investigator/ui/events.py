from enum import StrEnum


class UIEvent(StrEnum):
    CASE_SELECTED = "case_selected"
    CASE_CHANGED = "case_changed"
    EXECUTION_CHANGED = "execution_changed"
    ARTIFACT_CREATED = "artifact_created"
    SETTINGS_CHANGED = "settings_changed"
