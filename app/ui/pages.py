"""The main pages: 新增紀錄 / 查詢紀錄 / 報表統計 / 備份還原 / 設定."""
import datetime as _dt
import os

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QDate, pyqtSignal

from app import backup, config
from app.db import Database, DataError
from app.ui import pdf
from app.ui.customer_card import CustomerCard
from app.ui.items import ItemManager
from app.ui.record_form import RecordForm
from app.ui.style import sized
from app.ui.widgets import (Card, OptionalDateButton, Segmented, Tile, ask, button, fit_to_screen,
                            fill_table, fmt_date, fmt_money, info, label, make_table, table_item, warn)


def documents_dir() -> str:
    path = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
    return path or os.path.expanduser("~")


def scrollable(inner: QtWidgets.QWidget, hscroll: bool = False) -> QtWidgets.QScrollArea:
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(
        QtCore.Qt.ScrollBarAsNeeded if hscroll else QtCore.Qt.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


def page_layout(widget, kind=QtWidgets.QVBoxLayout):
    lay = kind(widget)
    sized(lay, "setContentsMargins", 20, 16, 20, 16)
    sized(lay, "setSpacing", 16)
    return lay


class Page(QtWidgets.QWidget):
    data_changed = pyqtSignal()  # records or items changed; other pages refresh

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

    def refresh(self):
        pass


# =================================================================== 新增紀錄
class NewRecordPage(Page):
    open_history = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        outer = page_layout(self, QtWidgets.QHBoxLayout)

        # left: the form card (form scrolls, buttons always visible)
        form_card = Card("新增保養紀錄")
        self.form = RecordForm(db)
        self.form.items_changed.connect(self.data_changed.emit)
        self.form.date_changed.connect(lambda _d: self.refresh_day())
        holder = QtWidgets.QWidget()
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 10, 0)
        hl.addWidget(self.form)
        hl.addStretch(1)
        form_card.add(scrollable(holder), 1)
        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(button("清除重填", slot=self.form.clear))
        btns.addStretch(1)
        self.save_btn = button("儲存紀錄", "primary", self._save)
        sized(self.save_btn, "setMinimumWidth", 260)
        btns.addWidget(self.save_btn)
        form_card.add(btns)
        outer.addWidget(form_card, 13)

        # right: customer info + the day's records (scrolls as a whole)
        side = QtWidgets.QWidget()
        sl = QtWidgets.QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 4, 0)
        sized(sl, "setSpacing", 16)
        self.customer = CustomerCard(db)
        self.customer.show_history.connect(self.open_history.emit)
        self._card_timer = QtCore.QTimer(self)
        self._card_timer.setSingleShot(True)
        self._card_timer.setInterval(250)  # update the card once typing pauses
        self._card_timer.timeout.connect(lambda: self.customer.set_plate(self.form.plate.text()))
        self.form.plate_changed.connect(lambda _t: self._card_timer.start())
        sl.addWidget(self.customer)
        day_card = Card("今天的紀錄")
        self.day_title = day_card.title
        self.day_table = make_table(["車牌", "金額", "項目"])
        hh = self.day_table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        sized(self.day_table, "setMinimumHeight", 200)
        day_card.add(self.day_table, 1)
        self.day_total = label("", "total")
        day_card.add(self.day_total)
        sl.addWidget(day_card, 1)
        outer.addWidget(scrollable(side), 8)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, self._save)
        self._clock = QtCore.QTimer(self)  # app may stay open overnight
        self._clock.setInterval(60_000)
        self._clock.timeout.connect(self.form.date.roll_to_today)
        self._clock.start()
        self.refresh_day()

    def refresh(self):
        self.form.date.roll_to_today()
        self.form.reload_items(keep_selection=True)
        self.customer.set_plate(self.form.plate.text())
        self.refresh_day()

    def refresh_day(self):
        iso = self.form.date.iso()
        recs = self.db.search_records(date_from=iso, date_to=iso)
        is_today = iso == QDate.currentDate().toString("yyyy-MM-dd")
        self.day_title.setText("今天的紀錄" if is_today else f"{fmt_date(iso)} 的紀錄")
        fill_table(self.day_table, [(r["plate"], fmt_money(r["amount"]), "、".join(r["item_names"]))
                                    for r in recs], right=(1,))
        total = sum(r["amount"] for r in recs)
        self.day_total.setText(f"共 {len(recs)} 台　合計 {fmt_money(total)}")

    def _save(self):
        try:
            v = self.form.values()
            if not v["item_ids"] and not ask(
                    self, "還沒有選擇任何項目。\n\n確定要這樣儲存嗎？", yes="直接儲存", no="回去選項目"):
                return
            self.db.add_record(**v)
        except DataError as e:
            warn(self, str(e))
            return
        info(self, f"已儲存！\n\n車牌：{v['plate'].upper()}\n金額：{fmt_money(v['amount'])}", "儲存成功")
        self.form.clear()
        self.refresh_day()
        self.data_changed.emit()


