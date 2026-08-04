from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from crypto_investigator.ui.main_window import MainWindow


def create_application(argv: list[str] | None = None) -> QApplication:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
    application = QApplication.instance()
    if application is None:
        application = QApplication(argv if argv is not None else sys.argv)
    application.setApplicationName("ChainSherlock")
    application.setOrganizationName("ChainSherlock")
    return application


def launch_ui(case_root: Path | str = "cases") -> int:
    application = create_application()
    window = MainWindow(case_root=case_root)
    window.show()
    return application.exec()
