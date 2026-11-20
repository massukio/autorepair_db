"""Render every page (and the main dialogs) to PNG for visual checks.

Usage: AUTOREPAIR_DATA_DIR=<tmp> python tools/screenshot.py <out_dir>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5 import QtCore, QtWidgets  # noqa: E402

from app import config  # noqa: E402
from app.db import Database  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui import pages  # noqa: E402
from app.ui.pages import EditRecordDialog  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    app = QtWidgets.QApplication(sys.argv)
    db = Database(config.db_path())
    if db.count_records() == 0:
        import random
        random.seed(1)
        ids = [i["id"] for i in db.list_items()]
        plates = ["ABC-1234", "XYZ-5678", "BCD-2345", "KLM-8888", "RAA-0912", "TPE-3366"]
        today = QtCore.QDate.currentDate()
        for n in range(120):
            d = today.addDays(-random.randint(1, 330)).toString("yyyy-MM-dd")
            db.add_record(d, random.choice(plates), random.choice([800, 1500, 1800, 2200, 3500]),
                          random.sample(ids, random.randint(1, 3)), random.randint(20, 90) * 1000)
        db.add_record(today.toString("yyyy-MM-dd"), "ABC-1234", 1800, ids[:2], 52000, "下次 57000 公里")
    plate = db.report("2000-01-01", "2100-01-01")["customers"][0]["plate"]
    win = MainWindow(db)
    win.show()
    win.new_page.form.plate.setText(plate)
    win.new_page.form.amount.setText("2200")
    win.new_page.form.items.buttons[0].setChecked(True)
    sizes = [(1070, 540), (1280, 760), (1920, 1040), (800, 480)]
    for w, h in sizes:
        win.resize(w, h)
        app.processEvents()
        win.apply_font_size()
        for i in range(5):
            win.show_page(i)
            for _ in range(4):
                app.processEvents()
                QtCore.QThread.msleep(20)
            win.grab().save(os.path.join(out, f"{w}x{h}_page{i}.png"))
    win.resize(1280, 760)
    app.processEvents()
    win.apply_font_size()
    dlg = EditRecordDialog(db, db.search_records()[0], win)
    dlg.resize(1200, 700)
    dlg.show()
    app.processEvents()
    dlg.grab().save(os.path.join(out, "edit.png"))
    from app.ui.items import ItemManagerDialog
    im = ItemManagerDialog(db, win)
    im.resize(900, 600)
    im.show()
    app.processEvents()
    im.grab().save(os.path.join(out, "items.png"))

    # PDFs: history (one plate) and monthly report
    from app.ui import pdf
    win.show_page(1)
    win.history_page.show_plate(plate)
    app.processEvents()
    win.grab().save(os.path.join(out, "history_plate.png"))
    captured = {}
    pages.pdf.save_pdf = lambda parent, name, html_text, start_dir=None: captured.setdefault(name, html_text)
    win.history_page._export()
    win.show_page(2)
    win.report_page._export()
    for name, html_text in captured.items():
        pdf.render_pdf(html_text, os.path.join(out, name))
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
