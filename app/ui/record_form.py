"""The data-entry form: 日期 / 車牌 / 金額 / 項目 (+ optional 公里數, 備註).

Used both on the 新增紀錄 page and in the 修改紀錄 dialog."""
from typing import Optional

from app.ui.style import sized
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal

from app.db import Database, DataError, normalize_plate
from app.ui.items import ItemManagerDialog, add_item_flow, delete_item_flow, rename_item_flow
from app.ui.widgets import DatePicker, ItemGrid, button, fmt_date, fmt_money, label

def customer_card_text(db: Database, plate: str, exclude_id: Optional[int] = None) -> str:
    """Summary of one car: how often it comes, total spent, last visit details."""
    s = db.plate_summary(plate)
    if not s:
        return ""
    head = f"{s['plate']}　共來過 {s['visits']} 次，總共 {fmt_money(s['total'])}"
    if s["visits"] > 1 and s["avg_interval_days"]:
        head += f"，平均約每 {s['avg_interval_days']} 天來一次（第一次 {fmt_date(s['first_date'])}）"
    lines = [head]
    last = db.last_record_for_plate(plate, exclude_id=exclude_id)
    if last:
        ago = s["days_since_last"] if exclude_id is None else None
        ago_txt = f"，{ago} 天前" if ago else ("，今天" if ago == 0 else "")
        km = f"，{last['mileage']:,} 公里" if last.get("mileage") else ""
        lines.append(f"上次來：{fmt_date(last['date'])}{ago_txt}　金額 {fmt_money(last['amount'])}{km}")
        done = f"上次做了：{'、'.join(last['item_names']) or '（沒有選項目）'}"
        if last.get("note"):
            done += f"　備註：{last['note']}"
        lines.append(done)
    return "\n".join(lines)


PLATE_RE = QtCore.QRegExp(r"[A-Za-z0-9\- ]{0,12}")


class RecordForm(QtWidgets.QWidget):
    items_changed = pyqtSignal()   # an item was added from the form
    date_changed = pyqtSignal(str)
    show_history = pyqtSignal(str)  # user wants all records of this plate

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
        sized(self.plate, "setMaximumWidth", 380)
        self.plate.textEdited.connect(self._upper_plate)
        self.plate.textChanged.connect(self._update_last_visit)
        form.addWidget(self.plate, row, 1)
        row += 1
        # shown by the parent page (right-hand panel or dialog)
        self.last_visit = label("", "info")
        self.last_visit.hide()
        self.history_btn = button("看這台車的全部紀錄",
                                  slot=lambda: self.show_history.emit(normalize_plate(self.plate.text())))
        self.history_btn.hide()

        # 金額
        form.addWidget(label("金額", "field"), row, 0)
        amount_row = QtWidgets.QHBoxLayout()
        self.amount = QtWidgets.QLineEdit()
        self.amount.setPlaceholderText("例如 1500")
        self.amount.setValidator(QtGui.QIntValidator(0, 99_999_999, self.amount))
        sized(self.amount, "setMaximumWidth", 380)
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
        self.items.manage_requested.connect(self._manage_items)
        self.items.rename_requested.connect(self._rename_item)
        self.items.delete_requested.connect(self._delete_item)
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
        sized(self.mileage, "setMaximumWidth", 260)
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
        card = customer_card_text(self.db, text, exclude_id=self.editing_id) \
            if len(normalize_plate(text)) >= 3 else ""
        self.last_visit.setText(card)
        self.last_visit.setVisible(bool(card))
        self.history_btn.setVisible(bool(card) and self.editing_id is None)

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
