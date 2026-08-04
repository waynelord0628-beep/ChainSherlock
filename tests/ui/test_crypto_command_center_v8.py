from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QPushButton, QSizePolicy, QTabWidget

from crypto_investigator.ui.main_window import MainWindow, WORKSPACE_TABS
from crypto_investigator.ui.theme import CRYPTO_INVESTIGATION_THEME
from crypto_investigator.ui.widgets import (
    AssetBadge,
    ChainBadge,
    MonoValueLabel,
    StatusBadge,
    abbreviate_chain_value,
)


@pytest.fixture
def window(qtbot, tmp_path):
    item = MainWindow(tmp_path / "cases", tmp_path / "settings.json")
    qtbot.addWidget(item)
    item.show()
    return item


@pytest.mark.parametrize(
    "token",
    [
        "CRYPTO",
        "#0B1220",
        "#2DD4BF",
        "#60A5FA",
        "#A78BFA",
        "#F59E0B",
        '"Cascadia Mono"',
        "QFrame#queueItem",
        "QLabel#chainBadge",
        "QLabel#assetBadge",
    ],
)
def test_crypto_investigation_theme_tokens(token) -> None:
    content = CRYPTO_INVESTIGATION_THEME
    if token == "CRYPTO":
        assert "QMainWindow" in content
    else:
        assert token in content


def test_hero_has_investigation_semantics(window) -> None:
    text = " ".join(label.text() for label in window.home_page.findChildren(
        __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
    ))
    assert "鏈上線索" in text
    assert "EVIDENCE-BASED" in text
    assert "HASH-VERIFIED" in text


def test_investigation_queue_empty_state(window) -> None:
    assert window.home_recent_stack.currentWidget() is window.home_recent_empty
    text = " ".join(label.text() for label in window.home_recent_empty.findChildren(
        __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
    ))
    assert "尚無調查案件" in text
    assert "CSV／Excel Evidence" in text


@pytest.mark.parametrize(
    "chain,expected", [("ethereum", "ETH"), ("tron", "TRON"), ("bitcoin", "BTC"), ("evm", "EVM")]
)
def test_chain_badges(qtbot, chain, expected) -> None:
    badge = ChainBadge(chain)
    qtbot.addWidget(badge)
    assert badge.text() == expected
    assert badge.objectName() == "chainBadge"


@pytest.mark.parametrize("asset", ["USDT", "ETH", "TRX", "BTC", "USDC"])
def test_asset_badges(qtbot, asset) -> None:
    badge = AssetBadge(asset.lower())
    qtbot.addWidget(badge)
    assert badge.text() == asset


@pytest.mark.parametrize(
    "value",
    [
        "0x1234567890abcdef1234567890abcdef12345678",
        "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE",
        "a" * 64,
    ],
)
def test_chain_values_abbreviate_and_preserve_copy(qtbot, value) -> None:
    label = MonoValueLabel(value)
    qtbot.addWidget(label)
    assert label.text() != value
    assert "…" in label.text()
    assert label.property("copyValue") == value
    assert label.toolTip() == value


def test_short_values_are_not_corrupted() -> None:
    assert abbreviate_chain_value("TX HASH") == "TX HASH"


def test_system_readiness_entries(window) -> None:
    assert {
        "TronGrid", "Etherscan", "Blockscout", "Blockstream", "Local Pipeline",
        "Case Workspace", "Cache", "Audit Chain", "AI", "PDF CJK Font",
    } == set(window.home_status_badges)


def test_provider_not_configured_is_not_error(window, monkeypatch) -> None:
    monkeypatch.delenv("TRONGRID_API_KEY", raising=False)
    row = next(item for item in window._system_readiness() if item[0] == "TronGrid")
    assert row[1:3] == ("not_configured", "未設定")


def test_blockscout_fallback_explanation(window) -> None:
    row = next(item for item in window._system_readiness() if item[0] == "Etherscan")
    assert "Blockscout fallback" in row[3]


@pytest.mark.parametrize(
    "provider,text",
    [("Blockscout", "程式支援"), ("Blockstream", "公開服務")],
)
def test_public_provider_support_is_not_verified(window, provider, text) -> None:
    row = next(item for item in window._system_readiness() if item[0] == provider)
    assert row[1] == "supported"
    assert row[2] == text
    assert "未驗證" in row[3] or "未測試" in row[3]


def test_supported_badge_uses_cold_blue_semantics() -> None:
    assert "QLabel#supported" in CRYPTO_INVESTIGATION_THEME
    supported_rule = CRYPTO_INVESTIGATION_THEME.split("QLabel#supported", 1)[1].split("}", 1)[0]
    assert "#173553" in supported_rule
    assert "#123C3B" not in supported_rule


