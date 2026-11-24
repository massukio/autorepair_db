# Architecture

Keep this file true. If you move, rename or add a module, update it in the retro.

## Layout

```
start.py                 entry: Qt attributes, excepthook -> error.log, open DB, daily auto backup, MainWindow
app/config.py            APP_* constants (name, version, author, license), default items,
                         UI scaling constants, data-folder logic, resource_path()
app/db.py                Database class: schema + migrations, items, records, search, stats,
                         reports, backup_to / check_backup_file / restore_from
app/backup.py            daily_auto_backup(), safety_backup_before_restore() (+ pruning)
app/ui/main_window.py    header bar (icon + name + nav tabs), QStackedWidget of pages,
                         window-size -> font scaling (apply_font_size), lazy page refresh
app/ui/pages.py          NewRecordPage, EditRecordDialog, HistoryPage, ReportPage,
                         BackupPage, SettingsPage
app/ui/record_form.py    RecordForm: the shared entry form (new + edit)
app/ui/customer_card.py  CustomerCard: 車輛資訊 (visits, total, interval, last visit); compact variant
app/ui/items.py          add/rename/delete item flows, ItemManager widget, ItemManagerDialog
app/ui/widgets.py        Card, Tile, Segmented, WrapLabel, DatePicker, OptionalDateButton,
                         CalendarDialog, ItemGrid, message boxes (info/warn/ask/ask_text),
                         make_table / fill_table / table_item, fit_to_screen, fmt_date / fmt_money
app/ui/style.py          palette, global stylesheet build_stylesheet(base_pt), scaling registry sized()
app/ui/pdf.py            HTML -> A4 PDF (QTextDocument + QPrinter), save_pdf() with open prompt
assets/icon_source.jpg   icon artwork (source of truth); app.ico/app.png are generated (gitignored)
tools/make_icon.py       builds assets/app.ico (16-256) + app.png from icon_source.jpg
tools/screenshot.py      renders every page at several window sizes + sample PDFs (offscreen)
tools/make_fake_data.py  ~1 year of realistic fake records (makes a safety copy first)
tools/bench.py           large-database performance benchmark
tests/test_db.py         data-layer tests (pytest)
tests/test_ui.py         UI logic tests, offscreen Qt (skipped without PyQt5)
tests/conftest.py        turns exceptions inside Qt slots into test failures
autorepair.spec          PyInstaller onefile spec (exe name, icon, bundled assets, excludes)
build_exe.bat            Windows: pip install -> tests -> icon -> PyInstaller (CRLF, ASCII only)
```

## Data model (SQLite, `autorepair_data/autorepair.db`, schema version 2)

```
vehicles(id, plate_key UNIQUE, plate)                -- one row per car
records(id, vehicle_id → vehicles, date 'YYYY-MM-DD', amount INT, mileage INT NULL,
        note, created_at INT, updated_at INT)        -- unix seconds
record_items(record_id → records ON DELETE CASCADE, item_id → items,
             PRIMARY KEY(record_id, item_id)) WITHOUT ROWID
items(id, name UNIQUE, sort_order, active)
settings(key, value)                                 -- schema_version, items_seeded, font_size, last_manual_backup*
idx_records_date    ON records(date, vehicle_id, amount)   -- covering: reports, totals, newest-first list
idx_records_vehicle ON records(vehicle_id, date, amount)   -- covering: one car's history / stats
```

- `plate` = display spelling (prefers the dashed one), `plate_key` = no dashes;
  all matching goes through `plate_key` so `ABC1234` finds `ABC-1234`.
- `Database._vehicle_id(plate)` finds-or-creates the car inside the write
  transaction; `_drop_unused_vehicle` removes a car when its last record is
  deleted or moved to another plate.
- Record dicts returned by `search_records` / `get_record` /
  `last_record_for_plate` include `plate`, `plate_key`, `item_ids`, `item_names`.
- Items: `active=0` is a soft delete (old records keep the name; re-adding
  un-hides it; renaming onto a hidden name moves the hidden one to `名稱（舊N）`).
- Why this design (2026-11-20 redesign, measured on 90k visits): plates were
  stored per visit in v1 → partial-plate search scanned every visit (110 ms),
  file 19 MB. v2: search scans ~3k vehicles (23 ms), car stats are index-only
  (<1 ms), year report 17 ms, file 11 MB.
