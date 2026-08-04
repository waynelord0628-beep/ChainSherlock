from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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
    QStackedWidget,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from crypto_investigator.cases import CaseRepository
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.ui.models import RecordsTableModel
from crypto_investigator.ui.services import CaseUIService, UISettings, UISettingsService
from crypto_investigator.ui.state import UIState
from crypto_investigator.ui.theme import LIGHT_THEME
from crypto_investigator.ui.workers import BackgroundWorker
from crypto_investigator.ui.widgets import SafeGraphView


WORKSPACE_TABS = (
    "案件摘要",
    "調查目標",
    "地址與交易",
    "證據",
    "調查計畫",
    "執行進度",
    "分析結果",
    "Investigation",
    "Graph",
    "Narrative",
    "報告",
    "Audit Log",
)


class MainWindow(QMainWindow):
    case_opened = Signal(str)

    def __init__(
        self,
        case_root: Path | str = "cases",
        settings_path: Path | None = None,
        execution_service=None,
    ) -> None:
        super().__init__()
        self.setObjectName("main_window")
        self.setWindowTitle("ChainSherlock — 案件調查工作台")
        self.resize(1280, 820)
        self.repository = CaseRepository(case_root)
        self.case_service = CaseUIService(self.repository)
        self.execution_service = execution_service
        self.settings_service = UISettingsService(
            settings_path or Path(case_root) / ".ui-settings.json"
        )
        self.settings = self.settings_service.load()
        self.state = UIState(case_root=Path(case_root))
        self.thread_pool = QThreadPool(self)
        self.active_workers: list[BackgroundWorker] = []
        self.setStyleSheet(LIGHT_THEME)
        self._build_ui()
        self.refresh_cases()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(210)
        side_layout = QVBoxLayout(sidebar)
        brand = QLabel("ChainSherlock\nInvestigation Workbench")
        brand.setStyleSheet("font-size: 17px; font-weight: 700; color: white; padding: 14px;")
        side_layout.addWidget(brand)
        self.navigation = QListWidget(objectName="navigation")
        self.navigation.addItems(["首頁", "案件清單", "建立案件", "設定"])
        self.navigation.currentRowChanged.connect(self._navigate)
        side_layout.addWidget(self.navigation)
        self.case_status = QLabel("未開啟案件")
        self.case_status.setWordWrap(True)
        self.case_status.setStyleSheet("color: #b9c8dc; padding: 10px;")
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

        refresh = QAction("重新整理", self)
        refresh.triggered.connect(self.refresh_cases)
        self.menuBar().addAction(refresh)
        self.statusBar().showMessage("就緒")

    def _title(self, text: str, subtitle: str = "") -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(text)
        label.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(label)
        if subtitle:
            description = QLabel(subtitle)
            description.setWordWrap(True)
            description.setStyleSheet("color: #526174;")
            layout.addWidget(description)
        return page, layout

    def _build_home(self) -> QWidget:
        page, layout = self._title(
            "案件調查工作台",
            "本機優先、可驗證、具完整稽核軌跡。AI 預設停用。",
        )
        self.home_counts = QLabel()
        self.home_counts.setStyleSheet("font-size: 18px; padding: 20px; background: white;")
        layout.addWidget(self.home_counts)
        layout.addStretch()
        return page

    def _build_case_list(self) -> QWidget:
        page, layout = self._title("案件清單")
        tools = QHBoxLayout()
        self.case_search = QLineEdit(placeholderText="搜尋案件名稱或 ID")
        self.case_search.textChanged.connect(self.refresh_cases)
        self.show_archived = QCheckBox("顯示已封存")
        self.show_archived.toggled.connect(self.refresh_cases)
        tools.addWidget(self.case_search)
        tools.addWidget(self.show_archived)
        layout.addLayout(tools)
        self.case_model = RecordsTableModel(
            ["Case ID", "標題", "狀態", "更新時間", "Evidence", "Execution"]
        )
        self.case_table = QTableView()
        self.case_table.setModel(self.case_model)
        self.case_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.case_table.setSortingEnabled(True)
        self.case_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.case_table.doubleClicked.connect(lambda _: self.open_selected_case())
        layout.addWidget(self.case_table)
        buttons = QHBoxLayout()
        open_button = QPushButton("開啟案件")
        open_button.clicked.connect(self.open_selected_case)
        archive_button = QPushButton("封存")
        archive_button.clicked.connect(self.archive_selected_case)
        delete_button = QPushButton("移至資源回收區")
        delete_button.clicked.connect(self.delete_selected_case)
        buttons.addWidget(open_button)
        buttons.addWidget(archive_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _build_new_case(self) -> QWidget:
        page, layout = self._title("建立案件")
        form = QFormLayout()
        self.new_title = QLineEdit()
        self.new_description = QPlainTextEdit()
        self.new_description.setMaximumHeight(110)
        self.new_chain = QComboBox()
        self.new_chain.addItems(["未指定", "TRON", "Ethereum", "Bitcoin"])
        self.new_address = QLineEdit()
        self.new_tx = QLineEdit()
        form.addRow("案件標題 *", self.new_title)
        form.addRow("描述", self.new_description)
        form.addRow("主要鏈", self.new_chain)
        form.addRow("已知地址", self.new_address)
        form.addRow("已知 Tx Hash", self.new_tx)
        layout.addLayout(form)
        create = QPushButton("建立並開啟案件")
        create.clicked.connect(self.create_case)
        layout.addWidget(create, alignment=Qt.AlignLeft)
        layout.addStretch()
        return page

    def _build_settings(self) -> QWidget:
        page, layout = self._title(
            "設定", "秘密值僅由環境變數或 Credential Adapter 提供，不寫入此頁設定檔。"
        )
        form = QFormLayout()
        self.setting_theme = QComboBox()
        self.setting_theme.addItems(["light"])
        self.setting_language = QComboBox()
        self.setting_language.addItems(["zh-TW", "en"])
        self.setting_case_root = QLineEdit(self.settings.case_root)
        self.setting_max_pages = QLineEdit(str(self.settings.max_pages))
        self.setting_max_records = QLineEdit(str(self.settings.max_records))
        self.setting_ai = QCheckBox("啟用 AI（預設關閉）")
        self.setting_ai.setChecked(False)
        self.credential_status = QLabel("API Key：由環境變數管理（未顯示）")
        form.addRow("Theme", self.setting_theme)
        form.addRow("Language", self.setting_language)
        form.addRow("Case Root", self.setting_case_root)
        form.addRow("Provider max_pages", self.setting_max_pages)
        form.addRow("Provider max_records", self.setting_max_records)
        form.addRow("AI", self.setting_ai)
        form.addRow("Credentials", self.credential_status)
        layout.addLayout(form)
        save = QPushButton("儲存安全設定")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save, alignment=Qt.AlignLeft)
        layout.addStretch()
        return page

    def _build_workspace(self) -> QWidget:
        page, layout = self._title("案件工作區")
        self.workspace_header = QLabel("尚未開啟案件")
        self.workspace_header.setStyleSheet("padding: 8px; background: white; font-weight: 600;")
        layout.addWidget(self.workspace_header)
        self.workspace_tabs = QTabWidget()
        self.tab_views: dict[str, QPlainTextEdit] = {}
        for tab_name in WORKSPACE_TABS:
            container = QWidget()
            tab_layout = QVBoxLayout(container)
            if tab_name == "執行進度":
                progress = QProgressBar()
                progress.setRange(0, 0)
                progress.setVisible(False)
                progress.setObjectName("execution_progress")
                tab_layout.addWidget(progress)
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setObjectName(f"view_{len(self.tab_views)}")
            self.tab_views[tab_name] = view
            tab_layout.addWidget(view)
            if tab_name == "Graph":
                self.graph_view = SafeGraphView()
                self.graph_view.setMinimumHeight(320)
                self.graph_view.hide()
                tab_layout.addWidget(self.graph_view)
            if tab_name == "證據":
                button = QPushButton("匯入證據")
                button.clicked.connect(self.import_evidence)
                tab_layout.addWidget(button, alignment=Qt.AlignLeft)
            if tab_name == "調查目標":
                goal_actions = QHBoxLayout()
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
                self.goal_target = QLineEdit(placeholderText="Target address（選填）")
                add_goal = QPushButton("新增 Goal")
                add_goal.clicked.connect(self.add_goal)
                goal_actions.addWidget(self.goal_type)
                goal_actions.addWidget(self.goal_target)
                goal_actions.addWidget(add_goal)
                tab_layout.addLayout(goal_actions)
            if tab_name == "調查計畫":
                actions = QHBoxLayout()
                create_plan = QPushButton("背景產生 Plan")
                create_plan.clicked.connect(self.generate_plan)
                confirm_plan = QPushButton("確認最新 Plan")
                confirm_plan.clicked.connect(self.confirm_plan)
                actions.addWidget(create_plan)
                actions.addWidget(confirm_plan)
                actions.addStretch()
                tab_layout.addLayout(actions)
            if tab_name == "報告":
                button = QPushButton("背景產生四格式報告")
                button.clicked.connect(self.generate_report)
                tab_layout.addWidget(button, alignment=Qt.AlignLeft)
            if tab_name == "執行進度":
                execution_actions = QHBoxLayout()
                start = QPushButton("開始")
                start.clicked.connect(self.start_execution)
                cancel = QPushButton("取消")
                cancel.clicked.connect(self.cancel_execution)
                resume = QPushButton("Resume")
                resume.clicked.connect(self.resume_execution)
                execution_actions.addWidget(start)
                execution_actions.addWidget(cancel)
                execution_actions.addWidget(resume)
                execution_actions.addStretch()
                tab_layout.addLayout(execution_actions)
            self.workspace_tabs.addTab(container, tab_name)
        layout.addWidget(self.workspace_tabs)
        return page

    def _navigate(self, index: int) -> None:
        if index >= 0:
            self.pages.setCurrentIndex(index)
            self.state.current_page = self.navigation.item(index).text()

    def refresh_cases(self) -> None:
        records = self.case_service.list_cases(
            self.case_search.text() if hasattr(self, "case_search") else "",
            self.show_archived.isChecked() if hasattr(self, "show_archived") else False,
        )
        self._case_ids = [item.case_id for item in records]
        if hasattr(self, "case_model"):
            self.case_model.replace(
                [
                    [
                        item.case_id,
                        item.title,
                        item.status.value,
                        item.updated_at.isoformat(),
                        len(item.evidence),
                        item.last_execution_status or "not_started",
                    ]
                    for item in records
                ]
            )
        if hasattr(self, "home_counts"):
            self.home_counts.setText(
                f"案件：{len(records)}\n執行中："
                f"{sum(item.active_execution_id is not None for item in records)}\n"
                f"部分完成：{sum(item.last_execution_status == 'partial' for item in records)}"
            )

    def selected_case_id(self) -> str | None:
        index = self.case_table.currentIndex()
        if not index.isValid():
            return None
        value = self.case_model.rows[index.row()][0]
        return str(value)

    def create_case(self) -> None:
        try:
            metadata = {
                "chain": None if self.new_chain.currentIndex() == 0 else self.new_chain.currentText().lower(),
                "known_addresses": [self.new_address.text().strip()] if self.new_address.text().strip() else [],
                "known_transactions": [self.new_tx.text().strip()] if self.new_tx.text().strip() else [],
            }
            case = self.case_service.create_case(
                self.new_title.text(), self.new_description.toPlainText()
            )
            self.repository.save(case.model_copy(update={"metadata": metadata}))
            self.new_title.clear()
            self.new_description.clear()
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
        self.workspace_header.setText(
            f"{case.title}  |  {case.status.value}  |  Evidence: {len(case.evidence)}"
        )
        self._load_case_views(case)
        self.pages.setCurrentWidget(self.workspace_page)
        self.case_opened.emit(case_id)

    def _load_case_views(self, case) -> None:
        result = None
        try:
            result = self.case_service.result(case.case_id)
        except Exception:
            pass
        data = {
            "案件摘要": {
                "case_id": case.case_id, "title": case.title, "description": case.description,
                "status": case.status.value, "metadata": case.metadata,
            },
            "調查目標": case.goals,
            "地址與交易": {
                "addresses": case.metadata.get("known_addresses", []),
                "transactions": case.metadata.get("known_transactions", []),
            },
            "證據": [item.model_dump(mode="json") for item in case.evidence],
            "調查計畫": case.plans,
            "執行進度": {
                "active": case.active_execution_id,
                "latest": case.latest_execution_id,
                "status": case.last_execution_status or "not_started",
                "summary": case.execution_summary,
            },
            "分析結果": result.model_dump(mode="json") if result else {"status": "unavailable"},
            "Investigation": {
                "confirmed_facts": [item.model_dump(mode="json") for item in result.confirmed_facts] if result else [],
                "observations": [item.model_dump(mode="json") for item in result.deterministic_observations] if result else [],
                "candidates": [item.model_dump(mode="json") for item in result.candidate_interpretations] if result else [],
                "unresolved": [item.model_dump(mode="json") for item in result.unresolved_questions] if result else [],
            },
            "Graph": {"status": "unavailable", "note": "UI only loads an existing flow.html artifact."},
            "Narrative": {"ai_enabled": False, "status": "deterministic fallback / unavailable"},
            "報告": self.case_service.reports(case.case_id),
            "Audit Log": {
                "chain_integrity": self.case_service.audit_valid(case.case_id),
                "entries": [item.model_dump(mode="json") for item in self.case_service.audit_entries(case.case_id)],
            },
        }
        for name, value in data.items():
            self.tab_views[name].setPlainText(
                json.dumps(redact_sensitive(value), ensure_ascii=False, indent=2, default=str)
            )
        self.graph_view.hide()
        if result:
            graph = next(
                (
                    item for item in result.evidence_index
                    if item.evidence_type == "graph_html"
                    and item.relative_path.endswith("flow.html")
                ),
                None,
            )
            if graph:
                try:
                    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                        self.graph_view.load_graph(
                            self.repository.workspace(case.case_id).resolve_relative(
                                graph.relative_path
                            ),
                            self.repository.workspace(case.case_id).path,
                        )
                        self.graph_view.show()
                    else:
                        self.tab_views["Graph"].appendPlainText(
                            f"\nHeadless validation: {graph.relative_path}"
                        )
                except ValueError:
                    pass

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
            self.run_background(
                "匯入證據",
                lambda: self.case_service.import_evidence(
                    self.state.current_case_id, Path(source)
                ),
                lambda _: self.open_case(self.state.current_case_id),
            )

    def generate_report(self) -> None:
        if self.state.current_case_id:
            self.run_background(
                "產生案件報告",
                lambda: self.case_service.create_report(self.state.current_case_id),
                lambda _: self.open_case(self.state.current_case_id),
            )

    def generate_plan(self) -> None:
        if self.state.current_case_id:
            self.run_background(
                "產生調查計畫",
                lambda: self.case_service.create_plan(self.state.current_case_id),
                lambda _: self.open_case(self.state.current_case_id),
            )

    def add_goal(self) -> None:
        if not self.state.current_case_id:
            return
        try:
            target = self.goal_target.text().strip()
            goal_type = self.goal_type.currentText()
            self.case_service.add_goal(
                self.state.current_case_id,
                goal_type,
                goal_type.replace("_", " ").title(),
                [target] if target else [],
            )
            self.goal_target.clear()
            self.open_case(self.state.current_case_id)
        except Exception as exc:
            self.show_safe_error("新增 Goal 失敗", exc)

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
            self.run_background(
                "執行調查計畫",
                lambda: self.execution_service.run_execution(
                    execution.execution_id
                ),
                lambda _: self.open_case(case.case_id),
            )
        except Exception as exc:
            self.show_safe_error("開始 Execution 失敗", exc)

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
        execution_id = (
            self.state.running_execution_id
            or (case.latest_execution_id if case else None)
        )
        if self.execution_service is None or not execution_id:
            self.statusBar().showMessage("沒有可恢復的 Execution", 5000)
            return
        self.run_background(
            "恢復 Execution",
            lambda: self.execution_service.resume_execution(execution_id),
            lambda _: self.open_case(case.case_id),
        )

    def confirm_plan(self) -> None:
        if not self.state.current_case_id:
            return
        try:
            self.case_service.confirm_latest_plan(self.state.current_case_id)
            self.open_case(self.state.current_case_id)
        except Exception as exc:
            self.show_safe_error("確認 Plan 失敗", exc)

    def run_background(self, stage: str, operation, on_complete=None) -> BackgroundWorker:
        worker = BackgroundWorker(operation)
        self.active_workers.append(worker)
        worker.signals.started.connect(lambda: self.statusBar().showMessage(f"{stage}…"))
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
