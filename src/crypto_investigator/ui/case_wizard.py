from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from crypto_investigator.ui.labels import HUMAN_LABELS


DEFAULT_GOALS = (
    "identify_main_sources",
    "identify_main_destinations",
    "detect_batch_distribution",
    "detect_funding_transition",
    "identify_service_candidates",
    "generate_investigation_report",
)


class CaseWizard(QDialog):
    """Five-step case wizard that returns only user-confirmed clues."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("建立新案件")
        self.setMinimumSize(760, 590)
        self.attachments: list[Path] = []
        self.step_names = ["基本資料", "案件說明", "匯入證據", "確認線索", "調查目標"]
        root = QVBoxLayout(self)
        self.progress = QLabel()
        self.progress.setObjectName("sectionTitle")
        root.addWidget(self.progress)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self._build_steps()
        buttons = QHBoxLayout()
        self.back_button = QPushButton("上一步")
        self.back_button.setProperty("variant", "secondary")
        self.next_button = QPushButton("下一步")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setProperty("variant", "secondary")
        self.back_button.clicked.connect(self.back)
        self.next_button.clicked.connect(self.next)
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.next_button)
        root.addLayout(buttons)
        self._sync()

    def _page(self, title: str, description: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(title, objectName="pageTitle")
        note = QLabel(description, objectName="muted")
        note.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(note)
        layout.addSpacing(14)
        return page, layout

    def _build_steps(self) -> None:
        page, layout = self._page("基本資料", "建立案件識別資訊；案件 ID 會由系統安全產生。")
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.number_edit = QLineEdit()
        self.chain_edit = QComboBox()
        self.chain_edit.addItems(["未指定", "TRON", "Ethereum", "Bitcoin"])
        self.owner_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        form.addRow("案件標題 *", self.title_edit)
        form.addRow("案件編號", self.number_edit)
        form.addRow("主要鏈", self.chain_edit)
        form.addRow("案件負責人", self.owner_edit)
        form.addRow("標籤（逗號分隔）", self.tags_edit)
        layout.addLayout(form)
        layout.addStretch()
        self.stack.addWidget(page)

        page, layout = self._page("案件說明", "記錄案件背景與目前希望釐清的問題。")
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("案件背景、資金事件與調查目的…")
        self.questions_edit = QPlainTextEdit()
        self.questions_edit.setPlaceholderText("一行一個待回答問題")
        layout.addWidget(QLabel("案件背景", objectName="sectionTitle"))
        layout.addWidget(self.description_edit)
        layout.addWidget(QLabel("待回答問題", objectName="sectionTitle"))
        layout.addWidget(self.questions_edit)
        self.stack.addWidget(page)

        page, layout = self._page("匯入證據", "原始檔案會在案件建立後複製並計算 SHA-256。")
        self.attachment_list = QListWidget()
        add_file = QPushButton("選擇證據檔案")
        add_file.clicked.connect(self.add_attachment)
        layout.addWidget(self.attachment_list)
        layout.addWidget(add_file, alignment=Qt.AlignLeft)
        self.stack.addWidget(page)

        page, layout = self._page(
            "確認線索",
            "只有明確確認的線索會寫入案件；系統不會自動猜測地址角色。",
        )
        form = QFormLayout()
        self.address_edit = QLineEdit()
        self.tx_edit = QLineEdit()
        self.asset_edit = QLineEdit()
        self.amount_edit = QLineEdit()
        self.confirm_clues = QCheckBox("我確認上述線索應加入案件")
        form.addRow("地址", self.address_edit)
        form.addRow("Tx Hash", self.tx_edit)
        form.addRow("資產", self.asset_edit)
        form.addRow("金額", self.amount_edit)
        layout.addLayout(form)
        layout.addWidget(self.confirm_clues)
        layout.addStretch()
        self.stack.addWidget(page)

        page, layout = self._page("調查目標", "選擇本案要回答的問題；建立後仍可調整。")
        self.goal_checks: dict[str, QCheckBox] = {}
        for goal in DEFAULT_GOALS:
            checkbox = QCheckBox(HUMAN_LABELS[goal])
            checkbox.setChecked(goal in {"identify_main_sources", "identify_main_destinations"})
            self.goal_checks[goal] = checkbox
            layout.addWidget(checkbox)
        layout.addStretch()
        self.stack.addWidget(page)

    def add_attachment(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "選擇證據")
        for value in paths:
            path = Path(value)
            if path not in self.attachments:
                self.attachments.append(path)
                self.attachment_list.addItem(path.name)

    def back(self) -> None:
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._sync()

    def next(self) -> None:
        index = self.stack.currentIndex()
        if index == 0 and not self.title_edit.text().strip():
            QMessageBox.warning(self, "缺少資料", "請輸入案件標題。")
            return
        if index < self.stack.count() - 1:
            self.stack.setCurrentIndex(index + 1)
            self._sync()
        else:
            self.accept()

    def _sync(self) -> None:
        index = self.stack.currentIndex()
        self.progress.setText(
            f"步驟 {index + 1}／{self.stack.count()}　{self.step_names[index]}"
        )
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("建立案件" if index == self.stack.count() - 1 else "下一步")

    def payload(self) -> dict:
        confirmed = self.confirm_clues.isChecked()
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "metadata": {
                "case_number": self.number_edit.text().strip() or None,
                "chain": (
                    None
                    if self.chain_edit.currentIndex() == 0
                    else self.chain_edit.currentText().lower()
                ),
                "owner": self.owner_edit.text().strip() or None,
                "tags": [
                    item.strip()
                    for item in self.tags_edit.text().split(",")
                    if item.strip()
                ],
                "questions": [
                    item.strip()
                    for item in self.questions_edit.toPlainText().splitlines()
                    if item.strip()
                ],
                "known_addresses": (
                    [self.address_edit.text().strip()]
                    if confirmed and self.address_edit.text().strip()
                    else []
                ),
                "known_transactions": (
                    [self.tx_edit.text().strip()]
                    if confirmed and self.tx_edit.text().strip()
                    else []
                ),
                "confirmed_assets": (
                    [self.asset_edit.text().strip()]
                    if confirmed and self.asset_edit.text().strip()
                    else []
                ),
                "confirmed_amount": (
                    self.amount_edit.text().strip() if confirmed else None
                ),
            },
            "attachments": list(self.attachments),
            "goals": [
                name for name, checkbox in self.goal_checks.items() if checkbox.isChecked()
            ],
        }
