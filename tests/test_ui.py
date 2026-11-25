"""UI logic tests (offscreen Qt). Skipped when PyQt5 is not installed."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
from PyQt5.QtCore import QDate  # noqa: E402

from app import config  # noqa: E402
from app.db import Database  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOREPAIR_DATA_DIR", str(tmp_path))
    return tmp_path


def test_font_size_survives_restart(qapp, data_dir):
    from app.ui.main_window import MainWindow
    db = Database(config.db_path())
    w = MainWindow(db)
    w.show_page(4)
    w.settings_page.font_seg.buttons["特大"].click()
    first = w._base_pt
    w.close()
    db.close()

    db = Database(config.db_path())  # "next open"
    w = MainWindow(db)
    w.show_page(4)
    assert w.settings_page.font_size_name() == "特大"
    assert w._base_pt == first
    assert w.settings_page.font_seg.buttons["特大"].isChecked()
    w.close()
    db.close()


def test_edit_keeps_item_deleted_during_edit(qapp, data_dir, monkeypatch):
    from app.ui import items as items_mod
    from app.ui.pages import EditRecordDialog
    db = Database(config.db_path())
    oil, filt = [i["id"] for i in db.list_items()[:2]]
    rid = db.add_record("2026-11-01", "ABC-1234", 1500, [oil, filt])
    dlg = EditRecordDialog(db, db.get_record(rid))
    monkeypatch.setattr(items_mod, "ask", lambda *a, **k: True)
    dlg.form._delete_item(oil, "機油")  # deleted from the item list while editing
    dlg.form.amount.setText("1600")
    dlg._save()
    rec = db.get_record(rid)
    assert rec["amount"] == 1600
    assert set(rec["item_ids"]) == {oil, filt}  # the record keeps 機油
    # a new record does not show the deleted item
    from app.ui.record_form import RecordForm
    assert oil not in [b.property("item_id") for b in RecordForm(db).items.buttons]
    db.close()


def test_history_load_more_and_today_range(qapp, data_dir):
    from app.ui.pages import HistoryPage
    db = Database(config.db_path())
    today = QDate.currentDate().toString("yyyy-MM-dd")
    for i in range(450):
        db.add_record("2026-01-01", f"XY{i:04d}", 100)
    db.add_record(today, "TODAY1", 100)
    h = HistoryPage(db)
    h.refresh()
    assert h.table.rowCount() == 200
    h._load_more()
    h._load_more()
    assert h.table.rowCount() == 451
    ids = [h.table.item(r, 0).data(0x0100) for r in range(h.table.rowCount())]
    assert len(set(ids)) == 451 and None not in ids
    assert not h.more_btn.isVisibleTo(h)

    h._quick_range("today")
    assert h.d_from.iso() == today and h.table.rowCount() == 1
    # past midnight the stored dates are stale; refresh must re-apply 「今天」
    h.d_from.set_date(QDate(2020, 1, 1), emit=False)
    h.d_to.set_date(QDate(2020, 1, 1), emit=False)
    h.refresh()
    assert h.d_from.iso() == today and h.table.rowCount() == 1
    # dates picked by hand are kept
    h.d_from.set_date(QDate(2026, 1, 1))
    assert h.range_key == "" and h.d_from.iso() == "2026-01-01"
    db.close()


def test_failed_restore_puts_old_data_back(qapp, data_dir, tmp_path, monkeypatch):
    import sqlite3
    from app import db as db_mod
    from app.ui import pages
    db = Database(config.db_path())
    db.add_record("2026-11-01", "KEEP-1", 100)
    other = Database(str(tmp_path / "other.db"))
    for i in range(3):
        other.add_record("2026-11-02", f"NEW{i}", 1)
    other.close()
    page = pages.BackupPage(db)
    monkeypatch.setattr(pages.QtWidgets.QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(tmp_path / "other.db"), ""))
    monkeypatch.setattr(pages, "ask", lambda *a, **k: True)
    msgs = []
    monkeypatch.setattr(pages, "warn", lambda _p, t, *a: msgs.append(t))
    real = db_mod._create_schema
    calls = []

    def flaky(conn):  # the upgrade after the copy fails once
        calls.append(1)
        if len(calls) == 1:
            raise sqlite3.IntegrityError("boom")
        real(conn)
    monkeypatch.setattr(db_mod, "_create_schema", flaky)
    page._restore()
    assert msgs and "恢復成還原前" in msgs[0]
    assert [r["plate"] for r in db.search_records()] == ["KEEP-1"]
    db.close()


def test_pdf_filename_is_safe_on_windows():
    from app.ui.pdf import safe_filename
    assert safe_filename('保養紀錄_AB/12*?:"<>|\\x.pdf') == "保養紀錄_AB12x.pdf"


def test_manual_is_complete():
    """Every picture exists, every link has its target, every page has a chapter."""
    import re
    from app.ui import manual
    from app.ui.main_window import MainWindow
    html = manual.manual_html()
    names = set(re.findall(r'<a name="([^"]+)"', html))
    for img in manual.image_names(html):
        assert os.path.exists(os.path.join(manual.MANUAL_DIR, img)), img
    for link in re.findall(r'<a href="#([^"]+)"', html):
        assert link in names, link
    assert set(MainWindow.MANUAL_ANCHORS) <= names and "toc" in names


def test_manual_opens_at_the_current_page_and_saves_pdf(qapp, data_dir, tmp_path, monkeypatch):
    from PyQt5 import QtCore
    from app.ui import manual
    from app.ui.main_window import MainWindow
    db = Database(config.db_path())
    w = MainWindow(db)
    w.resize(1070, 540)
    w.show()
    w.show_page(3)
    w.open_manual()
    dlg = w._manual
    for _ in range(20):
        qapp.processEvents()
        QtCore.QThread.msleep(10)
    assert dlg.isVisible() and not dlg.isModal()
    assert "備份" in dlg.view.toPlainText() and dlg.view.verticalScrollBar().value() > 0  # at chapter 六
    w.open_manual()  # a second click reuses the same window
    assert w._manual is dlg
    # the header never cuts a tab or the help button off
    assert w.header.sizeHint().width() <= w.width()
    out = tmp_path / "說明.pdf"
    monkeypatch.setattr(manual.QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    monkeypatch.setattr(manual, "ask", lambda *a, **k: False)
    dlg.save_pdf()
    assert out.exists() and out.stat().st_size > 100_000  # text + pictures
    dlg.close()
    w.close()
    db.close()


def test_chip_grid_relayout_never_runs_after_it_is_gone(qapp):
    """A font change schedules a relayout; closing the window first must not crash."""
    import sys
    from PyQt5 import QtCore, QtWidgets
    from app.ui.widgets import ItemGrid
    errors = []
    old, sys.excepthook = sys.excepthook, lambda *a: errors.append(a[1])
    try:
        holder = QtWidgets.QWidget()
        grid = ItemGrid(holder)
        grid.set_items([{"id": 1, "name": "機油"}, {"id": 2, "name": "電瓶"}])
        holder.setStyleSheet("QPushButton { font-size: 30pt; }")  # like 設定 → 字體大小
        from PyQt5 import sip
        sip.delete(holder)  # the window is gone before the relayout runs
        for _ in range(5):
            qapp.processEvents()
    finally:
        sys.excepthook = old
    assert not errors, errors


def test_release_zip_is_one_folder_with_exe_and_manual(tmp_path):
    """The zip users get: a folder with the exe and ONE html manual (pictures inside)."""
    import importlib.util
    import zipfile
    from app import config as cfg
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("make_release", os.path.join(root, "tools", "make_release.py"))
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    exe = tmp_path / f"{cfg.APP_NAME}.exe"
    exe.write_bytes(b"MZ fake exe")
    out = mr.pack(str(exe), str(tmp_path))
    folder = f"{cfg.APP_NAME}_{cfg.APP_VERSION}"
    with zipfile.ZipFile(out) as z:
        assert z.namelist() == [f"{folder}/{cfg.APP_NAME}.exe", f"{folder}/使用說明書.html"]
        assert all(i.flag_bits & 0x800 for i in z.infolist())  # Chinese names show right in Windows
        html = z.read(f"{folder}/使用說明書.html").decode("utf-8")
    import re
    srcs = re.findall(r'<img src="([^"]+)"', html)
    assert srcs and all(s.startswith("data:image/png;base64,") for s in srcs)  # no outside files needed
    assert '<a name="toc">' in html