# ============================================================= 修改紀錄 dialog
class EditRecordDialog(QtWidgets.QDialog):
    def __init__(self, db: Database, rec: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.rec = rec
        self.items_added = False
        self.setWindowTitle("修改紀錄")
        lay = QtWidgets.QVBoxLayout(self)
        sized(lay, "setContentsMargins", 20, 16, 20, 16)
        sized(lay, "setSpacing", 14)
        card = Card("修改紀錄")
        self.form = RecordForm(db, editing_id=rec["id"])
        self.form.load(rec)
        self.form.items_changed.connect(lambda: setattr(self, "items_added", True))
        holder = QtWidgets.QWidget()
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 10, 0)
        hl.addWidget(self.form)
        hl.addStretch(1)
        card.add(scrollable(holder), 1)
        lay.addWidget(card, 1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(button("取消", slot=self.reject))
        row.addStretch(1)
        save = button("儲存修改", "primary", self._save)
        sized(save, "setMinimumWidth", 240)
        row.addWidget(save)
        lay.addLayout(row)
        fit_to_screen(self, 1100, 820)

    def _save(self):
        try:
            v = self.form.values()
            self.db.update_record(self.rec["id"], **v)
        except DataError as e:
            warn(self, str(e))
            return
        self.accept()


# =================================================================== 查詢紀錄
class HistoryPage(Page):
    HEADERS = ["日期", "車牌", "金額", "項目", "公里數", "備註"]
    PAGE_SIZE = 200          # rows loaded at a time (keeps old PCs fast)
    PDF_WARN_ROWS = 3000     # PDFs bigger than this take long to make

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        inner = QtWidgets.QWidget()
        lay = page_layout(inner)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

        # filters
        filters = Card("查詢紀錄")
        filters.add_header_widget(button("清除條件", "link", self._reset))
        row = QtWidgets.QHBoxLayout()
        sized(row, "setSpacing", 10)
        row.addWidget(label("車牌", "field"))
        self.plate = QtWidgets.QLineEdit()
        self.plate.setPlaceholderText("可只打一部分")
        sized(self.plate, "setMaximumWidth", 300)
        self.plate.textEdited.connect(self._upper)
        # wait until the user stops typing before searching
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.refresh)
        self.plate.textChanged.connect(lambda _t: self._search_timer.start())
        row.addWidget(self.plate, 1)
        row.addSpacing(16)
        row.addWidget(label("日期", "field"))
        self.d_from = OptionalDateButton()
        self.d_to = OptionalDateButton()
        self.d_from.changed.connect(self._manual_date)
        self.d_to.changed.connect(self._manual_date)
        row.addWidget(self.d_from)
        row.addWidget(label("到", "muted", wrap=False))
        row.addWidget(self.d_to)
        row.addStretch(1)
        filters.add(row)
        quick = QtWidgets.QHBoxLayout()
        quick.addWidget(label("快速選擇", "muted", wrap=False))
        self.range_seg = Segmented([("today", "今天"), ("month", "這個月"), ("year", "今年"),
                                    ("all", "全部日期")])
        self.range_seg.changed.connect(self._quick_range)
        quick.addWidget(self.range_seg)
        quick.addStretch(1)
        filters.add(quick)
        lay.addWidget(filters)

        # customer summary when one car is found
        self.customer = CustomerCard(db, compact=True)
        self.customer.hide()
        lay.addWidget(self.customer)

        # results
        results = Card("")
        self.total = results.title
        self.total.setProperty("role", "total")
        self.total.show()
        results.add_header_widget(button("存成 PDF", slot=self._export))
        results.add_header_widget(button("修改", slot=self._edit))
        results.add_header_widget(button("刪除", "danger", self._delete))
        self.table = make_table(self.HEADERS)
        hh = self.table.horizontalHeader()
        for c in (0, 1, 2, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _i: self._edit())
        sized(self.table, "setMinimumHeight", 300)
        results.add(self.table, 1)
        more_row = QtWidgets.QHBoxLayout()
        self.shown_label = label("", "muted", wrap=False)
        more_row.addWidget(self.shown_label)
        more_row.addStretch(1)
        self.more_btn = button("顯示更多", slot=self._load_more)
        more_row.addWidget(self.more_btn)
        results.add(more_row)
        results.add(label("先點一下表格中的一行，再按「修改」或「刪除」。點兩下也可以直接修改。", "hint"))
        lay.addWidget(results, 1)
        self.range_seg.set_current("all")
        self.records = []

    def _upper(self, t):
        if t != t.upper():
            pos = self.plate.cursorPosition()
            self.plate.setText(t.upper())
            self.plate.setCursorPosition(pos)

    def _set_range(self, a, b):
        self.d_from.set_date(a, emit=False)
        self.d_to.set_date(b, emit=False)
        self.refresh()

    def _manual_date(self):
        self.range_seg.set_current("")
        self.refresh()

    def _quick_range(self, key):
        self.range_seg.set_current(key)
        t = QDate.currentDate()
        if key == "today":
            self._set_range(t, t)
        elif key == "month":
            self._set_range(QDate(t.year(), t.month(), 1), QDate(t.year(), t.month(), t.daysInMonth()))
        elif key == "year":
            self._set_range(QDate(t.year(), 1, 1), QDate(t.year(), 12, 31))
        else:
            self._set_range(None, None)

    def _reset(self):
        self.plate.blockSignals(True)
        self.plate.clear()
        self.plate.blockSignals(False)
        self._quick_range("all")

    def show_plate(self, plate: str):
        """Jump here from another page with a plate filled in and all dates."""
        self.range_seg.set_current("all")
        self.d_from.set_date(None, emit=False)
        self.d_to.set_date(None, emit=False)
        self.plate.blockSignals(True)
        self.plate.setText(plate)
        self.plate.blockSignals(False)
        self.refresh()

    def _filters(self):
        return self.plate.text(), self.d_from.iso(), self.d_to.iso()

    @staticmethod
    def _row(rec):
        return (fmt_date(rec["date"]), rec["plate"], fmt_money(rec["amount"]), "、".join(rec["item_names"]),
                f"{rec['mileage']:,}" if rec.get("mileage") is not None else "", rec.get("note") or "")

    def refresh(self):
        self._search_timer.stop()
        self.stats = self.db.search_stats(*self._filters())
        self.records = self.db.search_records(*self._filters(), limit=self.PAGE_SIZE)
        fill_table(self.table, [self._row(r) for r in self.records], right=(2, 4),
                   row_data=[r["id"] for r in self.records])
        self.table.scrollToTop()
        self._update_counts()
        if self.plate.text().strip() and self.stats["cars"] == 1:
            self.customer.set_plate(self.stats["plate"])
        else:
            self.customer.hide()

    def _load_more(self):
        more = self.db.search_records(*self._filters(), limit=self.PAGE_SIZE, offset=len(self.records))
        if not more:
            return
        start = len(self.records)
        self.records += more
        t = self.table
        t.setUpdatesEnabled(False)
        t.setRowCount(len(self.records))
        for i, rec in enumerate(more):
            for c, v in enumerate(self._row(rec)):
                t.setItem(start + i, c, table_item(v, rec["id"] if c == 0 else None, align_right=c in (2, 4)))
            t.resizeRowToContents(start + i)
        t.setUpdatesEnabled(True)
        self._update_counts()

    def _update_counts(self):
        st = self.stats
        self.total.setText(f"共 {st['count']:,} 筆　合計 {fmt_money(st['total'])}")
        shown = len(self.records)
        self.more_btn.setVisible(shown < st["count"])
        self.more_btn.setText(f"顯示更多（再 {min(self.PAGE_SIZE, st['count'] - shown)} 筆）")
        self.shown_label.setText(f"目前顯示最新的 {shown:,} 筆" if shown < st["count"] else "")

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.selectionModel().hasSelection():
            warn(self, "請先在表格中點一下要處理的那一行。")
            return None
        rid = self.table.item(row, 0).data(QtCore.Qt.UserRole)
        return self.db.get_record(rid)

    def _edit(self):
        rec = self._selected()
        if not rec:
            return
        dlg = EditRecordDialog(self.db, rec, self)
        changed = dlg.exec_() == QtWidgets.QDialog.Accepted
        if changed or dlg.items_added:
            self.refresh()
            self.data_changed.emit()
        if changed:
            info(self, "修改完成！")

    def _delete(self):
        rec = self._selected()
        if not rec:
            return
        text = (f"確定要刪除這筆紀錄嗎？\n\n日期：{fmt_date(rec['date'])}\n車牌：{rec['plate']}\n"
                f"金額：{fmt_money(rec['amount'])}\n\n刪除後無法復原。")
        if not ask(self, text, "刪除紀錄", yes="確定刪除", no="不要刪除"):
            return
        self.db.delete_record(rec["id"])
        self.refresh()
        self.data_changed.emit()

    def _export(self):
        if not self.records:
            warn(self, "目前沒有資料可以存成 PDF。")
            return
        if self.stats["count"] > self.PDF_WARN_ROWS and not ask(
                self, f"目前條件共有 {self.stats['count']:,} 筆紀錄，做成 PDF 會很多頁，也要等比較久。\n\n"
                      f"建議先選擇日期範圍或輸入車牌，縮小範圍。\n\n還是要全部存成 PDF 嗎？",
                yes="全部存成 PDF", no="先不要"):
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            all_records = self.db.search_records(*self._filters())
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        plate = self.plate.text().strip()
        cond = []
        if plate:
            cond.append(f"車牌：{plate}")
        cond.append(f"日期：{fmt_date(self.d_from.iso()) if self.d_from.iso() else '不限'} ～ "
                    f"{fmt_date(self.d_to.iso()) if self.d_to.iso() else '不限'}")
        lines = ["　".join(cond), self.total.text()]
        if plate and self.stats["cars"] == 1:
            s = self.db.plate_summary(self.stats["plate"])
            if s:
                every = f"，平均約每 {s['avg_interval_days']} 天來一次" if s["avg_interval_days"] else ""
                lines.append(f"{s['plate']} 共來過 {s['visits']} 次，累計 {fmt_money(s['total'])}{every}")
        rows = [self._row(r) for r in all_records]
        doc = pdf.document_html("保養紀錄", lines, ["<br>", pdf.table_html(self.HEADERS, rows, right=(2, 4))])
        name = f"保養紀錄_{plate + '_' if plate else ''}{_dt.date.today():%Y%m%d}.pdf"
        pdf.save_pdf(self, name, doc)


