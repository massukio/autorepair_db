"""Make the screenshots of the 使用說明 (assets/manual/*.png), with highlights.

    AUTOREPAIR_DATA_DIR=<empty folder> QT_QPA_PLATFORM=offscreen python tools/make_manual.py [out_dir]

Runs the real program on sample data in AUTOREPAIR_DATA_DIR (must be empty or a
throw-away folder: sample records are added). Each picture gets orange boxes with
numbers ①②③ that the text in assets/manual/manual.html refers to. Run it on
Windows for the real fonts (workflows/build-release.md), then check every picture.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402

from app import config  # noqa: E402
from app.db import Database  # noqa: E402

ORANGE = QtGui.QColor("#E8590C")
SIZE = (1280, 900)  # taller than the reference: same font size, room for every highlighted part


# ------------------------------------------------------------------ drawing
def rect_of(target, root) -> QtCore.QRect:
    if isinstance(target, QtCore.QRect):
        return QtCore.QRect(target)
    if isinstance(target, (list, tuple)):
        r = QtCore.QRect()
        for t in target:
            r = r.united(rect_of(t, root))
        return r
    r = QtCore.QRect(target.mapTo(root, QtCore.QPoint(0, 0)), target.size())
    w = target  # inside a scroll area only the visible part may be boxed
    while w is not None and w is not root:
        area = w.parentWidget()
        if isinstance(area, QtWidgets.QAbstractScrollArea) and w is area.viewport():
            r = r.intersected(QtCore.QRect(w.mapTo(root, QtCore.QPoint(0, 0)), w.size()))
        w = area
    return r


def row_rect(table, row, root) -> QtCore.QRect:
    r = table.visualRect(table.model().index(row, 0))
    left = table.viewport().mapTo(root, QtCore.QPoint(0, r.top()))
    return QtCore.QRect(left, QtCore.QSize(table.viewport().width(), r.height()))


def find_button(root, text):
    for b in root.findChildren(QtWidgets.QPushButton):
        if b.text() == text and b.isVisible():
            return b
    raise LookupError(text)


def settle(app, n=6):
    for _ in range(n):
        app.processEvents()
        QtCore.QThread.msleep(15)


def shot(root, marks, path, crop=None):
    """Grab root, draw a box + number for each (number, target), optionally crop."""
    pm = root.grab()
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    font = QtGui.QFont("Arial")
    font.setPixelSize(22)
    font.setBold(True)
    p.setFont(font)
    radius = 17
    inside = pm.rect().adjusted(3, 3, -3, -3)  # parts that run past the edge: box what is visible
    for number, target in marks:
        r = rect_of(target, root).adjusted(-5, -5, 5, 5).intersected(inside)
        p.setPen(QtGui.QPen(ORANGE, 4))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(r, 10, 10)
    for number, target in marks:  # badges on top of every box
        r = rect_of(target, root).adjusted(-5, -5, 5, 5).intersected(inside)
        cx = min(max(r.left(), radius + 3), pm.width() - radius - 3)
        cy = min(max(r.top(), radius + 3), pm.height() - radius - 3)
        circle = QtCore.QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        p.setPen(QtGui.QPen(QtCore.Qt.white, 3))
        p.setBrush(ORANGE)
        p.drawEllipse(circle)
        p.setPen(QtCore.Qt.white)
        p.drawText(circle, QtCore.Qt.AlignCenter, str(number))
    p.end()
    if crop is not None:
        c = rect_of(crop, root).adjusted(-24, -24, 24, 24).intersected(pm.rect())
        pm = pm.copy(c)
    p = QtGui.QPainter(pm)  # thin frame: the picture must not melt into the white page
    p.setPen(QtGui.QPen(QtGui.QColor("#BDB6AA"), 2))
    p.drawRect(pm.rect().adjusted(1, 1, -1, -1))
    p.end()
    pm.save(path)
    print("saved", os.path.basename(path), pm.width(), "x", pm.height())


# --------------------------------------------------------------- sample data
def sample_data(db: Database):
    random.seed(7)
    ids = [i["id"] for i in db.list_items()]
    regulars = ["ABC-1234", "RAA-0912", "KLM-8888", "BCD-2345", "TPE-3366", "AMG-5203"]
    today = QtCore.QDate.currentDate()
    for n in range(260):
        plate = random.choice(regulars) if n % 3 else f"{random.choice('BCDEFGHKMNPRT')}" \
            f"{random.choice('ABCDEFGHKMNP')}{random.choice('ABCDEFKLMNPQRT')}-{random.randint(1000, 9999)}"
        d = today.addDays(-random.randint(1, 360)).toString("yyyy-MM-dd")
        db.add_record(d, plate, random.choice([800, 1200, 1500, 1800, 2200, 2800, 3500]),
                      random.sample(ids, random.randint(1, 3)), random.randint(20, 120) * 1000)
    t = today.toString("yyyy-MM-dd")
    db.add_record(t, "RAA-0912", 1500, ids[:2], 63500)
    db.add_record(t, "KLM-8888", 2800, [ids[0], ids[1], ids[4]], 91200, "變速箱油下次再換")
    db.add_record(t, "TPE-3366", 800, [ids[3]])
    db.add_record(today.addDays(-95).toString("yyyy-MM-dd"), "ABC-1234", 1800, ids[:3], 52000,
                  "下次 57000 公里換機油")
    db.set_setting("last_manual_backup", today.addDays(-3).toString("yyyy/MM/dd") + " 18:30")
    db.set_setting("last_manual_backup_path", "E:\\汽車保養備份_" + today.addDays(-3).toString("yyyyMMdd") + "_1830.db")


# -------------------------------------------------------------------- shots
def main(out):
    os.makedirs(out, exist_ok=True)
    app = QtWidgets.QApplication(sys.argv)
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Chinese, QtCore.QLocale.Taiwan))
    db = Database(config.db_path())
    if db.count_records() == 0:
        sample_data(db)
    from app.ui.main_window import MainWindow
    from app.ui.pages import EditRecordDialog
    from app.ui.items import ItemManagerDialog
    win = MainWindow(db)
    win.resize(*SIZE)
    win.show()
    settle(app)
    win.apply_font_size()
    settle(app)
    o = lambda name: os.path.join(out, name)  # noqa: E731

    # 1. the whole window
    win.show_page(0)
    settle(app)
    shot(win, [(i + 1, win.group.button(i)) for i in range(5)] + [(6, win.help_btn)], o("overview.png"))

    # 2. 新增紀錄 filled in
    page, f = win.new_page, win.new_page.form
    f.plate.setText("ABC-1234")
    f.amount.setText("1800")
    for b in f.items.buttons[:2]:
        b.setChecked(True)
    f.mileage.setText("57200")
    page.customer.set_plate("ABC-1234")
    settle(app, 10)
    shot(win, [(1, f.date), (2, f.plate), (3, f.amount), (4, f.items), (5, [f.mileage, f.note]),
               (6, page.save_btn), (7, page.customer), (8, page.day_table)], o("new_record.png"))
    shot(win, [(1, find_button(page, "＋ 新增項目")), (2, find_button(page, "管理項目")), (3, f.items.buttons[2])],
         o("items_on_form.png"), crop=[find_button(page, "管理項目"), f.items])
    f.clear()

    # 3. 管理項目
    dlg = ItemManagerDialog(db, win)
    dlg.resize(900, 620)
    dlg.show()
    settle(app)
    m = dlg.manager
    m.list.setCurrentRow(1)
    settle(app)
    shot(dlg, [(1, m.list), (2, find_button(dlg, "＋ 新增項目")), (3, find_button(dlg, "改名")),
               (4, [find_button(dlg, "往上移"), find_button(dlg, "往下移")]), (5, find_button(dlg, "刪除項目")),
               (6, find_button(dlg, "完成"))], o("items_manage.png"))
    dlg.close()

    # 4. 查詢紀錄 for one car, a row selected
    win.show_page(1)
    h = win.history_page
    h.show_plate("ABC")
    settle(app, 10)
    h.table.selectRow(1)
    settle(app)
    shot(win, [(1, h.plate), (2, [h.d_from, h.d_to]), (3, h.range_seg), (4, row_rect(h.table, 1, win)),
               (5, [find_button(h, "修改"), find_button(h, "刪除")]), (6, find_button(h, "存成 PDF"))],
         o("history.png"))
    h._reset()
    settle(app, 10)
    h.table.scrollToBottom()
    settle(app)
    shot(win, [(1, h.shown_label), (2, h.more_btn)], o("history_more.png"),
         crop=[h.shown_label, h.more_btn, row_rect(h.table, h.table.rowCount() - 1, win)])

    # 5. 修改紀錄
    rec = h.records[0]
    ed = EditRecordDialog(db, rec, win)
    ed.resize(1100, 860)
    ed.show()
    settle(app)
    shot(ed, [(1, ed.form), (2, find_button(ed, "儲存修改")), (3, find_button(ed, "取消"))], o("edit.png"))
    ed.close()

    # 6. 報表統計
    win.show_page(2)
    r = win.report_page
    settle(app, 10)
    tiles = [t.parentWidget() for t in r.tiles.values()]
    shot(win, [(1, r.seg), (2, [r.prev_btn, r.period, r.next_btn]), (3, find_button(r, "存成 PDF")),
               (4, tiles), (5, r.t_cust)], o("report.png"))
    r._step(-1)
    settle(app)
    shot(win, [(1, r.now_btn)], o("report_back.png"), crop=[r.seg, r.now_btn])
    r._now()

    # 7. 備份 / 還原
    win.show_page(3)
    b = win.backup_page
    settle(app, 10)
    shot(win, [(1, find_button(b, "備份資料（存成檔案）")), (2, b.last_backup),
               (3, find_button(b, "選擇備份檔並還原")), (4, find_button(b, "打開資料夾"))], o("backup.png"))

    # 8. 設定
    win.show_page(4)
    s = win.settings_page
    settle(app, 10)
    shot(win, [(1, s.font_seg), (2, s.items)], o("settings.png"))
    print("done:", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "manual"))
