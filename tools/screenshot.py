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
from app.ui.pages import EditRecordDialog  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    app = QtWidgets.QApplication(sys.argv)
    db = Database(config.db_path())
    if db.count_records() == 0:
        ids = {i["name"]: i["id"] for i in db.list_items()}
        today = QtCore.QDate.currentDate().toString("yyyy-MM-dd")
        db.add_record(today, "ABC-1234", 1800, [ids["機油"], ids["機油濾芯"]], 52000, "下次 57000 公里")
        db.add_record(today, "XYZ-5678", 3500, [ids["電瓶"]])
        db.add_record("2026-10-01", "ABC-1234", 1500, [ids["機油"]], 47000)
    win = MainWindow(db)
    win.resize(1280, 760)
    win.show()
    win.new_page.form.plate.setText("ABC-1234")
    win.new_page.form.amount.setText("2200")
    win.new_page.form.items.buttons[0].setChecked(True)
    for i in range(4):
        win.show_page(i)
        app.processEvents()
        win.grab().save(os.path.join(out, f"page{i}.png"))
    dlg = EditRecordDialog(db, db.search_records()[0], win)
    dlg.resize(1200, 760)
    dlg.show()
    app.processEvents()
    dlg.grab().save(os.path.join(out, "edit.png"))
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
