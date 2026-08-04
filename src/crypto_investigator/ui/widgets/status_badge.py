from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    SAFE_STATUSES = {
        "available", "supported", "configured", "not_configured", "disabled", "unknown",
        "confirmed", "candidate", "observation", "pending", "ready", "running",
        "completed", "warning", "partial", "failed", "error", "cancelled",
        "skipped", "unavailable", "verified", "mismatch", "missing",
    }

    def set_status(self, status: str, text: str | None = None) -> None:
        normalized = status.lower()
        if normalized not in self.SAFE_STATUSES:
            normalized = "unknown"
        self.setObjectName(normalized)
        self.setProperty("status", normalized)
        self.setText(text or normalized)
        self.style().unpolish(self)
        self.style().polish(self)
