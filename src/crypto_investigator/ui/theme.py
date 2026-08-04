LIGHT_THEME = """
* { font-family: "Segoe UI", "Microsoft JhengHei UI"; font-size: 13px; }
QMainWindow, QWidget { background: #F4F6F8; color: #1F2937; }
QLabel { background: transparent; }
QFrame#sidebar { background: #1F2937; border: 0; }
QFrame#sidebar QLabel { background: transparent; color: #E5E7EB; }
QLabel#brand { color: #FFFFFF; font-size: 19px; font-weight: 700; }
QLabel#brandSubtitle { color: #9CA3AF; font-size: 11px; }
QListWidget#navigation {
  background: transparent; color: #CBD5E1; border: 0; outline: 0;
}
QListWidget#navigation::item {
  margin: 3px 8px; padding: 11px 12px; border-radius: 7px;
}
QListWidget#navigation::item:hover { background: #374151; color: #FFFFFF; }
QListWidget#navigation::item:selected {
  background: #0F766E; color: #FFFFFF; font-weight: 600;
}
QFrame#card, QFrame#metricCard, QFrame#heroCard, QFrame#sectionCard {
  background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
}
QFrame#heroCard { background: #F0FDFA; border-color: #99F6E4; }
QLabel#pageTitle { font-size: 25px; font-weight: 700; color: #111827; }
QLabel#sectionTitle { font-size: 16px; font-weight: 650; color: #1F2937; }
QLabel#muted { color: #64748B; }
QLabel#metricValue { font-size: 25px; font-weight: 700; color: #0F766E; }
QLabel#metricLabel { color: #64748B; font-size: 12px; }
QPushButton {
  background: #0F766E; color: #FFFFFF; border: 0;
  padding: 8px 15px; border-radius: 6px; font-weight: 600;
}
QPushButton:hover { background: #115E59; }
QPushButton:pressed { background: #134E4A; }
QPushButton:disabled { background: #CBD5E1; color: #64748B; }
QPushButton[variant="secondary"] {
  background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1;
}
QPushButton[variant="secondary"]:hover { background: #F8FAFC; border-color: #94A3B8; }
QPushButton[variant="danger"] { background: #B42318; }
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QTableView {
  background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px;
  selection-background-color: #CCFBF1; selection-color: #134E4A;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
  border: 2px solid #14B8A6;
}
QHeaderView::section {
  background: #F8FAFC; color: #475569; border: 0;
  border-bottom: 1px solid #E2E8F0; padding: 8px; font-weight: 600;
}
QTableView { gridline-color: #EEF2F6; alternate-background-color: #F8FAFC; }
QTabWidget::pane { border: 1px solid #E2E8F0; background: #FFFFFF; border-radius: 8px; }
QTabBar::tab {
  background: transparent; color: #64748B; min-width: 135px;
  padding: 11px 14px; margin: 2px 0; text-align: left;
}
QTabBar::tab:selected {
  background: #ECFDF5; color: #0F766E; font-weight: 650;
  border-left: 3px solid #0F766E;
}
QProgressBar {
  background: #E2E8F0; border: 0; border-radius: 4px; min-height: 8px; max-height: 8px;
}
QProgressBar::chunk { background: #14B8A6; border-radius: 4px; }
QStatusBar { background: #FFFFFF; color: #64748B; border-top: 1px solid #E2E8F0; }
QLabel#confirmed { color: #166534; background: #DCFCE7; padding: 4px 8px; border-radius: 9px; }
QLabel#candidate { color: #92400E; background: #FEF3C7; padding: 4px 8px; border-radius: 9px; }
QLabel#partial, QLabel#warning { color: #9A3412; background: #FFEDD5; padding: 4px 8px; border-radius: 9px; }
QLabel#failed { color: #991B1B; background: #FEE2E2; padding: 4px 8px; border-radius: 9px; }
QLabel#running { color: #1D4ED8; background: #DBEAFE; padding: 4px 8px; border-radius: 9px; }
QLabel#completed { color: #166534; background: #DCFCE7; padding: 4px 8px; border-radius: 9px; }
QLabel#cancelled, QLabel#skipped, QLabel#unavailable {
  color: #475569; background: #E2E8F0; padding: 4px 8px; border-radius: 9px;
}
"""
