from __future__ import annotations

import json
import os
import tempfile
import tracemalloc
from pathlib import Path
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from crypto_investigator.ui.app import create_application
from crypto_investigator.ui.main_window import MainWindow
from crypto_investigator.ui.models import RecordsTableModel
from crypto_investigator.ui.case_wizard import CaseWizard


def measured(operation):
    started = perf_counter()
    value = operation()
    return value, round((perf_counter() - started) * 1000, 3)


def run() -> dict:
    tracemalloc.start()
    with tempfile.TemporaryDirectory(prefix="chainsherlock_ui_") as temporary:
        root = Path(temporary)
        _, startup_ms = measured(lambda: create_application([]))
        window, render_ms = measured(lambda: MainWindow(root / "cases", root / "ui.json"))
        wizard, wizard_ms = measured(CaseWizard)
        for index in range(100):
            window.case_service.create_case(f"Benchmark case {index:03d}")
        _, list_ms = measured(window.refresh_cases)
        case_id = window._case_ids[0]
        _, open_ms = measured(lambda: window.open_case(case_id))
        case = window.repository.load(case_id)
        result = window.case_service.result(case_id)
        _, home_ms = measured(window.refresh_cases)
        _, plan_ms = measured(lambda: window._render_plan(case))
        _, execution_ms = measured(lambda: window._render_execution(case))
        _, result_ms = measured(lambda: window._render_result(result))
        _, investigation_ms = measured(lambda: window._render_investigation(result))
        _, graph_ms = measured(lambda: window._render_graph(result))
        _, report_ms = measured(lambda: window._render_reports(case))
        evidence_rows = [
            [f"evidence_{index}", f"file_{index}.csv", "a" * 64, index]
            for index in range(1_000)
        ]
        _, evidence_ms = measured(
            lambda: RecordsTableModel(["ID", "File", "SHA-256", "Size"], evidence_rows)
        )
        counterparties = [
            [index, f"T{index:033d}", "tron", index % 100]
            for index in range(10_000)
        ]
        model, counterparties_ms = measured(
            lambda: RecordsTableModel(["Rank", "Address", "Chain", "Count"], counterparties)
        )
        _, sort_ms = measured(lambda: model.sort(1))
        current, peak = tracemalloc.get_traced_memory()
        window.close()
        wizard.close()
    tracemalloc.stop()
    return {
        "cold_startup_ms": startup_ms,
        "main_window_render_ms": render_ms,
        "home_render_ms": home_ms,
        "wizard_open_ms": wizard_ms,
        "case_list_100_rows_ms": list_ms,
        "case_open_ms": open_ms,
        "plan_render_ms": plan_ms,
        "execution_timeline_render_ms": execution_ms,
        "result_dashboard_render_ms": result_ms,
        "investigation_tree_render_ms": investigation_ms,
        "graph_page_render_ms": graph_ms,
        "report_preview_render_ms": report_ms,
        "evidence_model_1000_rows_ms": evidence_ms,
        "counterparty_model_10000_rows_ms": counterparties_ms,
        "counterparty_sort_10000_rows_ms": sort_ms,
        "current_memory_mb": round(current / 1024 / 1024, 3),
        "peak_memory_mb": round(peak / 1024 / 1024, 3),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
