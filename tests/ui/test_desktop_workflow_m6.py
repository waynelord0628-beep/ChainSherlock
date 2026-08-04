from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

import pytest
from PySide6.QtWidgets import QDialog, QTabWidget

from crypto_investigator.ui.case_wizard import CaseWizard, DEFAULT_GOALS
from crypto_investigator.ui.labels import HUMAN_LABELS, human_label
from crypto_investigator.ui.main_window import MainWindow, WORKSPACE_TABS
from crypto_investigator.ui.theme import LIGHT_THEME
from crypto_investigator.ui.widgets import MetricCard, StatusBadge


@pytest.fixture
def window(qtbot, tmp_path):
    item = MainWindow(tmp_path / "cases", tmp_path / "ui.json")
    qtbot.addWidget(item)
    item.show()
    return item


@pytest.fixture
def wizard(qtbot):
    item = CaseWizard()
    qtbot.addWidget(item)
    item.show()
    return item


@pytest.mark.parametrize("code,label", sorted(HUMAN_LABELS.items()))
def test_human_readable_labels(code, label) -> None:
    assert human_label(code) == label
    assert "_" not in label


@pytest.mark.parametrize("tab", WORKSPACE_TABS)
def test_workflow_navigation_has_all_stages(window, tab) -> None:
    labels = [window.workspace_tabs.tabText(i) for i in range(window.workspace_tabs.count())]
    assert tab in labels


@pytest.mark.parametrize(
    "token",
        [
            "#0B1220",
            "#111B2B",
            "#2DD4BF",
            "#60A5FA",
            "#A78BFA",
            "#F59E0B",
        "QFrame#card",
        "QFrame#metricCard",
        "QFrame#heroCard",
        'QPushButton[variant="secondary"]',
        'QPushButton[variant="danger"]',
        "QTabBar::tab:selected",
    ],
)
def test_visual_system_tokens(token) -> None:
    assert token in LIGHT_THEME


@pytest.mark.parametrize(
    "status",
    [
        "confirmed",
        "candidate",
        "pending",
        "running",
        "completed",
        "warning",
        "partial",
        "failed",
        "cancelled",
        "skipped",
        "unavailable",
    ],
)
def test_status_badges_are_text_and_color(qtbot, status) -> None:
    badge = StatusBadge()
    qtbot.addWidget(badge)
    badge.set_status(status)
    assert badge.text() == status
    assert badge.objectName() == status


@pytest.mark.parametrize("index,name", enumerate(("基本資料", "案件說明", "匯入證據", "確認線索", "調查目標")))
def test_case_wizard_steps(wizard, index, name) -> None:
    wizard.stack.setCurrentIndex(index)
    wizard._sync()
    assert name in wizard.progress.text()
    assert f"{index + 1}／5" in wizard.progress.text()


def test_case_wizard_next_and_back(wizard) -> None:
    wizard.title_edit.setText("Wizard Case")
    wizard.next()
    assert wizard.stack.currentIndex() == 1
    wizard.back()
    assert wizard.stack.currentIndex() == 0


def test_case_wizard_minimal_payload(wizard) -> None:
    wizard.title_edit.setText("Minimal")
    payload = wizard.payload()
    assert payload["title"] == "Minimal"
    assert payload["metadata"]["known_addresses"] == []
    assert payload["attachments"] == []


def test_case_wizard_unconfirmed_clues_not_persisted(wizard) -> None:
    wizard.title_edit.setText("No Guess")
    wizard.address_edit.setText("TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE")
    wizard.tx_edit.setText("a" * 64)
    payload = wizard.payload()
    assert payload["metadata"]["known_addresses"] == []
    assert payload["metadata"]["known_transactions"] == []


def test_case_wizard_confirmed_clues_persisted(wizard) -> None:
    wizard.title_edit.setText("Confirmed")
    wizard.address_edit.setText("TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE")
    wizard.confirm_clues.setChecked(True)
    assert wizard.payload()["metadata"]["known_addresses"]


@pytest.mark.parametrize("goal", DEFAULT_GOALS)
def test_case_wizard_goal_selection(wizard, goal) -> None:
    wizard.goal_checks[goal].setChecked(True)
    assert goal in wizard.payload()["goals"]


@pytest.mark.parametrize("key", ["cases", "running", "partial", "review"])
def test_home_summary_cards(window, key) -> None:
    card = window.home_metric_cards[key]
    assert isinstance(card, MetricCard)
    assert card.value_label.text() == "0"


