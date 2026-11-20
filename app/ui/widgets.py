"""Reusable elder-friendly widgets: message boxes, date picker, item grid."""
from typing import Iterable, List, Optional

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QDate, pyqtSignal

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def set_role(widget: QtWidgets.QWidget, role: str) -> QtWidgets.QWidget:
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def label(text: str, role: Optional[str] = None) -> QtWidgets.QLabel:
    lb = QtWidgets.QLabel(text)
    if role:
        lb.setProperty("role", role)
    lb.setWordWrap(role in ("hint", "info"))
    return lb


def button(text: str, role: Optional[str] = None, slot=None) -> QtWidgets.QPushButton:
    b = QtWidgets.QPushButton(text)
    if role:
        b.setProperty("role", role)
    b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setFocusPolicy(QtCore.Qt.NoFocus if role in ("item", "nav") else QtCore.Qt.StrongFocus)
    if slot is not None:
        b.clicked.connect(slot)
    return b


def fmt_date(iso: str) -> str:
    d = QDate.fromString(iso, "yyyy-MM-dd")
    if not d.isValid():
        return iso
    return f"{d.toString('yyyy/MM/dd')} ({WEEKDAYS[d.dayOfWeek() - 1]})"


def fmt_money(n) -> str:
    try:
        return f"${int(n):,}"
    except (TypeError, ValueError):
        return ""


# ----------------------------------------------------------------- messages
def _box(parent, icon, title, text, buttons):
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    created = [box.addButton(t, r) for t, r in buttons]
    box.setDefaultButton(created[0])
    box.exec_()
    return created.index(box.clickedButton()) if box.clickedButton() in created else -1


def info(parent, text: str, title: str = "完成") -> None:
    _box(parent, QtWidgets.QMessageBox.Information, title, text,
         [("知道了", QtWidgets.QMessageBox.AcceptRole)])


def warn(parent, text: str, title: str = "請注意") -> None:
    _box(parent, QtWidgets.QMessageBox.Warning, title, text,
         [("知道了", QtWidgets.QMessageBox.AcceptRole)])


def ask(parent, text: str, title: str = "請確認", yes: str = "是", no: str = "否") -> bool:
    return _box(parent, QtWidgets.QMessageBox.Question, title, text,
                [(no, QtWidgets.QMessageBox.RejectRole),
                 (yes, QtWidgets.QMessageBox.AcceptRole)]) == 1


def ask_text(parent, title: str, prompt: str, text: str = "") -> Optional[str]:
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title)
    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(16)
    lay.addWidget(label(prompt, "field"))
    edit = QtWidgets.QLineEdit(text)
    edit.setMinimumWidth(420)
    lay.addWidget(edit)
    row = QtWidgets.QHBoxLayout()
    row.addStretch(1)
    row.addWidget(button("取消", slot=dlg.reject))
    ok = button("確定", "primary", dlg.accept)
    row.addWidget(ok)
    lay.addLayout(row)
    edit.returnPressed.connect(dlg.accept)
    edit.selectAll()
    if dlg.exec_() == QtWidgets.QDialog.Accepted:
        return edit.text().strip()
    return None


# -------------------------------------------------------------- date picking
class CalendarDialog(QtWidgets.QDialog):
    def __init__(self, parent, date: QDate):
        super().__init__(parent)
        self.setWindowTitle("選擇日期")
        lay = QtWidgets.QVBoxLayout(self)
        self.cal = QtWidgets.QCalendarWidget()
        self.cal.setLocale(QtCore.QLocale(QtCore.QLocale.Chinese, QtCore.QLocale.Taiwan))
        self.cal.setGridVisible(True)
        self.cal.setFirstDayOfWeek(QtCore.Qt.Sunday)
        self.cal.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)
        self.cal.setSelectedDate(date)
        self.cal.setMinimumSize(560, 420)
        self.cal.activated.connect(lambda _d: self.accept())
        lay.addWidget(self.cal)
        lay.addWidget(label("點一下日期，再按「確定」。", "hint"))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(button("今天", slot=lambda: self.cal.setSelectedDate(QDate.currentDate())))
        row.addStretch(1)
        row.addWidget(button("取消", slot=self.reject))
        row.addWidget(button("確定", "primary", self.accept))
        lay.addLayout(row)

    def selected(self) -> QDate:
        return self.cal.selectedDate()