def test_ai_is_disabled_with_deterministic_fallback(window) -> None:
    row = next(item for item in window._system_readiness() if item[0] == "AI")
    assert row[1] == "disabled"
    assert "Deterministic fallback" in row[3]


def test_audit_chain_is_verified(window) -> None:
    assert window.home_status_badges["Audit Chain"].text() == "已驗證"


def test_pdf_font_status_does_not_expose_path(window) -> None:
    rows = window._system_readiness()
    pdf = next(item for item in rows if item[0] == "PDF CJK Font")
    assert ":\\" not in pdf[3]
    assert "/Users/" not in pdf[3]


def test_execution_idle_is_compact(window) -> None:
    assert window.global_execution_badge.text() == "IDLE"
    assert "目前沒有執行中的工作" in window.global_execution_title.text()
    assert not window.global_execution_progress.isVisible()
    assert not window.global_execution_actions.isVisible()


def test_empty_state_actions_stay_with_message(window) -> None:
    buttons = window.home_recent_empty.findChildren(QPushButton)
    assert {button.text() for button in buttons} == {"建立新案件", "開啟案件清單"}
    message = next(
        item for item in window.home_recent_empty.findChildren(
            __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
        )
        if "CSV／Excel Evidence" in item.text()
    )
    assert max(button.geometry().top() for button in buttons) >= message.geometry().bottom()


def test_english_helper_text_has_readable_size_and_contrast() -> None:
    eyebrow_rule = CRYPTO_INVESTIGATION_THEME.split(
        "QLabel#brandSubtitle, QLabel#eyebrow", 1
    )[1].split("}", 1)[0]
    assert "font-size: 11px" in eyebrow_rule
    assert "#7DD3FC" in eyebrow_rule


def test_execution_running_event_has_records_elapsed_and_artifacts(window, monkeypatch) -> None:
    monkeypatch.setattr("crypto_investigator.ui.main_window.time.monotonic", lambda: 15.0)
    window._execution_started_at = 3.0
    window._apply_execution_event(
        SimpleNamespace(
            stage="provider_fetch",
            message="fetch_transactions",
            provider="Blockstream",
            capability="address_transactions",
            current_records=40,
            total_records_if_known=None,
            artifacts=["artifacts/provider_status.json"],
            status="running",
        )
    )
    assert "Blockstream" in window.global_execution_detail.text()
    assert "40 records" in window.global_execution_meta.text()
    assert "00:00:12" in window.global_execution_meta.text()
    assert "Artifacts：1" in window.global_execution_meta.text()
    assert window.global_execution_progress.maximum() == 0
    assert "%" not in window.global_execution_meta.text()


def test_execution_long_content_is_bounded_and_available_in_tooltip(window, monkeypatch) -> None:
    monkeypatch.setattr("crypto_investigator.ui.main_window.time.monotonic", lambda: 5.0)
    window._execution_started_at = 0.0
    long_step = "非常長的調查執行步驟名稱" * 8
    window._apply_execution_event(
        SimpleNamespace(
            stage=long_step,
            message=long_step,
            provider="Blockscout fallback provider",
            capability="address_transactions",
            current_records=2,
            total_records_if_known=None,
            artifacts=[],
            status="partial",
        )
    )
    assert long_step in window.global_execution_detail.toolTip()
    assert window.global_execution_detail.maximumHeight() > 0
    assert window.global_execution_badge.text() == "PARTIAL"
    assert window.global_execution_progress.maximum() == 0


@pytest.mark.parametrize(
    "status",
    ["confirmed", "observation", "candidate", "partial", "warning", "failed"],
)
def test_semantic_statuses_are_textual(qtbot, status) -> None:
    badge = StatusBadge()
    qtbot.addWidget(badge)
    badge.set_status(status)
    assert badge.text() == status
    assert badge.objectName() == status


def test_workspace_uses_fourteen_investigation_stages() -> None:
    assert WORKSPACE_TABS == (
        "案情", "線索", "Evidence", "調查目標", "調查計畫", "Execution",
        "Result", "Investigation", "Counterparty", "Graph", "Narrative",
        "Report", "Review", "Audit",
    )


def test_workspace_stage_labels_are_horizontal_and_scrollable(window) -> None:
    assert window.workspace_tabs.tabPosition() == QTabWidget.North
    assert window.workspace_tabs.tabBar().usesScrollButtons()


def test_workspace_badge_does_not_expand_vertically(window) -> None:
    assert window.workspace_badge.sizePolicy().verticalPolicy() == QSizePolicy.Fixed
    case = window.case_service.create_case("Badge semantics")
    window.open_case(case.case_id)
    assert window.workspace_badge.text() == "進行中"
    assert window.workspace_badge.height() < window.workspace_header.parentWidget().height()


