from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class MetricCard(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "0",
        note: str = "",
        eyebrow: str = "",
        accent: str = "teal",
    ) -> None:
        super().__init__(objectName="metricCard")
        self.setProperty("accent", accent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.eyebrow = QLabel(eyebrow, objectName="eyebrow")
        self.value_label = QLabel(value, objectName="metricValue")
        self.label = QLabel(label, objectName="metricLabel")
        self.note = QLabel(note, objectName="muted")
        self.note.setWordWrap(True)
        if eyebrow:
            layout.addWidget(self.eyebrow)
        layout.addWidget(self.value_label)
        layout.addWidget(self.label)
        if note:
            layout.addWidget(self.note)

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))


class EmptyState(QFrame):
    def __init__(self, title: str, message: str) -> None:
        super().__init__(objectName="emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 30)
        title_label = QLabel(title, objectName="sectionTitle")
        message_label = QLabel(message, objectName="muted")
        message_label.setWordWrap(True)
        layout.addStretch()
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        layout.addWidget(message_label, alignment=Qt.AlignCenter)
        layout.addStretch()
        self.action_layout = QHBoxLayout()
        self.action_layout.addStretch()
        layout.addLayout(self.action_layout)

    def add_action(self, text: str, callback, *, secondary: bool = False) -> QPushButton:
        button = QPushButton(text)
        if secondary:
            button.setProperty("variant", "secondary")
        button.clicked.connect(callback)
        self.action_layout.insertWidget(self.action_layout.count() - 1, button)
        return button


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
