"""The data-entry form: 日期 / 車牌 / 金額 / 項目 (+ optional 公里數, 備註).

Used both on the 新增紀錄 page and in the 修改紀錄 dialog."""
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal

from app.db import Database, DataError, normalize_plate
from app.ui.items import ItemManagerDialog, add_item_flow, delete_item_flow, rename_item_flow
from app.ui.style import sized
from app.ui.widgets import DatePicker, ItemGrid, button, label

PLATE_RE = QtCore.QRegExp(r"[A-Za-z0-9\- ]{0,12}")


def _int_validator(top: int, parent) -> QtGui.QIntValidator:
    """Digits only: C locale and no group separators (zh_TW would allow "1,500")."""
    v = QtGui.QIntValidator(0, top, parent)
    loc = QtCore.QLocale.c()
    loc.setNumberOptions(QtCore.QLocale.RejectGroupSeparator)
    v.setLocale(loc)
    return v


class RecordForm(QtWidgets.QWidget):
    items_changed = pyqtSignal()   # an item was added / renamed / deleted from the form
    date_changed = pyqtSignal(str)
    plate_changed = pyqtSignal(str)

    def __init__(self, db: Database, parent=None, editing_id: Optional[int] = None):
        super().__init__(parent)
        self.db = db
        self.editing_id = editing_id
        self._record_item_ids = []  # items on the record being edited (they keep a chip even once deleted)

        form = QtWidgets.QGridLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        sized(form, "setHorizontalSpacing", 18)
        sized(form, "setVerticalSpacing", 16)
        form.setColumnStretch(1, 1)

        def key(text):
            lb = label(text, "field")
            lb.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            sized(lb, "setMinimumWidth", 64)
            return lb

        # 日期
        form.addWidget(key("日期"), 0, 0)
        self.date = DatePicker()
        self.date.changed.connect(self.date_changed.emit)
        form.addWidget(self.date, 0, 1)

        # 車牌
        form.addWidget(key("車牌"), 1, 0)
        self.plate = QtWidgets.QLineEdit()
        self.plate.setPlaceholderText("例如 ABC-1234")
        self.plate.setValidator(QtGui.QRegExpValidator(PLATE_RE, self.plate))
        sized(self.plate, "setMaximumWidth", 360)
        self.plate.textEdited.connect(self._upper_plate)
        self.plate.textChanged.connect(lambda t: self.plate_changed.emit(t))
        form.addWidget(self.plate, 1, 1)

        # 金額
        form.addWidget(key("金額"), 2, 0)
        amount_row = QtWidgets.QHBoxLayout()
        self.amount = QtWidgets.QLineEdit()
        self.amount.setPlaceholderText("例如 1500")
        self.amount.setValidator(_int_validator(99_999_999, self.amount))
        sized(self.amount, "setMaximumWidth", 360)
        amount_row.addWidget(self.amount)
        amount_row.addWidget(label("元", "muted", wrap=False))
        amount_row.addStretch(1)
        form.addLayout(amount_row, 2, 1)
        self.plate.returnPressed.connect(self.amount.setFocus)

        # 項目
        form.addWidget(key("項目"), 3, 0)
        items_head = QtWidgets.QHBoxLayout()
        items_head.addWidget(label("綠色＝已選", "muted", wrap=False))
        items_head.addStretch(1)
        items_head.addWidget(button("＋ 新增項目", "link", self._add_item))
        items_head.addWidget(button("管理項目", "link", self._manage_items))
        form.addLayout(items_head, 3, 1)
        self.items = ItemGrid()
        self.items.rename_requested.connect(self._rename_item)
        self.items.delete_requested.connect(self._delete_item)
        form.addWidget(self.items, 4, 1)

        # optional: 公里數 + 備註 on one row
        form.addWidget(key("公里數"), 5, 0)
        opt = QtWidgets.QHBoxLayout()
        sized(opt, "setSpacing", 12)
        self.mileage = QtWidgets.QLineEdit()
        self.mileage.setProperty("role", "small")
        self.mileage.setPlaceholderText("可不填")
        self.mileage.setValidator(_int_validator(9_999_999, self.mileage))
        sized(self.mileage, "setMaximumWidth", 200)
        opt.addWidget(self.mileage)
        opt.addSpacing(10)
        opt.addWidget(label("備註", "field"))
        self.note = QtWidgets.QLineEdit()
        self.note.setProperty("role", "small")
        self.note.setPlaceholderText("可不填")
        opt.addWidget(self.note, 1)
        form.addLayout(opt, 5, 1)

        self.reload_items(keep_selection=False)

    # --------------------------------------------------------------- helpers
    def _upper_plate(self, text: str):
        up = text.upper()
        if up != text:
            pos = self.plate.cursorPosition()
            self.plate.setText(up)
            self.plate.setCursorPosition(pos)

    def _after_items_changed(self, select_id=None):
        selected = self.items.selected_ids() + ([select_id] if select_id else [])
        self.reload_items(keep_selection=False)
        self.items.set_selected(selected)
        self.items_changed.emit()

    def _add_item(self):
        new_id = add_item_flow(self, self.db)
        if new_id is not None:
            self._after_items_changed(new_id)

    def _rename_item(self, item_id, name):
        if rename_item_flow(self, self.db, item_id, name):
            self._after_items_changed()

    def _delete_item(self, item_id, name):
        if delete_item_flow(self, self.db, item_id, name):
            self._after_items_changed()

    def _manage_items(self):
        dlg = ItemManagerDialog(self.db, self)
        dlg.manager.changed.connect(self._after_items_changed)
        dlg.exec_()

    def reload_items(self, keep_selection: bool = True):
        active = self.db.list_items()
        extra = []
        if self._record_item_ids:
            # deleted items that are on the record being edited keep their chip
            # (also when deleted during this edit), otherwise saving would
            # silently drop them from the record
            ids = {i["id"] for i in active}
            extra = [i for i in self.db.list_items(include_hidden=True)
                     if i["id"] in self._record_item_ids and i["id"] not in ids]
        self.items.set_items(active + extra, keep_selection=keep_selection)

    # ---------------------------------------------------------------- public
    def values(self) -> dict:
        """Return form values or raise DataError (and focus the bad field)."""
        if not normalize_plate(self.plate.text()):
            self.plate.setFocus()
            raise DataError("請輸入車牌。")
        if not self.amount.text().strip():
            self.amount.setFocus()
            raise DataError("請輸入金額。")
        km = self.mileage.text().replace(",", "").strip()
        if km and not km.isdigit():
            self.mileage.setFocus()
            raise DataError("公里數只能填數字。")
        return {
            "date": self.date.iso(),
            "plate": self.plate.text(),
            "amount": self.amount.text(),  # parsed and checked by the database layer
            "item_ids": self.items.selected_ids(),
            "mileage": int(km) if km else None,
            "note": self.note.text(),
        }

    def load(self, rec: dict):
        self.editing_id = rec["id"]
        self.date.set_date(rec["date"])
        self.plate.setText(rec["plate"])
        self.amount.setText(str(rec["amount"]))
        self.mileage.setText(str(rec["mileage"]) if rec.get("mileage") is not None else "")
        self.note.setText(rec.get("note") or "")
        self._record_item_ids = list(rec["item_ids"])
        self.reload_items(keep_selection=False)
        self.items.set_selected(rec["item_ids"])

    def clear(self):
        """Clear everything except the date (several cars are entered per day)."""
        self.plate.clear()
        self.amount.clear()
        self.mileage.clear()
        self.note.clear()
        self.items.clear()
        self.plate.setFocus()