class DatePicker(QtWidgets.QWidget):
    """[◀ 前一天] [2026/11/20 (五)] [後一天 ▶] [今天]"""

    changed = pyqtSignal(str)

    def __init__(self, parent=None, show_today: bool = True):
        super().__init__(parent)
        self._date = QDate.currentDate()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(button("◀ 前一天", slot=lambda: self.set_date(self._date.addDays(-1))))
        self.btn = button("", "date", self._pick)
        self.btn.setToolTip("點一下可以從月曆選日期")
        lay.addWidget(self.btn)
        lay.addWidget(button("後一天 ▶", slot=lambda: self.set_date(self._date.addDays(1))))
        if show_today:
            lay.addWidget(button("今天", slot=lambda: self.set_date(QDate.currentDate())))
        lay.addStretch(1)
        self._refresh()

    def _pick(self):
        dlg = CalendarDialog(self, self._date)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.set_date(dlg.selected())

    def _refresh(self):
        self.btn.setText(fmt_date(self.iso()))

    def set_date(self, d: QDate):
        if isinstance(d, str):
            d = QDate.fromString(d, "yyyy-MM-dd")
        if not d.isValid() or d == self._date:
            return
        self._date = d
        self._refresh()
        self.changed.emit(self.iso())

    def iso(self) -> str:
        return self._date.toString("yyyy-MM-dd")


class OptionalDateButton(QtWidgets.QPushButton):
    """A date button that can also be empty ("不限")."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._date: Optional[QDate] = None
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.clicked.connect(self._pick)
        self.setMinimumWidth(260)
        self._refresh()

    def _pick(self):
        dlg = CalendarDialog(self, self._date or QDate.currentDate())
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.set_date(dlg.selected())

    def _refresh(self):
        self.setText(fmt_date(self.iso()) if self._date else "不限")

    def set_date(self, d: Optional[QDate], emit: bool = True):
        self._date = d if (d is not None and d.isValid()) else None
        self._refresh()
        if emit:
            self.changed.emit()

    def iso(self) -> Optional[str]:
        return self._date.toString("yyyy-MM-dd") if self._date else None


# ------------------------------------------------------------------ item grid
class ItemGrid(QtWidgets.QWidget):
    """Big toggle buttons, one per service item, plus a 「＋ 新增項目」 button."""

    add_requested = pyqtSignal()

    def __init__(self, parent=None, max_columns: int = 5):
        super().__init__(parent)
        self.max_columns = max_columns
        self.columns = 3
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.buttons: List[QtWidgets.QPushButton] = []
        self.add_btn = button("＋ 新增項目", "additem", self.add_requested.emit)
        self.add_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

    def set_items(self, items: Iterable[dict], keep_selection: bool = True):
        selected = set(self.selected_ids()) if keep_selection else set()
        for b in self.buttons:
            self.grid.removeWidget(b)
            b.hide()
            b.setParent(None)
            b.deleteLater()
        self.buttons = []
        for it in items:
            b = button(it["name"], "item")
            b.setCheckable(True)
            b.setProperty("item_id", it["id"])
            b.setProperty("item_name", it["name"])
            b.toggled.connect(lambda on, btn=b: self._decorate(btn))
            b.setChecked(it["id"] in selected)
            self._decorate(b)
            b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            self.buttons.append(b)
        self._relayout(force=True)

    def _best_columns(self) -> int:
        widgets = self.buttons + [self.add_btn]
        cell = max(w.sizeHint().width() for w in widgets) + self.grid.spacing()
        width = self.width() if self.width() > 50 else 700
        return max(2, min(self.max_columns, width // max(cell, 1)))

    def _relayout(self, force: bool = False):
        cols = self._best_columns()
        if cols == self.columns and not force:
            return
        self.columns = cols
        for w in self.buttons + [self.add_btn]:
            self.grid.removeWidget(w)
        for i, w in enumerate(self.buttons + [self.add_btn]):
            self.grid.addWidget(w, i // cols, i % cols)
            w.show()
        for c in range(self.max_columns):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def changeEvent(self, event):  # font size changed via stylesheet
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.StyleChange, QtCore.QEvent.FontChange):
            QtCore.QTimer.singleShot(0, lambda: self._relayout(force=True))

    @staticmethod
    def _decorate(b: QtWidgets.QPushButton):
        name = b.property("item_name")
        b.setText(f"✔ {name}" if b.isChecked() else name)

    def selected_ids(self) -> List[int]:
        return [b.property("item_id") for b in self.buttons if b.isChecked()]

    def set_selected(self, ids: Iterable[int]):
        ids = set(ids)
        for b in self.buttons:
            b.setChecked(b.property("item_id") in ids)

    def clear(self):
        self.set_selected([])


def make_table(headers: List[str]) -> QtWidgets.QTableWidget:
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    t.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(44)
    t.setWordWrap(True)
    return t


def table_item(text: str, data=None, align_right: bool = False) -> QtWidgets.QTableWidgetItem:
    it = QtWidgets.QTableWidgetItem(text)
    if data is not None:
        it.setData(QtCore.Qt.UserRole, data)
    if align_right:
        it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    else:
        it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    return it
