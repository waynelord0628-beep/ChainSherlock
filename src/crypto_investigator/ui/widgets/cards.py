from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "0", note: str = "") -> None:
        super().__init__(objectName="metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.value_label = QLabel(value, objectName="metricValue")
        self.label = QLabel(label, objectName="metricLabel")
        self.note = QLabel(note, objectName="muted")
        self.note.setWordWrap(True)
        layout.addWidget(self.value_label)
        layout.addWidget(self.label)
        if note:
            layout.addWidget(self.note)

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))


class EmptyState(QFrame):
    def __init__(self, title: str, message: str) -> None:
        super().__init__(objectName="sectionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 30)
        title_label = QLabel(title, objectName="sectionTitle")
        message_label = QLabel(message, objectName="muted")
        message_label.setWordWrap(True)
        layout.addStretch()
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        layout.addWidget(message_label, alignment=Qt.AlignCenter)
        layout.addStretch()


class SectionHeader(QFrame):
    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 8)
        text = QVBoxLayout()
        text.addWidget(QLabel(title, objectName="sectionTitle"))
        if description:
            description_label = QLabel(description, objectName="muted")
            description_label.setWordWrap(True)
            text.addWidget(description_label)
        layout.addLayout(text)
        layout.addStretch()
