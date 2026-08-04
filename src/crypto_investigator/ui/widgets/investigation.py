from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


def abbreviate_chain_value(value: str, head: int = 6, tail: int = 4) -> str:
    text = str(value)
    if len(text) <= head + tail + 1:
        return text
    return f"{text[:head]}…{text[-tail:]}"


class ChainBadge(QLabel):
    SAFE_CHAINS = {"ETH", "EVM", "TRON", "BTC", "MULTI", "UNKNOWN"}

    def __init__(self, chain: str) -> None:
        normalized = str(chain or "UNKNOWN").upper()
        if normalized == "ETHEREUM":
            normalized = "ETH"
        elif normalized == "BITCOIN":
            normalized = "BTC"
        if normalized not in self.SAFE_CHAINS:
            normalized = "UNKNOWN"
        super().__init__(normalized)
        self.setObjectName("chainBadge")
        self.setProperty("chain", normalized.lower())


class AssetBadge(QLabel):
    def __init__(self, asset: str) -> None:
        super().__init__(str(asset or "UNKNOWN").upper())
        self.setObjectName("assetBadge")


class MonoValueLabel(QLabel):
    def __init__(self, value: str, *, abbreviated: bool = True) -> None:
        self.full_value = str(value)
        super().__init__(
            abbreviate_chain_value(self.full_value) if abbreviated else self.full_value
        )
        self.setObjectName("monoValue")
        self.setToolTip(self.full_value)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setProperty("copyValue", self.full_value)


class InvestigationBackdrop(QFrame):
    """Static, low-contrast node graph. It never represents case data."""

    def __init__(self) -> None:
        super().__init__(objectName="investigationBackdrop")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        points = (
            (0.61, 0.28), (0.74, 0.20), (0.84, 0.38),
            (0.68, 0.57), (0.89, 0.68), (0.77, 0.82),
        )
        pen = QPen(QColor(45, 212, 191, 32), 1.0)
        painter.setPen(pen)
        for first, second in ((0, 1), (1, 2), (0, 3), (3, 4), (3, 5), (4, 5)):
            a, b = points[first], points[second]
            painter.drawLine(
                int(a[0] * self.width()), int(a[1] * self.height()),
                int(b[0] * self.width()), int(b[1] * self.height()),
            )
        for x, y in points:
            center_x, center_y = x * self.width(), y * self.height()
            painter.setBrush(QColor(56, 189, 248, 42))
            painter.setPen(QPen(QColor(94, 234, 212, 85), 1))
            painter.drawEllipse(QRectF(center_x - 4, center_y - 4, 8, 8))
        painter.setPen(QColor(148, 163, 184, 45))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(
            self.rect().adjusted(0, 0, -18, -12),
            Qt.AlignRight | Qt.AlignBottom,
            "LOCAL WORKSPACE  •  EVIDENCE VERIFIED",
        )


class InvestigationQueueItem(QFrame):
    def __init__(
        self,
        *,
        title: str,
        case_id: str,
        chain: str,
        assets: list[str],
        seed_count: int,
        evidence_count: int,
        status: str,
        completeness: str,
        updated_at: str,
        next_action: str,
        open_case,
    ) -> None:
        super().__init__(objectName="queueItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        heading = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight:600;color:#E6EDF7")
        heading.addWidget(title_label, 1)
        open_button = QPushButton("開啟案件")
        open_button.setProperty("variant", "secondary")
        open_button.clicked.connect(open_case)
        heading.addWidget(open_button)
        layout.addLayout(heading)
        layout.addWidget(MonoValueLabel(case_id, abbreviated=False))
        badges = QHBoxLayout()
        badges.addWidget(ChainBadge(chain))
        for asset in assets[:4]:
            badges.addWidget(AssetBadge(asset))
        badges.addStretch()
        layout.addLayout(badges)
        summary = QLabel(
            f"Seed {seed_count}  ·  Evidence {evidence_count}  ·  {status}  ·  "
            f"Completeness {completeness}"
        )
        summary.setObjectName("muted")
        summary.setWordWrap(True)
        layout.addWidget(summary)
        action = QLabel(f"下一步：{next_action}  ·  {updated_at}")
        action.setObjectName("muted")
        action.setWordWrap(True)
        layout.addWidget(action)
