from PyQt5 import QtCore, QtWidgets

from app import config
from app.db import Database
from app.ui.pages import BackupPage, HistoryPage, NewRecordPage, SettingsPage
from app.ui.style import build_stylesheet
from app.ui.widgets import button


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle(f"{config.APP_NAME}")
        central = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        nav = QtWidgets.QHBoxLayout()
        nav.setSpacing(12)
        self.stack = QtWidgets.QStackedWidget()
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)

        self.new_page = NewRecordPage(db)
        self.history_page = HistoryPage(db)
        self.backup_page = BackupPage(db)
        self.settings_page = SettingsPage(db)
        self.pages = [("新增紀錄", self.new_page), ("查詢紀錄", self.history_page),
                      ("備份 / 還原", self.backup_page), ("設定", self.settings_page)]
        for i, (title, page) in enumerate(self.pages):
            b = button(title, "nav")
            b.setCheckable(True)
            b.setMinimumWidth(200)
            self.group.addButton(b, i)
            nav.addWidget(b)
            self.stack.addWidget(page)
            page.data_changed.connect(self._on_data_changed)
        nav.addStretch(1)
        self.group.buttonClicked[int].connect(self.show_page)
        root.addLayout(nav)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        root.addWidget(line)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.backup_page.restored.connect(self._on_data_changed)
        self.settings_page.font_size_changed.connect(self.set_font_size)
        self.apply_font_size()
        self.show_page(0)

    def show_page(self, index: int):
        self.group.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        self.pages[index][1].refresh()

    def _on_data_changed(self):
        for _t, page in self.pages:
            if page is not self.stack.currentWidget():
                page.refresh()
        # items may have changed: keep the new-record form in sync too
        self.new_page.refresh()

    def apply_font_size(self):
        name = self.settings_page.font_size_name()
        QtWidgets.QApplication.instance().setStyleSheet(
            build_stylesheet(config.FONT_SIZES[name]))

    def set_font_size(self, name: str):
        self.db.set_setting("font_size", name)
        self.apply_font_size()
        self.settings_page.refresh()
