"""車輛資訊 card: how often a car comes, how much it spent, and its last visit."""
from typing import Optional

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal

from app.db import Database, normalize_plate
from app.ui.style import sized
from app.ui.widgets import Card, Tile, button, divider, fmt_date, fmt_money, label


class CustomerCard(Card):
    show_history = pyqtSignal(str)

    def __init__(self, db: Database, compact: bool = False, parent=None):
        super().__init__("" if compact else "車輛資訊", parent)
        self.db = db
        self.compact = compact
        self._plate = ""

        self.empty = label("輸入車牌後，這裡會顯示這台車以前來保養的紀錄。", "empty")
        self.add(self.empty)

        self.body = QtWidgets.QWidget()
        body = QtWidgets.QVBoxLayout(self.body) if not compact else QtWidgets.QHBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        sized(body, "setSpacing", 14 if not compact else 24)

        # plate + badge + link
        head_w = QtWidgets.QWidget()
        head = QtWidgets.QVBoxLayout(head_w) if compact else QtWidgets.QHBoxLayout(head_w)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self.plate = label("", "plate")
        self.badge = label("", "badge")
        head.addWidget(self.plate)
        head.addWidget(self.badge, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        if not compact:
            head.addStretch(1)
        self.more = button("看這台車的全部紀錄 ›", slot=lambda: self.show_history.emit(self._plate))
        if compact:
            head.addStretch(1)
        body.addWidget(head_w)

        # stat tiles
        tiles = QtWidgets.QHBoxLayout()
        sized(tiles, "setSpacing", 10)
        self.t_visits = Tile("來店次數")
        self.t_total = Tile("累計消費")
        self.t_every = Tile("平均間隔")
        for t in (self.t_visits, self.t_total, self.t_every):
            tiles.addWidget(t, 1)
        tiles_w = QtWidgets.QWidget()
        tiles_w.setLayout(tiles)
        tiles.setContentsMargins(0, 0, 0, 0)
        body.addWidget(tiles_w, 3 if compact else 0)

        # last visit
        last_w = QtWidgets.QWidget()
        last = QtWidgets.QVBoxLayout(last_w)
        last.setContentsMargins(0, 0, 0, 0)
        last.setSpacing(6)
        if not compact:
            last.addWidget(divider())
        last.addWidget(label("上次保養", "field"))
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        self.rows = {}
        for r, key in enumerate(["日期", "金額", "公里數", "項目", "備註"]):
            k = label(key, "rowkey")
            k.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            v = label("", "rowval", wrap=True)
            grid.addWidget(k, r, 0)
            grid.addWidget(v, r, 1)
            self.rows[key] = (k, v)
        last.addLayout(grid)
        body.addWidget(last_w, 4 if compact else 0)
        if not compact:
            body.addWidget(self.more)

        self.add(self.body)
        if not compact:
            self.lay.addStretch(1)
        self.body.hide()

    def set_plate(self, plate: str, exclude_id: Optional[int] = None):
        plate = normalize_plate(plate)
        self._plate = plate
        s = self.db.plate_summary(plate) if len(plate) >= 3 else None
        if not s:
            self.body.hide()
            self.empty.setText(
                f"找不到「{plate}」以前的紀錄，這是新客人。" if len(plate) >= 3
                else "輸入車牌後，這裡會顯示這台車以前來保養的紀錄。")
            self.empty.show()
            self.setVisible(not self.compact)
            return
        self.setVisible(True)
        self.empty.hide()
        self.body.show()
        self.plate.setText(s["plate"])
        self.badge.setText("常客" if s["visits"] >= 3 else "")
        self.badge.setVisible(s["visits"] >= 3)
        self.t_visits.set(f"{s['visits']} 次")
        self.t_total.set(fmt_money(s["total"]))
        self.t_every.set(f"{s['avg_interval_days']} 天" if s["avg_interval_days"] else "—")

        last = self.db.last_record_for_plate(plate, exclude_id=exclude_id)
        if not last:
            for k, v in self.rows.values():
                k.hide()
                v.hide()
            return
        ago = (QtCore.QDate.fromString(last["date"], "yyyy-MM-dd")
               .daysTo(QtCore.QDate.currentDate()))
        ago_txt = "今天" if ago == 0 else (f"{ago} 天前" if ago > 0 else "")
        values = {
            "日期": f"{fmt_date(last['date'])}　{ago_txt}",
            "金額": fmt_money(last["amount"]),
            "公里數": f"{last['mileage']:,} 公里" if last.get("mileage") else "",
            "項目": "、".join(last["item_names"]) or "（沒有選項目）",
            "備註": last.get("note") or "",
        }
        for key, (k, v) in self.rows.items():
            v.setText(values[key])
            k.setVisible(bool(values[key]))
            v.setVisible(bool(values[key]))
