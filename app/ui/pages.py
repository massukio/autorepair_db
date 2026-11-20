"""The four main pages: 新增紀錄 / 查詢紀錄 / 備份還原 / 設定."""
import datetime as _dt
import os

from app.ui.style import sized
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QDate, pyqtSignal

from app import backup, config
from app.db import Database, DataError
from app.ui import pdf
from app.ui.items import ItemManager
from app.ui.record_form import RecordForm, customer_card_text
from app.ui.widgets import (OptionalDateButton, ask, button, fmt_date, fmt_money, info, label,
                            make_table, table_item, warn)


def documents_dir() -> str:
    path = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
    return path or os.path.expanduser("~")


def scrollable(inner: QtWidgets.QWidget, hscroll: bool = True) -> QtWidgets.QScrollArea:
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(
        QtCore.Qt.ScrollBarAsNeeded if hscroll else QtCore.Qt.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


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
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(20, 12, 20, 12)
        outer.setSpacing(24)

        # left column: title / scrollable form / buttons that are always visible
        lv = QtWidgets.QVBoxLayout()
        form_holder = QtWidgets.QWidget()
        fh = QtWidgets.QVBoxLayout(form_holder)
        fh.setContentsMargins(0, 0, 12, 0)
        self.form = RecordForm(db)
        self.form.items_changed.connect(self.data_changed.emit)
        self.form.date_changed.connect(lambda _d: self.refresh_day())
        fh.addWidget(self.form)
        fh.addStretch(1)
        lv.addWidget(scrollable(form_holder), 1)
        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(button("清除重填", slot=self._clear))
        btns.addStretch(1)
        self.save_btn = button("儲存紀錄", "primary", self._save)
        sized(self.save_btn, "setMinimumWidth", 280)
        btns.addWidget(self.save_btn)
        lv.addLayout(btns)
        outer.addLayout(lv, 5)

        right_w = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(right_w)
        right.setContentsMargins(0, 0, 8, 0)
        self.form.last_visit.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        right.addWidget(self.form.last_visit)
        right.addWidget(self.form.history_btn)
        self.form.show_history.connect(self.open_history.emit)
        self.day_title = label("", "field")
        self.day_title.setWordWrap(True)
        right.addWidget(self.day_title)
        self.day_table = make_table(["車牌", "金額", "項目"])
        hh = self.day_table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        right.addWidget(self.day_table, 1)
        self.day_total = label("", "total")
        right.addWidget(self.day_total)
        right.addWidget(label("要修改或刪除，請到「查詢紀錄」。", "hint"))
        outer.addWidget(scrollable(right_w, hscroll=False), 2)
        sized(self.day_table, "setMinimumWidth", 200)
        sized(self.day_table, "setMinimumHeight", 160)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, self._save)
        self.refresh_day()

    def refresh(self):
        self.form.reload_items(keep_selection=True)
        self.refresh_day()

    def refresh_day(self):
        iso = self.form.date.iso()
        recs = self.db.search_records(date_from=iso, date_to=iso)
        self.day_title.setText(f"{fmt_date(iso)} 已登記的車")
        self.day_table.setRowCount(len(recs))
        for r, rec in enumerate(recs):
            self.day_table.setItem(r, 0, table_item(rec["plate"]))
            self.day_table.setItem(r, 1, table_item(fmt_money(rec["amount"]), align_right=True))
            self.day_table.setItem(r, 2, table_item("、".join(rec["item_names"])))
        self.day_table.resizeRowsToContents()
        total = sum(r["amount"] for r in recs)
        self.day_total.setText(f"共 {len(recs)} 台，合計 {fmt_money(total)}")

    def _clear(self):
        self.form.clear()

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
        lay.addWidget(label("修改紀錄", "title"))
        self.form = RecordForm(db, editing_id=rec["id"])
        self.form.load(rec)
        self.form.items_changed.connect(lambda: setattr(self, "items_added", True))
        body = QtWidgets.QHBoxLayout()
        body.addWidget(scrollable(self.form), 3)
        side = QtWidgets.QVBoxLayout()
        side.addWidget(self.form.last_visit)
        side.addStretch(1)
        body.addLayout(side, 1)
        lay.addLayout(body, 1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(button("取消", slot=self.reject))
        row.addStretch(1)
        row.addWidget(button("儲存修改", "primary", self._save))
        lay.addLayout(row)
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.resize(min(1200, screen.width() - 80), min(900, screen.height() - 80))

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

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(12)
        lay.addWidget(label("查詢紀錄", "title"))

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(label("車牌", "field"))
        self.plate = QtWidgets.QLineEdit()
        self.plate.setPlaceholderText("可只打一部分")
        sized(self.plate, "setMaximumWidth", 420)
        self.plate.textEdited.connect(lambda t: self._upper(t))
        self.plate.textChanged.connect(lambda _t: self.refresh())
        row1.addWidget(self.plate)
        row1.addSpacing(20)
        row1.addWidget(button("清除條件", slot=self._reset))
        row1.addStretch(1)
        lay.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(label("日期", "field"))
        self.d_from = OptionalDateButton()
        self.d_to = OptionalDateButton()
        self.d_from.changed.connect(self.refresh)
        self.d_to.changed.connect(self.refresh)
        row2.addWidget(self.d_from)
        row2.addWidget(label("到"))
        row2.addWidget(self.d_to)
        row2.addSpacing(20)
        row2.addWidget(button("今天", slot=self._today))
        row2.addWidget(button("這個月", slot=self._this_month))
        row2.addWidget(button("全部日期", slot=self._all_dates))
        row2.addStretch(1)
        lay.addLayout(row2)

        self.card = label("", "info")
        self.card.hide()
        lay.addWidget(self.card)

        self.table = make_table(self.HEADERS)
        hh = self.table.horizontalHeader()
        for c in (0, 1, 2, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _i: self._edit())
        lay.addWidget(self.table, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.total = label("", "total")
        bottom.addWidget(self.total)
        bottom.addStretch(1)
        bottom.addWidget(button("存成 PDF", slot=self._export))
        bottom.addWidget(button("修改選取的紀錄", slot=self._edit))
        bottom.addWidget(button("刪除選取的紀錄", "danger", self._delete))
        lay.addLayout(bottom)
        lay.addWidget(label("先點一下表格中的一行選取，再按「修改」或「刪除」。也可以直接點兩下來修改。", "hint"))
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

    def _today(self):
        t = QDate.currentDate()
        self._set_range(t, t)

    def _this_month(self):
        t = QDate.currentDate()
        self._set_range(QDate(t.year(), t.month(), 1), QDate(t.year(), t.month(), t.daysInMonth()))

    def _all_dates(self):
        self._set_range(None, None)

    def _reset(self):
        self.plate.blockSignals(True)
        self.plate.clear()
        self.plate.blockSignals(False)
        self._all_dates()

    def refresh(self):
        self.records = self.db.search_records(self.plate.text(), self.d_from.iso(), self.d_to.iso())
        t = self.table
        t.setRowCount(len(self.records))
        for r, rec in enumerate(self.records):
            t.setItem(r, 0, table_item(fmt_date(rec["date"]), rec["id"]))
            t.setItem(r, 1, table_item(rec["plate"]))
            t.setItem(r, 2, table_item(fmt_money(rec["amount"]), align_right=True))
            t.setItem(r, 3, table_item("、".join(rec["item_names"])))
            km = f"{rec['mileage']:,}" if rec.get("mileage") is not None else ""
            t.setItem(r, 4, table_item(km, align_right=True))
            t.setItem(r, 5, table_item(rec.get("note") or ""))
        t.resizeRowsToContents()
        total = sum(r["amount"] for r in self.records)
        self.total.setText(f"共 {len(self.records)} 筆，合計 {fmt_money(total)}")
        # one car found -> show how often it comes, last visit, etc.
        keys = {r["plate_key"] for r in self.records}
        card = customer_card_text(self.db, self.records[0]["plate"]) \
            if self.plate.text().strip() and len(keys) == 1 else ""
        self.card.setText(card)
        self.card.setVisible(bool(card))

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
        cond = []
        if self.plate.text().strip():
            cond.append(f"車牌：{self.plate.text().strip()}")
        cond.append(f"日期：{fmt_date(self.d_from.iso()) if self.d_from.iso() else '不限'} ～ "
                    f"{fmt_date(self.d_to.iso()) if self.d_to.iso() else '不限'}")
        lines = [" 　".join(cond), self.total.text()]
        if self.card.isVisible():
            lines += [""] + [ln for ln in self.card.text().split("\n") if ln]
        rows = [(fmt_date(r["date"]), r["plate"], fmt_money(r["amount"]), "、".join(r["item_names"]),
                 f"{r['mileage']:,}" if r.get("mileage") is not None else "", r.get("note") or "")
                for r in self.records]
        doc = pdf.document_html("保養紀錄", lines, ["<br>", pdf.table_html(self.HEADERS, rows, right=(2, 4))])
        name = f"保養紀錄_{self.plate.text().strip() + '_' if self.plate.text().strip() else ''}{_dt.date.today():%Y%m%d}.pdf"
        pdf.save_pdf(self, name, doc)

    def show_plate(self, plate: str):
        """Jump here from another page with a plate filled in and all dates."""
        self.d_from.set_date(None, emit=False)
        self.d_to.set_date(None, emit=False)
        self.plate.setText(plate)  # triggers refresh


# =================================================================== 備份還原
class BackupPage(Page):
    restored = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        inner = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(inner)
        lay.setContentsMargins(30, 12, 30, 12)
        lay.setSpacing(14)
        lay.addWidget(label("備份與還原", "title"))

        lay.addWidget(label("① 備份資料", "field"))
        lay.addWidget(label(
            "把全部資料存成一個備份檔。建議存到隨身碟或雲端硬碟（例如 Google 雲端硬碟、OneDrive）。"
            "電腦壞掉時，可以在新電腦用這個檔案把資料救回來。", "hint"))
        b1 = button("備份資料（存成檔案）", "primary", self._backup)
        sized(b1, "setMaximumWidth", 600)
        lay.addWidget(b1)
        self.last_backup = label("", "info")
        lay.addWidget(self.last_backup)

        lay.addSpacing(20)
        lay.addWidget(label("② 從備份檔還原", "field"))
        lay.addWidget(label(
            "換新電腦或資料不見時使用。選擇以前存的備份檔，目前電腦上的資料會被備份檔的內容取代。"
            "（還原前，程式會自動先把目前的資料另存一份，以防選錯檔案。）", "hint"))
        b2 = button("從備份檔還原", slot=self._restore)
        sized(b2, "setMaximumWidth", 600)
        lay.addWidget(b2)

        lay.addSpacing(20)
        lay.addWidget(label("③ 資料存放位置", "field"))
        self.location = label("", "hint")
        self.location.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lay.addWidget(self.location)
        b3 = button("打開資料夾", slot=self._open_folder)
        sized(b3, "setMaximumWidth", 600)
        lay.addWidget(b3)
        lay.addStretch(1)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

    def refresh(self):
        last = self.db.get_setting("last_manual_backup")
        if last:
            self.last_backup.setText(f"上次備份時間：{last}\n上次備份位置：{self.db.get_setting('last_manual_backup_path', '')}")
        else:
            self.last_backup.setText("還沒有手動備份過，建議現在備份一次。")
        self.location.setText(
            f"資料檔：{self.db.path}\n"
            f"程式每天開啟時會自動備份到：{config.auto_backup_dir()}（保留最近 {config.AUTO_BACKUP_KEEP} 天）\n"
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
        lay = QtWidgets.QVBoxLayout(inner)
        lay.setContentsMargins(30, 12, 30, 12)
        lay.setSpacing(12)
        lay.addWidget(label("設定", "title"))

        lay.addWidget(label("字體大小", "field"))
        lay.addWidget(label("字體會跟著視窗大小自動調整。覺得太小或太大，可以在這裡再調整。", "hint"))
        fs = QtWidgets.QHBoxLayout()
        self.font_group = QtWidgets.QButtonGroup(self)
        for name in config.FONT_SCALES:
            b = button(name, "nav")
            b.setCheckable(True)
            b.setFocusPolicy(QtCore.Qt.StrongFocus)
            b.clicked.connect(lambda _c, n=name: self.font_size_changed.emit(n))
            self.font_group.addButton(b)
            fs.addWidget(b)
        fs.addStretch(1)
        lay.addLayout(fs)

        lay.addSpacing(16)
        lay.addWidget(label("保養項目", "field"))
        self.items = ItemManager(db)
        self.items.changed.connect(self.data_changed.emit)
        lay.addWidget(self.items)

        lay.addSpacing(16)
        lay.addWidget(label(f"{config.APP_NAME}　版本 {config.APP_VERSION}", "hint"))
        lay.addStretch(1)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

    def refresh(self):
        current = self.font_size_name()
        for b in self.font_group.buttons():
            b.setChecked(b.text() == current)
        self.items.refresh()

    def font_size_name(self) -> str:
        name = self.db.get_setting("font_size")
        return name if name in config.FONT_SCALES else config.DEFAULT_FONT_SIZE


# =================================================================== 報表統計
class ReportPage(Page):
    open_history = pyqtSignal(str)
    MODES = [("week", "每週"), ("month", "每月"), ("year", "每年")]

    def __init__(self, db, parent=None):
        super().__init__(db, parent)
        self.mode = "month"
        self.anchor = QDate.currentDate()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(10)

        row = QtWidgets.QHBoxLayout()
        self.mode_group = QtWidgets.QButtonGroup(self)
        for key, text in self.MODES:
            b = button(text, "nav")
            b.setCheckable(True)
            b.setProperty("mode", key)
            b.clicked.connect(lambda _c, k=key: self._set_mode(k))
            self.mode_group.addButton(b)
            row.addWidget(b)
        row.addSpacing(20)
        self.prev_btn = button("◀ 上一個月", slot=lambda: self._step(-1))
        self.period = label("", "title")
        self.next_btn = button("下一個月 ▶", slot=lambda: self._step(1))
        self.now_btn = button("本月", slot=self._now)
        for w in (self.prev_btn, self.period, self.next_btn, self.now_btn):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(button("存成 PDF", slot=self._export))
        lay.addLayout(row)

        cards = QtWidgets.QHBoxLayout()
        self.cards = {}
        for key, title in [("total", "營業額"), ("visits", "來店台次"), ("cars", "不同車輛"),
                           ("avg", "平均每次")]:
            box = QtWidgets.QFrame()
            box.setProperty("role", "card")
            bl = QtWidgets.QVBoxLayout(box)
            bl.addWidget(label(title, "hint"))
            value = label("", "cardvalue")
            bl.addWidget(value)
            self.cards[key] = value
            cards.addWidget(box)
        lay.addLayout(cards)

        tables = QtWidgets.QHBoxLayout()
        tables.setSpacing(16)

        def column(title, headers, stretch_col, stretch=2):
            v = QtWidgets.QVBoxLayout()
            v.addWidget(label(title, "field"))
            t = make_table(headers)
            hh = t.horizontalHeader()
            for c in range(len(headers)):
                hh.setSectionResizeMode(c, QtWidgets.QHeaderView.Stretch if c == stretch_col
                                        else QtWidgets.QHeaderView.ResizeToContents)
            v.addWidget(t, 1)
            tables.addLayout(v, stretch)
            return t

        self.t_break = column("明細", ["日期", "台次", "金額"], 0)
        self.t_items = column("各項目做了幾次", ["項目", "次數"], 0)
        self.t_cust = column("常來的客人（點兩下看紀錄）", ["車牌", "次數", "金額", "最近來店"], 0, 3)
        self.t_cust.doubleClicked.connect(self._open_customer)
        lay.addLayout(tables, 1)
        self._sync_mode_buttons()

    # ----------------------------------------------------------- period logic
    def _range(self):
        d = self.anchor
        if self.mode == "week":
            start = d.addDays(1 - d.dayOfWeek())  # Monday
            return start, start.addDays(6)
        if self.mode == "month":
            start = QDate(d.year(), d.month(), 1)
            return start, QDate(d.year(), d.month(), d.daysInMonth())
        return QDate(d.year(), 1, 1), QDate(d.year(), 12, 31)

    def _set_mode(self, mode):
        self.mode = mode
        self._sync_mode_buttons()
        self.refresh()

    def _sync_mode_buttons(self):
        for b in self.mode_group.buttons():
            b.setChecked(b.property("mode") == self.mode)
        word = {"week": ("週", "本週"), "month": ("個月", "本月"), "year": ("年", "今年")}[self.mode]
        self.prev_btn.setText(f"◀ 上一{word[0]}")
        self.next_btn.setText(f"下一{word[0]} ▶")
        self.now_btn.setText(word[1])

    def _step(self, n):
        if self.mode == "week":
            self.anchor = self.anchor.addDays(7 * n)
        elif self.mode == "month":
            self.anchor = self.anchor.addMonths(n)
        else:
            self.anchor = self.anchor.addYears(n)
        self.refresh()

    def _now(self):
        self.anchor = QDate.currentDate()
        self.refresh()

    # ------------------------------------------------------------------ view
    def refresh(self):
        start, end = self._range()
        if self.mode == "week":
            self.period.setText(f"{start.toString('yyyy/MM/dd')} ～ {end.toString('MM/dd')}")
        elif self.mode == "month":
            self.period.setText(f"{start.year()} 年 {start.month()} 月")
        else:
            self.period.setText(f"{start.year()} 年")
        bucket = "month" if self.mode == "year" else "day"
        r = self.db.report(start.toString("yyyy-MM-dd"), end.toString("yyyy-MM-dd"), bucket)
        self.cards["total"].setText(fmt_money(r["total"]))
        self.cards["visits"].setText(f"{r['visits']} 台次")
        self.cards["cars"].setText(f"{r['cars']} 台")
        self.cards["avg"].setText(fmt_money(round(r["total"] / r["visits"])) if r["visits"] else "-")

        self.t_break.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem("月份" if bucket == "month" else "日期"))
        self._fill(self.t_break, [
            (f"{int(b['period'][5:7])} 月" if bucket == "month" else fmt_date(b["period"]),
             str(b["visits"]), fmt_money(b["total"])) for b in r["buckets"]], right=(1, 2))
        self._fill(self.t_items, [(i["name"], f"{i['times']} 次") for i in r["items"]], right=(1,))
        self._fill(self.t_cust, [(c["plate"], f"{c['visits']} 次", fmt_money(c["total"]),
                                  c["last_date"].replace("-", "/")) for c in r["customers"]], right=(1, 2))

    def _export(self):
        start, end = self._range()
        title = {"week": "每週報表", "month": "每月報表", "year": "每年報表"}[self.mode]
        lines = [f"期間：{fmt_date(start.toString('yyyy-MM-dd'))} ～ {fmt_date(end.toString('yyyy-MM-dd'))}",
                 f"營業額：{self.cards['total'].text()}　　來店台次：{self.cards['visits'].text()}　　"
                 f"不同車輛：{self.cards['cars'].text()}　　平均每次：{self.cards['avg'].text()}"]

        def rows_of(t):
            return [[t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())]
                    for r in range(t.rowCount())]

        def headers_of(t):
            return [t.horizontalHeaderItem(c).text() for c in range(t.columnCount())]

        sections = []
        for t, name, right in [(self.t_break, "明細", (1, 2)), (self.t_items, "各項目做了幾次", (1,)),
                               (self.t_cust, "常來的客人", (1, 2))]:
            sections.append(f"<h3 style='margin:14px 0 4px 0'>{name}</h3>")
            sections.append(pdf.table_html(headers_of(t), rows_of(t), right))
        doc = pdf.document_html(f"{title}　{self.period.text()}", lines, sections)
        safe = self.period.text().replace("/", "").replace(" ", "").replace("～", "-")
        pdf.save_pdf(self, f"{title}_{safe}.pdf", doc)

    @staticmethod
    def _fill(table, rows, right=()):
        table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, v in enumerate(values):
                table.setItem(r, c, table_item(v, align_right=c in right))
        table.resizeRowsToContents()

    def _open_customer(self, index):
        item = self.t_cust.item(index.row(), 0)
        if item:
            self.open_history.emit(item.text())
