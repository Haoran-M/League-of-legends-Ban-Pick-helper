STYLE = """
QWidget { background: #10151e; color: #e5ecf7; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background: #10151e; }
QLabel#title { font-size: 24px; font-weight: 700; }
QLabel#subtitle, QLabel#muted { color: #9aaac1; }
QLabel#badge { color: #8ee5c0; background: #17342e; border-radius: 5px; padding: 7px 12px; font-weight: 600; }
QLabel#section { font-size: 16px; font-weight: 650; }
QFrame#panel { background: #161e2b; border: 1px solid #2a374b; border-radius: 8px; }
QFrame#panel QLabel, QFrame#panel QCheckBox { background: transparent; }
QLabel#blueTitle { color: #8cc8ff; font-weight: 700; font-size: 17px; }
QLabel#redTitle { color: #ffabb8; font-weight: 700; font-size: 17px; }
QPushButton { background: #202c3e; border: 1px solid #34445b; border-radius: 5px; padding: 8px 10px; }
QPushButton:hover { background: #2c3e56; border-color: #7a9bbe; }
QPushButton:pressed { background: #36516b; }
QPushButton:disabled { color: #68788f; background: #192231; }
QPushButton[active="true"] { background: #183c50; border: 2px solid #6cd6ed; color: #c4f3ff; }
QPushButton#pickSlot { text-align: left; padding: 4px 6px; min-height: 30px; }
QPushButton#banSlot { padding: 2px 1px; min-height: 40px; font-size: 11px; }
QLineEdit, QComboBox { background: #111a27; border: 1px solid #42546e; border-radius: 5px; padding: 7px; }
QLineEdit:focus, QComboBox:focus, QPushButton:focus { border: 2px solid #6cd6ed; }
QComboBox QAbstractItemView { background: #1c283a; selection-background-color: #315674; }
QListWidget { background: #111a27; border: 1px solid #2b3a50; border-radius: 6px; padding: 6px; }
QListWidget::item { background: #202d40; border: 1px solid #334760; border-radius: 6px; margin: 3px; padding: 2px; }
QListWidget::item:hover { background: #2c435d; border-color: #8ab9d9; }
QListWidget::item:selected { background: #234f66; border: 2px solid #6cd6ed; color: white; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QStatusBar { border-top: 1px solid #2b3a50; }
QSplitter::handle { background: #10151e; width: 10px; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #202c3e; color: #b7c8df; padding: 9px 20px; margin-right: 5px; border-radius: 4px; }
QTabBar::tab:selected { background: #234f66; color: #d8f4ff; }
QTableWidget, QPlainTextEdit { background: #111a27; border: 1px solid #34445b; selection-background-color: #24536c; }
QHeaderView::section { background: #202c3e; color: #d4e4f6; border: 0; padding: 8px; }
QTableWidget::item { padding: 6px; }
QScrollBar:vertical { background: #141e2c; width: 12px; }
QScrollBar::handle:vertical { background: #425670; min-height: 32px; border-radius: 5px; }
"""
