from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from crypto_investigator.cases import CaseRepository
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.ui.case_wizard import CaseWizard
from crypto_investigator.ui.labels import human_label
from crypto_investigator.ui.models import RecordsTableModel
from crypto_investigator.ui.services import CaseUIService, UISettings, UISettingsService
from crypto_investigator.ui.state import UIState
from crypto_investigator.ui.theme import LIGHT_THEME
from crypto_investigator.ui.widgets import (
    AssetBadge,
    ChainBadge,
    EmptyState,
    InvestigationBackdrop,
    InvestigationQueueItem,
    MetricCard,
    MonoValueLabel,
    SafeGraphView,
    StatusBadge,
    abbreviate_chain_value,
)
from crypto_investigator.ui.workers import BackgroundWorker


WORKSPACE_TABS = (
    "案情",
    "線索",
    "Evidence",
    "調查目標",
    "調查計畫",
    "Execution",
    "Result",
    "Investigation",
    "Counterparty",
    "Graph",
    "Narrative",
    "Report",
    "Review",
    "Audit",
)

_STATUS_ZH = {
    "not_started": "尚未開始",
    "pending": "等待中",
    "running": "執行中",
    "completed": "已完成",
    "complete": "完整",
    "warning": "需要注意",
    "partial": "部分完成",
    "failed": "失敗",
    "cancelled": "已取消",
    "skipped": "已略過",
    "unavailable": "尚無資料",
    "open": "進行中",
    "archived": "已封存",
    "approved": "已核准",
    "proposed": "待確認",
    "confirmed": "已確認",
    "candidate": "候選",
    "ready": "就緒",
    "unknown": "未知",
    "supported": "已支援",
    "available": "可用",
    "configured": "已設定",
    "not_configured": "未設定",
    "disabled": "已停用",
    "not_reviewed": "尚未覆核",
    "reviewed": "已覆核",
}


def _safe(value: object) -> str:
    return html.escape(str(redact_sensitive(value)))


def _badge(status: str) -> str:
    normalized = status.lower()
    label = _STATUS_ZH.get(normalized, human_label(normalized))
    colors = {
        "completed": ("#DCFCE7", "#166534"),
        "confirmed": ("#DCFCE7", "#166534"),
        "running": ("#DBEAFE", "#1D4ED8"),
        "partial": ("#FFEDD5", "#9A3412"),
        "warning": ("#FFEDD5", "#9A3412"),
        "failed": ("#FEE2E2", "#991B1B"),
        "candidate": ("#FEF3C7", "#92400E"),
    }
    background, foreground = colors.get(normalized, ("#E2E8F0", "#475569"))
    return (
        f"<span style='background:{background};color:{foreground};"
        "padding:3px 8px;border-radius:9px;font-weight:600'>"
        f"{_safe(label)}</span>"
    )


