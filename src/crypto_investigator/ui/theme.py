LIGHT_THEME = """
QMainWindow, QWidget { background: #f5f7fa; color: #172033; }
QFrame#sidebar { background: #16233a; color: white; }
QListWidget#navigation { background: #16233a; color: #dce7f7; border: 0; }
QListWidget#navigation::item { padding: 10px; }
QListWidget#navigation::item:selected { background: #245ea8; color: white; }
QPushButton { background: #245ea8; color: white; padding: 7px 12px; border-radius: 4px; }
QPushButton:disabled { background: #9aa7b8; }
QLineEdit, QComboBox, QPlainTextEdit, QTableView {
  background: white; border: 1px solid #cbd5e1; border-radius: 3px; padding: 4px;
}
QLabel#candidate { color: #9a5a00; }
QLabel#confirmed { color: #146c43; font-weight: 600; }
QLabel#partial { color: #9a5a00; font-weight: 600; }
QLabel#failed { color: #b42318; font-weight: 600; }
"""