def test_home_primary_action_visible(window) -> None:
    buttons = [item.text() for item in window.home_page.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)]
    assert "＋ 建立新案件" in buttons
    assert "開啟案件清單" in buttons


def test_home_recent_cases(window) -> None:
    case = window.case_service.create_case("最近案件")
    window.refresh_cases()
    assert window.home_recent.count() == 1
    assert case.title in window.home_recent.item(0).text()


@pytest.mark.parametrize(
    "tab,empty_text",
    [
        ("線索", "尚未加入已確認線索"),
        ("Evidence", "尚未匯入證據"),
        ("調查目標", "尚未設定調查目標"),
        ("調查計畫", "尚未產生 Plan"),
        ("Execution", "尚無執行時間軸"),
        ("Graph", "尚無 Graph"),
        ("Report", "尚無報告版本"),
    ],
)
def test_actionable_empty_states(window, tab, empty_text) -> None:
    case = window.case_service.create_case(f"Empty {tab}")
    window.open_case(case.case_id)
    assert empty_text in window.tab_views[tab].toPlainText()


def test_workflow_next_action_goals(window) -> None:
    case = window.case_service.create_case("Next")
    window.open_case(case.case_id)
    window.next_workflow_action()
    assert window.workspace_tabs.currentIndex() == WORKSPACE_TABS.index("調查目標")


def test_workflow_next_action_plan(window) -> None:
    case = window.case_service.create_case("Plan")
    window.case_service.add_goal(
        case.case_id, "identify_main_sources", "找出主要資金來源"
    )
    window.open_case(case.case_id)
    window.next_workflow_action()
    assert window.workspace_tabs.currentIndex() == WORKSPACE_TABS.index("調查計畫")


def test_no_engineering_names_in_primary_goal_ui(window) -> None:
    labels = [window.goal_type.itemText(i) for i in range(window.goal_type.count())]
    assert all("_" not in item for item in labels)
    assert "找出主要資金來源" in labels


def test_execution_unknown_total_has_no_percentage(window) -> None:
    case = window.case_service.create_case("Unknown total")
    window.open_case(case.case_id)
    text = window.tab_views["Execution"].toPlainText()
    assert "總量未知" in text
    assert "%" not in text


def test_result_asset_cards_separated(window) -> None:
    case = window.case_service.create_case("Assets")
    result = window.case_service.result(case.case_id).model_copy(
        update={"assets": ["TRX", "USDT"]}
    )
    html = window._render_result(result)
    assert "TRX" in html and "USDT" in html
    assert "不與其他資產加總" in html


def test_candidate_and_confirmed_visual_distinction() -> None:
    assert "#302A52" in LIGHT_THEME
    assert "#123C3B" in LIGHT_THEME
    assert "#D0C4FF" in LIGHT_THEME
    assert "#7EE7D5" in LIGHT_THEME


def test_escape_has_no_execution_cancel_shortcut(window) -> None:
    shortcuts = window.findChildren(__import__("PySide6.QtGui", fromlist=["QShortcut"]).QShortcut)
    assert all(item.key().toString() != "Esc" for item in shortcuts)


def test_keyboard_workflow_shortcuts(window) -> None:
    shortcuts = {
        item.key().toString()
        for item in window.findChildren(
            __import__("PySide6.QtGui", fromlist=["QShortcut"]).QShortcut
        )
    }
    assert {"Ctrl+N", "Ctrl+O", "Ctrl+S", "Ctrl+Enter"} <= shortcuts


def test_traditional_chinese_primary_navigation(window) -> None:
    labels = [window.navigation.item(i).text() for i in range(window.navigation.count())]
    assert labels == ["首頁", "案件清單", "建立案件", "設定"]


def test_ai_disabled_card(window) -> None:
    assert not window.setting_ai.isChecked()
    assert "不顯示" in window.credential_status.text()


def test_workspace_uses_readable_stage_navigation(window) -> None:
    assert window.workspace_tabs.tabPosition() == QTabWidget.North
    assert window.workspace_tabs.tabBar().usesScrollButtons()


def test_no_raw_json_on_empty_primary_pages(window) -> None:
    case = window.case_service.create_case("Readable")
    window.open_case(case.case_id)
    for page in ("案情", "調查目標", "調查計畫", "Result"):
        text = window.tab_views[page].toPlainText()
        assert not text.lstrip().startswith("{")
        assert not text.lstrip().startswith("[")