# =================================================================== 報表統計
class ReportPage(Page):
    open_history = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        self.mode = "month"
        self.anchor = QDate.currentDate()
        self.follows_today = True  # False after 上一期/下一期
        inner = QtWidgets.QWidget()
        lay = page_layout(inner)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

        bar = Card("")
        row = QtWidgets.QHBoxLayout()
        sized(row, "setSpacing", 10)
        self.seg = Segmented([("week", "每週"), ("month", "每月"), ("year", "每年")])
        self.seg.changed.connect(self._set_mode)
        row.addWidget(self.seg)
        row.addSpacing(16)
        self.prev_btn = button("‹ 上一個月", slot=lambda: self._step(-1))
        self.period = label("", "cardtitle")
        self.period.setAlignment(QtCore.Qt.AlignCenter)
        sized(self.period, "setMinimumWidth", 220)
        self.next_btn = button("下一個月 ›", slot=lambda: self._step(1))
        self.now_btn = button("本月", "link", self._now)
        for w in (self.prev_btn, self.period, self.next_btn, self.now_btn):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(button("存成 PDF", slot=self._export))
        bar.add(row)
        lay.addWidget(bar)

        tiles = QtWidgets.QHBoxLayout()
        sized(tiles, "setSpacing", 16)
        self.tiles = {}
        for key, cap in [("total", "營業額"), ("visits", "來店台次"), ("cars", "不同車輛"),
                         ("avg", "平均每次")]:
            card = Card("", margins=12)
            t = Tile(cap)
            t.setStyleSheet("background: transparent;")
            card.add(t)
            self.tiles[key] = t
            tiles.addWidget(card, 1)
        lay.addLayout(tiles)

        tables = QtWidgets.QHBoxLayout()
        sized(tables, "setSpacing", 16)

        def table_card(title, headers, stretch_col, stretch):
            card = Card(title)
            t = make_table(headers)
            hh = t.horizontalHeader()
            for c in range(len(headers)):
                hh.setSectionResizeMode(c, QtWidgets.QHeaderView.Stretch if c == stretch_col
                                        else QtWidgets.QHeaderView.ResizeToContents)
            sized(t, "setMinimumHeight", 260)
            card.add(t, 1)
            tables.addWidget(card, stretch)
            return t, card

        self.t_break, self.break_card = table_card("每日明細", ["日期", "台次", "金額"], 0, 4)
        self.t_items, _ = table_card("各項目次數", ["項目", "次數"], 0, 3)
        self.t_cust, _ = table_card("常來的客人", ["車牌", "次數", "金額", "最近來店"], 3, 5)
        self.t_cust.setToolTip("點兩下可以看這台車的全部紀錄")
        self.t_cust.doubleClicked.connect(self._open_customer)
        lay.addLayout(tables, 1)
        self.seg.set_current(self.mode)
        self._sync_labels()

    def _range(self):
        d = self.anchor
        if self.mode == "week":
            start = d.addDays(1 - d.dayOfWeek())  # Monday
            return start, start.addDays(6)
        if self.mode == "month":
            return QDate(d.year(), d.month(), 1), QDate(d.year(), d.month(), d.daysInMonth())
        return QDate(d.year(), 1, 1), QDate(d.year(), 12, 31)

    def _set_mode(self, mode):
        self.mode = mode
        self.seg.set_current(mode)
        self._sync_labels()
        self.refresh()

    def _sync_labels(self):
        word = {"week": ("週", "本週"), "month": ("個月", "本月"), "year": ("年", "今年")}[self.mode]
        self.prev_btn.setText(f"‹ 上一{word[0]}")
        self.next_btn.setText(f"下一{word[0]} ›")
        self.now_btn.setText(f"回到{word[1]}")

    def _step(self, n):
        self.follows_today = False
        if self.mode == "week":
            self.anchor = self.anchor.addDays(7 * n)
        elif self.mode == "month":
            self.anchor = self.anchor.addMonths(n)
        else:
            self.anchor = self.anchor.addYears(n)
        self.refresh()

    def _now(self):
        self.anchor = QDate.currentDate()
        self.follows_today = True
        self.refresh()

    def refresh(self):
        if self.follows_today:
            self.anchor = QDate.currentDate()
        start, end = self._range()
        if self.mode == "week":
            self.period.setText(f"{start.toString('yyyy/MM/dd')} ～ {end.toString('MM/dd')}")
        elif self.mode == "month":
            self.period.setText(f"{start.year()} 年 {start.month()} 月")
        else:
            self.period.setText(f"{start.year()} 年")
        today = QDate.currentDate()
        self.now_btn.setVisible(not (start <= today <= end))  # only when away from the current period
        bucket = "month" if self.mode == "year" else "day"
        r = self.db.report(start.toString("yyyy-MM-dd"), end.toString("yyyy-MM-dd"), bucket)
        self.tiles["total"].set(fmt_money(r["total"]))
        self.tiles["visits"].set(f"{r['visits']} 台次")
        self.tiles["cars"].set(f"{r['cars']} 台")
        self.tiles["avg"].set(fmt_money(round(r["total"] / r["visits"])) if r["visits"] else "—")
        self.break_card.title.setText("每月明細" if bucket == "month" else "每日明細")
        self.t_break.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem("月份" if bucket == "month" else "日期"))
        self._fill(self.t_break, [
            (f"{int(b['period'][5:7])} 月" if bucket == "month" else fmt_date(b["period"])[5:],
             str(b["visits"]), fmt_money(b["total"])) for b in r["buckets"]], right=(1, 2))
        self._fill(self.t_items, [(i["name"], f"{i['times']} 次") for i in r["items"]], right=(1,))
        self._fill(self.t_cust, [(c["plate"], f"{c['visits']} 次", fmt_money(c["total"]),
                                  c["last_date"][5:].replace("-", "/")) for c in r["customers"]], right=(1, 2))

    @staticmethod
    def _fill(table, rows, right=()):
        fill_table(table, rows, right)

    def _open_customer(self, index):
        item = self.t_cust.item(index.row(), 0)
        if item:
            self.open_history.emit(item.text())

    def _export(self):
        start, end = self._range()
        title = {"week": "每週報表", "month": "每月報表", "year": "每年報表"}[self.mode]
        t = self.tiles
        lines = [f"期間：{fmt_date(start.toString('yyyy-MM-dd'))} ～ {fmt_date(end.toString('yyyy-MM-dd'))}",
                 f"營業額：{t['total'].value.text()}　　來店台次：{t['visits'].value.text()}　　"
                 f"不同車輛：{t['cars'].value.text()}　　平均每次：{t['avg'].value.text()}"]

        def rows_of(tb):
            return [[tb.item(r, c).text() if tb.item(r, c) else "" for c in range(tb.columnCount())]
                    for r in range(tb.rowCount())]

        def headers_of(tb):
            return [tb.horizontalHeaderItem(c).text() for c in range(tb.columnCount())]

        sections = []
        for tb, name, right in [(self.t_break, self.break_card.title.text(), (1, 2)),
                                (self.t_items, "各項目次數", (1,)), (self.t_cust, "常來的客人", (1, 2))]:
            sections.append(f"<h3 style='margin:14px 0 4px 0'>{name}</h3>")
            sections.append(pdf.table_html(headers_of(tb), rows_of(tb), right))
        doc = pdf.document_html(f"{title}　{self.period.text()}", lines, sections)
        safe = self.period.text().replace("/", "").replace(" ", "").replace("～", "-")
        pdf.save_pdf(self, f"{title}_{safe}.pdf", doc)


