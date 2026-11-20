# Develop: run, test, look

## Setup (any OS for development; the product targets Windows)

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt   # PyQt5, pyinstaller, pytest, pillow
```

## Run

```bash
AUTOREPAIR_DATA_DIR=/tmp/ar_data python start.py      # never point at real user data while developing
```

## Test

```bash
python -m pytest -q tests          # data layer; add a test for every db.py change
```

## Fake data

```bash
python tools/make_fake_data.py <path/to/autorepair.db>    # ~1 year, 40 regulars + 160 one-time cars
```
It copies the DB to `<name>.before_fake_<timestamp>.db` first. Never run it on a
real shop database.

## Screenshots (the way to "see" the UI)

```bash
AUTOREPAIR_DATA_DIR=<dir with data> QT_QPA_PLATFORM=offscreen python tools/screenshot.py <out_dir>
```
Produces `<w>x<h>_page<i>.png` for 4 window sizes × 5 pages, `edit.png`,
`items.png`, `history_plate.png` and two sample PDFs. Open and inspect them.
Uses the most frequent plate in the data, so it works with any dataset.

Gotchas:
- Any `QMessageBox` (e.g. 「沒有資料」 warning) blocks offscreen runs forever.
  If a run "hangs" at low CPU, it is a modal dialog. Wrap runs with
  `faulthandler.dump_traceback_later(25, exit=True)` to see where.
- Mac offscreen fonts render larger than Windows. Final judgement on Windows.

## Inspect query plans

```bash
python -c "import sqlite3; c=sqlite3.connect('<db>'); print(c.execute('EXPLAIN QUERY PLAN <sql>').fetchall())"
```

## Performance

`QT_QPA_PLATFORM=offscreen python tools/bench.py --records 90000` — see
`workflows/performance.md` for budgets.
