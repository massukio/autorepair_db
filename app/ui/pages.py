"""The four main pages: 新增紀錄 / 查詢紀錄 / 備份還原 / 設定."""
import csv
import datetime as _dt
import os

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QDate, pyqtSignal

from app import backup, config
from app.db import Database, DataError
from app.ui.record_form import RecordForm
from app.ui.widgets import (OptionalDateButton, ask, button, fmt_date, fmt_money, info, label,
                            make_table, table_item, warn)


def documents_dir() -> str:
    path = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
    return path or os.path.expanduser("~")


def scrollable(inner: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
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
        self.save_btn.setMinimumWidth(280)
        btns.addWidget(self.save_btn)
        lv.addLayout(btns)
        outer.addLayout(lv, 5)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self.form.last_visit)
        self.day_title = label("", "field")
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
        outer.addLayout(right, 2)
        self.day_table.setMinimumWidth(360)

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
        self.plate.setMaximumWidth(420)
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
        bottom.addWidget(button("匯出 Excel", slot=self._export))
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
            warn(self, "目前沒有資料可以匯出。")
            return
        default = os.path.join(documents_dir(), f"保養紀錄_{_dt.date.today():%Y%m%d}.csv")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "匯出 Excel 檔", default, "Excel 可開啟的檔案 (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(self.HEADERS)
                for rec in reversed(self.records):
                    w.writerow([rec["date"], rec["plate"], rec["amount"], "、".join(rec["item_names"]),
                                rec["mileage"] if rec.get("mileage") is not None else "",
                                rec.get("note") or ""])
        except OSError as e:
            warn(self, f"匯出失敗：{e}")
            return
        info(self, f"已匯出 {len(self.records)} 筆紀錄到：\n{path}\n\n可以用 Excel 開啟。")


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
        b1.setMaximumWidth(600)
        lay.addWidget(b1)
        self.last_backup = label("", "info")
        lay.addWidget(self.last_backup)

        lay.addSpacing(20)
        lay.addWidget(label("② 從備份檔還原", "field"))
        lay.addWidget(label(
            "換新電腦或資料不見時使用。選擇以前存的備份檔，目前電腦上的資料會被備份檔的內容取代。"
            "（還原前，程式會自動先把目前的資料另存一份，以防選錯檔案。）", "hint"))
        b2 = button("從備份檔還原", slot=self._restore)
        b2.setMaximumWidth(600)
        lay.addWidget(b2)

        lay.addSpacing(20)
        lay.addWidget(label("③ 資料存放位置", "field"))
        self.location = label("", "hint")
        self.location.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lay.addWidget(self.location)
        b3 = button("打開資料夾", slot=self._open_folder)
        b3.setMaximumWidth(600)
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

        lay.addWidget(label("保養項目", "field"))
        lay.addWidget(label("先點一下清單中的項目，再按右邊的按鈕。刪除的項目不會影響以前的紀錄。", "hint"))
        row = QtWidgets.QHBoxLayout()
        self.list = QtWidgets.QListWidget()
        self.list.setMinimumHeight(300)
        self.list.setMaximumWidth(500)
        row.addWidget(self.list)
        btns = QtWidgets.QVBoxLayout()
        for text, role, slot in [("＋ 新增項目", None, self._add), ("改名", None, self._rename),
                                 ("往上移", None, lambda: self._move(-1)),
                                 ("往下移", None, lambda: self._move(1)),
                                 ("刪除項目", "danger", self._hide)]:
            b = button(text, role, slot)
            b.setMinimumWidth(200)
            btns.addWidget(b)
        btns.addStretch(1)
        row.addLayout(btns)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addSpacing(16)
        lay.addWidget(label("字體大小", "field"))
        fs = QtWidgets.QHBoxLayout()
        self.font_group = QtWidgets.QButtonGroup(self)
        for name in config.FONT_SIZES:
            b = button(name, "nav")
            b.setCheckable(True)
            b.setFocusPolicy(QtCore.Qt.StrongFocus)
            b.clicked.connect(lambda _c, n=name: self.font_size_changed.emit(n))
            self.font_group.addButton(b)
            fs.addWidget(b)
        fs.addStretch(1)
        lay.addLayout(fs)

        lay.addSpacing(16)
        lay.addWidget(label(f"{config.APP_NAME}　版本 {config.APP_VERSION}", "hint"))
        lay.addStretch(1)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scrollable(inner))

    def refresh(self, select_id=None):
        current = self.font_size_name()
        for b in self.font_group.buttons():
            b.setChecked(b.text() == current)
        if select_id is None and self.list.currentItem():
            select_id = self.list.currentItem().data(QtCore.Qt.UserRole)
        self.list.clear()
        for it in self.db.list_items():
            li = QtWidgets.QListWidgetItem(it["name"])
            li.setData(QtCore.Qt.UserRole, it["id"])
            self.list.addItem(li)
            if it["id"] == select_id:
                self.list.setCurrentItem(li)

    def font_size_name(self) -> str:
        name = self.db.get_setting("font_size")
        if name in config.FONT_SIZES:
            return name
        # first launch: pick a size that fits the screen
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        return "中" if screen.height() < 1000 or screen.width() < 1600 else config.DEFAULT_FONT_SIZE

    def _current(self):
        li = self.list.currentItem()
        if li is None:
            warn(self, "請先在清單中點一下要處理的項目。")
            return None
        return li.data(QtCore.Qt.UserRole), li.text()

    def _add(self):
        from app.ui.widgets import ask_text
        name = ask_text(self, "新增項目", "請輸入新的項目名稱：")
        if not name:
            return
        try:
            iid = self.db.add_item(name)
        except DataError as e:
            warn(self, str(e))
            return
        self.refresh(iid)
        self.data_changed.emit()

    def _rename(self):
        from app.ui.widgets import ask_text
        cur = self._current()
        if not cur:
            return
        name = ask_text(self, "改名", f"「{cur[1]}」要改成：", cur[1])
        if not name or name == cur[1]:
            return
        try:
            self.db.rename_item(cur[0], name)
        except DataError as e:
            warn(self, str(e))
            return
        self.refresh(cur[0])
        self.data_changed.emit()

    def _move(self, delta):
        cur = self._current()
        if not cur:
            return
        self.db.move_item(cur[0], delta)
        self.refresh(cur[0])
        self.data_changed.emit()

    def _hide(self):
        cur = self._current()
        if not cur:
            return
        if not ask(self, f"確定要刪除項目「{cur[1]}」嗎？\n\n以前紀錄上的「{cur[1]}」不會被刪掉。",
                   yes="確定刪除", no="不要刪除"):
            return
        self.db.hide_item(cur[0])
        self.refresh()
        self.data_changed.emit()