# =================================================================== 備份還原
class BackupPage(Page):
    restored = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        inner = QtWidgets.QWidget()
        lay = page_layout(inner)

        actions = QtWidgets.QHBoxLayout()
        sized(actions, "setSpacing", 16)
        b_card = Card("備份資料")
        b_card.add(label("把全部資料存成一個備份檔。建議存到隨身碟或雲端硬碟（例如 Google 雲端硬碟、"
                         "OneDrive）。電腦壞掉時，可以在新電腦用這個檔案把資料救回來。", "hint"))
        self.last_backup = label("", "info")
        b_card.add(self.last_backup)
        b_card.lay.addStretch(1)
        b_card.add(button("備份資料（存成檔案）", "primary", self._backup))
        actions.addWidget(b_card, 1)

        r_card = Card("從備份檔還原")
        r_card.add(label("換新電腦或資料不見時使用。選擇以前存的備份檔，目前電腦上的資料會被備份檔的內容取代。", "hint"))
        r_card.add(label("還原前，程式會自動先把目前的資料另存一份，以防選錯檔案。", "hint"))
        r_card.lay.addStretch(1)
        r_card.add(button("選擇備份檔並還原", slot=self._restore))
        actions.addWidget(r_card, 1)
        lay.addLayout(actions)

        loc = Card("資料存放位置")
        loc.add_header_widget(button("打開資料夾", "link", self._open_folder))
        self.location = label("", "hint")
        self.location.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        loc.add(self.location)
        lay.addWidget(loc)
        lay.addStretch(1)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

    def refresh(self):
        last = self.db.get_setting("last_manual_backup")
        if last:
            self.last_backup.setText(f"上次備份：{last}\n{self.db.get_setting('last_manual_backup_path', '')}")
        else:
            self.last_backup.setText("還沒有備份過，建議現在備份一次。")
        self.location.setText(
            f"資料檔：{self.db.path}\n"
            f"每天開啟程式時會自動備份到：{config.auto_backup_dir()}（保留最近 {config.AUTO_BACKUP_KEEP} 天）\n"
            f"目前共有 {self.db.count_records()} 筆紀錄。")

    def _backup(self):
        name = f"汽車保養備份_{_dt.datetime.now():%Y%m%d_%H%M}.db"
        start = self.db.get_setting("last_manual_backup_dir") or documents_dir()
        if not os.path.isdir(start):
            start = documents_dir()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "選擇備份檔要存在哪裡（可選隨身碟）", os.path.join(start, name), "備份檔 (*.db)")
        if not path:
            return
        if not path.lower().endswith(".db"):
            path += ".db"
        try:
            self.db.backup_to(path)
            Database.check_backup_file(path)
        except (OSError, DataError) as e:
            warn(self, f"備份失敗！\n\n{e}\n\n請確認隨身碟有插好，或換一個位置再試一次。")
            return
        now = _dt.datetime.now().strftime("%Y/%m/%d %H:%M")
        self.db.set_setting("last_manual_backup", now)
        self.db.set_setting("last_manual_backup_path", path)
        self.db.set_setting("last_manual_backup_dir", os.path.dirname(path))
        self.refresh()
        info(self, f"備份成功！\n\n備份檔存在：\n{path}", "備份成功")

    def _restore(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "選擇要還原的備份檔", self.db.get_setting("last_manual_backup_dir") or documents_dir(),
            "備份檔 (*.db);;所有檔案 (*.*)")
        if not path:
            return
        try:
            count = Database.check_backup_file(path)
        except DataError as e:
            warn(self, str(e))
            return
        if not ask(self,
                   f"這個備份檔裡有 {count} 筆紀錄。\n\n"
                   f"還原後，目前電腦上的 {self.db.count_records()} 筆紀錄會被取代。\n\n確定要還原嗎？",
                   "還原資料", yes="確定還原", no="取消"):
            return
        try:
            safety = backup.safety_backup_before_restore(self.db, config.auto_backup_dir())
            self.db.restore_from(path)
        except (OSError, DataError) as e:
            warn(self, f"還原失敗！\n\n{e}")
            return
        self.refresh()
        self.restored.emit()
        info(self, f"還原成功！目前共有 {self.db.count_records()} 筆紀錄。\n\n"
                   f"（原本的資料已另存在：{safety}）", "還原成功")

    def _open_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(self.db.path)))


