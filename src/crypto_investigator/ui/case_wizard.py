from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDateTimeEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
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
    "trace_funds",
    "generate_investigation_report",
)


class CaseWizard(QDialog):
    """Five-step case wizard that returns only user-confirmed clues."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("建立新案件")
        self.setMinimumSize(760, 590)
        self.attachments: list[Path] = []
        self.step_names = [
            "基本資料",
            "案件說明",
            "匯入證據",
            "確認線索",
            "分析範圍",
            "調查目標",
        ]
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

        page, layout = self._page(
            "分析範圍",
            "正式報告預設使用 Full History；若 Provider 無法完整分頁，報告會標記 partial。",
        )
        form = QFormLayout()
        self.scope_type = QComboBox()
        self.scope_type.addItem("Full History", "full_history")
        self.scope_type.addItem("Custom Date Range", "custom_date_range")
        self.scope_type.addItem("Quick Preview（非正式）", "quick_preview")
        self.scope_timezone = QComboBox()
        self.scope_timezone.addItems(["Asia/Taipei", "UTC"])
        self.scope_from = QDateTimeEdit()
        self.scope_from.setCalendarPopup(True)
        self.scope_from.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.scope_to = QDateTimeEdit()
        self.scope_to.setCalendarPopup(True)
        self.scope_to.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.scope_from.setEnabled(False)
        self.scope_to.setEnabled(False)
        self.scope_inclusive_start = QCheckBox("包含開始時間")
        self.scope_inclusive_start.setChecked(True)
        self.scope_inclusive_end = QCheckBox("包含結束時間")
        self.scope_inclusive_end.setChecked(True)
        self.scope_max_pages = QLineEdit("1")
        self.scope_max_records = QLineEdit("500")
        self.scope_max_pages.setEnabled(False)
        self.scope_max_records.setEnabled(False)
        self.scope_type.currentIndexChanged.connect(self._scope_changed)
        self.chain_edit.currentIndexChanged.connect(self._scope_changed)
        form.addRow("模式", self.scope_type)
        form.addRow("時區", self.scope_timezone)
        form.addRow("開始", self.scope_from)
        form.addRow("結束", self.scope_to)
        form.addRow("", self.scope_inclusive_start)
        form.addRow("", self.scope_inclusive_end)
        form.addRow("Quick Preview max pages", self.scope_max_pages)
        form.addRow("Quick Preview max records", self.scope_max_records)
        self.trace_depth = QSpinBox()
        self.trace_depth.setRange(1, 5)
        self.trace_depth.setValue(3)
        self.trace_max_nodes = QSpinBox()
        self.trace_max_nodes.setRange(10, 500)
        self.trace_max_nodes.setValue(100)
        self.trace_materiality = QDoubleSpinBox()
        self.trace_materiality.setRange(0, 1_000_000_000)
        self.trace_materiality.setDecimals(8)
        self.trace_materiality.setValue(1)
        self.trace_direction = QComboBox()
        self.trace_direction.addItem("向前及向後", "bidirectional")
        self.trace_direction.addItem("僅向前", "forward")
        self.trace_direction.addItem("僅向後", "backward")
        self.trace_manual_stops = QLineEdit()
        self.trace_manual_stops.setPlaceholderText("地址以逗號分隔（選填）")
        form.addRow("多層追蹤深度", self.trace_depth)
        form.addRow("多層追蹤節點上限", self.trace_max_nodes)
        form.addRow("最低重要金額", self.trace_materiality)
        form.addRow("追蹤方向", self.trace_direction)
        form.addRow("人工停止地址", self.trace_manual_stops)
        layout.addLayout(form)
        self.scope_guidance = QLabel(objectName="muted")
        self.scope_guidance.setWordWrap(True)
        layout.addWidget(self.scope_guidance)
        self._scope_changed()
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

    def _scope_changed(self) -> None:
        value = self.scope_type.currentData()
        custom = value == "custom_date_range"
        quick = value == "quick_preview"
        self.scope_from.setEnabled(custom)
        self.scope_to.setEnabled(custom)
        self.scope_max_pages.setEnabled(quick)
        self.scope_max_records.setEnabled(quick)
        chain = self.chain_edit.currentText().lower()
        capabilities = {
            "ethereum": "normal transactions、token transfers",
            "tron": "native transactions、TRC20 transfers",
            "bitcoin": "address transactions、UTXO/spend information",
        }.get(chain, "依所選鏈別決定")
        if value == "full_history":
            message = (
                "Full History 會持續分頁到 Provider 明確資料結尾，可能耗時且增加 "
                f"API 呼叫；必要資料能力：{capabilities}。只有必要能力均完整時才會"
                "標記為完整歷史。"
            )
        elif value == "custom_date_range":
            message = (
                f"指定期間會使用所選時區與包含邊界；必要資料能力：{capabilities}。"
                "期間外交易不會進入分析、圖譜、調查或報告。"
            )
        else:
            message = (
                "Quick Preview 受頁數與筆數上限限制，只供快速預覽；不得解讀為完整"
                "歷史或正式首次／最後交易判定。"
            )
        self.scope_guidance.setText(message)

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
        scope_type = self.scope_type.currentData()
        analysis_scope = {
            "scope_type": scope_type,
            "date_from": (
                self.scope_from.dateTime().toPython().astimezone().isoformat()
                if scope_type == "custom_date_range"
                else None
            ),
            "date_to": (
                self.scope_to.dateTime().toPython().astimezone().isoformat()
                if scope_type == "custom_date_range"
                else None
            ),
            "timezone": self.scope_timezone.currentText(),
            "inclusive_start": self.scope_inclusive_start.isChecked(),
            "inclusive_end": self.scope_inclusive_end.isChecked(),
            "completeness_requirement": (
                "best_effort"
                if scope_type == "quick_preview"
                else "required_capabilities_complete"
            ),
            "pagination_policy": (
                "bounded" if scope_type == "quick_preview" else "to_provider_end"
            ),
            "max_pages": (
                max(1, int(self.scope_max_pages.text() or "1"))
                if scope_type == "quick_preview"
                else None
            ),
            "max_records": (
                max(1, int(self.scope_max_records.text() or "500"))
                if scope_type == "quick_preview"
                else None
            ),
        }
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
                "analysis_scope": analysis_scope,
                "trace_settings": {
                    "max_depth": self.trace_depth.value(),
                    "max_nodes": self.trace_max_nodes.value(),
                    "min_material_amount": str(self.trace_materiality.value()),
                    "direction": self.trace_direction.currentData(),
                    "manual_stop_addresses": [
                        item.strip()
                        for item in self.trace_manual_stops.text().split(",")
                        if item.strip()
                    ],
                    "allocation_method": "fifo",
                    "checkpoint_enabled": True,
                },
            },
            "attachments": list(self.attachments),
            "goals": [
                name for name, checkbox in self.goal_checks.items() if checkbox.isChecked()
            ],
        }