class MainWindow(QMainWindow):
    case_opened = Signal(str)
    execution_event_received = Signal(object)

    def __init__(
        self,
        case_root: Path | str = "cases",
        settings_path: Path | None = None,
        execution_service=None,
    ) -> None:
        super().__init__()
        self.setObjectName("main_window")
        self.setWindowTitle("ChainSherlock — 案件調查工作台")
        self.resize(1360, 860)
        self.repository = CaseRepository(case_root)
        self.case_service = CaseUIService(self.repository)
        if execution_service is None:
            from crypto_investigator.application import (
                CaseExecutionService,
                create_desktop_execution_registry,
            )

            execution_service = CaseExecutionService(
                self.repository,
                create_desktop_execution_registry(self.repository),
            )
        self.execution_service = execution_service
        self.settings_service = UISettingsService(
            settings_path or Path(case_root) / ".ui-settings.json"
        )
        self.settings = self.settings_service.load()
        self.state = UIState(case_root=Path(case_root))
        self.thread_pool = QThreadPool(self)
        self.active_workers: list[BackgroundWorker] = []
        self._execution_started_at: float | None = None
        self._active_execution_case_id: str | None = None
        self._active_execution_artifacts: set[str] = set()
        self.execution_event_received.connect(self._apply_execution_event)
        self.execution_clock = QTimer(self)
        self.execution_clock.setInterval(1000)
        self.execution_clock.timeout.connect(self._update_execution_elapsed)
        self.setStyleSheet(LIGHT_THEME)
        self._build_ui()
        self._install_shortcuts()
        self.refresh_cases()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(224)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 18, 10, 14)
        brand = QLabel("ChainSherlock", objectName="brand")
        brand_note = QLabel("BLOCKCHAIN FORENSICS", objectName="brandSubtitle")
        side_layout.addWidget(brand)
        side_layout.addWidget(brand_note)
        side_layout.addSpacing(16)
        self.navigation = QListWidget(objectName="navigation")
        self.navigation.addItems(["首頁", "案件清單", "建立案件", "設定"])
        self.navigation.currentRowChanged.connect(self._navigate)
        side_layout.addWidget(self.navigation, 1)
        self.global_execution = QFrame(objectName="sectionCard")
        global_layout = QVBoxLayout(self.global_execution)
        global_layout.setContentsMargins(10, 10, 10, 10)
        global_layout.addWidget(QLabel("LIVE EXECUTION", objectName="eyebrow"))
        self.global_execution_badge = StatusBadge()
        self.global_execution_badge.set_status("disabled", "IDLE")
        self.global_execution_title = QLabel("目前沒有執行中的工作")
        self.global_execution_title.setWordWrap(True)
        self.global_execution_title.setStyleSheet("font-weight:600")
        self.global_execution_title.setMaximumHeight(
            self.global_execution_title.fontMetrics().lineSpacing() * 2 + 6
        )
        self.global_execution_detail = QLabel("建立並確認調查計畫後即可開始執行。")
        self.global_execution_detail.setWordWrap(True)
        self.global_execution_detail.setObjectName("muted")
        self.global_execution_detail.setMaximumHeight(
            self.global_execution_detail.fontMetrics().lineSpacing() * 6 + 6
        )
        self.global_execution_meta = QLabel()
        self.global_execution_meta.setWordWrap(True)
        self.global_execution_meta.setObjectName("muted")
        self.global_execution_progress = QProgressBar(objectName="global_execution_progress")
        self.global_execution_progress.setTextVisible(False)
        self.global_execution_progress.hide()
        self.global_execution_actions = QWidget()
        global_actions = QHBoxLayout(self.global_execution_actions)
        global_actions.setContentsMargins(0, 2, 0, 0)
        details = QPushButton("查看詳情")
        details.setProperty("variant", "secondary")
        details.clicked.connect(self._open_active_execution)
        cancel = QPushButton("取消")
        cancel.setProperty("variant", "danger")
        cancel.clicked.connect(self.cancel_execution)
        global_actions.addWidget(details)
        global_actions.addWidget(cancel)
        self.global_execution_actions.hide()
        global_layout.addWidget(self.global_execution_badge, alignment=Qt.AlignLeft)
        global_layout.addWidget(self.global_execution_title)
        global_layout.addWidget(self.global_execution_detail)
        global_layout.addWidget(self.global_execution_meta)
        global_layout.addWidget(self.global_execution_progress)
        global_layout.addWidget(self.global_execution_actions)
        side_layout.addWidget(self.global_execution)
        self.case_status = QLabel("未開啟案件")
        self.case_status.setWordWrap(True)
        self.case_status.setStyleSheet("color:#94A3B8;padding:8px")
        side_layout.addWidget(self.case_status)

        self.pages = QStackedWidget()
        self.home_page = self._build_home()
        self.case_list_page = self._build_case_list()
        self.new_case_page = self._build_new_case()
        self.settings_page = self._build_settings()
        self.workspace_page = self._build_workspace()
        for page in (
            self.home_page,
            self.case_list_page,
            self.new_case_page,
            self.settings_page,
            self.workspace_page,
        ):
            self.pages.addWidget(page)
        layout.addWidget(sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.navigation.setCurrentRow(0)
        self.statusBar().showMessage("就緒")

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.navigation.setCurrentRow(2))
        QShortcut(QKeySequence("Ctrl+O"), self, activated=lambda: self.navigation.setCurrentRow(1))
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_current_case)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.next_workflow_action)

    def _page(self, title: str, subtitle: str = "") -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 20)
        title_label = QLabel(title, objectName="pageTitle")
        layout.addWidget(title_label)
        if subtitle:
            note = QLabel(subtitle, objectName="muted")
            note.setWordWrap(True)
            layout.addWidget(note)
        layout.addSpacing(8)
        return page, layout

    def _build_home(self) -> QWidget:
        page, layout = self._page(
            "案件調查工作台",
            "從鏈上線索、Evidence、資金流分析到案件報告，建立可驗證、可追溯的完整調查流程。",
        )
        hero = InvestigationBackdrop()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_text = QVBoxLayout()
        hero_title = QLabel("CRYPTO INVESTIGATION COMMAND CENTER", objectName="eyebrow")
        hero_note = QLabel(
            "LOCAL-FIRST  ·  EVIDENCE-BASED  ·  HASH-VERIFIED  ·  AUDITABLE",
            objectName="muted",
        )
        hero_text.addWidget(hero_title)
        hero_text.addWidget(hero_note)
        primary = QPushButton("＋ 建立新案件")
        primary.clicked.connect(self.open_case_wizard)
        secondary = QPushButton("開啟案件清單")
        secondary.setProperty("variant", "secondary")
        secondary.clicked.connect(lambda: self.navigation.setCurrentRow(1))
        hero_layout.addLayout(hero_text, 1)
        hero_layout.addWidget(secondary)
        hero_layout.addWidget(primary)
        layout.addWidget(hero)

        metrics = QGridLayout()
        self.home_metrics_layout = metrics
        self.home_metric_cards = {
            "cases": MetricCard("進行中案件", eyebrow="ACTIVE CASES", accent="teal"),
            "running": MetricCard("執行中的工作", eyebrow="LIVE EXECUTIONS", accent="blue"),
            "partial": MetricCard("部分完成", eyebrow="PARTIAL COVERAGE", accent="amber"),
            "review": MetricCard("等待審核", eyebrow="REVIEW REQUIRED", accent="violet"),
        }
        for index, card in enumerate(self.home_metric_cards.values()):
            metrics.addWidget(card, 0, index)
        layout.addLayout(metrics)

        lower_content = QWidget()
        lower = QHBoxLayout(lower_content)
        lower.setContentsMargins(0, 0, 0, 0)
        recent_card = QFrame(objectName="sectionCard")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.addWidget(QLabel("調查佇列", objectName="sectionTitle"))
        recent_layout.addWidget(QLabel("INVESTIGATION QUEUE", objectName="eyebrow"))
        self.home_recent_stack = QStackedWidget()
        loading = QLabel("正在載入調查案件…", objectName="muted")
        loading.setAlignment(Qt.AlignCenter)
        self.home_recent_stack.addWidget(loading)
        self.home_recent_empty = EmptyState(
            "尚無調查案件",
            "建立案件並加入地址、交易雜湊或 CSV／Excel Evidence，開始第一個鏈上調查。",
        )
        self.home_recent_empty.add_action("建立新案件", self.open_case_wizard)
        self.home_recent_empty.add_action(
            "開啟案件清單",
            lambda: self.navigation.setCurrentRow(1),
            secondary=True,
        )
        self.home_recent_stack.addWidget(self.home_recent_empty)
        self.home_recent_error = EmptyState(
            "無法載入調查佇列",
            "案件資料目前無法讀取，請檢查本機 workspace 後重試。",
        )
        self.home_recent_error.add_action("重新載入", self.refresh_cases)
        self.home_recent_stack.addWidget(self.home_recent_error)
        self.home_recent = QListWidget()
        self.home_recent.setSpacing(6)
        self.home_recent.setWordWrap(True)
        self.home_recent.itemDoubleClicked.connect(self._open_recent_case)
        self.home_recent_stack.addWidget(self.home_recent)
        recent_layout.addWidget(self.home_recent_stack)
        lower.addWidget(recent_card, 2)
        status_card = QFrame(objectName="sectionCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.addWidget(QLabel("調查系統狀態", objectName="sectionTitle"))
        status_layout.addWidget(QLabel("SYSTEM READINESS", objectName="eyebrow"))
        self.home_status_badges: dict[str, StatusBadge] = {}
        for name, status_code, status_text, description in self._system_readiness():
            row = QHBoxLayout()
            text = QVBoxLayout()
            text.addWidget(QLabel(name))
            detail = QLabel(description, objectName="muted")
            detail.setWordWrap(True)
            text.addWidget(detail)
            badge = StatusBadge()
            badge.set_status(status_code, status_text)
            self.home_status_badges[name] = badge
            row.addLayout(text, 1)
            row.addWidget(badge, alignment=Qt.AlignTop)
            status_layout.addLayout(row)
        lower.addWidget(status_card, 1)
        lower_scroll = QScrollArea()
        lower_scroll.setWidgetResizable(True)
        lower_scroll.setFrameShape(QFrame.NoFrame)
        lower_scroll.setWidget(lower_content)
        layout.addWidget(lower_scroll, 1)
        self.home_counts = QLabel()
        self.home_counts.hide()
        layout.addWidget(self.home_counts)
        return page

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if not hasattr(self, "home_metrics_layout"):
            return
        columns = 2 if self.width() < 1180 else 4
        for index, card in enumerate(self.home_metric_cards.values()):
            self.home_metrics_layout.addWidget(card, index // columns, index % columns)

    def _build_case_list(self) -> QWidget:
        page, layout = self._page("案件清單", "搜尋、排序並開啟既有案件。")
        tools = QHBoxLayout()
        self.case_search = QLineEdit(placeholderText="搜尋案件名稱、編號或 Case ID")
        self.case_search.textChanged.connect(self.refresh_cases)
        self.show_archived = QCheckBox("顯示已封存")
        self.show_archived.toggled.connect(self.refresh_cases)
        create = QPushButton("＋ 建立案件")
        create.clicked.connect(self.open_case_wizard)
        tools.addWidget(self.case_search, 1)
        tools.addWidget(self.show_archived)
        tools.addWidget(create)
        layout.addLayout(tools)
        self.case_model = RecordsTableModel(
            ["Case ID", "案件標題", "狀態", "主要鏈", "證據", "執行狀態", "更新時間"]
        )
        self.case_table = QTableView()
        self.case_table.setModel(self.case_model)
        self.case_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.case_table.setAlternatingRowColors(True)
        self.case_table.setSortingEnabled(True)
        self.case_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.case_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.case_table.doubleClicked.connect(lambda _: self.open_selected_case())
        layout.addWidget(self.case_table, 1)
        buttons = QHBoxLayout()
        open_button = QPushButton("開啟案件")
        open_button.clicked.connect(self.open_selected_case)
        archive_button = QPushButton("封存")
        archive_button.setProperty("variant", "secondary")
        archive_button.clicked.connect(self.archive_selected_case)
        delete_button = QPushButton("移至回收區")
        delete_button.setProperty("variant", "danger")
        delete_button.clicked.connect(self.delete_selected_case)
        buttons.addWidget(open_button)
        buttons.addWidget(archive_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _build_new_case(self) -> QWidget:
        page, layout = self._page(
            "建立案件",
            "建議使用完整 Wizard；也可在下方快速建立最小案件。",
        )
        wizard_card = QFrame(objectName="heroCard")
        wizard_layout = QHBoxLayout(wizard_card)
        wizard_text = QVBoxLayout()
        wizard_text.addWidget(QLabel("五步驟案件 Wizard", objectName="sectionTitle"))
        wizard_text.addWidget(
            QLabel(
                "基本資料 → 案件說明 → 證據 → 線索確認 → 調查目標",
                objectName="muted",
            )
        )
        wizard_button = QPushButton("開啟 Wizard")
        wizard_button.clicked.connect(self.open_case_wizard)
        wizard_layout.addLayout(wizard_text, 1)
        wizard_layout.addWidget(wizard_button)
        layout.addWidget(wizard_card)
        quick = QFrame(objectName="sectionCard")
        quick_layout = QFormLayout(quick)
        self.new_title = QLineEdit()
        self.new_description = QPlainTextEdit()
        self.new_description.setMaximumHeight(90)
        self.new_chain = QComboBox()
        self.new_chain.addItems(["未指定", "TRON", "Ethereum", "Bitcoin"])
        self.new_address = QLineEdit()
        self.new_tx = QLineEdit()
        quick_layout.addRow("案件標題 *", self.new_title)
        quick_layout.addRow("描述", self.new_description)
        quick_layout.addRow("主要鏈", self.new_chain)
        quick_layout.addRow("已確認地址", self.new_address)
        quick_layout.addRow("已確認 Tx Hash", self.new_tx)
        layout.addWidget(quick)
        create = QPushButton("快速建立並開啟")
        create.clicked.connect(self.create_case)
        layout.addWidget(create, alignment=Qt.AlignLeft)
        layout.addStretch()
        return page

    def _build_settings(self) -> QWidget:
        page, layout = self._page(
            "設定",
            "設定只保存非秘密選項；Credentials 由環境變數或 Credential Adapter 管理。",
        )
        cards = QGridLayout()
        general = QFrame(objectName="sectionCard")
        general_form = QFormLayout(general)
        general_form.addRow(QLabel("一般設定", objectName="sectionTitle"))
        self.setting_theme = QComboBox()
        self.setting_theme.addItems(["light"])
        self.setting_language = QComboBox()
        self.setting_language.addItems(["zh-TW", "en"])
        self.setting_case_root = QLineEdit(self.settings.case_root)
        general_form.addRow("Theme", self.setting_theme)
        general_form.addRow("Language", self.setting_language)
        general_form.addRow("Case Root", self.setting_case_root)
        cards.addWidget(general, 0, 0)
        provider = QFrame(objectName="sectionCard")
        provider_form = QFormLayout(provider)
        provider_form.addRow(QLabel("Provider", objectName="sectionTitle"))
        self.setting_max_pages = QLineEdit(str(self.settings.max_pages))
        self.setting_max_records = QLineEdit(str(self.settings.max_records))
        provider_form.addRow("Credential", QLabel("•••• 由環境管理"))
        provider_form.addRow("max_pages", self.setting_max_pages)
        provider_form.addRow("max_records", self.setting_max_records)
        cards.addWidget(provider, 0, 1)
        ai = QFrame(objectName="sectionCard")
        ai_form = QFormLayout(ai)
        ai_form.addRow(QLabel("AI 敘事", objectName="sectionTitle"))
        self.setting_ai = QCheckBox("啟用 AI")
        self.setting_ai.setChecked(False)
        self.credential_status = QLabel("Credential：••••（不顯示）")
        ai_form.addRow("狀態", self.setting_ai)
        ai_form.addRow("Prompt Mode", QLabel(self.settings.prompt_mode))
        ai_form.addRow("Privacy Mode", QLabel(self.settings.privacy_mode))
        ai_form.addRow(self.credential_status)
        cards.addWidget(ai, 1, 0, 1, 2)
        layout.addLayout(cards)
        save = QPushButton("儲存安全設定")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save, alignment=Qt.AlignLeft)
        layout.addStretch()
        return page

    def _build_workspace(self) -> QWidget:
        page, layout = self._page("案件工作區")
        header = QFrame(objectName="sectionCard")
        header_layout = QHBoxLayout(header)
        header_text = QVBoxLayout()
        header_text.addWidget(
            QLabel("CASE WORKSPACE · ON-CHAIN INVESTIGATION", objectName="eyebrow")
        )
        self.workspace_header = QLabel("尚未開啟案件", objectName="sectionTitle")
        self.workspace_header.setWordWrap(True)
        self.workspace_intelligence = QLabel("EVIDENCE VERIFIED", objectName="muted")
        self.workspace_intelligence.setWordWrap(True)
        self.workflow_stage = QLabel("下一步：確認案件線索", objectName="muted")
        header_text.addWidget(self.workspace_header)
        header_text.addWidget(self.workspace_intelligence)
        header_text.addWidget(self.workflow_stage)
        self.workspace_badge = StatusBadge()
        self.workspace_badge.set_status("unavailable")
        self.workspace_badge.setAlignment(Qt.AlignCenter)
        self.workspace_badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        next_button = QPushButton("前往下一步")
        next_button.clicked.connect(self.next_workflow_action)
        header_layout.addLayout(header_text, 1)
        header_layout.addWidget(self.workspace_badge, alignment=Qt.AlignVCenter)
        header_layout.addWidget(next_button)
        layout.addWidget(header)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setTabPosition(QTabWidget.North)
        self.workspace_tabs.tabBar().setUsesScrollButtons(True)
        self.workspace_tabs.tabBar().setElideMode(Qt.ElideRight)
        self.workspace_tabs.currentChanged.connect(self._workflow_changed)
        self.tab_views: dict[str, QTextBrowser] = {}
        for tab_name in WORKSPACE_TABS:
            container = QWidget()
            tab_layout = QVBoxLayout(container)
            tab_layout.setContentsMargins(14, 14, 14, 14)
            if tab_name == "Execution":
                self.execution_progress = QProgressBar(objectName="execution_progress")
                self.execution_progress.setRange(0, 0)
                self.execution_progress.setVisible(False)
                tab_layout.addWidget(self.execution_progress)
            view = QTextBrowser()
            view.setOpenExternalLinks(False)
            view.setObjectName(f"view_{len(self.tab_views)}")
            self.tab_views[tab_name] = view
            tab_layout.addWidget(view, 1)
            if tab_name == "Graph":
                self.graph_view = SafeGraphView()
                self.graph_view.setMinimumHeight(360)
                self.graph_view.hide()
                tab_layout.addWidget(self.graph_view, 2)
            self._add_tab_actions(tab_name, tab_layout)
            self.workspace_tabs.addTab(container, tab_name)
        layout.addWidget(self.workspace_tabs, 1)
        return page

    def _add_tab_actions(self, name: str, layout: QVBoxLayout) -> None:
        actions = QHBoxLayout()
        if name == "Evidence":
            button = QPushButton("匯入證據")
            button.clicked.connect(self.import_evidence)
            actions.addWidget(button)
        elif name == "調查目標":
            self.goal_type = QComboBox()
            self.goal_type.addItems(
                [
                    "identify_main_sources",
                    "identify_main_destinations",
                    "detect_batch_distribution",
                    "detect_funding_transition",
                    "identify_service_candidates",
                    "generate_investigation_report",
                ]
            )
            self.goal_type.setItemText(0, "找出主要資金來源")
            self.goal_type.setItemText(1, "找出主要資金去向")
            self.goal_type.setItemText(2, "辨識批次出款模式")
            self.goal_type.setItemText(3, "辨識供款來源變化")
            self.goal_type.setItemText(4, "辨識可能服務商")
            self.goal_type.setItemText(5, "產生案件調查報告")
            for index, code in enumerate(
                [
                    "identify_main_sources",
                    "identify_main_destinations",
                    "detect_batch_distribution",
                    "detect_funding_transition",
                    "identify_service_candidates",
                    "generate_investigation_report",
                ]
            ):
                self.goal_type.setItemData(index, code)
            self.goal_target = QLineEdit(placeholderText="目標地址（選填）")
            button = QPushButton("新增調查目標")
            button.clicked.connect(self.add_goal)
            actions.addWidget(self.goal_type)
            actions.addWidget(self.goal_target, 1)
            actions.addWidget(button)
        elif name == "調查計畫":
            create = QPushButton("產生調查計畫")
            create.clicked.connect(self.generate_plan)
            confirm = QPushButton("確認計畫")
            confirm.setProperty("variant", "secondary")
            confirm.clicked.connect(self.confirm_plan)
            actions.addWidget(create)
            actions.addWidget(confirm)
        elif name == "Execution":
            start = QPushButton("開始執行")
            start.clicked.connect(self.start_execution)
            cancel = QPushButton("取消")
            cancel.setProperty("variant", "danger")
            cancel.clicked.connect(self.cancel_execution)
            resume = QPushButton("繼續執行")
            resume.setProperty("variant", "secondary")
            resume.clicked.connect(self.resume_execution)
            actions.addWidget(start)
            actions.addWidget(resume)
            actions.addWidget(cancel)
        elif name == "Report":
            self.report_ai_enrichment = QCheckBox("AI 專業綜合")
            self.report_ai_enrichment.setChecked(False)
            self.report_ai_enrichment.setToolTip(
                "預設停用；僅採用已驗證的 AI Narrative，否則保留完整 deterministic report。"
            )
            generate = QPushButton("產生新版報告")
            generate.clicked.connect(self.generate_report)
            package = QPushButton("匯出案件套件")
            package.setProperty("variant", "secondary")
            package.clicked.connect(self.export_case_package)
            actions.addWidget(self.report_ai_enrichment)
            actions.addWidget(generate)
            actions.addWidget(package)
        actions.addStretch()
        if actions.count() > 1:
            layout.addLayout(actions)

    def _navigate(self, index: int) -> None:
        if index >= 0:
            self.pages.setCurrentIndex(index)
            self.state.current_page = self.navigation.item(index).text()

    def _workflow_changed(self, index: int) -> None:
        if index >= 0:
            self.workflow_stage.setText(
                f"目前階段：{self.workspace_tabs.tabText(index)}"
            )

    def _system_readiness(self) -> list[tuple[str, str, str, str]]:
        from crypto_investigator.reports.pdf_exporter import pdf_font_status

        pdf = pdf_font_status()
        return [
            (
                "TronGrid",
                "configured" if os.getenv("TRONGRID_API_KEY") else "not_configured",
                "已設定" if os.getenv("TRONGRID_API_KEY") else "未設定",
                "TRON transaction provider",
            ),
            (
                "Etherscan",
                "configured" if os.getenv("ETHERSCAN_API_KEY") else "not_configured",
                "已設定" if os.getenv("ETHERSCAN_API_KEY") else "未設定",
                "Blockscout fallback available",
            ),
            ("Blockscout", "supported", "程式支援", "尚未驗證連線 · Ethereum public fallback"),
            ("Blockstream", "supported", "公開服務", "Bitcoin provider · 未測試連線"),
            ("Local Pipeline", "available", "正常", "CSV／Excel offline execution"),
            ("Case Workspace", "available", "正常", "Local-first case storage"),
            ("Cache", "available", "正常", "Local execution cache"),
            ("Audit Chain", "verified", "已驗證", "Hash-chain verified"),
            ("AI", "disabled", "已停用", "Deterministic fallback enabled"),
            (
                "PDF CJK Font",
                "available" if pdf.get("available") else "unavailable",
                "可用" if pdf.get("available") else "不可用",
                (
                    f"{pdf.get('font_name')} · {pdf.get('source')}"
                    if pdf.get("available")
                    else "PDF export may be partial"
                ),
            ),
        ]

    def refresh_cases(self) -> None:
        if hasattr(self, "home_recent_stack"):
            self.home_recent_stack.setCurrentIndex(0)
        try:
            records = self.case_service.list_cases(
                self.case_search.text() if hasattr(self, "case_search") else "",
                self.show_archived.isChecked() if hasattr(self, "show_archived") else False,
            )
        except Exception:
            if hasattr(self, "home_recent_stack"):
                self.home_recent_stack.setCurrentIndex(2)
            return
        self._case_ids = [item.case_id for item in records]
        if hasattr(self, "case_model"):
            self.case_model.replace(
                [
                    [
                        item.case_id,
                        item.title,
                        _STATUS_ZH.get(item.status.value, item.status.value),
                        item.metadata.get("chain") or "未指定",
                        len(item.evidence),
                        _STATUS_ZH.get(
                            item.last_execution_status or "not_started",
                            item.last_execution_status or "尚未開始",
                        ),
                        item.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                    ]
                    for item in records
                ]
            )
        active = [item for item in records if item.status.value == "open"]
        running = [item for item in records if item.active_execution_id]
        partial = [item for item in records if item.last_execution_status == "partial"]
        review = [
            item
            for item in records
            if item.metadata.get("review_status", "not_reviewed") == "not_reviewed"
            and item.last_execution_status in {"completed", "partial"}
        ]
        if hasattr(self, "home_metric_cards"):
            for key, value in (
                ("cases", len(active)),
                ("running", len(running)),
                ("partial", len(partial)),
                ("review", len(review)),
            ):
                self.home_metric_cards[key].set_value(value)
            self.home_recent.clear()
            for item in sorted(records, key=lambda case: case.updated_at, reverse=True)[:6]:
                chain = str(item.metadata.get("chain") or "UNKNOWN").upper()
                assets = ", ".join(
                    str(asset).upper() for asset in item.metadata.get("assets", [])
                ) or "未指定資產"
                seeds = len(item.metadata.get("known_addresses", []))
                status = _STATUS_ZH.get(
                    item.last_execution_status or "not_started", "尚未開始"
                )
                completeness = item.execution_summary.get("completeness", "尚無資料")
                next_action = self._next_action(item).replace("下一步：", "")
                self.home_recent.addItem(
                    f"{item.title}\n"
                    f"{item.case_id}  ·  {chain}  ·  {assets}\n"
                    f"Seed {seeds}  ·  Evidence {len(item.evidence)}  ·  {status}  ·  "
                    f"Completeness {completeness}\n"
                    f"下一步：{next_action}  ·  "
                    f"{item.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
                )
                self.home_recent.item(self.home_recent.count() - 1).setData(
                    Qt.UserRole, item.case_id
                )
                list_item = self.home_recent.item(self.home_recent.count() - 1)
                widget = InvestigationQueueItem(
                    title=item.title,
                    case_id=item.case_id,
                    chain=chain,
                    assets=list(item.metadata.get("assets", [])) or ["UNSPECIFIED"],
                    seed_count=seeds,
                    evidence_count=len(item.evidence),
                    status=status,
                    completeness=str(completeness),
                    updated_at=item.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                    next_action=next_action,
                    open_case=lambda checked=False, case_id=item.case_id: self.open_case(case_id),
                )
                list_item.setSizeHint(widget.sizeHint())
                self.home_recent.setItemWidget(list_item, widget)
            self.home_recent_stack.setCurrentIndex(3 if records else 1)
        if hasattr(self, "home_counts"):
            self.home_counts.setText(
                f"案件：{len(records)} 執行中：{len(running)} 部分完成：{len(partial)}"
            )

    def _open_recent_case(self, item) -> None:
        case_id = item.data(Qt.UserRole)
        if case_id:
            self.open_case(str(case_id))

    def selected_case_id(self) -> str | None:
        index = self.case_table.currentIndex()
        if not index.isValid():
            return None
        return str(self.case_model.rows[index.row()][0])

    def open_case_wizard(self) -> None:
        wizard = CaseWizard(self)
        if wizard.exec() != QDialog.Accepted:
            return
        payload = wizard.payload()
        try:
            case = self.case_service.create_case(
                payload["title"], payload["description"]
            )
            case = self.repository.save(
                case.model_copy(update={"metadata": payload["metadata"]})
            )
            for source in payload["attachments"]:
                self.case_service.import_evidence(case.case_id, source)
            targets = payload["metadata"].get("known_addresses", [])
            for goal in payload["goals"]:
                self.case_service.add_goal(
                    case.case_id, goal, human_label(goal), targets
                )
            self.refresh_cases()
            self.open_case(case.case_id)
        except Exception as exc:
            self.show_safe_error("建立案件失敗", exc)

    def create_case(self) -> None:
        try:
            metadata = {
                "chain": (
                    None
                    if self.new_chain.currentIndex() == 0
                    else self.new_chain.currentText().lower()
                ),
                "known_addresses": (
                    [self.new_address.text().strip()]
                    if self.new_address.text().strip()
                    else []
                ),
                "known_transactions": (
                    [self.new_tx.text().strip()]
                    if self.new_tx.text().strip()
                    else []
                ),
            }
            case = self.case_service.create_case(
                self.new_title.text(), self.new_description.toPlainText()
            )
            self.repository.save(case.model_copy(update={"metadata": metadata}))
            self.new_title.clear()
            self.new_description.clear()
            self.refresh_cases()
            self.open_case(case.case_id)
        except Exception as exc:
            self.show_safe_error("建立案件失敗", exc)

    def open_selected_case(self) -> None:
        case_id = self.selected_case_id()
        if case_id:
            self.open_case(case_id)

    def open_case(self, case_id: str) -> None:
        case = self.repository.load(case_id)
        self.state.select_case(case_id)
        self.case_status.setText(f"{case.title}\n{case.case_id}")
        self.workspace_header.setText(case.title)
        try:
            result = self.case_service.result(case.case_id)
        except Exception:
            result = None
        chain = str(case.metadata.get("chain") or "UNKNOWN").upper()
        assets = ", ".join(
            str(item).upper() for item in case.metadata.get("assets", [])
        ) or "UNSPECIFIED"
        transaction_count = len(result.known_transactions) if result else 0
        completeness = result.completeness if result else "unavailable"
        self.workspace_intelligence.setText(
            f"{case.case_id}  ·  CHAIN {chain}  ·  ASSET {assets}  ·  "
            f"SEEDS {len(case.metadata.get('known_addresses', []))}  ·  "
            f"EVIDENCE {len(case.evidence)}  ·  TX {transaction_count}  ·  "
            f"COMPLETENESS {completeness}  ·  "
            f"REVIEW {human_label(case.metadata.get('review_status', 'not_reviewed'))}  ·  "
            f"UPDATED {case.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
        )
        status = case.last_execution_status or case.status.value
        self.workspace_badge.set_status(
            status,
            _STATUS_ZH.get(status, human_label(status)),
        )
        self.workflow_stage.setText(self._next_action(case))
        self._load_case_views(case)
        self.pages.setCurrentWidget(self.workspace_page)
        self.case_opened.emit(case_id)

    def _next_action(self, case) -> str:
        if not case.goals:
            return "下一步：確認線索並加入調查目標"
        if not case.plans:
            return "下一步：產生調查計畫"
        latest_plan = case.plans[-1]
        if not latest_plan.get("confirmed_at"):
            return "下一步：檢查並確認調查計畫"
        if not case.executions:
            return "下一步：開始執行調查計畫"
        if case.last_execution_status in {"completed", "partial"}:
            return "下一步：覆核結果並產生報告"
        return f"目前狀態：{_STATUS_ZH.get(case.last_execution_status or '', '等待更新')}"

    def _load_case_views(self, case) -> None:
        try:
            result = self.case_service.result(case.case_id)
        except Exception:
            result = None
        renderers = {
            "案情": self._render_overview(case, result),
            "線索": self._render_clues(case),
            "Evidence": self._render_evidence(case),
            "調查目標": self._render_goals(case),
            "調查計畫": self._render_plan(case),
            "Execution": self._render_execution(case),
            "Result": self._render_result(result),
            "Investigation": self._render_investigation(result),
            "Counterparty": self._render_counterparties(result),
            "Graph": self._render_graph(result),
            "Narrative": self._render_narrative(result),
            "Report": self._render_reports(case),
            "Review": self._render_review(case),
            "Audit": self._render_audit(case),
        }
        for name, content in renderers.items():
            self.tab_views[name].setHtml(content)
        self.graph_view.hide()
        if result:
            graph = next(
                (
                    item
                    for item in result.evidence_index
                    if item.evidence_type in {"graph_html", "trace_graph"}
                    and item.relative_path.endswith("flow.html")
                ),
                None,
            )
            if graph:
                if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                    self.tab_views["Graph"].append(
                        f"<p>Headless validation: {_safe(Path(graph.relative_path).name)}</p>"
                    )
                else:
                    try:
                        workspace = self.repository.workspace(case.case_id)
                        self.graph_view.load_graph(
                            workspace.resolve_relative(graph.relative_path),
                            workspace.path,
                        )
                        self.graph_view.show()
                    except ValueError:
                        pass

    def _html(self, title: str, body: str) -> str:
        return (
            "<style>"
            "body{font-family:'Segoe UI','Microsoft JhengHei UI';color:#d9e4f0;"
            "background:#0d1726;margin:8px;line-height:1.55}"
            "h2{color:#f1f5f9;margin:0 0 4px}h3{color:#b8c8db;margin:18px 0 8px}"
            ".muted{color:#8fa1b7}.card{border:1px solid #2b3b52;border-radius:8px;"
            "padding:13px;margin:8px 0;background:#111b2b}.grid{display:flex;gap:10px;flex-wrap:wrap}"
            ".mono{font-family:'Cascadia Mono','Consolas','Courier New';color:#b9f5ec}"
            ".fact{border-left:3px solid #2dd4bf}.observation{border-left:3px solid #60a5fa}"
            ".candidate{border-left:3px solid #a78bfa}.limitation{border-left:3px solid #f59e0b}"
            ".format{border:1px solid #3b5872;border-radius:7px;padding:2px 6px;color:#bfe8ff}"
            "table{border-collapse:collapse;width:100%}th,td{padding:8px;"
            "border-bottom:1px solid #26364d;text-align:left}th{color:#93a8c0;background:#142033}"
            ".empty{padding:42px;text-align:center;color:#8fa1b7;background:#101b2b;"
            "border:1px dashed #334a65;border-radius:8px}</style>"
            f"<h2>{_safe(title)}</h2>{body}"
        )

    def _render_overview(self, case, result) -> str:
        chain = case.metadata.get("chain") or "未指定"
        facts = len(result.confirmed_facts) if result else 0
        observations = len(result.deterministic_observations) if result else 0
        candidates = len(result.candidate_interpretations) if result else 0
        body = (
            f"<p class='muted'>{_safe(case.description or '尚未填寫案件背景')}</p>"
            "<div class='grid'>"
            f"<div class='card'><b>主要鏈</b><br>{_safe(chain)}</div>"
            f"<div class='card'><b>證據</b><br>{len(case.evidence)} 件</div>"
            f"<div class='card'><b>調查目標</b><br>{len(case.goals)} 項</div>"
            f"<div class='card'><b>執行狀態</b><br>{_badge(case.last_execution_status or 'not_started')}</div>"
            "</div><h3>目前調查內容</h3>"
            f"<div class='card'>已確認事實：{facts}　確定性觀察：{observations}　"
            f"候選解釋：{candidates}</div><h3>下一步</h3>"
            f"<div class='card'>{_safe(self._next_action(case))}</div>"
        )
        return self._html("案件摘要", body)

    def _render_clues(self, case) -> str:
        addresses = case.metadata.get("known_addresses", [])
        transactions = case.metadata.get("known_transactions", [])
        clues = "".join(
            f"<tr><td>地址</td><td class='mono' title='{_safe(item)}'>"
            f"{_safe(abbreviate_chain_value(item))}</td><td>{_badge('confirmed')}</td></tr>"
            for item in addresses
        ) + "".join(
            f"<tr><td>交易</td><td class='mono' title='{_safe(item)}'>"
            f"{_safe(abbreviate_chain_value(item, 10, 8))}</td><td>{_badge('confirmed')}</td></tr>"
            for item in transactions
        )
        body = "<h3>已確認線索</h3>"
        body += (
            f"<table><tr><th>類型</th><th>內容</th><th>狀態</th></tr>{clues}</table>"
            if clues
            else "<div class='empty'>尚未加入已確認線索。請先確認資料來源再加入案件。</div>"
        )
        return self._html("線索", body)

    def _render_evidence(self, case) -> str:
        evidence = "".join(
            f"<tr><td>{_safe(item.original_filename)}</td><td>{_safe(item.file_type)}</td>"
            f"<td>{item.size:,}</td><td class='mono' title='{_safe(item.sha256)}'>"
            f"{_safe(abbreviate_chain_value(item.sha256, 12, 8))}</td>"
            f"<td>{_badge('verified' if self.case_service.verify_evidence(case.case_id, item.evidence_id) else 'mismatch')}</td></tr>"
            for item in case.evidence
        )
        body = "<h3>DIGITAL EVIDENCE · SHA-256 INTEGRITY</h3>"
        body += (
            f"<table><tr><th>檔案</th><th>類型</th><th>大小</th><th>SHA-256</th><th>Integrity</th></tr>{evidence}</table>"
            if evidence
            else "<div class='empty'>尚未匯入證據。匯入後會保留原始檔並計算 SHA-256。</div>"
        )
        return self._html("Evidence", body)

    def _render_goals(self, case) -> str:
        rows = "".join(
            f"<tr><td>{_safe(human_label(item.get('goal_type')))}</td>"
            f"<td>{_safe(item.get('description') or '—')}</td>"
            f"<td>{_safe(human_label(item.get('priority', 'normal')))}</td>"
            f"<td>{_badge(item.get('status', 'pending'))}</td></tr>"
            for item in case.goals
        )
        body = (
            f"<table><tr><th>調查目標</th><th>說明</th><th>優先級</th><th>狀態</th></tr>{rows}</table>"
            if rows
            else "<div class='empty'>尚未設定調查目標。先選擇本案要回答的問題。</div>"
        )
        return self._html("調查目標", body)

    def _render_plan(self, case) -> str:
        if not case.plans:
            return self._html(
                "調查計畫",
                "<div class='empty'>尚未產生 Plan。系統會依已確認 Goals 建立可覆核的步驟。</div>",
            )
        plan = case.plans[-1]
        cards = []
        for step in sorted(plan.get("steps", []), key=lambda item: item.get("order", 0)):
            limits = step.get("parameters", {})
            advanced = "　".join(
                f"{_safe(key)}={_safe(value)}"
                for key, value in limits.items()
                if key in {"max_pages", "max_records", "depth"}
            ) or "使用安全預設值"
            cards.append(
                "<div class='card'>"
                f"<b>{step.get('order', '?')}. {_safe(human_label(step.get('step_type')))}</b> "
                f"{_badge(step.get('status', 'pending'))}"
                f"<p>{_safe(step.get('reason', ''))}</p>"
                f"<p class='muted'>Provider：{_safe(step.get('provider') or '自動選擇')}　"
                f"限制：{advanced}</p></div>"
            )
        enabled = sum(bool(item.get("enabled", True)) for item in plan.get("steps", []))
        warning_count = len(plan.get("warnings", []))
        body = (
            f"<div class='card'><b>Plan v{plan.get('plan_version', 1)}</b>　"
            f"啟用 {enabled} 個步驟　Warning {warning_count}　"
            f"{_badge('confirmed' if plan.get('confirmed_at') else 'pending')}</div>"
            + "".join(cards)
        )
        return self._html("調查計畫", body)

    def _render_execution(self, case) -> str:
        status = case.last_execution_status or "not_started"
        summary = case.execution_summary
        steps = summary.get("steps", []) if isinstance(summary, dict) else []
        timeline = "".join(
            "<div class='card'>"
            f"<b>{_safe(human_label(item.get('step_type') or item.get('step_id')))}</b> "
            f"{_badge(item.get('status', 'pending'))}"
            f"<p class='muted'>處理筆數：{_safe(item.get('records_processed', 0))}　"
            f"Warning：{_safe(len(item.get('warnings', [])))}</p></div>"
            for item in steps
        )
        total = summary.get("total_records") if isinstance(summary, dict) else None
        current = summary.get("records_processed", 0) if isinstance(summary, dict) else 0
        progress = (
            f"<p><b>{current:,} / {total:,}</b></p>"
            if isinstance(total, int) and total > 0
            else f"<p><b>目前已處理 {current:,} 筆</b>　<span class='muted'>總量未知</span></p>"
        )
        body = (
            f"<div class='card'><b>執行狀態</b>　{_badge(status)}"
            f"{progress}<p class='muted'>Execution：{_safe(case.latest_execution_id or '尚未建立')}</p></div>"
            + (
                timeline
                or "<div class='empty'>尚無執行時間軸。確認 Plan 後即可開始。</div>"
            )
        )
        return self._html("執行進度", body)

    def _render_result(self, result) -> str:
        if result is None:
            return self._html(
                "結果總覽",
                "<div class='empty'>尚無分析結果。完成 Execution 後會在此顯示重點。</div>",
            )
        trace_summaries = [
            item["trace_summary"]
            for item in result.address_results
            if item.get("trace_summary")
        ]
        trace_cards = "".join(
            "<div class='card observation'>"
            f"<b>多層追蹤：{_safe(item.get('status', 'unknown'))}</b>"
            f"<p>節點 {int(item.get('node_count', 0)):,}｜"
            f"交易邊 {int(item.get('edge_count', 0)):,}｜"
            f"FIFO 配對 {int(item.get('allocation_count', 0)):,}</p>"
            f"<p class='muted'>深度上限：{_safe(item.get('max_depth'))}｜"
            f"下車點候選：{int(item.get('off_ramp_candidate_count', 0)):,}｜"
            f"資產：{_safe(', '.join(item.get('assets', [])) or '未分類')}</p>"
            "</div>"
            for item in trace_summaries
        )
        asset_cards = "".join(
            f"<div class='card'><b>{_safe(asset)}</b><br>"
            "ASSET-SEGREGATED · 不與其他資產加總</div>"
            for asset in result.assets
        ) or "<div class='card'>尚無資產統計</div>"
        observations = "".join(
            f"<div class='card'><b>{_safe(item.factual_statement)}</b>"
            f"<p class='muted'>Confidence：{_safe(item.confidence)}　"
            f"Evidence：{len(item.evidence_refs)}</p></div>"
            for item in result.deterministic_observations[:10]
        ) or "<div class='empty'>尚無確定性觀察。</div>"
        body = (
            "<div class='grid'>"
            f"<div class='card'><b>已分析地址</b><br>{len(result.known_addresses)}</div>"
            f"<div class='card'><b>已分析交易</b><br>{len(result.known_transactions)}</div>"
            f"<div class='card'><b>完整度</b><br>{_badge(result.completeness)}</div>"
            f"<div class='card'><b>Counterparties</b><br>{sum(len(item.get('counterparties', [])) for item in result.address_results)}</div>"
            f"<div class='card'><b>Operation Stages</b><br>{sum(len(item.get('operation_stages', [])) for item in result.address_results)}</div>"
            f"<div class='card'><b>Evidence</b><br>{len(result.evidence_index)}</div>"
            f"<div class='card limitation'><b>Partial Coverage</b><br>{len(result.unresolved_questions)}</div>"
            "</div><h3>資產摘要</h3><div class='grid'>"
            f"{asset_cards}</div>"
            + ("<h3>多層資金追蹤</h3>" + trace_cards if trace_cards else "")
            + f"<h3>重要觀察</h3>{observations}"
        )
        return self._html("結果總覽", body)

    def _render_investigation(self, result) -> str:
        if result is None:
            return self._html(
                "Investigation",
                "<div class='empty'>尚無 Investigation 結果。</div>",
            )
        facts = "".join(
            f"<div class='card fact'>{_badge('confirmed')} <b>CONFIRMED FACT · 已確認事實</b>"
            f"<p>{_safe(item.statement)}</p><p class='muted'>VERIFIED · Evidence："
            f"{_safe(', '.join(item.evidence_ids) or '未提供')}</p></div>"
            for item in result.confirmed_facts
        )
        observations = "".join(
            f"<div class='card observation'>{_badge('observation')} <b>OBSERVATION · 規則式觀察</b>"
            f"<p>{_safe(item.factual_statement)}</p>"
            f"<p class='muted'>Deterministic rule · Confidence：{_safe(item.confidence)}　"
            f"Limitation：{_safe('; '.join(item.limitations) or '無')}</p></div>"
            for item in result.deterministic_observations
        )
        candidates = "".join(
            f"<div class='card candidate'>{_badge('candidate')} <b>CANDIDATE · 候選解釋</b>"
            f"<p><b>{_safe(item.title)}</b></p>"
            f"<p>{_safe(item.statement)}</p><p class='muted'>Confidence：{_safe(item.confidence)}　"
            f"Limitation：{_safe('; '.join(item.limitations))}</p></div>"
            for item in result.candidate_interpretations
        )
        body = (
            "<h3>已確認事實</h3>"
            + (facts or "<div class='empty'>尚無已確認事實。</div>")
            + "<h3>確定性觀察</h3>"
            + (observations or "<div class='empty'>尚無觀察。</div>")
            + "<h3>候選解釋</h3>"
            + (candidates or "<div class='empty'>尚無候選解釋。</div>")
        )
        return self._html("Investigation", body)

    def _render_counterparties(self, result) -> str:
        rows = []
        if result:
            for address_result in result.address_results:
                for item in address_result.get("counterparties", []):
                    rows.append(
                        f"<tr><td>{_safe(item.get('address'))}</td>"
                        f"<td>{_safe(item.get('label') or '未標記')}</td>"
                        f"<td>{_safe(item.get('direction') or '—')}</td>"
                        f"<td>{_safe(item.get('transaction_count', 0))}</td></tr>"
                    )
        body = (
            "<p class='muted'>可依地址、資產、方向、Label 與 Candidate Role 篩選。</p>"
            f"<table><tr><th>地址</th><th>Label</th><th>方向</th><th>交易數</th></tr>{''.join(rows)}</table>"
            if rows
            else "<div class='empty'>尚無交易對手資料。完成地址分析後可在此檢視。</div>"
        )
        return self._html("交易對手", body)

    def _render_graph(self, result) -> str:
        graph_entries = (
            [
                item
                for item in result.evidence_index
                if item.evidence_type
                in {"graph_html", "graph_json", "graphml", "trace_graph"}
            ]
            if result
            else []
        )
        rows = "".join(
            f"<tr><td>{_safe(item.evidence_type)}</td><td>{_safe(Path(item.relative_path).name)}</td>"
            f"<td>{_safe(item.integrity_status)}</td></tr>"
            for item in graph_entries
        )
        body = (
            "<div class='card'>GRAPH ARTIFACT · LOCAL WORKSPACE ONLY · NO EXTERNAL URL</div>"
            f"<table><tr><th>Graph Artifact</th><th>來源</th><th>Integrity</th></tr>{rows}</table>"
            if rows
            else "<div class='empty'>尚無 Graph。UI 不會重新產生 Graph；完成對應步驟後載入既有 flow.html。</div>"
        )
        return self._html("Graph", body)

    def _render_narrative(self, result) -> str:
        body = (
            "<div class='grid'>"
            "<div class='card'><b>敘事來源</b><br>Deterministic fallback</div>"
            "<div class='card'><b>AI</b><br>預設停用</div>"
            "<div class='card'><b>Validation</b><br>等待 narrative artifact</div>"
            "<div class='card'><b>人工覆核</b><br>尚未覆核</div></div>"
            "<div class='card limitation'>"
            "<b>目前使用 deterministic fallback。</b>"
            "<p>內容只整理已保存的事實與觀察，不代表 AI 模型已成功執行。</p></div>"
        )
        return self._html("Narrative", body)

    def _render_reports(self, case) -> str:
        reports = self.case_service.reports(case.case_id)
        cards = []
        for item in reversed(reports):
            formats = []
            for name in item.get("files", {}).keys():
                suffix = Path(name).suffix.lower().lstrip(".")
                if suffix in {"md", "html", "docx", "pdf"} and suffix not in formats:
                    formats.append(suffix)
            format_badges = " ".join(
                f"<span class='format'>{_safe(name.upper())}</span>"
                for name in formats
            ) or "<span class='muted'>尚無主要報告格式</span>"
            cards.append(
                "<div class='card'>"
                f"<b>Report v{_safe(item.get('report_version'))}</b>　"
                f"{_badge(item.get('status', 'unavailable'))}"
                f" {_badge(item.get('report_type', 'deterministic'))}"
                f"<p class='muted'>產生時間：{_safe(item.get('created_at'))}<br>"
                f"格式：{format_badges}<br>"
                f"AI validation：{_safe(item.get('validation_status', 'not_requested'))}"
                f"<br>AI：{_safe('enabled' if item.get('ai_enrichment_enabled') else 'disabled')}"
                f"<br>Provider／Model：{_safe(item.get('ai_provider') or 'unavailable')}／"
                f"{_safe(item.get('ai_model') or 'unavailable')}"
                f"<br>Tokens：input {_safe(item.get('ai_input_tokens', 0))} ／ "
                f"limit {_safe(item.get('ai_output_token_limit', 0))} ／ "
                f"actual {_safe(item.get('ai_output_tokens', 0))}"
                f"<br>Finish reason：{_safe(item.get('ai_finish_reason') or 'unavailable')}"
                + (
                    f"<br>Fallback：{_safe(item.get('fallback_reason'))}"
                    if item.get("fallback_reason")
                    else ""
                )
                + "</p></div>"
            )
        return self._html(
            "案件報告",
            "".join(cards)
            or "<div class='empty'>尚無報告版本。覆核結果後再產生第一版報告。</div>",
        )

    def _render_audit(self, case) -> str:
        entries = self.case_service.audit_entries(case.case_id)
        timeline = "".join(
            "<div class='card'>"
            f"<b>{_safe(item.timestamp.astimezone().strftime('%Y-%m-%d %H:%M:%S'))}</b>　"
            f"{_safe(human_label(item.action))}"
            f"<p>{_safe(item.description)}</p>"
            f"<p class='muted'>{_safe(item.object_type)} · {_safe(item.object_id)} · "
            f"Actor {_safe(item.actor)}</p>"
            f"<p class='mono'>PREV {_safe(abbreviate_chain_value(item.previous_hash or 'GENESIS', 8, 6))} "
            f"→ HASH {_safe(abbreviate_chain_value(item.entry_hash, 8, 6))}</p></div>"
            for item in reversed(entries)
        )
        integrity = "confirmed" if self.case_service.audit_valid(case.case_id) else "failed"
        label = "CHAIN VERIFIED" if integrity == "confirmed" else "INTEGRITY WARNING"
        body = f"<p>Hash-chain integrity：{_badge(integrity)} {label}</p>{timeline}"
        return self._html("稽核時間軸", body)

    def _render_review(self, case) -> str:
        status = case.metadata.get("review_status", "not_reviewed")
        return self._html(
            "Review",
            "<div class='card'>"
            f"<b>人工覆核</b>　{_badge('confirmed' if status == 'reviewed' else 'pending')}"
            f"<p class='muted'>狀態：{_safe(_STATUS_ZH.get(status, human_label(status)))}。"
            "UI 不會略過 Plan confirmation 或自動確認調查結論。</p></div>",
        )

    def archive_selected_case(self) -> None:
        case_id = self.selected_case_id()
        if case_id:
            self.case_service.archive_case(case_id)
            self.refresh_cases()

    def delete_selected_case(self) -> None:
        case_id = self.selected_case_id()
        if not case_id:
            return
        answer = QMessageBox.question(
            self, "確認移除", "案件將移至可復原的 .trash，是否繼續？"
        )
        if answer == QMessageBox.Yes:
            self.case_service.delete_case(case_id)
            self.refresh_cases()

    def import_evidence(self) -> None:
        if not self.state.current_case_id:
            return
        source, _ = QFileDialog.getOpenFileName(self, "選擇證據")
        if source:
            case_id = self.state.current_case_id
            self.run_background(
                "匯入證據",
                lambda: self.case_service.import_evidence(case_id, Path(source)),
                lambda _: self.open_case(case_id),
            )

    def generate_report(self) -> None:
        if self.state.current_case_id:
            case_id = self.state.current_case_id
            self.run_background(
                "產生案件報告",
                lambda: self.case_service.create_report(
                    case_id,
                    ai_enrichment_enabled=self.report_ai_enrichment.isChecked(),
                ),
                lambda _: self.open_case(case_id),
            )

    def export_case_package(self) -> None:
        if not self.state.current_case_id:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "匯出案件套件",
            "case.chainsherlock-case.zip",
            "ChainSherlock Case (*.zip)",
        )
        if destination:
            case_id = self.state.current_case_id
            self.run_background(
                "匯出案件套件",
                lambda: self.case_service.export_package(
                    case_id, Path(destination), "full"
                ),
            )

    def generate_plan(self) -> None:
        if self.state.current_case_id:
            case_id = self.state.current_case_id
            self.run_background(
                "產生調查計畫",
                lambda: self.case_service.create_plan(case_id),
                lambda _: self.open_case(case_id),
            )

    def add_goal(self) -> None:
        if not self.state.current_case_id:
            return
        try:
            target = self.goal_target.text().strip()
            code = self.goal_type.currentData() or self.goal_type.currentText()
            self.case_service.add_goal(
                self.state.current_case_id,
                str(code),
                human_label(code),
                [target] if target else [],
            )
            self.goal_target.clear()
            self.open_case(self.state.current_case_id)
        except Exception as exc:
            self.show_safe_error("新增調查目標失敗", exc)

    def confirm_plan(self) -> None:
        if not self.state.current_case_id:
            return
        try:
            self.case_service.confirm_latest_plan(self.state.current_case_id)
            self.open_case(self.state.current_case_id)
        except Exception as exc:
            self.show_safe_error("確認 Plan 失敗", exc)

    def start_execution(self) -> None:
        if not self.state.current_case_id:
            return
        if self.execution_service is None:
            self.show_safe_error(
                "無法開始 Execution",
                RuntimeError("No execution handlers are configured."),
            )
            return
        try:
            case = self.repository.load(self.state.current_case_id)
            if not case.plans:
                raise ValueError("No confirmed plan is available")
            plan = case.plans[-1]
            if not plan.get("confirmed_at"):
                raise ValueError("Unconfirmed plan cannot run")
            execution = self.execution_service.create_execution(
                case.case_id, str(plan["plan_id"])
            )
            self.state.running_execution_id = execution.execution_id
            self._active_execution_case_id = case.case_id
            self._execution_started_at = time.monotonic()
            self._active_execution_artifacts.clear()
            self.execution_clock.start()
            self.global_execution_badge.set_status("running", "RUNNING")
            self.global_execution_title.setText(f"案件：{case.title}")
            self.global_execution_title.setToolTip(f"案件：{case.title}")
            self.global_execution_detail.setText("目前階段：準備執行調查計畫")
            self.global_execution_meta.setText("紀錄：0 records  ·  耗時：00:00:00  ·  Artifacts：0")
            self.global_execution_progress.setRange(0, 0)
            self.global_execution_progress.show()
            self.global_execution_actions.show()
            self.execution_progress.show()
            self.run_background(
                "執行調查計畫",
                lambda: self.execution_service.run_execution(
                    execution.execution_id,
                    event_callback=self.execution_event_received.emit,
                ),
                lambda _: self._execution_complete(case.case_id),
            )
        except Exception as exc:
            self.show_safe_error("開始 Execution 失敗", exc)

    def _execution_complete(self, case_id: str) -> None:
        self.execution_clock.stop()
        self._execution_started_at = None
        self._active_execution_case_id = None
        self.global_execution_badge.set_status("disabled", "IDLE")
        self.global_execution_title.setText("目前沒有執行中的工作")
        self.global_execution_title.setToolTip("")
        self.global_execution_detail.setText("建立並確認調查計畫後即可開始執行。")
        self.global_execution_meta.clear()
        self.global_execution_progress.hide()
        self.global_execution_actions.hide()
        self.execution_progress.hide()
        self.open_case(case_id)

    def _apply_execution_event(self, event) -> None:
        stage = human_label(getattr(event, "stage", "") or "執行")
        message = human_label(getattr(event, "message", "") or stage)
        provider = getattr(event, "provider", None)
        capability = getattr(event, "capability", None)
        current = max(0, int(getattr(event, "current_records", 0) or 0))
        total = getattr(event, "total_records_if_known", None)
        artifacts = getattr(event, "artifacts", []) or []
        self._active_execution_artifacts.update(Path(item).name for item in artifacts)
        status = str(getattr(event, "status", "running"))
        badge_status = status if status in StatusBadge.SAFE_STATUSES else "running"
        self.global_execution_badge.set_status(badge_status, badge_status.upper())
        source = provider or "Local Pipeline"
        if capability:
            source = f"{source} · {human_label(capability)}"
        self.global_execution_detail.setText(
            f"目前階段：{stage}\n目前步驟：{message}\n來源：{source}"
        )
        self.global_execution_detail.setToolTip(
            f"目前階段：{stage}\n目前步驟：{message}\n來源：{source}"
        )
        if isinstance(total, int) and total > 0:
            self.global_execution_progress.setRange(0, total)
            self.global_execution_progress.setValue(min(current, total))
        else:
            self.global_execution_progress.setRange(0, 0)
        self._update_execution_elapsed(current)

    def _update_execution_elapsed(self, current_records: int | None = None) -> None:
        if self._execution_started_at is None:
            return
        elapsed = max(0, int(time.monotonic() - self._execution_started_at))
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if current_records is None:
            current_records = 0
            text = self.global_execution_meta.text()
            if text.startswith("紀錄："):
                try:
                    current_records = int(text.split("：", 1)[1].split()[0])
                except (ValueError, IndexError):
                    pass
        self.global_execution_meta.setText(
            f"紀錄：{current_records} records  ·  "
            f"耗時：{hours:02d}:{minutes:02d}:{seconds:02d}  ·  "
            f"Artifacts：{len(self._active_execution_artifacts)}"
        )

    def _open_active_execution(self) -> None:
        if self._active_execution_case_id:
            self.open_case(self._active_execution_case_id)
            self.workspace_tabs.setCurrentIndex(WORKSPACE_TABS.index("Execution"))

    def cancel_execution(self) -> None:
        if self.execution_service is None or not self.state.running_execution_id:
            self.statusBar().showMessage("沒有可取消的 Execution", 5000)
            return
        try:
            self.execution_service.cancel_execution(
                self.state.running_execution_id, "Cancelled by desktop user"
            )
            for worker in self.active_workers:
                worker.cancel()
        except Exception as exc:
            self.show_safe_error("取消 Execution 失敗", exc)

    def resume_execution(self) -> None:
        case = (
            self.repository.load(self.state.current_case_id)
            if self.state.current_case_id
            else None
        )
        execution_id = self.state.running_execution_id or (
            case.latest_execution_id if case else None
        )
        if self.execution_service is None or not execution_id:
            self.statusBar().showMessage("沒有可恢復的 Execution", 5000)
            return
        self.run_background(
            "恢復 Execution",
            lambda: self.execution_service.resume_execution(execution_id),
            lambda _: self.open_case(case.case_id),
        )

    def next_workflow_action(self) -> None:
        if not self.state.current_case_id:
            self.open_case_wizard()
            return
        case = self.repository.load(self.state.current_case_id)
        if not case.goals:
            target = WORKSPACE_TABS.index("調查目標")
        elif not case.plans or not case.plans[-1].get("confirmed_at"):
            target = WORKSPACE_TABS.index("調查計畫")
        elif not case.executions:
            target = WORKSPACE_TABS.index("Execution")
        elif case.last_execution_status in {"completed", "partial"}:
            target = WORKSPACE_TABS.index("Result")
        else:
            target = WORKSPACE_TABS.index("Execution")
        self.workspace_tabs.setCurrentIndex(target)

    def save_current_case(self) -> None:
        if not self.state.current_case_id:
            self.statusBar().showMessage("目前沒有可儲存的案件", 3000)
            return
        case = self.repository.load(self.state.current_case_id)
        self.repository.save(case)
        self.statusBar().showMessage("案件已儲存", 3000)

    def run_background(self, stage: str, operation, on_complete=None) -> BackgroundWorker:
        worker = BackgroundWorker(operation)
        self.active_workers.append(worker)
        worker.signals.started.connect(
            lambda: self.statusBar().showMessage(f"{stage}…")
        )
        worker.signals.completed.connect(
            lambda result: self._worker_finished(worker, result, on_complete)
        )
        worker.signals.failed.connect(
            lambda message: self._worker_failed(worker, stage, message)
        )
        worker.signals.cancelled.connect(lambda: self._worker_cancelled(worker))
        self.thread_pool.start(worker)
        return worker

    def _worker_finished(self, worker, result, callback) -> None:
        if worker in self.active_workers:
            self.active_workers.remove(worker)
        self.statusBar().showMessage("完成", 5000)
        if callback:
            callback(result)

    def _worker_failed(self, worker, stage: str, message: str) -> None:
        if worker in self.active_workers:
            self.active_workers.remove(worker)
        self.show_safe_error(f"{stage}失敗", RuntimeError(message))

    def _worker_cancelled(self, worker) -> None:
        if worker in self.active_workers:
            self.active_workers.remove(worker)
        self.statusBar().showMessage("已取消", 5000)

    def save_settings(self) -> None:
        try:
            self.settings = self.settings_service.save(
                UISettings(
                    theme=self.setting_theme.currentText(),
                    language=self.setting_language.currentText(),
                    case_root=self.setting_case_root.text(),
                    ai_enabled=self.setting_ai.isChecked(),
                    max_pages=max(1, int(self.setting_max_pages.text())),
                    max_records=max(1, int(self.setting_max_records.text())),
                )
            )
            self.statusBar().showMessage("設定已安全儲存", 5000)
        except Exception as exc:
            self.show_safe_error("設定儲存失敗", exc)

    def show_safe_error(self, title: str, error: Exception) -> None:
        message = str(redact_sensitive(str(error)))
        self.statusBar().showMessage(f"{title}: {message}", 10000)

    def closeEvent(self, event) -> None:
        for worker in self.active_workers:
            worker.cancel()
        event.accept()