# ======================================================================= 設定
class SettingsPage(Page):
    font_size_changed = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        inner = QtWidgets.QWidget()
        cols = page_layout(inner, QtWidgets.QHBoxLayout)

        left = QtWidgets.QVBoxLayout()
        sized(left, "setSpacing", 16)
        font_card = Card("字體大小")
        font_card.add(label("字體會跟著視窗大小自動調整。覺得太小或太大，可以在這裡再調整。", "hint"))
        self.font_seg = Segmented([(n, n) for n in config.FONT_SCALES])
        self.font_seg.changed.connect(self.font_size_changed.emit)
        fs = QtWidgets.QHBoxLayout()
        fs.addWidget(self.font_seg)
        fs.addStretch(1)
        font_card.add(fs)
        left.addWidget(font_card)

        items_card = Card("保養項目")
        self.items = ItemManager(db)
        self.items.changed.connect(self.data_changed.emit)
        items_card.add(self.items)
        left.addWidget(items_card)
        left.addStretch(1)
        cols.addLayout(left, 3)

        about_card = Card("關於本程式")
        about = QtWidgets.QLabel(
            f"{config.APP_NAME}\n"
            f"版本：{config.APP_VERSION}（{config.APP_RELEASE_DATE}）\n"
            f"作者：{config.APP_AUTHOR}\n"
            f"建立年份：{config.APP_CREATED_YEAR}\n"
            f"授權：{config.APP_LICENSE}\n"
            f"Copyright © {config.APP_CREATED_YEAR} {config.APP_AUTHOR}\n\n"
            f"本程式以 MIT 授權釋出，詳見：\n{config.APP_LICENSE_URL}")
        about.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        about.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        about_card.add(about)
        right = QtWidgets.QVBoxLayout()
        right.addWidget(about_card)
        right.addStretch(1)
        cols.addLayout(right, 2)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

    def refresh(self):
        self.font_seg.set_current(self.font_size_name())
        self.items.refresh()

    def font_size_name(self) -> str:
        name = self.db.get_setting("font_size")
        return name if name in config.FONT_SCALES else config.DEFAULT_FONT_SIZE
