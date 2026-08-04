from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QPushButton

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
    assert "class='format'" in window._html("Report", "<span class='format'>PDF</span>")


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
