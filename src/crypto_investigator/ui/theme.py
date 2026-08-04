CRYPTO_INVESTIGATION_THEME = """
* { font-family: "Segoe UI", "Microsoft JhengHei UI"; font-size: 13px; }
QMainWindow, QWidget { background: #0B1220; color: #D9E4F0; }
QScrollArea, QScrollArea > QWidget > QWidget { background:#0B1220; border:0; }
QLabel { background: transparent; }
QToolTip { background:#172235; color:#E6EDF7; border:1px solid #334155; padding:5px; }
QFrame#sidebar { background: #0A101C; border-right: 1px solid #223047; }
QFrame#sidebar QLabel { background: transparent; color: #D9E4F0; }
QLabel#brand { color: #F1F5F9; font-size: 20px; font-weight: 700; }
QLabel#brandSubtitle, QLabel#eyebrow {
  color: #5EEAD4; font-family: "Consolas"; font-size: 10px; font-weight: 600;
}
QListWidget#navigation {
  background: transparent; color: #AAB8CA; border: 0; outline: 0;
}
QListWidget#navigation::item {
  margin: 3px 6px; padding: 11px 12px; border-radius: 5px;
}
QListWidget#navigation::item:hover { background: #132035; color: #E6EDF7; }
QListWidget#navigation::item:selected {
  background: #12313A; color: #D6FFFA; font-weight: 600;
  border-left: 3px solid #2DD4BF;
}
QFrame#card, QFrame#metricCard, QFrame#heroCard, QFrame#sectionCard {
  background: #111B2B; border: 1px solid #26364D; border-radius: 9px;
}
QFrame#heroCard { background: #0E1B2B; border-color: #285665; }
QFrame#emptyState {
  background:#0E1828; border:1px dashed #334A65; border-radius:8px;
}
QFrame#queueItem { background:#111B2B; border:1px solid #26364D; border-radius:7px; }
QFrame#metricCard[accent="teal"] { border-top: 2px solid #2DD4BF; }
QFrame#metricCard[accent="blue"] { border-top: 2px solid #60A5FA; }
QFrame#metricCard[accent="amber"] { border-top: 2px solid #F59E0B; }
QFrame#metricCard[accent="violet"] { border-top: 2px solid #A78BFA; }
QLabel#pageTitle { font-size: 25px; font-weight: 700; color: #F1F5F9; }
QLabel#sectionTitle { font-size: 16px; font-weight: 650; color: #E6EDF7; }
QLabel#muted { color: #8FA1B7; }
QLabel#metricValue { font-size: 27px; font-weight: 700; color: #E6FFFB; }
QLabel#metricLabel { color: #B8C6D8; font-size: 12px; }
QLabel#monoValue {
  color:#B9F5EC; font-family:"Cascadia Mono","Consolas","Courier New";
}
QLabel#chainBadge, QLabel#assetBadge {
  background:#172A40; color:#BFE8FF; border:1px solid #31506C;
  border-radius:8px; padding:3px 7px; font-family:"Consolas"; font-size:11px;
}
QLabel#chainBadge[chain="tron"] { color:#F4B4B4; border-color:#704048; }
QLabel#chainBadge[chain="eth"] { color:#C8C7FF; border-color:#515284; }
QLabel#chainBadge[chain="btc"] { color:#F8D59A; border-color:#73562D; }
QPushButton {
  background: #13796F; color: #F1FFFD; border: 1px solid #229A8E;
  padding: 8px 15px; border-radius: 5px; font-weight: 600;
}
QPushButton:hover { background: #16877C; border-color:#5EEAD4; }
QPushButton:focus { border: 2px solid #7DD3FC; }
QPushButton:pressed { background: #0F625A; }
QPushButton:disabled { background: #263449; color: #718096; border-color:#334155; }
QPushButton[variant="secondary"] {
  background: #142033; color: #C7D4E5; border: 1px solid #3A4C65;
}
QPushButton[variant="secondary"]:hover { background: #1A2A40; border-color: #5A718F; }
QPushButton[variant="danger"] { background: #813B42; border-color:#A4515A; }
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QTableView, QListWidget {
  background: #0D1726; color:#D9E4F0; border: 1px solid #2B3B52;
  border-radius: 5px; padding: 6px;
  selection-background-color: #155E75; selection-color: #ECFEFF;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {
  border: 2px solid #2DD4BF;
}
QHeaderView::section {
  background: #142033; color: #93A8C0; border: 0;
  border-bottom: 1px solid #304159; padding: 8px; font-weight: 600;
}
QTableView { gridline-color: #26364D; alternate-background-color: #101C2D; }
QTabWidget::pane { border: 1px solid #26364D; background: #0D1726; border-radius: 7px; }
QTabBar::tab {
  background: transparent; color: #8294AA; min-width: 138px;
  padding: 10px 12px; margin: 1px 0; text-align: left;
}
QTabBar::tab:hover { color:#C5D2E2; background:#111E30; }
QTabBar::tab:selected {
  background: #12313A; color: #9FF5E8; font-weight: 650;
  border-left: 3px solid #2DD4BF;
}
QProgressBar {
  background: #243147; border: 0; border-radius: 3px; min-height: 6px; max-height: 6px;
  color:transparent;
}
QProgressBar::chunk { background: #2DD4BF; border-radius: 3px; }
QStatusBar { background: #0A101C; color: #8799AF; border-top: 1px solid #223047; }
QLabel#available, QLabel#configured, QLabel#confirmed, QLabel#completed, QLabel#verified {
  color:#7EE7D5; background:#123C3B; border:1px solid #21645F; padding:3px 8px; border-radius:8px;
}
QLabel#observation, QLabel#running, QLabel#ready {
  color:#A5D8FF; background:#173553; border:1px solid #285E87; padding:3px 8px; border-radius:8px;
}
QLabel#candidate { color:#D0C4FF; background:#302A52; border:1px solid #554B82; padding:3px 8px; border-radius:8px; }
QLabel#partial, QLabel#warning { color:#F7D08A; background:#49361C; border:1px solid #765625; padding:3px 8px; border-radius:8px; }
QLabel#failed, QLabel#error, QLabel#mismatch { color:#F2A6AD; background:#49242A; border:1px solid #75363E; padding:3px 8px; border-radius:8px; }
QLabel#pending, QLabel#unknown, QLabel#not_configured, QLabel#disabled,
QLabel#cancelled, QLabel#skipped, QLabel#unavailable, QLabel#missing {
  color:#AAB8CA; background:#263247; border:1px solid #3B4A61; padding:3px 8px; border-radius:8px;
}
"""

# Compatibility alias retained for existing integrations.
LIGHT_THEME = CRYPTO_INVESTIGATION_THEME
