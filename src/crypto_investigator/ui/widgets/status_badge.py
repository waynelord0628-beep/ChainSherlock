from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    SAFE_STATUSES = {
        "confirmed", "candidate", "pending", "running", "completed", "warning",
        "partial", "failed", "cancelled", "skipped", "unavailable",
    }

    def set_status(self, status: str) -> None:
        normalized = status.lower()
        if normalized not in self.SAFE_STATUSES:
            normalized = "unavailable"
        self.setObjectName(normalized)
        self.setText(normalized)
        self.style().unpolish(self)
        self.style().polish(self)