- Connection: `foreign_keys=ON`, rollback journal + synchronous FULL (single
  file, power-loss safe — no WAL on purpose), 16 MB cache, `PRAGMA optimize` on close.
- Backups are `VACUUM INTO` copies (compact + consistent), written to `.tmp`
  then renamed. Restore reads the file read-only (URI `mode=ro`), copies it with
  the backup API, then runs `_create_schema` (which migrates v1 files).
- v1 → v2 migration: `_migrate_v1_to_v2` rebuilds tables with foreign keys OFF
  inside one transaction and runs `PRAGMA foreign_key_check` before COMMIT.

## Data location and file names (all Chinese — owner decision)

`config.data_dir()`: `AUTOREPAIR_DATA_DIR` env var → `<exe dir>/汽車保養資料`
if writable → `%LOCALAPPDATA%/汽車保養資料庫/汽車保養資料`.

| Name (constant in `app/config.py`) | What |
| --- | --- |
| `汽車保養資料/` (`DATA_DIRNAME`) | data folder next to the exe |
| `保養資料.db` (`DB_FILENAME`) | the database |
| `自動備份/` (`AUTO_BACKUP_DIRNAME`) | `自動備份_YYYYMMDD.db` (30 kept), `還原前備份_YYYYMMDD_HHMMSS.db` (10 kept) |
| `錯誤紀錄.log` (`LOG_FILENAME`) | unhandled exceptions with timestamps |
| `使用中.lock` (`LOCK_FILENAME`) | single-instance `QLockFile` |
| `汽車保養備份_YYYYMMDD_HHMM.db` | default name of a manual backup |
| `保養紀錄_….pdf`, `每月報表_….pdf` … | default PDF names |

Installs created before the Chinese naming used `autorepair_data/`,
`autorepair.db`, `auto_backup/auto_*.db`, `before_restore_*.db`, `error.log`,
`app.lock`, `%LOCALAPPDATA%/AutoRepairDB`. `config._data_dir_in()` and
`_migrate_legacy_names()` rename them in place on start-up (`LEGACY_*`
constants). The database and its `-journal` are renamed as a pair; if a rename
fails (file in use) the old name keeps being used — never start empty.
Any new file the app creates must get a Chinese name too.

## UI structure and flow

- `MainWindow.show_page(i)` always calls `page.refresh()` — pages are rebuilt
  from the DB when shown. `data_changed` from a page does NOT refresh hidden
  pages (lazy); only a restore refreshes the current page.
- `NewRecordPage`: left Card with scrollable `RecordForm` + pinned buttons;
  right scroll column with `CustomerCard` (debounced on plate typing) and the
  day's records.
- `HistoryPage`: filters Card → compact `CustomerCard` when the search matches
  exactly one car (`search_stats()["cars"] == 1`) → results Card. Rows load
  `PAGE_SIZE` (200) at a time; totals come from `db.search_stats` over the whole
  filter. PDF export loads all rows (warns above `PDF_WARN_ROWS`). Plate typing
  is debounced 300 ms.
- `NewRecordPage` rolls the date to today every minute unless the user picked a
  day (`DatePicker.follows_today`); `ReportPage` does the same for its period.
- `start.py` holds a `QLockFile` (`autorepair_data/app.lock`): a second copy
  shows 「已經開著了」 and exits.
- `ReportPage`: Segmented 每週/每月/每年, period navigation (`回到本期` only shown
  when away from the current period), 4 stat tiles, 3 table Cards; double-click
  a customer → `open_history(plate)`.
- `BackupPage`: backup (save dialog → `backup_to` → verify), restore
  (`check_backup_file` → confirm → safety copy → `restore_from`).
- `SettingsPage`: font size Segmented, `ItemManager`, About card.

## Scaling system

`MainWindow.apply_font_size` computes a base point size from the window size
(`style.base_font_for`, reference 1280×760 @ 19pt, exponent 0.7, clamp 12–34)
× the user's 小/中/大/特大 factor, rebuilds the stylesheet, and calls
`style.set_scale()`. Any fixed pixel size set in code must go through
`sized(widget, "setMinimumWidth", 280)` so it rescales; stylesheet pixel values
use `p(n)` inside `build_stylesheet`.
