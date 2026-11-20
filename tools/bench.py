"""Performance check with a large database.

Usage:
    python tools/bench.py [--records 90000] [--keep DIR]

Creates a big database (about 10 years of a busy shop by default), then times
the data operations and the UI page refreshes the user actually triggers.
Run with QT_QPA_PLATFORM=offscreen to skip showing windows.
"""
import argparse
import datetime as dt
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import Database, plate_key  # noqa: E402


def build(path, n, seed=7):
    rng = random.Random(seed)
    db = Database(path)
    items = [i["id"] for i in db.list_items()]
    plates = [f"{''.join(rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ') for _ in range(3))}-{rng.randint(0, 9999):04d}"
              for _ in range(max(50, n // 30))]
    today = dt.date.today()
    days = 3650
    now = int(time.time())
    vids = {}
    with db.conn:
        for p in plates:
            vids[p] = db.conn.execute("INSERT INTO vehicles(plate_key, plate) VALUES(?, ?)",
                                      (plate_key(p), p)).lastrowid
    rows, links = [], []
    for rid in range(1, n + 1):
        d = (today - dt.timedelta(days=rng.randint(0, days))).isoformat()
        p = rng.choice(plates)
        rows.append((rid, vids[p], d, rng.randint(5, 80) * 50, rng.randint(10, 300) * 1000,
                     rng.choice(["", "", "", "下次換機油"]), now, now))
        for iid in rng.sample(items, rng.randint(1, 3)):
            links.append((rid, iid))
    with db.conn:
        db.conn.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?)", rows)
        db.conn.executemany("INSERT INTO record_items VALUES (?,?)", links)
    db.conn.execute("ANALYZE")
    return db, plates


def timed(label, fn, repeat=3):
    best = None
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        el = time.perf_counter() - t
        best = el if best is None else min(best, el)
    print(f"{label:<44} {best * 1000:8.1f} ms")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=int, default=90000)
    ap.add_argument("--keep")
    args = ap.parse_args()
    folder = args.keep or tempfile.mkdtemp()
    os.makedirs(folder, exist_ok=True)
    os.environ["AUTOREPAIR_DATA_DIR"] = folder
    from app.config import DB_FILENAME
    path = os.path.join(folder, DB_FILENAME)
    if os.path.exists(path):
        os.remove(path)
    t = time.perf_counter()
    db, plates = build(path, args.records)
    print(f"built {args.records} records, {len(plates)} cars in {time.perf_counter() - t:.1f}s "
          f"({os.path.getsize(path) / 1e6:.1f} MB)")
    plate = plates[0]
    today = dt.date.today()
    y0 = today.replace(month=1, day=1).isoformat()

    print("\n-- data layer --")
    timed("search: all records (PDF export only)", lambda: db.search_records())
    timed("search: first page of 200", lambda: db.search_records(limit=200))
    timed("search_stats: all", lambda: db.search_stats())
    timed("search_stats: partial plate '12'", lambda: db.search_stats("12"))
    timed("search: partial plate '12'", lambda: db.search_records("12"))
    timed("search: exact plate", lambda: db.search_records(plate))
    timed("search: one day", lambda: db.search_records(date_from=today.isoformat(), date_to=today.isoformat()))
    timed("plate_summary", lambda: db.plate_summary(plate))
    timed("last_record_for_plate", lambda: db.last_record_for_plate(plate))
    timed("report: month", lambda: db.report(today.replace(day=1).isoformat(), today.isoformat(), "day"))
    timed("report: year", lambda: db.report(y0, today.isoformat(), "month"))
    timed("add_record", lambda: db.add_record(today.isoformat(), "BENCH-1", 100, [1]), repeat=1)
    timed("backup_to", lambda: db.backup_to(os.path.join(folder, "bench_backup.db")), repeat=1)

    print("\n-- UI (offscreen) --")
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    from app.ui.main_window import MainWindow
    t = time.perf_counter()
    win = MainWindow(db)
    win.resize(1280, 760)
    win.show()
    app.processEvents()
    print(f"{'main window startup':<44} {(time.perf_counter() - t) * 1000:8.1f} ms")
    for i, (name, _p) in enumerate(win.pages):
        timed(f"open page: {name}", lambda i=i: (win.show_page(i), app.processEvents()), repeat=2)
    hp = win.history_page
    win.show_page(1)

    def type_plate():
        hp.plate.setText("")
        for ch in plate[:4]:
            hp.plate.setText(hp.plate.text() + ch)
            app.processEvents()
        if hasattr(hp, "_search_timer"):
            hp._search_timer.stop()
            hp.refresh()
        app.processEvents()
    timed("history: type 4 plate chars", type_plate, repeat=1)
    win.show_page(0)
    form = win.new_page.form

    def type_entry_plate():
        form.plate.setText("")
        for ch in plate:
            form.plate.setText(form.plate.text() + ch)
            app.processEvents()
        app.processEvents()
    timed("entry: type full plate (customer card)", type_entry_plate, repeat=1)

    def save_one():
        form.plate.setText("BENCH-2")
        form.amount.setText("500")
        db.add_record(**form.values())
        win.new_page.data_changed.emit()
        app.processEvents()
    timed("entry: save + refresh other pages", save_one, repeat=1)
    win.show_page(2)
    rp = win.report_page
    timed("report: switch to year", lambda: (rp._set_mode("year"), app.processEvents()), repeat=1)
    timed("report: previous year", lambda: (rp._step(-1), app.processEvents()), repeat=1)
    win.close()


if __name__ == "__main__":
    main()
