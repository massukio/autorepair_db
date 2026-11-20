"""The data-entry form: 日期 / 車牌 / 金額 / 項目 (+ optional 公里數, 備註).

Used both on the 新增紀錄 page and in the 修改紀錄 dialog."""
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal

from app.db import Database, DataError, normalize_plate
from app.ui.widgets import DatePicker, ItemGrid, ask_text, fmt_date, fmt_money, label, warn

PLATE_RE = QtCore.QRegExp(r"[A-Za-z0-9\- ]{0,12}")


class RecordForm(QtWidgets.QWidget):
    items_changed = pyqtSignal()   # an item was added from the form
    date_changed = pyqtSignal(str)

    def __init__(self, db: Database, parent=None, editing_id: Optional[int] = None):
        super().__init__(parent)
        self.db = db
        self.editing_id = editing_id

        form = QtWidgets.QGridLayout(self)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        form.setColumnStretch(1, 1)
        row = 0

        # 日期
        form.addWidget(label("日期", "field"), row, 0)
        self.date = DatePicker()
        self.date.changed.connect(self.date_changed.emit)
        form.addWidget(self.date, row, 1)
        row += 1

        # 車牌
        form.addWidget(label("車牌", "field"), row, 0)
        self.plate = QtWidgets.QLineEdit()
        self.plate.setPlaceholderText("例如 ABC-1234")
        self.plate.setValidator(QtGui.QRegExpValidator(PLATE_RE, self.plate))
        self.plate.setMaximumWidth(380)
        self.plate.textEdited.connect(self._upper_plate)
        self.plate.textChanged.connect(self._update_last_visit)
        form.addWidget(self.plate, row, 1)
        row += 1
        # shown by the parent page (right-hand panel or dialog)
        self.last_visit = label("", "info")
        self.last_visit.hide()

        # 金額
        form.addWidget(label("金額", "field"), row, 0)
        amount_row = QtWidgets.QHBoxLayout()
        self.amount = QtWidgets.QLineEdit()
        self.amount.setPlaceholderText("例如 1500")
        self.amount.setValidator(QtGui.QIntValidator(0, 99_999_999, self.amount))
        self.amount.setMaximumWidth(380)
        amount_row.addWidget(self.amount)
        amount_row.addWidget(label("元"))
        amount_row.addStretch(1)
        form.addLayout(amount_row, row, 1)
        row += 1
        self.plate.returnPressed.connect(self.amount.setFocus)

        # 項目
        lb = label("項目", "field")
        lb.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        form.addWidget(lb, row, 0)
        items_box = QtWidgets.QVBoxLayout()
        items_box.addWidget(label("點一下選擇（變綠色＝有選），再點一次取消。", "hint"))
        self.items = ItemGrid()
        self.items.add_requested.connect(self._add_item)
        items_box.addWidget(self.items)
        form.addLayout(items_box, row, 1)
        row += 1

        # optional
        form.addWidget(label("公里數"), row, 0)
        km_row = QtWidgets.QHBoxLayout()
        self.mileage = QtWidgets.QLineEdit()
        self.mileage.setProperty("role", "small")
        self.mileage.setPlaceholderText("可不填")
        self.mileage.setValidator(QtGui.QIntValidator(0, 9_999_999, self.mileage))
        self.mileage.setMaximumWidth(260)
        km_row.addWidget(self.mileage)
        km_row.addWidget(label("公里"))
        km_row.addStretch(1)
        form.addLayout(km_row, row, 1)
        row += 1

        form.addWidget(label("備註"), row, 0)
        self.note = QtWidgets.QLineEdit()
        self.note.setProperty("role", "small")
        self.note.setPlaceholderText("可不填")
        form.addWidget(self.note, row, 1)

        self.reload_items(keep_selection=False)

    # --------------------------------------------------------------- helpers
    def _upper_plate(self, text: str):
        up = text.upper()
        if up != text:
            pos = self.plate.cursorPosition()
            self.plate.setText(up)
            self.plate.setCursorPosition(pos)

    def _update_last_visit(self, text: str):
        rec = self.db.last_record_for_plate(text, exclude_id=self.editing_id) \
            if len(normalize_plate(text)) >= 3 else None
        if not rec:
            self.last_visit.hide()
            return
        items = "、".join(rec["item_names"]) or "（沒有選項目）"
        km = f"，{rec['mileage']:,} 公里" if rec.get("mileage") else ""
        self.last_visit.setText(
            f"這台車上次來：\n{fmt_date(rec['date'])}　{fmt_money(rec['amount'])}{km}\n項目：{items}"
        )
        self.last_visit.show()

    def _add_item(self):
        name = ask_text(self, "新增項目", "請輸入新的項目名稱：")
        if not name:
            return
        try:
            new_id = self.db.add_item(name)
        except DataError as e:
            warn(self, str(e))
            return
        self.reload_items(keep_selection=True)
        self.items.set_selected(self.items.selected_ids() + [new_id])
        self.items_changed.emit()

    def reload_items(self, keep_selection: bool = True):
        self.items.set_items(self.db.list_items(), keep_selection=keep_selection)

    # ---------------------------------------------------------------- public
    def values(self) -> dict:
        """Return form values or raise DataError (and focus the bad field)."""
        if not normalize_plate(self.plate.text()):
            self.plate.setFocus()
            raise DataError("請輸入車牌。")
        if not self.amount.text().strip():
            self.amount.setFocus()
            raise DataError("請輸入金額。")
        km = self.mileage.text().strip()
        return {
            "date": self.date.iso(),
            "plate": self.plate.text(),
            "amount": int(self.amount.text()),
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
        # hidden items that are on this record still need a button while editing
        items = self.db.list_items()
        active = {i["id"] for i in items}
        extra = [{"id": iid, "name": name} for iid, name in zip(rec["item_ids"], rec["item_names"])
                 if iid not in active]
        self.items.set_items(items + extra, keep_selection=False)
        self.items.set_selected(rec["item_ids"])

    def clear(self):
        """Clear everything except the date (several cars are entered per day)."""
        self.plate.clear()
        self.amount.clear()
        self.mileage.clear()
        self.note.clear()
        self.items.clear()
        self.plate.setFocus()
