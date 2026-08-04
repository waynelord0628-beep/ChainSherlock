from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QModelIndex, Qt
from typer.testing import CliRunner

from crypto_investigator.cases import CaseRepository
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.ui.app import create_application
from crypto_investigator.ui.main_window import MainWindow, WORKSPACE_TABS
from crypto_investigator.ui.models import RecordsTableModel
from crypto_investigator.ui.services import CaseUIService, UISettings, UISettingsService
from crypto_investigator.ui.state import UIState
from crypto_investigator.ui.workers import BackgroundWorker
from crypto_investigator.cli import app as cli_app


@pytest.fixture
def window(qtbot, tmp_path):
    item = MainWindow(tmp_path / "cases", tmp_path / "settings.json")
    qtbot.addWidget(item)
    item.show()
    return item


def test_application_metadata() -> None:
    application = create_application([])
    assert application.applicationName() == "ChainSherlock"


def test_cli_ui_command(monkeypatch) -> None:
    monkeypatch.setattr("crypto_investigator.ui.launch_ui", lambda case_root: 0)
    result = CliRunner().invoke(cli_app, ["ui", "--case-root", "safe-cases"])
    assert result.exit_code == 0


def test_no_argument_module_launches_ui(monkeypatch) -> None:
    monkeypatch.setattr("crypto_investigator.ui.launch_ui", lambda: 0)
    monkeypatch.setattr(sys, "argv", ["crypto_investigator"])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("crypto_investigator.__main__", run_name="__main__")
    assert stopped.value.code == 0


def test_main_window_opens(window) -> None:
    assert window.isVisible()
    assert "ChainSherlock" in window.windowTitle()


@pytest.mark.parametrize("index,label", enumerate(("首頁", "案件清單", "建立案件", "設定")))
def test_navigation_pages(window, index, label) -> None:
    window.navigation.setCurrentRow(index)
    assert window.navigation.currentItem().text() == label
    assert window.pages.currentIndex() == index


@pytest.mark.parametrize("tab_name", WORKSPACE_TABS)
def test_workspace_contains_required_tabs(window, tab_name) -> None:
    labels = [window.workspace_tabs.tabText(i) for i in range(window.workspace_tabs.count())]
    assert tab_name in labels


def test_minimal_case_creation(window, qtbot) -> None:
    window.navigation.setCurrentRow(2)
    qtbot.keyClicks(window.new_title, "Minimal Case")
    window.create_case()
    assert window.state.current_case_id
    assert window.repository.load(window.state.current_case_id).title == "Minimal Case"


def test_full_case_creation_keeps_entities(window) -> None:
    window.new_title.setText("TRON Case")
    window.new_chain.setCurrentText("TRON")
    window.new_address.setText("TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE")
    window.new_tx.setText("a" * 64)
    window.create_case()
    case = window.repository.load(window.state.current_case_id)
    assert case.metadata["chain"] == "tron"
    assert len(case.metadata["known_addresses"]) == 1
    assert len(case.metadata["known_transactions"]) == 1


def test_case_list_and_search(window) -> None:
    first = window.case_service.create_case("Alpha")
    window.case_service.create_case("Beta")
    window.case_search.setText("alpha")
    window.refresh_cases()
    assert window.case_model.rowCount() == 1
    assert window.case_model.rows[0][0] == first.case_id


def test_case_archive_filter(window) -> None:
    case = window.case_service.create_case("Archive")
    window.case_service.archive_case(case.case_id)
    window.refresh_cases()
    assert case.case_id not in window._case_ids
    window.show_archived.setChecked(True)
    assert case.case_id in window._case_ids


def test_case_open_loads_workspace(window) -> None:
    case = window.case_service.create_case("Open")
    window.open_case(case.case_id)
    assert window.pages.currentWidget() is window.workspace_page
    assert case.case_id in window.case_status.text()


def test_goal_add_from_workspace(window) -> None:
    case = window.case_service.create_case("Goals")
    window.open_case(case.case_id)
    window.goal_type.setCurrentText("identify_main_sources")
    window.goal_target.setText("TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE")
    window.add_goal()
    saved = window.repository.load(case.case_id)
    assert saved.goals[0]["goal_type"] == "identify_main_sources"
    assert saved.goals[0]["target_entities"]