@pytest.mark.parametrize(
    "status,expected",
    [
        ("proposed", "待確認"),
        ("approved", "已核准"),
        ("confirmed", "已確認"),
        ("unknown", "未知"),
    ],
)
def test_plan_and_workspace_statuses_are_human_readable(status, expected) -> None:
    from crypto_investigator.ui.main_window import _STATUS_ZH

    assert _STATUS_ZH[status] == expected


def test_evidence_integrity_and_monospace(window, tmp_path) -> None:
    case = window.case_service.create_case("Evidence UI")
    source = tmp_path / "fixture.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    window.case_service.import_evidence(case.case_id, source)
    case = window.repository.load(case.case_id)
    html = window._render_evidence(case)
    assert "SHA-256 INTEGRITY" in html
    assert "verified" in html.lower()
    assert "class='mono'" in html


def test_graph_keeps_local_workspace_boundary(window) -> None:
    case = window.case_service.create_case("Graph boundary")
    html = window._render_graph(window.case_service.result(case.case_id))
    assert "LOCAL WORKSPACE ONLY" not in html or "NO EXTERNAL URL" in html
    assert "http://" not in html and "https://" not in html


def test_report_format_badges(window) -> None:
    case = window.case_service.create_case("Report badges")
    window.case_service.reports = lambda case_id: [
        {
            "report_version": 1,
            "status": "complete",
            "created_at": "2026-01-01T00:00:00+00:00",
            "files": {
                "case_report.md": "reports/case_report.md",
                "case_report.html": "reports/case_report.html",
                "case_report.docx": "reports/case_report.docx",
                "case_report.pdf": "reports/case_report.pdf",
                "case_report_data.json": "reports/case_report_data.json",
            },
        }
    ]
    rendered = window._render_reports(case)
    for format_name in ("MD", "HTML", "DOCX", "PDF"):
        assert f"class='format'>{format_name}</span>" in rendered
    assert "CASE_REPORT_DATA.JSON" not in rendered
    assert "完整" in rendered


def test_narrative_fallback_uses_dark_theme_semantic_card(window) -> None:
    rendered = window._render_narrative(None)
    assert "card limitation" in rendered
    assert "#fff7ed" not in rendered.lower()


def test_review_status_is_human_readable(window) -> None:
    case = window.case_service.create_case("Review semantics")
    rendered = window._render_review(case)
    assert "尚未覆核" in rendered
    assert "Not Reviewed" not in rendered


def test_audit_timeline_shows_hash_chain_without_full_hash(window) -> None:
    case = window.case_service.create_case("Audit UI")
    text = window._render_audit(case)
    assert "CHAIN VERIFIED" in text
    assert "PREV" in text and "HASH" in text
    assert "…" in text


@pytest.mark.parametrize(
    "secret",
    ["sk-proj-secret-value", "Authorization: Bearer hidden", "api_key=hidden"],
)
def test_home_does_not_render_secrets(window, secret) -> None:
    assert secret not in window.home_page.objectName()
    visible = " ".join(
        item.text() for item in window.home_page.findChildren(
            __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
        )
    )
    assert secret not in visible


@pytest.mark.parametrize("width,height", [(1366, 768), (1600, 900), (1920, 1080), (980, 680)])
def test_supported_window_sizes_keep_primary_actions(window, qtbot, width, height) -> None:
    window.resize(width, height)
    qtbot.wait(20)
    buttons = {
        item.text(): item
        for item in window.home_page.findChildren(QPushButton)
    }
    assert buttons["＋ 建立新案件"].isVisible()
    assert buttons["開啟案件清單"].isVisible()
    assert window.home_metric_cards["cases"].geometry().width() > 0


@pytest.mark.parametrize("scale", [1.25, 1.5])
def test_dpi_key_text_is_complete(window, scale) -> None:
    font = window.font()
    font.setPointSizeF(font.pointSizeF() * scale)
    window.setFont(font)
    assert window.global_execution_title.text() == "目前沒有執行中的工作"
    assert window.home_recent_empty.findChildren(
        __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
    )[0].text() == "尚無調查案件"


def test_no_fake_case_data_or_external_asset_in_theme() -> None:
    forbidden = ("TR5WMA", "0x123456", "bc1q", "http://", "https://", "url(")
    assert all(item not in CRYPTO_INVESTIGATION_THEME for item in forbidden)


def test_keyboard_focus_has_explicit_style() -> None:
    assert "QPushButton:focus" in CRYPTO_INVESTIGATION_THEME