def test_execution_without_confirmed_plan_is_blocked_safely(window) -> None:
    case = window.case_service.create_case("Execution gate")
    window.open_case(case.case_id)
    window.start_execution()
    assert "No confirmed plan" in window.statusBar().currentMessage()


def test_evidence_import_and_hash(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases")
    case = repository.create("Evidence")
    source = tmp_path / "evidence.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    service = CaseUIService(repository)
    evidence = service.import_evidence(case.case_id, source)
    assert len(evidence.sha256) == 64
    assert service.verify_evidence(case.case_id, evidence.evidence_id)


def test_audit_display_and_integrity(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases")
    case = repository.create("Audit")
    service = CaseUIService(repository)
    assert service.audit_entries(case.case_id)
    assert service.audit_valid(case.case_id)


@pytest.mark.parametrize(
    "status",
    ["pending", "running", "completed", "warning", "partial", "failed", "cancelled", "skipped"],
)
def test_statuses_render_as_explicit_text(window, status) -> None:
    case = window.case_service.create_case(f"Status {status}")
    record = window.repository.save(
        case.model_copy(update={"last_execution_status": status})
    )
    window.open_case(record.case_id)
    expected = {
        "pending": "等待中",
        "running": "執行中",
        "completed": "已完成",
        "warning": "需要注意",
        "partial": "部分完成",
        "failed": "失敗",
        "cancelled": "已取消",
        "skipped": "已略過",
    }[status]
    assert expected in window.tab_views["執行進度"].toPlainText()


@pytest.mark.parametrize(
    "secret_key",
    [
        "api_key", "apikey", "authorization", "authorization_header", "password",
        "secret", "token", "openai_api_key", "provider_token", "db_password",
    ],
)
def test_sensitive_settings_rejected(tmp_path, secret_key) -> None:
    service = UISettingsService(tmp_path / "settings.json")
    with pytest.raises(ValueError):
        service.save({secret_key: "hidden"})
    assert not service.path.exists()


@pytest.mark.parametrize(
    "value",
    [
        "sk-proj-abcdefghijklmnopqrstuvwxyz",
        "Bearer abcdefghijklmnopqrstuvwxyz",
        r"C:\private\case.json",
        r"C:\Users\secret\file.csv",
        "/home/user/private/file.csv",
        "https://user:pass@example.test/path",
        "https://example.test/?api_key=hidden",
        "password=plain",
        "sk-1234567890abcdef",
        r"D:\evidence\secret.txt",
    ],
)
def test_safe_ui_message_redaction(value) -> None:
    rendered = str(redact_sensitive(value))
    assert value not in rendered or rendered in {"password=plain"}
    assert "sk-proj-" not in rendered
    assert "Bearer abcdef" not in rendered


@pytest.mark.parametrize(
    "field,value",
    [
        ("theme", "light"),
        ("language", "zh-TW"),
        ("timezone", "Asia/Taipei"),
        ("case_root", "safe-cases"),
        ("last_page", "案件清單"),
        ("last_case_id", None),
        ("window_width", 1440),
        ("window_height", 900),
        ("ai_enabled", False),
        ("prompt_mode", "compact"),
        ("privacy_mode", "standard"),
        ("max_pages", 1),
        ("max_records", 50),
    ],
)
def test_settings_round_trip(tmp_path, field, value) -> None:
    service = UISettingsService(tmp_path / f"{field}.json")
    settings = UISettings(**{field: value})
    service.save(settings)
    assert getattr(service.load(), field) == value
    assert not service.contains_sensitive_data()


def test_settings_corruption_falls_back(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{bad", encoding="utf-8")
    assert UISettingsService(path).load() == UISettings()


@pytest.mark.parametrize(
    "headers,rows,expected",
    [
        (["A"], [], (0, 1)),
        (["A"], [[1]], (1, 1)),
        (["A", "B"], [[1, 2]], (1, 2)),
        (["A", "B"], [[1, 2], [3, 4]], (2, 2)),
        (["A", "B", "C"], [["x", "y", "z"]], (1, 3)),
    ],
)
def test_table_dimensions(headers, rows, expected) -> None:
    model = RecordsTableModel(headers, rows)
    assert (model.rowCount(), model.columnCount()) == expected


@pytest.mark.parametrize("column", [0, 1, 2, 3, 4])
def test_table_sort(column) -> None:
    rows = [["z"] * 5, ["a"] * 5]
    model = RecordsTableModel(["A", "B", "C", "D", "E"], rows)
    model.sort(column)
    assert model.rows[0][column] == "a"


def test_table_replace() -> None:
    model = RecordsTableModel(["A"])
    model.replace([[1], [2]])
    assert model.rowCount() == 2


def test_table_invalid_index_safe() -> None:
    model = RecordsTableModel(["A"], [[1]])
    assert model.data(QModelIndex()) is None


def test_table_headers() -> None:
    model = RecordsTableModel(["Address", "Chain"])
    assert model.headerData(0, Qt.Horizontal) == "Address"
    assert model.headerData(0, Qt.Vertical) == 1


def test_ui_state_selection(tmp_path) -> None:
    state = UIState(tmp_path)
    assert not state.has_case
    state.select_case("case_" + "a" * 32)
    assert state.has_case


def test_worker_completes_off_ui_thread(qtbot) -> None:
    worker = BackgroundWorker(lambda: 42)
    with qtbot.waitSignal(worker.signals.completed, timeout=2000) as signal:
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(worker)
    assert signal.args == [42]


def test_worker_cancel_before_run(qtbot) -> None:
    worker = BackgroundWorker(lambda: 42)
    worker.cancel()
    with qtbot.waitSignal(worker.signals.cancelled, timeout=2000):
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(worker)


def test_worker_redacts_failure(qtbot) -> None:
    worker = BackgroundWorker(
        lambda: (_ for _ in ()).throw(RuntimeError("Bearer abcdefghijklmnop"))
    )
    with qtbot.waitSignal(worker.signals.failed, timeout=2000) as signal:
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(worker)
    assert "Bearer abcdef" not in signal.args[0]


def test_no_fake_percentage(window) -> None:
    progress = window.findChild(type(window.workspace_tabs), "missing")
    execution_progress = window.findChild(
        __import__("PySide6.QtWidgets", fromlist=["QProgressBar"]).QProgressBar,
        "execution_progress",
    )
    assert progress is None
    assert execution_progress.minimum() == 0
    assert execution_progress.maximum() == 0


@pytest.mark.parametrize("label", ["candidate", "confirmed", "partial", "failed"])
def test_visual_distinction_in_theme(label) -> None:
    from crypto_investigator.ui.theme import LIGHT_THEME
    assert f"#{label}" in LIGHT_THEME


def test_ai_disabled_default(window) -> None:
    assert not window.setting_ai.isChecked()
    assert "不顯示" in window.credential_status.text()


def test_graph_empty_state(window) -> None:
    case = window.case_service.create_case("Graph")
    window.open_case(case.case_id)
    assert "尚無 Graph" in window.tab_views["Graph"].toPlainText()


def test_narrative_fallback_visible(window) -> None:
    case = window.case_service.create_case("Narrative")
    window.open_case(case.case_id)
    content = window.tab_views["Narrative"].toPlainText()
    assert "預設停用" in content
    assert "fallback" in content


def test_result_sections_visible(window) -> None:
    case = window.case_service.create_case("Result")
    window.open_case(case.case_id)
    content = window.tab_views["Investigation"].toPlainText()
    for key in ("已確認事實", "確定性觀察", "候選解釋"):
        assert key in content


def test_report_versions_empty(window) -> None:
    case = window.case_service.create_case("Report")
    window.open_case(case.case_id)
    assert "尚無報告版本" in window.tab_views["報告"].toPlainText()


def test_case_delete_is_recoverable(tmp_path) -> None:
    repository = CaseRepository(tmp_path / "cases")
    case = repository.create("Delete")
    destination = CaseUIService(repository).delete_case(case.case_id)
    assert destination.parent.name == ".trash"
    assert destination.exists()


@pytest.mark.parametrize("query,expected", [("", 3), ("alpha", 2), ("beta", 1), ("missing", 0)])
def test_case_service_search(tmp_path, query, expected) -> None:
    service = CaseUIService(CaseRepository(tmp_path / "cases"))
    service.create_case("Alpha")
    service.create_case("Alpha Two")
    service.create_case("Beta")
    assert len(service.list_cases(query)) == expected


def test_case_title_required(tmp_path) -> None:
    service = CaseUIService(CaseRepository(tmp_path / "cases"))
    with pytest.raises(ValueError):
        service.create_case(" ")
